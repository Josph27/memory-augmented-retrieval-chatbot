from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.context_manager_agent import ContextManagerAgent
from src.core.contracts import ContextPacket, MemoryCandidate, RoutePlan
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.routing_agent import RoutingAgent


MAX_BASE_CANDIDATES = 32
MAX_EXPANDED_CANDIDATES = 16
MAX_TRACE_CANDIDATES = 20
MAX_TRACE_SNIPPET_CHARS = 160
RAW_EVIDENCE_SOURCES = frozenset({"raw_message_span", "current_chat_span"})


@dataclass(frozen=True)
class EvidenceContract:
    """Evidence requirements checked against the final ContextPacket."""

    requires_raw_span: bool = False
    requires_document_citation: bool = False
    requires_structured_memory: bool = False
    allows_gist_orientation: bool = True
    must_not_answer_from_gist_only: bool = False


class MemoryGraphState(TypedDict, total=False):
    """Bounded state for the read-only LangGraph orchestration spike."""

    run_id: str
    chat_id: str
    user_id: str | None
    user_query: str
    current_message_id: int | None
    route_plan: RoutePlan
    routing_metadata: dict[str, Any]
    evidence_contract: EvidenceContract
    candidates: list[MemoryCandidate]
    expanded_candidates: list[MemoryCandidate]
    reranked_candidates: list[MemoryCandidate]
    reranker_metadata: dict[str, Any]
    source_budgets: dict[str, int]
    context_packet: ContextPacket
    context_metadata: dict[str, Any]
    insufficient_evidence: bool
    insufficient_evidence_reason: str | None
    mock_answer: str | None
    errors: list[str]
    visited_nodes: list[str]
    node_timings_ms: dict[str, float]
    trace: dict[str, Any]


@dataclass(frozen=True)
class LangGraphSpikeServices:
    """Existing typed-memory services wrapped by graph nodes."""

    routing_agent: RoutingAgent
    dispatcher: RetrieverDispatcher
    reranker: MemoryReranker
    context_manager: ContextManagerAgent
    system_prompt: str


def build_langgraph_memory_pipeline(
    *,
    routing_agent: RoutingAgent,
    dispatcher: RetrieverDispatcher,
    reranker: MemoryReranker | None = None,
    context_manager: ContextManagerAgent | None = None,
    system_prompt: str = "Use only the supplied typed-memory evidence.",
    checkpointer: Any | None = None,
) -> Any:
    """Build the isolated read-only graph without production registration."""
    services = LangGraphSpikeServices(
        routing_agent=routing_agent,
        dispatcher=dispatcher,
        reranker=reranker or MemoryReranker(mode="deterministic"),
        context_manager=context_manager or ContextManagerAgent(),
        system_prompt=system_prompt,
    )
    graph = StateGraph(MemoryGraphState)
    graph.add_node("route", _route_node(services))
    graph.add_node("retrieve", _retrieve_node(services))
    graph.add_node("expand_gists", _expand_gists_node(services))
    graph.add_node("rerank", _rerank_node(services))
    graph.add_node("build_context", _build_context_node(services))
    graph.add_node("validate_evidence", _validate_evidence_contract_node())
    graph.add_node("mock_answer", _mock_answer_node())
    graph.add_node("insufficient_evidence", _insufficient_evidence_node())
    graph.add_node("trace", _trace_node())

    graph.add_edge(START, "route")
    graph.add_edge("route", "retrieve")
    graph.add_edge("retrieve", "expand_gists")
    graph.add_edge("expand_gists", "rerank")
    graph.add_edge("rerank", "build_context")
    graph.add_edge("build_context", "validate_evidence")
    graph.add_conditional_edges(
        "validate_evidence",
        _answer_branch,
        {
            "answer": "mock_answer",
            "insufficient": "insufficient_evidence",
        },
    )
    graph.add_edge("mock_answer", "trace")
    graph.add_edge("insufficient_evidence", "trace")
    graph.add_edge("trace", END)
    return graph.compile(checkpointer=checkpointer)


def run_langgraph_memory_pipeline(
    graph: Any,
    *,
    run_id: str,
    chat_id: str,
    user_query: str,
    evidence_contract: EvidenceContract | None = None,
    user_id: str | None = None,
    config: dict[str, Any] | None = None,
) -> MemoryGraphState:
    """Invoke the explicit spike entry point with no production side effects."""
    initial: MemoryGraphState = {
        "run_id": run_id,
        "chat_id": chat_id,
        "user_id": user_id,
        "user_query": user_query,
        "current_message_id": None,
        "evidence_contract": evidence_contract or EvidenceContract(),
        "candidates": [],
        "expanded_candidates": [],
        "reranked_candidates": [],
        "source_budgets": {},
        "insufficient_evidence": False,
        "insufficient_evidence_reason": None,
        "mock_answer": None,
        "errors": [],
        "visited_nodes": [],
        "node_timings_ms": {},
        "trace": {},
    }
    return graph.invoke(initial, config=config)


def _route_node(services: LangGraphSpikeServices):  # type: ignore[no-untyped-def]
    def route_node(state: MemoryGraphState) -> MemoryGraphState:
        started = perf_counter()
        decision = services.routing_agent.route(state["user_query"])
        return node_update(
            state,
            node="route",
            started=started,
            route_plan=decision.route_plan,
            routing_metadata=decision.to_trace_dict(),
        )

    return route_node


def _retrieve_node(services: LangGraphSpikeServices):  # type: ignore[no-untyped-def]
    def retrieve_node(state: MemoryGraphState) -> MemoryGraphState:
        started = perf_counter()
        route_plan = state["route_plan"]
        candidates: list[MemoryCandidate] = []
        errors = list(state.get("errors", []))
        for source_plan in route_plan.sources:
            if not source_plan.enabled:
                continue
            retriever = services.dispatcher.retrievers.get(source_plan.source)
            if retriever is None:
                continue
            try:
                candidates.extend(
                    retriever.retrieve(
                        chat_id=state["chat_id"],
                        source_plan=source_plan,
                    )
                )
            except Exception as error:
                errors.append(
                    f"retrieve:{source_plan.source}:{type(error).__name__}: {error}"
                )
        return node_update(
            state,
            node="retrieve",
            started=started,
            candidates=candidates[:MAX_BASE_CANDIDATES],
            errors=errors,
        )

    return retrieve_node


def _expand_gists_node(services: LangGraphSpikeServices):  # type: ignore[no-untyped-def]
    def expand_gists_node(state: MemoryGraphState) -> MemoryGraphState:
        started = perf_counter()
        errors = list(state.get("errors", []))
        try:
            expanded = services.dispatcher.gist_expander.expand(
                state.get("candidates", []),
                query=state["user_query"],
            )
        except Exception as error:
            errors.append(f"expand_gists:{type(error).__name__}: {error}")
            expanded = []
        return node_update(
            state,
            node="expand_gists",
            started=started,
            expanded_candidates=expanded[:MAX_EXPANDED_CANDIDATES],
            errors=errors,
        )

    return expand_gists_node


def _rerank_node(services: LangGraphSpikeServices):  # type: ignore[no-untyped-def]
    def rerank_node(state: MemoryGraphState) -> MemoryGraphState:
        started = perf_counter()
        route_plan = state["route_plan"]
        candidates = [
            *state.get("candidates", []),
            *state.get("expanded_candidates", []),
        ]
        result = services.reranker.rank_with_trace(
            candidates=candidates,
            ranking_profile=route_plan.ranking_profile,
            query=state["user_query"],
        )
        return node_update(
            state,
            node="rerank",
            started=started,
            reranked_candidates=result.candidates,
            reranker_metadata=result.metadata,
        )

    return rerank_node


def _build_context_node(services: LangGraphSpikeServices):  # type: ignore[no-untyped-def]
    def build_context_node(state: MemoryGraphState) -> MemoryGraphState:
        started = perf_counter()
        result = services.context_manager.build_context_packet(
            system_prompt=services.system_prompt,
            latest_user_message={"role": "user", "content": state["user_query"]},
            ranked_candidates=state.get("reranked_candidates", []),
            route_plan=state["route_plan"],
        )
        return node_update(
            state,
            node="build_context",
            started=started,
            source_budgets=dict(result.context_budget.source_token_budgets),
            context_packet=result.context_packet,
            context_metadata=result.metadata,
        )

    return build_context_node


def _validate_evidence_contract_node():  # type: ignore[no-untyped-def]
    def validate_evidence_contract_node(
        state: MemoryGraphState,
    ) -> MemoryGraphState:
        started = perf_counter()
        contract = state.get("evidence_contract", EvidenceContract())
        packet = state.get("context_packet")
        sources = {
            candidate.source
            for candidate in packet.candidates
        } if packet is not None else set()
        reason = evidence_failure_reason(contract, sources)
        return node_update(
            state,
            node="validate_evidence",
            started=started,
            insufficient_evidence=reason is not None,
            insufficient_evidence_reason=reason,
        )

    return validate_evidence_contract_node


def _mock_answer_node():  # type: ignore[no-untyped-def]
    def mock_answer_node(state: MemoryGraphState) -> MemoryGraphState:
        started = perf_counter()
        sources = context_sources(state.get("context_packet"))
        answer = (
            "MOCK ANSWER: evidence contract satisfied with sources "
            f"{', '.join(sources) or 'none'}."
        )
        return node_update(
            state,
            node="mock_answer",
            started=started,
            mock_answer=answer,
        )

    return mock_answer_node


def _insufficient_evidence_node():  # type: ignore[no-untyped-def]
    def insufficient_evidence_node(state: MemoryGraphState) -> MemoryGraphState:
        started = perf_counter()
        reason = state.get("insufficient_evidence_reason") or "required evidence missing"
        return node_update(
            state,
            node="insufficient_evidence",
            started=started,
            mock_answer=f"MOCK INSUFFICIENT EVIDENCE: {reason}.",
        )

    return insufficient_evidence_node


def _trace_node():  # type: ignore[no-untyped-def]
    def trace_node(state: MemoryGraphState) -> MemoryGraphState:
        started = perf_counter()
        route_plan = state.get("route_plan")
        trace = {
            "run_id": state.get("run_id"),
            "route_sources": (
                [source.source for source in route_plan.sources if source.enabled]
                if route_plan is not None
                else []
            ),
            "candidates": candidate_trace(state.get("candidates", [])),
            "expanded_candidates": candidate_trace(
                state.get("expanded_candidates", [])
            ),
            "reranked_source_order": [
                candidate.source
                for candidate in state.get("reranked_candidates", [])[
                    :MAX_TRACE_CANDIDATES
                ]
            ],
            "context_sources": context_sources(state.get("context_packet")),
            "source_budgets": dict(state.get("source_budgets", {})),
            "evidence_contract": asdict(
                state.get("evidence_contract", EvidenceContract())
            ),
            "insufficient_evidence": state.get("insufficient_evidence", False),
            "insufficient_evidence_reason": state.get(
                "insufficient_evidence_reason"
            ),
            "errors": list(state.get("errors", [])),
            "visited_nodes": [*state.get("visited_nodes", []), "trace"],
        }
        return node_update(
            state,
            node="trace",
            started=started,
            trace=trace,
        )

    return trace_node


def _answer_branch(state: MemoryGraphState) -> str:
    return "insufficient" if state.get("insufficient_evidence") else "answer"


def evidence_failure_reason(
    contract: EvidenceContract,
    context_candidate_sources: set[str],
) -> str | None:
    """Return why included ContextPacket candidates fail the contract."""
    has_raw = bool(RAW_EVIDENCE_SOURCES & context_candidate_sources)
    has_gist = bool(
        {"previous_chat_gist", "current_chat_gist"} & context_candidate_sources
    )
    if contract.requires_raw_span and not has_raw:
        return "raw span evidence required but absent from ContextPacket"
    if contract.requires_document_citation and "document_memory" not in (
        context_candidate_sources
    ):
        return "document citation required but absent from ContextPacket"
    if contract.requires_structured_memory and "structured_memory" not in (
        context_candidate_sources
    ):
        return "structured memory required but absent from ContextPacket"
    if contract.must_not_answer_from_gist_only and has_gist and not has_raw:
        return "gist orientation cannot satisfy exact evidence contract"
    return None


def node_update(
    state: MemoryGraphState,
    *,
    node: str,
    started: float,
    **updates: Any,
) -> MemoryGraphState:
    """Return a partial state update with bounded node observability."""
    timings = dict(state.get("node_timings_ms", {}))
    timings[node] = round((perf_counter() - started) * 1000, 3)
    return {
        **updates,
        "visited_nodes": [*state.get("visited_nodes", []), node],
        "node_timings_ms": timings,
    }


def candidate_trace(candidates: list[MemoryCandidate]) -> list[dict[str, Any]]:
    """Return bounded candidate identity/provenance without full transcripts."""
    return [
        {
            "source": candidate.source,
            "record_id": candidate.record_id,
            "chat_id": candidate.chat_id,
            "source_message_ids": candidate.source_message_ids[:20],
            "source_message_count": len(candidate.source_message_ids),
            "snippet": candidate.content[:MAX_TRACE_SNIPPET_CHARS],
        }
        for candidate in candidates[:MAX_TRACE_CANDIDATES]
    ]


def context_sources(packet: ContextPacket | None) -> list[str]:
    """Return stable included source names from a ContextPacket."""
    if packet is None:
        return []
    return [candidate.source for candidate in packet.candidates]
