from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from src.agents.context_manager_agent import ContextManagerAgent
from src.core.contracts import RoutePlan, SourcePlan
from src.database import Database
from src.orchestration.langgraph_memory_pipeline import (
    EvidenceContract,
    build_langgraph_memory_pipeline,
    run_langgraph_memory_pipeline,
)
from src.retrieval.current_chat_span_retriever import CurrentChatSpanRetriever
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.routing_agent import RoutingAgent
from src.routing.semantic_router import SemanticRouter


class FixedPlanner:
    def __init__(self, route_plan: RoutePlan) -> None:
        self.route_plan = route_plan

    def plan(self, query: str) -> RoutePlan:
        return replace(self.route_plan, query=query)


def route_plan_for(*enabled_sources: str, query: str) -> RoutePlan:
    sources = [
        SourcePlan(
            source=source,  # type: ignore[arg-type]
            enabled=True,
            query=query,
            limit=4,
        )
        for source in enabled_sources
    ]
    return RoutePlan(
        query=query,
        intent="langgraph_spike_fixture",
        confidence=1.0,
        requires_retrieval=True,
        sources=sources,
        ranking_profile="langgraph_spike",
        context_profile="memory_recall",
        metadata={"spike_fixture_route": True},
    )


def run_graph(
    *,
    database: Database,
    route_plan: RoutePlan,
    retrievers: dict[str, object],
    chat_id: str,
    query: str,
    contract: EvidenceContract,
):  # type: ignore[no-untyped-def]
    dispatcher = RetrieverDispatcher(
        database,
        retrievers=retrievers,  # type: ignore[arg-type]
    )
    graph = build_langgraph_memory_pipeline(
        routing_agent=RoutingAgent(
            route_planner=FixedPlanner(route_plan),  # type: ignore[arg-type]
        ),
        dispatcher=dispatcher,
        reranker=MemoryReranker(mode="deterministic"),
        context_manager=ContextManagerAgent(),
    )
    return run_langgraph_memory_pipeline(
        graph,
        run_id="test-run",
        chat_id=chat_id,
        user_query=query,
        evidence_contract=contract,
    )


def test_exact_quote_with_current_raw_span_passes_contract(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    exact_id = database.save_message(
        "chat",
        "user",
        "Ship slowly, measure twice, and preserve rollback.",
    )
    database.save_message("chat", "assistant", "Noted.")
    query = "What exact phrase did I use about rollback?"

    before = database.messages_for_chat("chat")
    state = run_graph(
        database=database,
        route_plan=route_plan_for("current_chat_span", query=query),
        retrievers={"current_chat_span": CurrentChatSpanRetriever(database)},
        chat_id="chat",
        query=query,
        contract=EvidenceContract(
            requires_raw_span=True,
            must_not_answer_from_gist_only=True,
        ),
    )

    assert state["insufficient_evidence"] is False
    assert state["mock_answer"].startswith("MOCK ANSWER:")
    assert "current_chat_span" in state["trace"]["context_sources"]
    span = next(
        candidate
        for candidate in state["context_packet"].candidates
        if candidate.source == "current_chat_span"
    )
    assert exact_id in span.source_message_ids
    assert span.chat_id == "chat"
    assert database.messages_for_chat("chat") == before


def test_gist_only_fails_exact_quote_contract(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("old-chat")
    database.insert_chat_gist(
        chat_id="old-chat",
        source_type="previous_chat_gist",
        gist_text="Rollback strategy was discussed.",
    )
    query = "Quote exactly what I said about rollback."

    state = run_graph(
        database=database,
        route_plan=route_plan_for("previous_chat_gist", query=query),
        retrievers={"previous_chat_gist": PreviousChatGistRetriever(database)},
        chat_id="new-chat",
        query=query,
        contract=EvidenceContract(
            requires_raw_span=True,
            must_not_answer_from_gist_only=True,
        ),
    )

    assert state["insufficient_evidence"] is True
    assert state["mock_answer"].startswith("MOCK INSUFFICIENT EVIDENCE:")
    assert state["trace"]["context_sources"] == ["previous_chat_gist"]
    assert state["expanded_candidates"] == []
    assert "mock_answer" not in state["visited_nodes"]


def test_previous_gist_expands_to_exact_raw_span(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("old-chat")
    first_id = database.save_message(
        "old-chat",
        "user",
        "The rollback phrase is preserve every recovery path.",
    )
    second_id = database.save_message("old-chat", "assistant", "Recorded.")
    gist_id = database.insert_chat_gist(
        chat_id="old-chat",
        source_type="previous_chat_gist",
        gist_text="Rollback phrase and recovery were discussed.",
        start_message_id=first_id,
        end_message_id=second_id,
        metadata={"source_message_ids": [first_id, second_id]},
    )
    query = "Quote exactly what I said about the rollback phrase."

    state = run_graph(
        database=database,
        route_plan=route_plan_for("previous_chat_gist", query=query),
        retrievers={"previous_chat_gist": PreviousChatGistRetriever(database)},
        chat_id="new-chat",
        query=query,
        contract=EvidenceContract(
            requires_raw_span=True,
            must_not_answer_from_gist_only=True,
        ),
    )

    assert state["insufficient_evidence"] is False
    assert {candidate.source for candidate in state["candidates"]} == {
        "previous_chat_gist"
    }
    raw = next(
        candidate
        for candidate in state["expanded_candidates"]
        if candidate.source == "raw_message_span"
    )
    assert "user: The rollback phrase is preserve every recovery path." in raw.content
    assert raw.metadata["parent_gist_id"] == gist_id
    assert raw.source_message_ids == [first_id, second_id]
    assert "raw_message_span" in state["trace"]["context_sources"]


def test_spike_remains_explicit_and_default_off() -> None:
    from src.orchestration.demo_orchestration import NATIVE, normalize_orchestration_mode

    assert normalize_orchestration_mode(None) == NATIVE
    assert normalize_orchestration_mode("unknown") == NATIVE


def test_trace_is_bounded_and_graph_has_no_write_nodes(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    database.save_message("chat", "user", "The marker is cobalt.")
    query = "What marker did I use?"
    before_messages = database.messages_for_chat("chat")
    before_gists = database.chat_gists_for_chat("chat")
    before_memory = database.chat_memory_state("chat")

    state = run_graph(
        database=database,
        route_plan=route_plan_for("current_chat_span", query=query),
        retrievers={"current_chat_span": CurrentChatSpanRetriever(database)},
        chat_id="chat",
        query=query,
        contract=EvidenceContract(requires_raw_span=True),
    )

    trace = state["trace"]
    assert trace["route_sources"] == ["current_chat_span"]
    assert trace["candidates"][0]["source"] == "current_chat_span"
    assert len(trace["candidates"][0]["snippet"]) <= 160
    assert trace["reranked_source_order"] == ["current_chat_span"]
    assert trace["insufficient_evidence"] is False
    assert set(state["visited_nodes"]) == {
        "route",
        "retrieve",
        "expand_gists",
        "rerank",
        "build_context",
        "validate_evidence",
        "mock_answer",
        "trace",
    }
    assert database.messages_for_chat("chat") == before_messages
    assert database.chat_gists_for_chat("chat") == before_gists
    assert database.chat_memory_state("chat") == before_memory


def test_semantic_router_exact_quote_reaches_current_raw_span(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    exact_id = database.save_message(
        "chat",
        "user",
        "For Router V2, preserve the original query exactly.",
    )
    query = "What exact phrase did I use about Router V2?"
    dispatcher = RetrieverDispatcher(
        database,
        retrievers={
            "current_chat_span": CurrentChatSpanRetriever(database),
        },
    )
    graph = build_langgraph_memory_pipeline(
        routing_agent=None,
        dispatcher=dispatcher,
        semantic_router=SemanticRouter(),
        use_semantic_router=True,
    )

    state = run_langgraph_memory_pipeline(
        graph,
        run_id="semantic-route-test",
        chat_id="chat",
        user_query=query,
    )

    assert state["semantic_route_plan"].original_query == query
    assert state["evidence_contract"].requires_raw_span is True
    assert state["insufficient_evidence"] is False
    assert "current_chat_span" in state["trace"]["route_sources"]
    assert "current_chat_span" in state["trace"]["context_sources"]
    assert state["trace"]["routing"]["routing_mode"] == "semantic_v2"
    assert state["trace"]["routing"]["intents"][0]["intent"] == "EXACT_QUOTE"
    assert state["trace"]["routing"]["evidence_contract"]["requires_raw_span"] is True
    span = next(
        candidate
        for candidate in state["context_packet"].candidates
        if candidate.source == "current_chat_span"
    )
    assert exact_id in span.source_message_ids
    assert state["routing_metadata"]["routing_mode"] == "semantic_v2"
    assert state["mock_answer"].startswith("MOCK ANSWER:")


def test_semantic_router_exact_quote_fails_closed_with_gist_only(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("old-chat")
    database.insert_chat_gist(
        chat_id="old-chat",
        source_type="previous_chat_gist",
        gist_text="Router V2 phrasing was discussed.",
    )
    query = "What exact phrase did I use about Router V2?"
    dispatcher = RetrieverDispatcher(
        database,
        retrievers={
            "previous_chat_gist": PreviousChatGistRetriever(database),
        },
    )
    graph = build_langgraph_memory_pipeline(
        routing_agent=None,
        dispatcher=dispatcher,
        semantic_router=SemanticRouter(),
        use_semantic_router=True,
    )

    state = run_langgraph_memory_pipeline(
        graph,
        run_id="semantic-gist-only-test",
        chat_id="new-chat",
        user_query=query,
    )

    assert state["evidence_contract"].requires_raw_span is True
    assert state["trace"]["context_sources"] == ["previous_chat_gist"]
    assert state["insufficient_evidence"] is True
    assert state["mock_answer"].startswith("MOCK INSUFFICIENT EVIDENCE:")
    assert all(
        candidate.content != query
        for candidate in state["context_packet"].candidates
    )


def test_semantic_router_required_scopes_are_visible_in_graph_trace(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    query = (
        "According to the uploaded report, compare it with the constraint "
        "I mentioned earlier in this chat."
    )
    graph = build_langgraph_memory_pipeline(
        routing_agent=None,
        dispatcher=RetrieverDispatcher(
            database,
            retrievers={
                "current_chat_span": CurrentChatSpanRetriever(database),
            },
        ),
        semantic_router=SemanticRouter(),
        use_semantic_router=True,
    )
    before_messages = database.messages_for_chat("chat")

    state = run_langgraph_memory_pipeline(
        graph,
        run_id="semantic-multi-scope-test",
        chat_id="chat",
        user_query=query,
    )

    assert state["trace"]["routing"]["primary_scope"] == "document"
    assert state["trace"]["routing"]["required_scopes"] == [
        "current_chat",
        "document",
    ]
    assert state["trace"]["route_sources"] == [
        "recent_messages",
        "document_memory",
        "current_chat_span",
    ]
    assert database.messages_for_chat("chat") == before_messages
