from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from src.actions.chat_end import ChatEndAction
from src.agents.context_manager_agent import ContextManagerAgent, ContextManagerResult
from src.core.contracts import RoutePlan, SourcePlan
from src.database import Database
from src.memory.short_term import ChatEndMemoryProcessingResult
from src.retrieval.raw_message_span_retriever import RawMessageSpanRetriever
from src.retrieval.recent_messages_retriever import RecentMessagesRetriever
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.route_planner import RoutePlanner


class NoopChatEndMemoryProcessor:
    def process_all_for_chat_end(
        self,
        chat_id: str,
    ) -> ChatEndMemoryProcessingResult:
        del chat_id
        return ChatEndMemoryProcessingResult(0, 0)


def build_production_context(
    *,
    database: Database,
    chat_id: str,
    query: str,
    route_plan: RoutePlan | None = None,
    dispatcher: RetrieverDispatcher | None = None,
) -> ContextManagerResult:
    """Run routed retrieval through the production context orchestration path."""
    plan = route_plan or RoutePlanner().plan(query)
    candidates = (dispatcher or RetrieverDispatcher(database)).retrieve(
        chat_id=chat_id,
        route_plan=plan,
    )
    return ContextManagerAgent().build_context_packet(
        system_prompt="Answer only from available context.",
        latest_user_message={"role": "user", "content": query},
        ranked_candidates=candidates,
        route_plan=plan,
    )


def assert_source_budgets_respect_total(result: ContextManagerResult) -> None:
    """Assert source reservations stay inside the allocator's hard allowance."""
    assert sum(result.context_budget.source_token_budgets.values()) <= int(
        result.context_budget.metadata["allocatable_tokens"]
    )


def test_production_previous_chat_raw_child_folds_gist_in_context_packet(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", "1")
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("previous-chat")
    start_id = database.save_message(
        "previous-chat",
        "user",
        "The deployment checklist requires a rollback rehearsal.",
    )
    end_id = database.save_message(
        "previous-chat",
        "assistant",
        "I recorded the rollback rehearsal requirement.",
    )
    gist_id = database.insert_chat_gist(
        chat_id="previous-chat",
        source_type="previous_chat_gist",
        gist_text="The deployment checklist includes a rollback rehearsal.",
        start_message_id=start_id,
        end_message_id=end_id,
    )
    database.create_chat("current-chat")
    query = "What did we discuss last time about the deployment checklist?"

    result = build_production_context(
        database=database,
        chat_id="current-chat",
        query=query,
    )

    assert result.context_budget.metadata["context_profile"] == "memory_recall"
    assert result.context_budget.source_token_budgets["previous_chat_gist"] > 0
    included = [
        candidate
        for candidate in result.context_packet.candidates
        if candidate.source == "raw_message_span"
    ]
    assert len(included) == 1
    assert included[0].metadata["parent_gist_id"] == gist_id
    assert included[0].source_message_ids == [start_id, end_id]
    assert any(
        "Raw Message Span:" in message["content"]
        and "rollback rehearsal" in message["content"]
        for message in result.context_packet.model_messages
    )
    assert_source_budgets_respect_total(result)


def test_ended_chat_gist_routes_by_intent_and_expands_exact_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", raising=False)
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("ended-chat")
    exact_sentence = "My exact deployment phrase is rehearse rollback before release."
    source_id = database.save_message("ended-chat", "user", exact_sentence)
    assistant_id = database.save_message("ended-chat", "assistant", "Recorded.")
    end_result = ChatEndAction(
        database,
        NoopChatEndMemoryProcessor(),
    ).execute("ended-chat")
    database.create_chat("new-chat")

    orientation_query = "What did we discuss last time about deployment?"
    orientation_plan = RoutePlanner().plan(orientation_query)
    orientation_candidates = RetrieverDispatcher(database).retrieve(
        "new-chat",
        orientation_plan,
    )

    exact_query = (
        "What exact phrase did I use in the previous chat about deployment?"
    )
    exact_plan = RoutePlanner().plan(exact_query)
    exact_candidates = RetrieverDispatcher(database).retrieve(
        "new-chat",
        exact_plan,
    )
    exact_context = ContextManagerAgent().build_context_packet(
        system_prompt="Use exact persisted evidence.",
        latest_user_message={"role": "user", "content": exact_query},
        ranked_candidates=exact_candidates,
        route_plan=exact_plan,
    ).context_packet

    casual_plan = RoutePlanner().plan("How are you?")
    casual_candidates = RetrieverDispatcher(database).retrieve(
        "new-chat",
        casual_plan,
    )

    assert end_result.gist_count == 1
    assert any(
        candidate.source == "previous_chat_gist"
        for candidate in orientation_candidates
    )
    raw = next(
        candidate
        for candidate in exact_candidates
        if candidate.source == "raw_message_span"
    )
    assert exact_sentence in raw.content
    assert raw.source_message_ids == [source_id, assistant_id]
    assert raw.metadata["parent_source"] == "previous_chat_gist"
    assert any(
        candidate.source == "raw_message_span"
        and exact_sentence in candidate.content
        for candidate in exact_context.candidates
    )
    assert all(
        candidate.source not in {"previous_chat_gist", "raw_message_span"}
        for candidate in casual_candidates
    )


def test_production_recent_messages_keep_old_fact_and_current_query_once(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("current-chat")
    old_user_id = database.save_message(
        "current-chat",
        "user",
        "Earlier fact: the staging environment is named cobalt.",
    )
    old_assistant_id = database.save_message(
        "current-chat",
        "assistant",
        "I will remember that staging is cobalt.",
    )
    query = "What did I say earlier in this chat about staging?"
    current_id = database.save_message("current-chat", "user", query)
    route_plan = RoutePlanner().plan(query)
    dispatcher = RetrieverDispatcher(
        database,
        retrievers={
            "recent_messages": RecentMessagesRetriever(database),
        },
    )

    result = build_production_context(
        database=database,
        chat_id="current-chat",
        query=query,
        route_plan=route_plan,
        dispatcher=dispatcher,
    )

    assert result.context_packet.recent_message_ids == [
        old_user_id,
        old_assistant_id,
    ]
    recent = [
        candidate
        for candidate in result.context_packet.candidates
        if candidate.source == "recent_messages"
    ]
    assert [candidate.record_id for candidate in recent] == [
        old_user_id,
        old_assistant_id,
    ]
    assert all(candidate.source_message_ids for candidate in recent)
    assert current_id not in result.context_packet.recent_message_ids
    assert [
        message["content"] for message in result.context_packet.model_messages
    ].index("Earlier fact: the staging environment is named cobalt.") < [
        message["content"] for message in result.context_packet.model_messages
    ].index("I will remember that staging is cobalt.")
    assert sum(
        message["role"] == "user" and message["content"] == query
        for message in result.context_packet.model_messages
    ) == 1
    assert_source_budgets_respect_total(result)


def test_explicit_raw_span_drill_down_reaches_context_with_provenance(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("evidence-chat")
    start_id = database.save_message(
        "evidence-chat",
        "user",
        "Use PostgreSQL for the audit service.",
    )
    end_id = database.save_message(
        "evidence-chat",
        "assistant",
        "Understood: PostgreSQL for the audit service.",
    )
    database.create_chat("current-chat")
    query = "Quote exactly what I said earlier about the audit service."
    production_plan = RoutePlanner().plan(query)
    raw_plan = SourcePlan(
        source="raw_message_span",
        enabled=True,
        reason="Explicit provenance drill-down requested by the acceptance fixture.",
        query=production_plan.query,
        filters={
            "chat_id": "evidence-chat",
            "start_message_id": start_id,
            "end_message_id": end_id,
        },
    )
    route_plan = replace(
        production_plan,
        sources=[
            source
            for source in production_plan.sources
            if source.source != "raw_message_span"
        ]
        + [raw_plan],
    )
    dispatcher = RetrieverDispatcher(
        database,
        retrievers={
            "raw_message_span": RawMessageSpanRetriever(database),
        },
    )

    result = build_production_context(
        database=database,
        chat_id="current-chat",
        query=query,
        route_plan=route_plan,
        dispatcher=dispatcher,
    )

    spans = [
        candidate
        for candidate in result.context_packet.candidates
        if candidate.source == "raw_message_span"
    ]
    assert len(spans) == 1
    assert spans[0].record_id == f"evidence-chat:{start_id}-{end_id}"
    assert spans[0].source_message_ids == [start_id, end_id]
    assert spans[0].metadata["start_message_id"] == start_id
    assert spans[0].metadata["end_message_id"] == end_id
    assert "user: Use PostgreSQL for the audit service." in spans[0].content
    assert any(
        "Raw Message Span:" in message["content"]
        and "user: Use PostgreSQL for the audit service." in message["content"]
        for message in result.context_packet.model_messages
    )
    assert_source_budgets_respect_total(result)


def test_production_disabled_previous_gist_does_not_retrieve_or_reach_context(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", "0")
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("previous-chat")
    message_id = database.save_message("previous-chat", "user", "Hidden old fact.")
    database.insert_chat_gist(
        chat_id="previous-chat",
        source_type="previous_chat_gist",
        gist_text="Hidden old fact.",
        start_message_id=message_id,
        end_message_id=message_id,
    )
    database.create_chat("current-chat")
    query = "What did we discuss last time?"
    route_plan = RoutePlanner().plan(query)

    result = build_production_context(
        database=database,
        chat_id="current-chat",
        query=query,
        route_plan=route_plan,
    )

    previous_plan = next(
        source
        for source in route_plan.sources
        if source.source == "previous_chat_gist"
    )
    assert previous_plan.enabled is False
    assert result.context_budget.source_token_budgets.get("previous_chat_gist", 0) == 0
    assert all(
        candidate.source != "previous_chat_gist"
        for candidate in result.context_packet.candidates
    )
    assert all(
        "Previous Chat Gist:" not in message["content"]
        for message in result.context_packet.model_messages
    )
    assert_source_budgets_respect_total(result)
