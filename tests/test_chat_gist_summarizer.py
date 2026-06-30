from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.actions.chat_end import ChatEndAction
from src.agents.context_manager_agent import ContextManagerAgent
from src.database import Database, StoredMessage
from src.memory.chat_gist_summarizer import (
    ChatGistSummary,
    CurrentChatGistSummarizer,
    parse_gist_summary,
)
from src.memory.short_term import ChatEndMemoryProcessingResult
from src.retrieval.current_chat_gist_retriever import CurrentChatGistRetriever
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.route_planner import RoutePlanner


class FakeGistExtractor:
    def summarize(self, messages: list[StoredMessage]) -> ChatGistSummary:
        joined = ", ".join(str(message.id) for message in messages)
        return ChatGistSummary(
            summary=f"Summarized message ids: {joined}",
            topics=["memory"],
            decisions=["Use gists for older chat history"],
            open_tasks=["Add vector retrieval later"],
            important_facts=["Raw messages remain source of truth"],
            corrections=["No corrections"],
        )


class EmptyGistExtractor:
    def summarize(self, messages: list[StoredMessage]) -> ChatGistSummary:
        del messages
        return ChatGistSummary(summary="")


class FailingInsertDatabase(Database):
    def insert_chat_gist(self, *args, **kwargs) -> int:  # type: ignore[no-untyped-def]
        raise RuntimeError("insert failed")


class NoopChatEndMemoryProcessor:
    def process_all_for_chat_end(
        self,
        chat_id: str,
    ) -> ChatEndMemoryProcessingResult:
        del chat_id
        return ChatEndMemoryProcessingResult(0, 0)


def populate_messages(db: Database, chat_id: str, count: int) -> list[int]:
    ids: list[int] = []
    for index in range(count):
        role = "user" if index % 2 == 0 else "assistant"
        ids.append(db.save_message(chat_id, role, f"message {index + 1}"))
    return ids


def test_no_gist_created_if_not_enough_messages(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    populate_messages(db, "chat", 5)

    result = CurrentChatGistSummarizer(
        database=db,
        extractor=FakeGistExtractor(),
        min_messages_to_summarize=6,
        keep_recent_messages=1,
        max_messages_per_gist=10,
        enabled=True,
    ).create_gist_if_needed("chat")

    assert result.created is False
    assert result.skipped_reason == "not_enough_old_unsummarized_messages"
    assert db.chat_gists_for_chat("chat") == []
    assert all(not message.summarized for message in db.messages_for_chat("chat"))
    assert all(not message.gist_processed for message in db.messages_for_chat("chat"))


def test_older_messages_are_gist_processed_and_latest_recent_messages_are_kept(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    ids = populate_messages(db, "chat", 8)

    result = CurrentChatGistSummarizer(
        database=db,
        extractor=FakeGistExtractor(),
        min_messages_to_summarize=3,
        keep_recent_messages=2,
        max_messages_per_gist=3,
        enabled=True,
    ).create_gist_if_needed("chat")

    assert result.created is True
    assert result.gist_id is not None
    assert result.summarized_message_ids == ids[:3]

    gist = db.chat_gist(result.gist_id)
    assert gist is not None
    assert gist.source_type == "current_chat_gist"
    assert gist.start_message_id == ids[0]
    assert gist.end_message_id == ids[2]
    assert "Summarized message ids" in gist.gist_text
    assert json.loads(gist.topics_json) == ["memory"]
    assert json.loads(gist.decisions_json) == ["Use gists for older chat history"]
    assert json.loads(gist.open_tasks_json) == ["Add vector retrieval later"]
    metadata = json.loads(gist.metadata_json)
    assert metadata["important_facts"] == ["Raw messages remain source of truth"]
    assert metadata["source_message_count"] == 3
    assert metadata["source_message_ids"] == ids[:3]
    assert metadata["evidence_role"] == "orientation_only"

    messages = db.messages_for_chat("chat")
    gist_processed = {message.id for message in messages if message.gist_processed}
    assert gist_processed == set(ids[:3])
    assert all(not message.gist_processed for message in messages[-2:])
    assert all(not message.summarized for message in messages)


def test_latest_user_message_is_not_summarized_even_with_small_recent_window(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    first_id = db.save_message("chat", "user", "first")
    second_id = db.save_message("chat", "assistant", "second")
    latest_user_id = db.save_message("chat", "user", "latest user")
    assistant_id = db.save_message("chat", "assistant", "latest assistant")

    result = CurrentChatGistSummarizer(
        database=db,
        extractor=FakeGistExtractor(),
        min_messages_to_summarize=2,
        keep_recent_messages=1,
        max_messages_per_gist=10,
        enabled=True,
    ).create_gist_if_needed("chat")

    assert result.created is True
    assert result.summarized_message_ids == [first_id, second_id]
    messages = {message.id: message for message in db.messages_for_chat("chat")}
    assert messages[latest_user_id].gist_processed is False
    assert messages[assistant_id].gist_processed is False


def test_messages_are_not_marked_summarized_if_insert_fails(tmp_path: Path) -> None:
    db = FailingInsertDatabase(tmp_path / "chatbot.db")
    db.create_chat("chat")
    ids = populate_messages(db, "chat", 5)

    with pytest.raises(RuntimeError, match="insert failed"):
        CurrentChatGistSummarizer(
            database=db,
            extractor=FakeGistExtractor(),
            min_messages_to_summarize=3,
            keep_recent_messages=1,
            max_messages_per_gist=3,
            enabled=True,
        ).create_gist_if_needed("chat")

    messages = db.messages_for_chat("chat")
    assert [message.id for message in messages] == ids
    assert all(not message.summarized for message in messages)
    assert all(not message.gist_processed for message in messages)


def test_empty_gist_is_rejected_without_marking_messages(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    populate_messages(db, "chat", 5)

    result = CurrentChatGistSummarizer(
        database=db,
        extractor=EmptyGistExtractor(),
        min_messages_to_summarize=3,
        keep_recent_messages=1,
        max_messages_per_gist=3,
        enabled=True,
    ).create_gist_if_needed("chat")

    assert result.created is False
    assert result.skipped_reason == "invalid_or_empty_gist"
    assert db.chat_gists_for_chat("chat") == []
    assert all(not message.summarized for message in db.messages_for_chat("chat"))
    assert all(not message.gist_processed for message in db.messages_for_chat("chat"))


def test_no_model_or_extractor_skips_without_side_effects(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    populate_messages(db, "chat", 5)

    result = CurrentChatGistSummarizer(
        database=db,
        min_messages_to_summarize=3,
        keep_recent_messages=1,
        max_messages_per_gist=3,
        enabled=True,
    ).create_gist_if_needed("chat")

    assert result.created is False
    assert result.skipped_reason == "no_gist_extractor_configured"
    assert db.chat_gists_for_chat("chat") == []


def test_structured_summarized_messages_remain_eligible_for_gist(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    ids = populate_messages(db, "chat", 5)
    db.mark_messages_summarized(ids[:3])

    result = CurrentChatGistSummarizer(
        database=db,
        extractor=FakeGistExtractor(),
        min_messages_to_summarize=3,
        keep_recent_messages=2,
        max_messages_per_gist=3,
        enabled=True,
    ).create_gist_if_needed("chat")

    assert result.created is True
    assert result.summarized_message_ids == ids[:3]
    messages = {message.id: message for message in db.messages_for_chat("chat")}
    assert all(messages[message_id].summarized for message_id in ids[:3])
    assert all(messages[message_id].gist_processed for message_id in ids[:3])


def test_gist_processing_does_not_mark_structured_memory_summarized(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    ids = populate_messages(db, "chat", 5)

    result = CurrentChatGistSummarizer(
        database=db,
        extractor=FakeGistExtractor(),
        min_messages_to_summarize=3,
        keep_recent_messages=2,
        max_messages_per_gist=3,
        enabled=True,
    ).create_gist_if_needed("chat")

    assert result.created is True
    messages = {message.id: message for message in db.messages_for_chat("chat")}
    assert all(messages[message_id].gist_processed for message_id in ids[:3])
    assert all(not message.summarized for message in messages.values())


def test_current_chat_gist_processor_is_disabled_by_default(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    populate_messages(db, "chat", 6)

    result = CurrentChatGistSummarizer(
        database=db,
        extractor=FakeGistExtractor(),
        min_messages_to_summarize=2,
        keep_recent_messages=2,
        max_messages_per_gist=2,
    ).process_current_chat_gist_batch("chat")

    assert result.created is False
    assert result.skipped_reason == "current_chat_gist_disabled"
    assert db.chat_gists_for_chat("chat", "current_chat_gist") == []
    assert all(
        not message.gist_processed
        for message in db.messages_for_chat("chat")
    )


def test_repeated_current_chat_gist_batch_does_not_duplicate_processed_span(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    ids = populate_messages(db, "chat", 5)
    summarizer = CurrentChatGistSummarizer(
        database=db,
        extractor=FakeGistExtractor(),
        min_messages_to_summarize=3,
        keep_recent_messages=2,
        max_messages_per_gist=3,
        enabled=True,
    )

    first = summarizer.process_current_chat_gist_batch("chat")
    second = summarizer.process_current_chat_gist_batch("chat")

    assert first.created is True
    assert first.summarized_message_ids == ids[:3]
    assert second.created is False
    assert second.skipped_reason == "not_enough_old_unsummarized_messages"
    assert len(db.chat_gists_for_chat("chat", "current_chat_gist")) == 1


def test_current_chat_gist_is_not_routed_into_default_context(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    first_id = db.save_message("chat", "user", "The current task uses cobalt.")
    second_id = db.save_message("chat", "assistant", "Recorded.")
    db.insert_chat_gist(
        chat_id="chat",
        source_type="current_chat_gist",
        gist_text="The current task uses cobalt.",
        start_message_id=first_id,
        end_message_id=second_id,
    )
    query = "What did I say earlier in this chat?"
    route_plan = RoutePlanner().plan(query)
    candidates = RetrieverDispatcher(
        db,
        retrievers={
            "current_chat_gist": CurrentChatGistRetriever(db),
        },
    ).retrieve("chat", route_plan)

    context = ContextManagerAgent().build_context_packet(
        system_prompt="Use available context.",
        latest_user_message={"role": "user", "content": query},
        ranked_candidates=candidates,
        route_plan=route_plan,
    ).context_packet

    current_gist_plan = next(
        source
        for source in route_plan.sources
        if source.source == "current_chat_gist"
    )
    assert current_gist_plan.enabled is False
    assert candidates == []
    assert all(
        candidate.source != "current_chat_gist"
        for candidate in context.candidates
    )


def test_chat_end_finalizes_only_messages_pending_after_rolling_gist(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    ids = populate_messages(db, "chat", 6)
    rolling = CurrentChatGistSummarizer(
        database=db,
        extractor=FakeGistExtractor(),
        min_messages_to_summarize=2,
        keep_recent_messages=2,
        max_messages_per_gist=2,
        enabled=True,
    )

    rolling_result = rolling.process_current_chat_gist_batch("chat")
    end_result = ChatEndAction(db, NoopChatEndMemoryProcessor()).execute("chat")

    current_gists = db.chat_gists_for_chat("chat", "current_chat_gist")
    previous_gists = db.chat_gists_for_chat("chat", "previous_chat_gist")
    assert rolling_result.summarized_message_ids == ids[:2]
    assert end_result.gist_processed_message_count == 4
    assert len(current_gists) == 1
    assert len(previous_gists) == 1
    assert (
        current_gists[0].start_message_id,
        current_gists[0].end_message_id,
    ) == (ids[0], ids[1])
    assert (
        previous_gists[0].start_message_id,
        previous_gists[0].end_message_id,
    ) == (ids[2], ids[5])
    assert all(
        message.gist_processed
        for message in db.messages_for_chat("chat")
    )
    assert [chat["id"] for chat in db.list_inactive_chats()] == ["chat"]


def test_parse_gist_summary_accepts_valid_json_and_rejects_transcripts() -> None:
    valid = parse_gist_summary(
        json.dumps(
            {
                "summary": "The user is building chat memory gists.",
                "topics": ["memory"],
                "decisions": ["Use SQLite storage"],
                "open_tasks": ["Add retrieval"],
                "important_facts": ["Raw messages are source of truth"],
                "corrections": [],
            }
        )
    )
    transcript = parse_gist_summary(
        json.dumps(
            {
                "summary": "user: one assistant: two user: three",
                "topics": [],
                "decisions": [],
                "open_tasks": [],
                "important_facts": [],
                "corrections": [],
            }
        )
    )

    assert valid is not None
    assert valid.summary == "The user is building chat memory gists."
    assert valid.topics == ["memory"]
    assert transcript is None
