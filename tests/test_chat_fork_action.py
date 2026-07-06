from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.actions.chat_fork import ChatForkAction
from src.database import Database
from src.memory.long_term_store import (
    DEFAULT_USER_NAMESPACE,
    LongTermMemoryWrite,
    SQLiteLongTermMemoryStore,
)
from src.memory.short_term import ShortTermMemory
from src.memory.structured_state import MemoryUpdateResult


def action_for(database: Database, new_chat_id: str = "forked-chat") -> ChatForkAction:
    return ChatForkAction(database, id_factory=lambda: new_chat_id)


class FakeModel:
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del messages, temperature
        return ""


class PersistingFactUpdater:
    """Store one distinct test record per processed user fact."""

    def __init__(self, database: Database) -> None:
        self.store = SQLiteLongTermMemoryStore(database)
        self.processed_batches: list[list[str]] = []
        self.write_count = 0
        self.last_saved_records: list[object] = []

    def update(self, existing_memory, messages):  # type: ignore[no-untyped-def]
        self.processed_batches.append([message.content for message in messages])
        for message in messages:
            if message.role != "user" or not message.content.startswith("Fact:"):
                continue
            self.write_count += 1
            self.store.upsert(
                LongTermMemoryWrite(
                    namespace=DEFAULT_USER_NAMESPACE,
                    memory_id=f"test-fact-{self.write_count}",
                    category="preferences",
                    key=f"fact_{self.write_count}",
                    value=message.content,
                    source_chat_id=message.chat_id,
                    source_message_ids=[message.id],
                )
            )
        return MemoryUpdateResult(memory_state=existing_memory, accepted=True)


def memory_for(database: Database, updater: PersistingFactUpdater) -> ShortTermMemory:
    return ShortTermMemory(
        database=database,
        model=FakeModel(),
        memory_update_batch_size=2,
        structured_memory_updater=updater,
    )


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
    database.mark_messages_gist_processed(original_ids[1:])
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
    assert [message.summarized for message in copied] == [True, True, True]
    assert [message.gist_processed for message in copied] == [False, True, True]
    assert {message.id for message in copied}.isdisjoint(original_ids)


def test_pending_inherited_messages_are_not_semantically_reprocessed(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("original")
    database.save_message(
        "original",
        "user",
        "Fact: I prefer mature open-source libraries.",
    )
    database.save_message("original", "assistant", "Recorded.")
    updater = PersistingFactUpdater(database)

    new_chat_id = action_for(database).execute("original")
    original_result = memory_for(database, updater).process_all_for_chat_end("original")
    fork_result = memory_for(database, updater).process_all_for_chat_end(new_chat_id)

    records = updater.store.list(DEFAULT_USER_NAMESPACE)
    assert original_result.processed_message_count == 2
    assert fork_result.processed_message_count == 0
    assert len(records) == 1
    assert records[0].value == "Fact: I prefer mature open-source libraries."
    assert records[0].source_chat_id == "original"
    assert all(
        message.summarized
        for message in database.messages_for_chat(new_chat_id)
    )


def test_post_fork_messages_remain_semantically_processable(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("original")
    database.save_message(
        "original",
        "user",
        "Fact: I prefer mature open-source libraries.",
    )
    database.save_message("original", "assistant", "Recorded.")
    updater = PersistingFactUpdater(database)
    memory_for(database, updater).process_all_for_chat_end("original")
    original_before = database.messages_for_chat("original")

    new_chat_id = action_for(database).execute("original")
    new_message_id = database.save_message(
        new_chat_id,
        "user",
        "Fact: I now prefer concise implementation notes.",
    )
    result = memory_for(database, updater).process_all_for_chat_end(new_chat_id)

    records = updater.store.list(DEFAULT_USER_NAMESPACE)
    assert result.processed_message_count == 1
    assert len(records) == 2
    assert {record.value for record in records} == {
        "Fact: I prefer mature open-source libraries.",
        "Fact: I now prefer concise implementation notes.",
    }
    assert sum(
        record.value == "Fact: I prefer mature open-source libraries."
        for record in records
    ) == 1
    new_record = next(
        record
        for record in records
        if record.value == "Fact: I now prefer concise implementation notes."
    )
    assert new_record.source_chat_id == new_chat_id
    assert new_record.source_message_ids == [new_message_id]
    assert database.messages_for_chat("original") == original_before
    assert new_chat_id in {
        chat["id"] for chat in database.list_active_chats()
    }


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
