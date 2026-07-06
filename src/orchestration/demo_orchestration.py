from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from src.agents.context_manager_agent import ContextManagerAgent
from src.core.contracts import OrchestrationResult, WorkflowTrace
from src.orchestration.langgraph_memory_pipeline import (
    build_langgraph_memory_pipeline,
    run_langgraph_memory_pipeline,
)
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.semantic_router import SemanticRouter


NATIVE = "native"
LANGGRAPH_SHADOW = "langgraph_shadow"
LANGGRAPH_DEMO = "langgraph_demo"
ORCHESTRATION_MODES = (NATIVE, LANGGRAPH_SHADOW, LANGGRAPH_DEMO)


@dataclass(frozen=True)
class OrchestrationComparison:
    """Bounded comparison between authoritative and shadow context construction."""

    native_sources: list[str]
    langgraph_sources: list[str]
    native_only_sources: list[str]
    langgraph_only_sources: list[str]
    selected_candidate_overlap: int
    native_selected_count: int
    langgraph_selected_count: int
    native_prompt_tokens: int | None
    langgraph_prompt_tokens: int | None
    token_difference: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "native_sources": self.native_sources,
            "langgraph_sources": self.langgraph_sources,
            "native_only_sources": self.native_only_sources,
            "langgraph_only_sources": self.langgraph_only_sources,
            "selected_candidate_overlap": self.selected_candidate_overlap,
            "native_selected_count": self.native_selected_count,
            "langgraph_selected_count": self.langgraph_selected_count,
            "native_prompt_tokens": self.native_prompt_tokens,
            "langgraph_prompt_tokens": self.langgraph_prompt_tokens,
            "token_difference": self.token_difference,
        }


def normalize_orchestration_mode(value: str | None) -> str:
    """Return a supported mode, preserving native as the safe default."""
    normalized = (value or NATIVE).strip().lower()
    return normalized if normalized in ORCHESTRATION_MODES else NATIVE


def run_read_only_langgraph_orchestration(
    *,
    chat_id: str,
    query: str,
    dispatcher: RetrieverDispatcher,
    reranker: MemoryReranker,
    context_manager: ContextManagerAgent,
    system_prompt: str,
    run_id: str | None = None,
    task_context: str | None = None,
) -> OrchestrationResult:
    """Build a ContextPacket through the read-only Semantic Router v2 graph."""
    trace_id = run_id or str(uuid4())
    graph = build_langgraph_memory_pipeline(
        routing_agent=None,
        dispatcher=dispatcher,
        reranker=reranker,
        context_manager=context_manager,
        system_prompt=system_prompt,
        semantic_router=SemanticRouter(),
        use_semantic_router=True,
    )
    state = run_langgraph_memory_pipeline(
        graph,
        run_id=trace_id,
        chat_id=chat_id,
        user_query=query,
        task_context=task_context,
    )
    packet = state["context_packet"]
    route_plan = state["route_plan"]
    errors = list(state.get("errors", []))
    trace = WorkflowTrace(
        trace_id=trace_id,
        chat_id=chat_id,
        route_plan=route_plan,
        retrieved_candidates=[
            *state.get("candidates", []),
            *state.get("expanded_candidates", []),
        ],
        ranked_candidates=list(state.get("reranked_candidates", [])),
        context_budget=packet.budget,
        context_packet=packet,
        errors=errors,
        metadata={
            "orchestration_mode": LANGGRAPH_DEMO,
            "router_version": "semantic_v2",
            "langgraph": dict(state.get("trace", {})),
            "reranker": dict(state.get("reranker_metadata", {})),
            "context_manager": dict(state.get("context_metadata", {})),
            "insufficient_evidence": state.get("insufficient_evidence", False),
            "insufficient_evidence_reason": state.get(
                "insufficient_evidence_reason"
            ),
        },
    )
    return OrchestrationResult(
        context_packet=packet,
        trace=trace,
        mode=LANGGRAPH_DEMO,
        error="; ".join(errors) if errors else None,
    )


def compare_orchestration(
    native: OrchestrationResult,
    langgraph: OrchestrationResult,
) -> OrchestrationComparison:
    """Compare selected evidence and token accounting without exposing content."""
    native_ids = candidate_identities(native.context_packet.candidates)
    graph_ids = candidate_identities(langgraph.context_packet.candidates)
    native_sources = sorted({candidate.source for candidate in native.context_packet.candidates})
    graph_sources = sorted(
        {candidate.source for candidate in langgraph.context_packet.candidates}
    )
    native_tokens = estimated_prompt_tokens(native.context_packet)
    graph_tokens = estimated_prompt_tokens(langgraph.context_packet)
    return OrchestrationComparison(
        native_sources=native_sources,
        langgraph_sources=graph_sources,
        native_only_sources=sorted(set(native_sources) - set(graph_sources)),
        langgraph_only_sources=sorted(set(graph_sources) - set(native_sources)),
        selected_candidate_overlap=sum((native_ids & graph_ids).values()),
        native_selected_count=sum(native_ids.values()),
        langgraph_selected_count=sum(graph_ids.values()),
        native_prompt_tokens=native_tokens,
        langgraph_prompt_tokens=graph_tokens,
        token_difference=(
            graph_tokens - native_tokens
            if graph_tokens is not None and native_tokens is not None
            else None
        ),
    )


def candidate_identities(candidates) -> Counter[tuple[str, str]]:  # type: ignore[no-untyped-def]
    """Return stable source/id identities without candidate text."""
    return Counter(
        (candidate.source, str(candidate.record_id))
        for candidate in candidates
    )


def estimated_prompt_tokens(packet) -> int | None:  # type: ignore[no-untyped-def]
    value = packet.metadata.get("estimated_prompt_tokens")
    return int(value) if isinstance(value, int | float) else None
