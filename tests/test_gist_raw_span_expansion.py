from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from src.actions.chat_end import ChatEndAction
from src.agents.context_manager_agent import ContextManagerAgent
from src.context.context_budget_allocator import (
    ContextBudgetAllocator,
    ContextBudgetPolicy,
)
from src.context.context_builder import ContextBuilder
from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan
from src.database import Database
from src.memory.short_term import ChatEndMemoryProcessingResult
from src.retrieval.current_chat_gist_retriever import CurrentChatGistRetriever
from src.retrieval.gist_raw_span_expander import GistRawSpanExpander
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.route_planner import RoutePlanner


class NoopMemoryProcessor:
    def process_all_for_chat_end(
        self,
        chat_id: str,
    ) -> ChatEndMemoryProcessingResult:
        del chat_id
        return ChatEndMemoryProcessingResult(0, 0)


def explicitly_enable_source(route_plan: RoutePlan, source_name: str) -> RoutePlan:
    """Enable one otherwise-disabled source without changing its query/profile."""
    return replace(
        route_plan,
        sources=[
            replace(source, enabled=True, query=route_plan.query)
            if source.source == source_name
            else source
            for source in route_plan.sources
        ],
    )


def test_finalized_previous_gist_expands_to_exact_raw_context(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", "1")
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("ended-chat")
    first_id = database.save_message(
        "ended-chat",
        "user",
        "The release phrase is preserve every rollback path.",
    )
    second_id = database.save_message("ended-chat", "assistant", "Recorded exactly.")
    ChatEndAction(database, NoopMemoryProcessor()).execute("ended-chat")
    database.create_chat("current-chat")
    query = "What did we discuss last time about the rollback path?"
    route_plan = RoutePlanner().plan(query)
    candidates = RetrieverDispatcher(
        database,
        retrievers={
            "previous_chat_gist": PreviousChatGistRetriever(database),
        },
    ).retrieve("current-chat", route_plan)

    result = ContextManagerAgent().build_context_packet(
        system_prompt="Use exact evidence.",
        latest_user_message={"role": "user", "content": query},
        ranked_candidates=candidates,
        route_plan=route_plan,
    )

    raw = next(
        candidate
        for candidate in result.context_packet.candidates
        if candidate.source == "raw_message_span"
    )
    assert (
        "user: The release phrase is preserve every rollback path."
        in raw.content
    )
    assert raw.source_message_ids == [first_id, second_id]
    parent_gist_id = raw.metadata["parent_gist_id"]
    assert parent_gist_id is not None
    assert raw.metadata["parent_source"] == "previous_chat_gist"
    assert raw.metadata["start_message_id"] == first_id
    assert raw.metadata["end_message_id"] == second_id
    assert any(
        item["record_id"] == parent_gist_id
        and item["reason"] == "folded_into_raw_child"
        for item in result.context_packet.metadata["dropped_candidates"]
    )
    assert result.context_budget.source_token_budgets["previous_chat_gist"] > 0
    assert result.context_budget.source_token_budgets["raw_message_span"] > 0
    assert any(
        "Raw Message Span:" in message["content"]
        and "preserve every rollback path" in message["content"]
        for message in result.context_packet.model_messages
    )


def test_exact_quote_query_reranks_expanded_raw_span_above_gist(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("old-chat")
    message_id = database.save_message(
        "old-chat",
        "user",
        "Measure twice, deploy once, preserve rollback.",
    )
    gist_id = database.insert_chat_gist(
        chat_id="old-chat",
        source_type="previous_chat_gist",
        gist_text="The user discussed cautious deployment.",
        start_message_id=message_id,
        end_message_id=message_id,
    )
    gist = PreviousChatGistRetriever(database).retrieve(
        "new-chat",
        source_plan=SourcePlan(
            source="previous_chat_gist",
            enabled=True,
            query=None,
        ),
    )[0]
    query = "What exact phrase did I use about rollback?"
    candidates = [gist] + GistRawSpanExpander(database).expand([gist], query)

    ranked = MemoryReranker().rank(
        candidates,
        ranking_profile=None,
        query=query,
    )

    assert gist.record_id == gist_id
    assert ranked[0].source == "raw_message_span"
    assert "Measure twice, deploy once, preserve rollback." in ranked[0].content


def test_missing_gist_provenance_keeps_orientation_without_malformed_span(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    gist = MemoryCandidate(
        source="previous_chat_gist",
        content="Orientation without persisted provenance.",
        record_id="missing",
    )

    expanded = GistRawSpanExpander(database).expand([gist], "orientation")

    assert expanded == []
    assert gist.content == "Orientation without persisted provenance."


def test_large_gist_range_expansion_is_query_centered_and_bounded(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    ids = [
        database.save_message(
            "chat",
            "user" if index % 2 == 0 else "assistant",
            "Distinctive zircon evidence." if index == 8 else f"message {index}",
        )
        for index in range(12)
    ]
    gist = MemoryCandidate(
        source="previous_chat_gist",
        content="A long prior discussion.",
        record_id="long-gist",
        chat_id="chat",
        source_message_ids=[ids[0], ids[-1]],
        metadata={
            "start_message_id": ids[0],
            "end_message_id": ids[-1],
        },
    )

    expanded = GistRawSpanExpander(database, max_messages=3).expand(
        [gist],
        "What was the zircon evidence?",
    )

    assert len(expanded) == 1
    assert len(expanded[0].source_message_ids) == 3
    assert ids[8] in expanded[0].source_message_ids
    assert "Distinctive zircon evidence." in expanded[0].content
    assert expanded[0].metadata["original_start_message_id"] == ids[0]
    assert expanded[0].metadata["original_end_message_id"] == ids[-1]
    assert expanded[0].metadata["truncated"] is True


def test_overlapping_gist_expansions_merge_and_preserve_parent_links(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    ids = [
        database.save_message("chat", "user", f"message {index}")
        for index in range(6)
    ]
    first = MemoryCandidate(
        source="previous_chat_gist",
        content="First orientation.",
        record_id="gist-a",
        chat_id="chat",
        metadata={
            "start_message_id": ids[0],
            "end_message_id": ids[3],
        },
    )
    second = MemoryCandidate(
        source="previous_chat_gist",
        content="Second orientation.",
        record_id="gist-b",
        chat_id="chat",
        metadata={
            "start_message_id": ids[2],
            "end_message_id": ids[5],
        },
    )

    expanded = GistRawSpanExpander(database, max_messages=10).expand(
        [first, second],
        "message",
    )

    assert len(expanded) == 1
    assert expanded[0].source_message_ids == ids
    assert expanded[0].metadata["parent_gist_ids"] == ["gist-a", "gist-b"]
    assert len(set(expanded[0].source_message_ids)) == len(ids)


def test_small_provenance_includes_all_messages_with_diagnostics(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    ids = [
        database.save_message("chat", "user", "first source message"),
        database.save_message("chat", "assistant", "second source message"),
        database.save_message("chat", "user", "third source message"),
    ]
    gist = MemoryCandidate(
        source="previous_chat_gist",
        content="Three-message orientation.",
        record_id="small-gist",
        chat_id="chat",
        source_message_ids=ids,
        metadata={
            "start_message_id": ids[0],
            "end_message_id": ids[-1],
        },
    )

    expanded = GistRawSpanExpander(database, max_messages=3).expand(
        [gist],
        "source message",
    )

    assert len(expanded) == 1
    raw = expanded[0]
    assert raw.source_message_ids == ids
    assert raw.content.splitlines() == [
        "user: first source message",
        "assistant: second source message",
        "user: third source message",
    ]
    assert raw.metadata["provenance_message_count"] == 3
    assert raw.metadata["included_message_ids"] == ids
    assert raw.metadata["omitted_message_ids_count"] == 0
    assert raw.metadata["selection_reason"] == "all_provenance_messages_fit"


def test_large_provenance_selects_near_end_query_anchor_and_neighbors(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    ids = [
        database.save_message(
            "chat",
            "user" if index % 2 == 0 else "assistant",
            (
                "The near-end retrieval marker is VERMILION-88."
                if index == 17
                else f"unrelated source message {index}"
            ),
        )
        for index in range(20)
    ]
    gist = MemoryCandidate(
        source="previous_chat_gist",
        content="Long source orientation.",
        record_id="near-end-gist",
        chat_id="chat",
        metadata={
            "start_message_id": ids[0],
            "end_message_id": ids[-1],
        },
    )

    expanded = GistRawSpanExpander(database, max_messages=5).expand(
        [gist],
        "What was the VERMILION-88 retrieval marker?",
    )

    assert len(expanded) == 1
    raw = expanded[0]
    assert ids[17] in raw.source_message_ids
    assert ids[0] not in raw.source_message_ids
    assert "The near-end retrieval marker is VERMILION-88." in raw.content
    assert raw.source_message_ids == sorted(raw.source_message_ids)
    assert raw.metadata["provenance_message_count"] == 20
    assert raw.metadata["omitted_message_ids_count"] == 15
    assert raw.metadata["selection_reason"] == "query_centered_contiguous_window"
    assert raw.metadata["window_char_count"] <= 4000


def test_adjacent_gists_keep_independent_query_centered_windows(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    ids = [
        database.save_message(
            "chat",
            "user",
            (
                f"segment anchor {index} shared retrieval phrase"
                if index in {2, 9}
                else f"unrelated message {index}"
            ),
        )
        for index in range(12)
    ]
    first = MemoryCandidate(
        source="previous_chat_gist",
        content="First segment shared retrieval phrase.",
        record_id="gist-first",
        chat_id="chat",
        metadata={
            "start_message_id": ids[0],
            "end_message_id": ids[5],
        },
    )
    second = MemoryCandidate(
        source="previous_chat_gist",
        content="Second segment shared retrieval phrase.",
        record_id="gist-second",
        chat_id="chat",
        metadata={
            "start_message_id": ids[6],
            "end_message_id": ids[11],
        },
    )

    expanded = GistRawSpanExpander(database, max_messages=3).expand(
        [first, second],
        "shared retrieval phrase",
    )

    assert len(expanded) == 2
    assert [candidate.metadata["parent_gist_id"] for candidate in expanded] == [
        "gist-first",
        "gist-second",
    ]
    assert ids[2] in expanded[0].source_message_ids
    assert ids[9] in expanded[1].source_message_ids
    assert all(
        candidate.metadata["omitted_message_ids_count"] == 3
        for candidate in expanded
    )

    route_plan = RoutePlan(
        query="shared retrieval phrase",
        intent="memory_recall",
        sources=[
            SourcePlan(
                source="previous_chat_gist",
                enabled=True,
                query="shared retrieval phrase",
            )
        ],
        context_profile="memory_recall",
    )
    packet = ContextManagerAgent(
        budget_allocator=ContextBudgetAllocator(
            policy=ContextBudgetPolicy(
                default_model_context_limit=600,
                default_answer_reserve=100,
            )
        ),
        context_builder=ContextBuilder(),
    ).build_context_packet(
        system_prompt="Use exact raw evidence.",
        latest_user_message={
            "role": "user",
            "content": "shared retrieval phrase",
        },
        ranked_candidates=expanded,
        route_plan=route_plan,
    ).context_packet

    assert any(
        candidate.source == "raw_message_span"
        and "segment anchor 2 shared retrieval phrase" in candidate.content
        for candidate in packet.candidates
    )


def test_window_diagnostics_are_bounded(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    ids = [
        database.save_message("chat", "user", f"message {index}")
        for index in range(40)
    ]
    gist = MemoryCandidate(
        source="previous_chat_gist",
        content="Large provenance.",
        record_id="bounded-diagnostics",
        chat_id="chat",
        metadata={
            "start_message_id": ids[0],
            "end_message_id": ids[-1],
        },
    )

    raw = GistRawSpanExpander(database, max_messages=30).expand(
        [gist],
        "message 25",
    )[0]

    assert len(raw.source_message_ids) == 30
    assert len(raw.metadata["included_message_ids"]) == 20
    assert raw.metadata["provenance_message_count"] == 40
    assert raw.metadata["omitted_message_ids_count"] == 10


def test_current_gist_expands_only_when_source_is_explicitly_enabled(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    first_id = database.save_message(
        "chat",
        "user",
        "The active task codename is topaz.",
    )
    second_id = database.save_message("chat", "assistant", "Recorded.")
    database.insert_chat_gist(
        chat_id="chat",
        source_type="current_chat_gist",
        gist_text="The active task has a codename.",
        start_message_id=first_id,
        end_message_id=second_id,
    )
    query = "What did I say earlier in this chat about the task codename?"
    default_plan = RoutePlanner().plan(query)
    dispatcher = RetrieverDispatcher(
        database,
        retrievers={
            "current_chat_gist": CurrentChatGistRetriever(database),
        },
    )

    default_candidates = dispatcher.retrieve("chat", default_plan)
    enabled_candidates = dispatcher.retrieve(
        "chat",
        explicitly_enable_source(default_plan, "current_chat_gist"),
    )

    assert default_candidates == []
    assert {candidate.source for candidate in enabled_candidates} == {
        "current_chat_gist",
        "raw_message_span",
    }
    raw = next(
        candidate
        for candidate in enabled_candidates
        if candidate.source == "raw_message_span"
    )
    assert "user: The active task codename is topaz." in raw.content
    assert raw.metadata["parent_source"] == "current_chat_gist"


def test_expansion_respects_tight_context_budget(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("old-chat")
    first_id = database.save_message(
        "old-chat",
        "user",
        f"Rollback evidence {'detail ' * 1000}",
    )
    second_id = database.save_message("old-chat", "assistant", "Recorded.")
    gist_id = database.insert_chat_gist(
        chat_id="old-chat",
        source_type="previous_chat_gist",
        gist_text="Rollback evidence was discussed.",
        start_message_id=first_id,
        end_message_id=second_id,
    )
    gist = PreviousChatGistRetriever(database).retrieve(
        "new-chat",
        source_plan=SourcePlan(
            source="previous_chat_gist",
            enabled=True,
            query=None,
        ),
    )[0]
    route_plan = explicitly_enable_source(
        RoutePlanner().plan("What did we discuss last time about rollback?"),
        "previous_chat_gist",
    )
    candidates = [gist] + GistRawSpanExpander(database).expand(
        [gist],
        route_plan.query,
    )
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
        system_prompt="Use bounded evidence.",
        latest_user_message={"role": "user", "content": route_plan.query},
        ranked_candidates=candidates,
        route_plan=route_plan,
    )

    assert gist.record_id == gist_id
    assert sum(result.context_budget.source_token_budgets.values()) <= int(
        result.context_budget.metadata["allocatable_tokens"]
    )
    assert result.context_packet.metadata["overflow_detected"] is False
    assert any(
        item["source"] == "raw_message_span"
        for item in result.context_packet.metadata["dropped_candidates"]
    )
