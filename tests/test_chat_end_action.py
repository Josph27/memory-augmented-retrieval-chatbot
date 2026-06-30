from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from src.actions.chat_end import ChatEndAction
from src.database import Database
from src.memory.short_term import (
    ChatEndMemoryProcessingError,
    ChatEndMemoryProcessingResult,
    ShortTermMemory,
)
from src.memory.structured_state import MemoryUpdateResult


class FakeModel:
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del messages, temperature
        return ""


@dataclass
class RecordingMemoryProcessor:
    result: ChatEndMemoryProcessingResult
    error: Exception | None = None

    def __post_init__(self) -> None:
        self.calls: list[str] = []

    def process_all_for_chat_end(
        self,
        chat_id: str,
    ) -> ChatEndMemoryProcessingResult:
        self.calls.append(chat_id)
        if self.error is not None:
            raise self.error
        return self.result


class RecordingUpdater:
    def __init__(self, fail_on_call: int | None = None) -> None:
        self.fail_on_call = fail_on_call
        self.batch_message_ids: list[list[int]] = []

    def update(self, existing_memory, messages):  # type: ignore[no-untyped-def]
        self.batch_message_ids.append([message.id for message in messages])
        if self.fail_on_call == len(self.batch_message_ids):
            return MemoryUpdateResult(
                memory_state=existing_memory,
                accepted=False,
                rejection_reason="fake_failure",
            )
        return MemoryUpdateResult(
            memory_state=existing_memory,
            accepted=True,
        )


class NoopUpdater:
    def __init__(self, rejection_reason: str) -> None:
        self.rejection_reason = rejection_reason
        self.batch_message_ids: list[list[int]] = []

    def update(self, existing_memory, messages):  # type: ignore[no-untyped-def]
        self.batch_message_ids.append([message.id for message in messages])
        return MemoryUpdateResult(
            memory_state=existing_memory,
            accepted=False,
            rejection_reason=self.rejection_reason,
        )


class RaisingUpdater:
    def update(self, existing_memory, messages):  # type: ignore[no-untyped-def]
        del existing_memory, messages
        raise RuntimeError("model unavailable")


def test_chat_end_success_processes_memory_then_marks_inactive(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    processor = RecordingMemoryProcessor(
        ChatEndMemoryProcessingResult(
            processed_message_count=4,
            batch_count=2,
        )
    )

    result = ChatEndAction(database, processor).execute("chat")

    assert processor.calls == ["chat"]
    assert result.processed_message_count == 4
    assert result.batch_count == 2
    assert database.list_active_chats() == []
    assert [chat["id"] for chat in database.list_inactive_chats()] == ["chat"]


def test_chat_end_failure_keeps_chat_active(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    processor = RecordingMemoryProcessor(
        ChatEndMemoryProcessingResult(0, 0),
        error=RuntimeError("memory failed"),
    )

    with pytest.raises(RuntimeError, match="memory failed"):
        ChatEndAction(database, processor).execute("chat")

    assert [chat["id"] for chat in database.list_active_chats()] == ["chat"]
    assert database.list_inactive_chats() == []


def test_empty_chat_is_a_successful_noop_and_becomes_inactive(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    memory = ShortTermMemory(
        database=database,
        model=FakeModel(),
        memory_update_batch_size=2,
        structured_memory_updater=RecordingUpdater(),
    )

    result = ChatEndAction(database, memory).execute("chat")

    assert result.processed_message_count == 0
    assert result.batch_count == 0
    assert [chat["id"] for chat in database.list_inactive_chats()] == ["chat"]


def test_chat_end_is_idempotent_for_already_inactive_chat(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    processor = RecordingMemoryProcessor(ChatEndMemoryProcessingResult(0, 0))
    action = ChatEndAction(database, processor)

    first = action.execute("chat")
    second = action.execute("chat")

    assert first.inactive is True
    assert second.inactive is True
    assert processor.calls == ["chat", "chat"]
    assert [chat["id"] for chat in database.list_inactive_chats()] == ["chat"]


def test_process_all_for_chat_end_uses_bounded_batches(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    message_ids = [
        database.save_message(
            "chat",
            "user" if index % 2 == 0 else "assistant",
            f"message {index}",
        )
        for index in range(7)
    ]
    updater = RecordingUpdater()
    memory = ShortTermMemory(
        database=database,
        model=FakeModel(),
        memory_update_batch_size=3,
        structured_memory_updater=updater,
    )

    result = memory.process_all_for_chat_end("chat")

    assert updater.batch_message_ids == [
        message_ids[:3],
        message_ids[3:6],
        message_ids[6:],
    ]
    assert result.processed_message_count == 7
    assert result.batch_count == 3
    assert all(message.summarized for message in database.messages_for_chat("chat"))


def test_rejected_chat_end_batch_remains_pending_and_chat_stays_active(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    for index in range(5):
        database.save_message(
            "chat",
            "user" if index % 2 == 0 else "assistant",
            f"message {index}",
        )
    updater = RecordingUpdater(fail_on_call=2)
    memory = ShortTermMemory(
        database=database,
        model=FakeModel(),
        memory_update_batch_size=3,
        structured_memory_updater=updater,
    )

    with pytest.raises(ChatEndMemoryProcessingError, match="fake_failure"):
        ChatEndAction(database, memory).execute("chat")

    summarized = [
        message.summarized for message in database.messages_for_chat("chat")
    ]
    assert summarized == [True, True, True, False, False]
    assert [chat["id"] for chat in database.list_active_chats()] == ["chat"]


def test_assistant_only_batch_is_processed_as_valid_noop(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    message_id = database.save_message("chat", "assistant", "No durable memory.")
    updater = NoopUpdater("no_user_messages")
    memory = ShortTermMemory(
        database=database,
        model=FakeModel(),
        memory_update_batch_size=2,
        structured_memory_updater=updater,
    )

    result = memory.process_all_for_chat_end("chat")

    assert updater.batch_message_ids == [[message_id]]
    assert result == ChatEndMemoryProcessingResult(1, 1)
    assert database.messages_for_chat("chat")[0].summarized is True


def test_no_valid_memories_is_processed_as_valid_noop(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    message_id = database.save_message("chat", "user", "Temporary small talk.")
    updater = NoopUpdater("langmem_no_valid_memories")
    memory = ShortTermMemory(
        database=database,
        model=FakeModel(),
        memory_update_batch_size=2,
        structured_memory_updater=updater,
    )

    result = memory.process_all_for_chat_end("chat")

    assert updater.batch_message_ids == [[message_id]]
    assert result == ChatEndMemoryProcessingResult(1, 1)
    assert database.messages_for_chat("chat")[0].summarized is True


@pytest.mark.parametrize(
    "rejection_reason",
    ["no_user_messages", "langmem_no_valid_memories"],
)
def test_chat_end_marks_inactive_after_valid_noop(
    tmp_path: Path,
    rejection_reason: str,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    database.save_message("chat", "user", "Temporary message.")
    memory = ShortTermMemory(
        database=database,
        model=FakeModel(),
        memory_update_batch_size=2,
        structured_memory_updater=NoopUpdater(rejection_reason),
    )

    result = ChatEndAction(database, memory).execute("chat")

    assert result.processed_message_count == 1
    assert [chat["id"] for chat in database.list_inactive_chats()] == ["chat"]


def test_updater_exception_keeps_chat_active_and_message_pending(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    database.save_message("chat", "user", "Remember this.")
    memory = ShortTermMemory(
        database=database,
        model=FakeModel(),
        memory_update_batch_size=2,
        structured_memory_updater=RaisingUpdater(),
    )

    with pytest.raises(RuntimeError, match="model unavailable"):
        ChatEndAction(database, memory).execute("chat")

    assert [chat["id"] for chat in database.list_active_chats()] == ["chat"]
    assert database.messages_for_chat("chat")[0].summarized is False
