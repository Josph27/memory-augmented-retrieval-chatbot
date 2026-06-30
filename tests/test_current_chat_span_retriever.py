from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from src.agents.context_manager_agent import ContextManagerAgent
from src.context.context_budget_allocator import (
    ContextBudgetAllocator,
    ContextBudgetPolicy,
)
from src.context.context_builder import ContextBuilder
from src.core.contracts import RoutePlan, SourcePlan
from src.database import Database
from src.retrieval.current_chat_span_retriever import CurrentChatSpanRetriever
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.route_planner import RoutePlanner


def enabled_span_plan(
    query: str,
    *,
    filters: dict[str, object] | None = None,
) -> RoutePlan:
    """Enable only the opt-in span source on a production-generated plan."""
    production_plan = RoutePlanner().plan(query)
    sources = [
        replace(
            source,
            enabled=True,
            query=production_plan.query,
            filters=filters or {},
        )
        if source.source == "current_chat_span"
        else source
        for source in production_plan.sources
    ]
    return replace(production_plan, sources=sources)


def span_dispatcher(database: Database) -> RetrieverDispatcher:
    """Return the production dispatcher with only the tested backend registered."""
    return RetrieverDispatcher(
        database,
        retrievers={
            "current_chat_span": CurrentChatSpanRetriever(database),
        },
    )


def test_old_same_chat_fact_reaches_context_packet_outside_recent_window(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    fact_id = database.save_message(
        "chat",
        "user",
        "The staging deployment codename is cobalt.",
    )
    database.save_message("chat", "assistant", "Recorded.")
    for index in range(12):
        database.save_message(
            "chat",
            "user" if index % 2 == 0 else "assistant",
            f"unrelated later message {index}",
        )
    query = "What was the staging deployment codename?"
    current_id = database.save_message("chat", "user", query)
    route_plan = enabled_span_plan(
        query,
        filters={"window_messages": 1, "max_spans": 1},
    )
    candidates = span_dispatcher(database).retrieve("chat", route_plan)

    result = ContextManagerAgent().build_context_packet(
        system_prompt="Use exact current-chat evidence.",
        latest_user_message={"role": "user", "content": query},
        ranked_candidates=candidates,
        route_plan=route_plan,
    )

    spans = [
        candidate
        for candidate in result.context_packet.candidates
        if candidate.source == "current_chat_span"
    ]
    assert len(spans) == 1
    assert "user: The staging deployment codename is cobalt." in spans[0].content
    assert spans[0].chat_id == "chat"
    assert spans[0].metadata["source_chat_id"] == "chat"
    assert spans[0].metadata["start_message_id"] == fact_id
    assert fact_id in spans[0].source_message_ids
    assert current_id not in spans[0].source_message_ids
    assert any(
        "Current Chat Span:" in message["content"]
        and "staging deployment codename is cobalt" in message["content"]
        for message in result.context_packet.model_messages
    )


def test_exact_quote_comes_from_raw_current_chat_messages(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    exact_id = database.save_message(
        "chat",
        "user",
        "Ship slowly, measure twice, and preserve rollback.",
    )
    database.save_message("chat", "assistant", "Noted.")
    query = "What exact phrase did I use about rollback?"

    candidates = span_dispatcher(database).retrieve(
        "chat",
        enabled_span_plan(
            query,
            filters={"window_messages": 0, "max_spans": 1},
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].source == "current_chat_span"
    assert candidates[0].content == (
        "user: Ship slowly, measure twice, and preserve rollback."
    )
    assert candidates[0].source_message_ids == [exact_id]
    assert candidates[0].metadata["span_kind"] == "current_chat_exact_raw"
    assert "gist" not in candidates[0].metadata["retrieval_mode"]


def test_current_chat_span_never_reads_other_chats(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat-a")
    chat_a_id = database.save_message(
        "chat-a",
        "user",
        "Cobalt belongs to chat A.",
    )
    database.create_chat("chat-b")
    database.save_message("chat-b", "user", "Cobalt belongs to chat B.")
    source_plan = SourcePlan(
        source="current_chat_span",
        enabled=True,
        query="Where does cobalt belong?",
        filters={"window_messages": 0},
    )

    candidates = CurrentChatSpanRetriever(database).retrieve("chat-a", source_plan)

    assert len(candidates) == 1
    assert candidates[0].chat_id == "chat-a"
    assert candidates[0].source_message_ids == [chat_a_id]
    assert "chat B" not in candidates[0].content


def test_current_user_query_is_excluded_from_span_and_context(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    database.save_message("chat", "user", "The audit database is PostgreSQL.")
    database.save_message("chat", "assistant", "Recorded.")
    query = "What did I say about the audit database?"
    current_id = database.save_message("chat", "user", query)
    route_plan = enabled_span_plan(
        query,
        filters={"window_messages": 3, "max_spans": 2},
    )
    candidates = span_dispatcher(database).retrieve("chat", route_plan)

    packet = ContextManagerAgent().build_context_packet(
        system_prompt="Use exact evidence.",
        latest_user_message={"role": "user", "content": query},
        ranked_candidates=candidates,
        route_plan=route_plan,
    ).context_packet

    assert all(current_id not in candidate.source_message_ids for candidate in candidates)
    assert all(query not in candidate.content for candidate in candidates)
    assert sum(
        message["role"] == "user" and message["content"] == query
        for message in packet.model_messages
    ) == 1


def test_span_expands_around_hit_in_chronological_order(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    ids = [
        database.save_message("chat", "user", "before"),
        database.save_message("chat", "assistant", "context before"),
        database.save_message("chat", "user", "The unique marker is zircon."),
        database.save_message("chat", "assistant", "context after"),
        database.save_message("chat", "user", "later"),
    ]

    candidates = CurrentChatSpanRetriever(database).retrieve(
        "chat",
        SourcePlan(
            source="current_chat_span",
            enabled=True,
            query="What is the zircon marker?",
            filters={"window_messages": 1, "max_spans": 1},
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].source_message_ids == ids[1:4]
    assert candidates[0].content.splitlines() == [
        "assistant: context before",
        "user: The unique marker is zircon.",
        "assistant: context after",
    ]
    assert candidates[0].metadata["start_message_id"] == ids[1]
    assert candidates[0].metadata["end_message_id"] == ids[3]


def test_overlapping_hit_windows_are_merged(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    ids = [
        database.save_message("chat", "user", "opening"),
        database.save_message("chat", "assistant", "before"),
        database.save_message("chat", "user", "Cobalt decision one."),
        database.save_message("chat", "assistant", "between"),
        database.save_message("chat", "user", "Cobalt decision two."),
        database.save_message("chat", "assistant", "after"),
    ]

    candidates = CurrentChatSpanRetriever(database).retrieve(
        "chat",
        SourcePlan(
            source="current_chat_span",
            enabled=True,
            query="cobalt decision",
            filters={"window_messages": 1, "max_spans": 2},
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].source_message_ids == ids[1:6]
    assert candidates[0].metadata["matched_message_ids"] == [ids[4], ids[2]]


def test_current_chat_span_is_disabled_by_default_but_works_when_enabled(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    database.save_message("chat", "user", "The build marker is amber.")
    query = "What is the build marker?"
    default_plan = RoutePlanner().plan(query)
    dispatcher = span_dispatcher(database)

    default_candidates = dispatcher.retrieve("chat", default_plan)
    enabled_candidates = dispatcher.retrieve(
        "chat",
        enabled_span_plan(query, filters={"window_messages": 0}),
    )

    source = next(
        source
        for source in default_plan.sources
        if source.source == "current_chat_span"
    )
    assert source.enabled is False
    assert default_candidates == []
    assert len(enabled_candidates) == 1


def test_oversized_span_is_dropped_without_exceeding_context_budget(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    database.save_message(
        "chat",
        "user",
        f"Cobalt evidence {'detail ' * 5000}",
    )
    query = "What cobalt evidence was recorded?"
    route_plan = enabled_span_plan(
        query,
        filters={"window_messages": 0, "max_spans": 1},
    )
    candidates = span_dispatcher(database).retrieve("chat", route_plan)
    manager = ContextManagerAgent(
        budget_allocator=ContextBudgetAllocator(
            policy=ContextBudgetPolicy(
                default_model_context_limit=300,
                default_answer_reserve=50,
            )
        ),
        context_builder=ContextBuilder(),
    )

    result = manager.build_context_packet(
        system_prompt="Use exact evidence.",
        latest_user_message={"role": "user", "content": query},
        ranked_candidates=candidates,
        route_plan=route_plan,
    )

    assert len(candidates) == 1
    assert all(
        candidate.source != "current_chat_span"
        for candidate in result.context_packet.candidates
    )
    assert any(
        item["source"] == "current_chat_span"
        and item["reason"] == "source_budget_exceeded"
        for item in result.context_packet.metadata["dropped_candidates"]
    )
    assert sum(result.context_budget.source_token_budgets.values()) <= int(
        result.context_budget.metadata["allocatable_tokens"]
    )
