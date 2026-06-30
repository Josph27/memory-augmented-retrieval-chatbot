from __future__ import annotations

from pathlib import Path

from src.agents.context_manager_agent import ContextManagerAgent
from src.context.context_budget_allocator import ContextBudgetAllocator
from src.context.context_builder import ContextBuilder
from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan
from src.database import Database
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.route_planner import RoutePlanner


def candidate(
    source: str,
    content: str,
    record_id: str,
    score: float = 0.8,
) -> MemoryCandidate:
    """Create a small test memory candidate."""
    return MemoryCandidate(
        source=source,
        content=content,
        score=score,
        record_id=record_id,
        chat_id="chat",
        metadata={"role": "user"} if source == "recent_messages" else {},
    )


def test_context_manager_agent_matches_direct_allocator_and_builder_output() -> None:
    route_plan = RoutePlan(
        query="q",
        context_profile="document_question",
        sources=[
            SourcePlan(source="recent_messages", enabled=True),
            SourcePlan(source="structured_memory", enabled=True),
            SourcePlan(source="document_memory", enabled=True),
        ],
    )
    ranked = [
        candidate("document_memory", "Document fact.", "doc-1"),
        candidate("recent_messages", "Recent message.", "recent-1"),
    ]
    latest_user_message = {"role": "user", "content": "latest question"}
    allocator = ContextBudgetAllocator()
    builder = ContextBuilder()

    direct_budget = allocator.allocate(
        route_plan=route_plan,
        ranked_candidates=ranked,
        system_prompt="system",
    )
    direct_packet = builder.build(
        system_prompt="system",
        latest_user_message=latest_user_message,
        ranked_candidates=ranked,
        context_budget=direct_budget,
        route_plan=route_plan,
    )

    result = ContextManagerAgent(
        budget_allocator=allocator,
        context_builder=builder,
    ).build_context_packet(
        system_prompt="system",
        latest_user_message=latest_user_message,
        ranked_candidates=ranked,
        route_plan=route_plan,
    )

    assert result.context_budget == direct_budget
    assert result.context_packet.model_messages == direct_packet.model_messages
    assert result.context_packet.candidates == direct_packet.candidates


def test_context_manager_agent_records_trace_metadata() -> None:
    route_plan = RoutePlan(
        query="q",
        context_profile="document_question",
        sources=[
            SourcePlan(source="recent_messages", enabled=True),
            SourcePlan(source="document_memory", enabled=True),
        ],
    )
    ranked = [
        candidate("document_memory", "Document fact.", "doc-1"),
        candidate("recent_messages", "Recent message.", "recent-1"),
    ]

    result = ContextManagerAgent().build_context_packet(
        system_prompt="system",
        latest_user_message={"role": "user", "content": "latest question"},
        ranked_candidates=ranked,
        route_plan=route_plan,
    )
    metadata = result.metadata

    assert metadata["context_manager_used"] is True
    assert metadata["source_budgets"]["document_memory"] > 0
    assert metadata["included_candidate_counts_by_source"]["document_memory"] == 1
    assert metadata["included_candidate_counts_by_source"]["recent_messages"] == 1
    assert metadata["dropped_candidate_counts_by_source"] == {}
    assert metadata["final_prompt_sections"] == [
        "system",
        "structured_memory",
        "retrieved_memory",
        "recent_messages",
        "latest_user_message",
    ]


def test_production_previous_chat_route_reaches_context_packet(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", "1")
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("old-chat")
    first_id = database.save_message(
        "old-chat",
        "user",
        "We discussed the release checklist.",
    )
    second_id = database.save_message("old-chat", "assistant", "Noted.")
    gist_id = database.insert_chat_gist(
        chat_id="old-chat",
        source_type="previous_chat_gist",
        gist_text="The previous chat discussed the release checklist.",
        start_message_id=first_id,
        end_message_id=second_id,
    )
    database.create_chat("current-chat")
    query = "What did we discuss last time about the release checklist?"
    route_plan = RoutePlanner().plan(query)
    candidates = RetrieverDispatcher(database).retrieve(
        chat_id="current-chat",
        route_plan=route_plan,
    )

    result = ContextManagerAgent().build_context_packet(
        system_prompt="system",
        latest_user_message={"role": "user", "content": query},
        ranked_candidates=candidates,
        route_plan=route_plan,
    )

    assert route_plan.context_profile == "memory_recall"
    assert result.context_budget.source_token_budgets["previous_chat_gist"] > 0
    included = [
        item
        for item in result.context_packet.candidates
        if item.source == "previous_chat_gist"
    ]
    assert len(included) == 1
    assert included[0].record_id == gist_id
    assert included[0].source_message_ids == [first_id, second_id]
    assert any(
        "Previous Chat Gist:" in message["content"]
        and "release checklist" in message["content"]
        for message in result.context_packet.model_messages
    )


def test_disabled_candidate_source_receives_no_budget() -> None:
    route_plan = RoutePlan(
        query="q",
        context_profile="memory_recall",
        sources=[SourcePlan(source="previous_chat_gist", enabled=False)],
    )
    candidate = MemoryCandidate(
        source="previous_chat_gist",
        content="Old chat evidence.",
        record_id=1,
        chat_id="old-chat",
        source_message_ids=[10, 11],
    )

    budget = ContextBudgetAllocator().allocate(
        route_plan=route_plan,
        ranked_candidates=[candidate],
        model_context_limit=1000,
        answer_reserve=100,
        system_prompt_tokens=50,
    )

    assert budget.source_token_budgets.get("previous_chat_gist", 0) == 0
    assert budget.metadata["candidate_source_minimum_budgets"] == {}


def test_candidate_fallback_budget_stays_within_allocatable_limit() -> None:
    route_plan = RoutePlan(
        query="q",
        context_profile="memory_recall",
        sources=[
            SourcePlan(source="recent_messages", enabled=True),
            SourcePlan(source="structured_memory", enabled=True),
            SourcePlan(source="previous_chat_gist", enabled=True),
            SourcePlan(source="raw_message_span", enabled=True),
        ],
    )
    candidates = [
        candidate("recent_messages", "Recent context.", "recent"),
        candidate("structured_memory", "Durable preference.", "memory"),
        candidate("previous_chat_gist", "Previous discussion.", "gist"),
        candidate("raw_message_span", "user: Exact evidence.", "span"),
    ]

    budget = ContextBudgetAllocator().allocate(
        route_plan=route_plan,
        ranked_candidates=candidates,
        model_context_limit=500,
        answer_reserve=100,
        system_prompt_tokens=50,
    )

    assert budget.source_token_budgets["previous_chat_gist"] > 0
    assert budget.source_token_budgets["raw_message_span"] > 0
    assert sum(budget.source_token_budgets.values()) <= budget.metadata[
        "allocatable_tokens"
    ]
