from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.actions.chat_fork import ChatForkAction
from src.database import Database


def action_for(database: Database, new_chat_id: str = "forked-chat") -> ChatForkAction:
    return ChatForkAction(database, id_factory=lambda: new_chat_id)


def test_fork_empty_chat_creates_active_copy_and_preserves_original(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("original", title="Original", model_name="test-model")

    new_chat_id = action_for(database).execute("original")

    assert new_chat_id == "forked-chat"
    assert database.get_chat("original") is not None
    forked = database.get_chat(new_chat_id)
    assert forked is not None
    assert forked.title == "Original"
    assert forked.model_name == "test-model"
    assert database.messages_for_chat(new_chat_id) == []
    assert {chat["id"] for chat in database.list_active_chats()} == {
        "original",
        "forked-chat",
    }


def test_fork_copies_messages_with_new_ids_and_preserves_order(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("original")
    original_ids = [
        database.save_message("original", "user", "First"),
        database.save_message("original", "assistant", "Second"),
        database.save_message("original", "user", "Third"),
    ]
    database.mark_messages_summarized(original_ids[:2])
    original_before = database.messages_for_chat("original")

    new_chat_id = action_for(database).execute("original")

    original_after = database.messages_for_chat("original")
    copied = database.messages_for_chat(new_chat_id)
    assert original_after == original_before
    assert [message.chat_id for message in copied] == [new_chat_id] * 3
    assert [(message.role, message.content) for message in copied] == [
        ("user", "First"),
        ("assistant", "Second"),
        ("user", "Third"),
    ]
    assert [message.summarized for message in copied] == [True, True, False]
    assert {message.id for message in copied}.isdisjoint(original_ids)


def test_fork_remaps_gist_provenance_without_copying_legacy_memory(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("original")
    first_id = database.save_message("original", "user", "Choose SQLite.")
    second_id = database.save_message("original", "assistant", "Recorded.")
    database.insert_chat_gist(
        chat_id="original",
        source_type="current_chat_gist",
        gist_text="SQLite was selected.",
        start_message_id=first_id,
        end_message_id=second_id,
        metadata={
            "source_chat_id": "original",
            "source_message_ids": [first_id, second_id],
            "nested": {
                "start_message_id": first_id,
                "end_message_id": second_id,
            },
        },
    )
    database.upsert_chat_memory_state(
        "original",
        json.dumps(
            {
                "memories": [
                    {
                        "id": "decisions:database",
                        "source_message_ids": [first_id],
                    }
                ]
            }
        ),
    )

    new_chat_id = action_for(database).execute("original")

    copied_messages = database.messages_for_chat(new_chat_id)
    copied_ids = [message.id for message in copied_messages]
    copied_gists = database.chat_gists_for_chat(new_chat_id)
    assert len(copied_gists) == 1
    gist = copied_gists[0]
    metadata = json.loads(gist.metadata_json)
    assert gist.chat_id == new_chat_id
    assert [gist.start_message_id, gist.end_message_id] == copied_ids
    assert metadata["source_chat_id"] == new_chat_id
    assert metadata["source_message_ids"] == copied_ids
    assert metadata["nested"] == {
        "start_message_id": copied_ids[0],
        "end_message_id": copied_ids[1],
    }
    assert {gist.start_message_id, gist.end_message_id}.isdisjoint(
        {first_id, second_id}
    )
    assert database.chat_memory_state(new_chat_id) is None
    assert database.chat_memory_state("original") is not None


def test_fork_rolls_back_if_provenance_cannot_be_remapped(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("original")
    database.save_message("original", "user", "Hello")
    database.insert_chat_gist(
        chat_id="original",
        source_type="current_chat_gist",
        gist_text="Broken provenance.",
        start_message_id=999_999,
        end_message_id=999_999,
    )

    with pytest.raises(ValueError, match="Cannot remap"):
        action_for(database).execute("original")

    assert database.get_chat("forked-chat") is None
    assert database.messages_for_chat("forked-chat") == []
    assert database.chat_gists_for_chat("forked-chat") == []
    assert database.message_count("original") == 1


def test_fork_missing_chat_raises_clear_error_without_partial_chat(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")

    with pytest.raises(ValueError, match="Chat not found: missing"):
        action_for(database).execute("missing")

    assert database.get_chat("forked-chat") is None
