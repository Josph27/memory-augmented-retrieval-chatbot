from __future__ import annotations

import inspect
from dataclasses import replace
from pathlib import Path

from src.agents.context_manager_agent import ContextManagerAgent
from src.agents.coordinator_agent import CoordinatorAgent
from src.chat_service import ChatService
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


def test_spike_is_isolated_from_production_path() -> None:
    assert "langgraph" not in inspect.getsource(ChatService).lower()
    assert "langgraph" not in inspect.getsource(CoordinatorAgent).lower()


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
