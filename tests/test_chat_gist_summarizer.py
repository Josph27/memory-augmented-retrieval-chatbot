from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.database import Database, StoredMessage
from src.memory.chat_gist_summarizer import (
    ChatGistSummary,
    CurrentChatGistSummarizer,
    parse_gist_summary,
)


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
    ).create_gist_if_needed("chat")

    assert result.created is True
    messages = {message.id: message for message in db.messages_for_chat("chat")}
    assert all(messages[message_id].gist_processed for message_id in ids[:3])
    assert all(not message.summarized for message in messages.values())


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
