from __future__ import annotations

from pathlib import Path

from src.chat_service import ChatService
from src.actions.chat_end import ChatEndAction
from src.config import AppConfig
from src.database import Database
from src.memory.short_term import ShortTermMemory
from src.memory.structured_state import MemoryUpdateResult


class FakeModel:
    model_name = "google/gemma-4-31B-it"

    def chat(self, messages, temperature=None):  # type: ignore[no-untyped-def]
        del messages, temperature
        return "ok"


class WordCounter:
    model_name = "google/gemma-4-31B-it"
    backend = "word-counter"

    def count_text(self, text: str) -> int:
        return len([token for token in text.split() if token])

    def count_messages(self, messages, *, add_generation_prompt):  # type: ignore[no-untyped-def]
        del add_generation_prompt
        return sum(self.count_text(message.get("content", "")) for message in messages)

    def estimate_text(self, text: str) -> int:
        return self.count_text(text)

    def estimate_messages(self, messages):  # type: ignore[no-untyped-def]
        return self.count_messages(messages, add_generation_prompt=False)


class RecordingUpdater:
    def __init__(self) -> None:
        self.calls: list[list[int]] = []
        self.call_messages: list[list[tuple[int, str, str]]] = []

    def update(self, existing_memory, messages):  # type: ignore[no-untyped-def]
        self.calls.append([message.id for message in messages])
        self.call_messages.append(
            [(message.id, message.role, message.content) for message in messages]
        )
        user_ids = [message.id for message in messages if message.role == "user"]
        accepted = bool(user_ids)
        return MemoryUpdateResult(
            memory_state=existing_memory,
            accepted=accepted,
            rejection_reason=None if accepted else "no_user_messages",
        )


def build_memory(
    db: Database,
    updater: RecordingUpdater,
    *,
    trigger_tokens: int = 6,
    max_input_tokens: int = 20,
    max_messages: int = 8,
    protection_tokens: int = 0,
    replay_trigger_tokens: int = 10,
    replay_max_input_tokens: int = 20,
    replay_max_messages: int = 16,
    recent_messages_max_count: int = 32,
    raw_message_limit: int = 1,
) -> ShortTermMemory:
    return ShortTermMemory(
        database=db,
        model=FakeModel(),
        raw_message_limit=raw_message_limit,
        memory_update_batch_size=2,
        structured_memory_updater=updater,
        recent_messages_max_count=recent_messages_max_count,
        memory_update_trigger_tokens=trigger_tokens,
        memory_update_max_input_tokens=max_input_tokens,
        memory_update_max_messages=max_messages,
        memory_recent_protection_tokens=protection_tokens,
        memory_replay_trigger_tokens=replay_trigger_tokens,
        memory_replay_max_input_tokens=replay_max_input_tokens,
        memory_replay_max_messages=replay_max_messages,
        token_estimator=WordCounter(),
    )


def test_below_trigger_content_does_not_update_online(tmp_path: Path) -> None:
    db = Database(tmp_path / "chat.db")
    db.create_chat("chat")
    db.save_message("chat", "user", "one two")
    db.save_message("chat", "assistant", "three four")
    updater = RecordingUpdater()
    memory = build_memory(db, updater, trigger_tokens=10)

    assert memory.update_memory_if_needed("chat") is False
    assert updater.calls == []


def test_token_threshold_triggers_update_and_keeps_turn_together(tmp_path: Path) -> None:
    db = Database(tmp_path / "chat.db")
    db.create_chat("chat")
    first = db.save_message("chat", "user", "one two three four")
    second = db.save_message("chat", "assistant", "five six")
    db.save_message("chat", "user", "latest")
    updater = RecordingUpdater()
    memory = build_memory(
        db,
        updater,
        trigger_tokens=4,
        max_input_tokens=12,
        max_messages=4,
        protection_tokens=2,
    )

    assert memory.update_memory_if_needed("chat") is True
    assert updater.calls == [[first, second]]


def test_assistant_only_pending_does_not_invoke_online_updater(tmp_path: Path) -> None:
    db = Database(tmp_path / "chat.db")
    db.create_chat("chat")
    db.save_message("chat", "assistant", "only assistant tokens here")
    updater = RecordingUpdater()
    memory = build_memory(db, updater, trigger_tokens=1)

    assert memory.update_memory_if_needed("chat") is False
    assert updater.calls == []


def test_oversized_individual_message_is_preserved(tmp_path: Path) -> None:
    db = Database(tmp_path / "chat.db")
    db.create_chat("chat")
    message_id = db.save_message("chat", "user", "one two three four five six seven eight")
    updater = RecordingUpdater()
    memory = build_memory(db, updater, trigger_tokens=1, max_input_tokens=3, max_messages=2)

    assert memory.update_memory_if_needed("chat") is True
    assert updater.calls == [[message_id]]


def test_chat_end_flushes_below_trigger_remainder(tmp_path: Path) -> None:
    db = Database(tmp_path / "chat.db")
    db.create_chat("chat")
    db.save_message("chat", "user", "one two")
    db.save_message("chat", "assistant", "three four")
    updater = RecordingUpdater()
    memory = build_memory(db, updater, trigger_tokens=10)

    result = ChatEndAction(db, memory).execute("chat")

    assert result.processed_message_count == 2
    assert updater.calls == [[1, 2]]
    assert all(message.summarized for message in db.messages_for_chat("chat"))


def test_online_protected_suffix_is_token_based(tmp_path: Path) -> None:
    db = Database(tmp_path / "chat.db")
    db.create_chat("chat")
    first = db.save_message("chat", "user", "one two three")
    second = db.save_message("chat", "assistant", "four five")
    db.save_message("chat", "user", "latest six seven eight")
    updater = RecordingUpdater()
    memory = build_memory(
        db,
        updater,
        trigger_tokens=1,
        protection_tokens=5,
        max_input_tokens=12,
    )

    assert memory.update_memory_if_needed("chat") is True
    assert updater.calls == [[first, second]]


def test_protection_boundary_snaps_to_turn_boundary(tmp_path: Path) -> None:
    db = Database(tmp_path / "chat.db")
    db.create_chat("chat")
    first = db.save_message("chat", "user", "u1 one two three")
    second = db.save_message("chat", "assistant", "a1 four five")
    third = db.save_message("chat", "user", "u2 six seven eight")
    fourth = db.save_message("chat", "assistant", "a2 nine ten")
    updater = RecordingUpdater()
    memory = build_memory(
        db,
        updater,
        trigger_tokens=1,
        protection_tokens=4,
        max_input_tokens=32,
        max_messages=8,
    )

    assert memory.update_memory_if_needed("chat") is True
    assert updater.calls == [[first, second]]
    protected = [
        (message.id, message.role, message.content)
        for message in db.messages_for_chat("chat")
        if message.id not in memory.last_processed_message_ids
    ]
    assert protected == [
        (third, "user", "u2 six seven eight"),
        (fourth, "assistant", "a2 nine ten"),
    ]


def test_no_split_sequence_user_then_assistant_plus_next_user(tmp_path: Path) -> None:
    db = Database(tmp_path / "chat.db")
    db.create_chat("chat")
    first = db.save_message("chat", "user", "u1 one two")
    second = db.save_message("chat", "assistant", "a1 three four")
    third = db.save_message("chat", "user", "u2 five six")
    updater = RecordingUpdater()
    memory = build_memory(
        db,
        updater,
        trigger_tokens=1,
        protection_tokens=3,
        max_input_tokens=32,
        max_messages=8,
    )

    assert memory.update_memory_if_needed("chat") is True
    assert updater.calls != [[first], [second, third]]
    assert updater.calls == [[first, second]]


def test_consecutive_user_messages_make_progress_deterministically(tmp_path: Path) -> None:
    db = Database(tmp_path / "chat.db")
    db.create_chat("chat")
    first = db.save_message("chat", "user", "u1 one two")
    second = db.save_message("chat", "user", "u2 three four")
    updater = RecordingUpdater()
    memory = build_memory(
        db,
        updater,
        trigger_tokens=1,
        max_input_tokens=32,
        max_messages=8,
    )

    assert memory.update_memory_if_needed("chat") is True
    assert updater.calls == [[first, second]]


def test_assistant_only_prefix_does_not_loop_and_chat_end_flushes_progress(tmp_path: Path) -> None:
    db = Database(tmp_path / "chat.db")
    db.create_chat("chat")
    db.save_message("chat", "assistant", "a0 one two")
    db.save_message("chat", "assistant", "a1 three four")
    updater = RecordingUpdater()
    memory = build_memory(
        db,
        updater,
        trigger_tokens=1,
        max_input_tokens=32,
        max_messages=8,
    )

    assert memory.update_memory_if_needed("chat") is False
    result = ChatEndAction(db, memory).execute("chat")
    assert result.processed_message_count == 2
    assert updater.calls == [[1, 2]]


def test_live_deferred_post_answer_update_keeps_turns_intact(tmp_path: Path) -> None:
    db = Database(tmp_path / "chat.db")
    updater = RecordingUpdater()
    service = ChatService(
        database=db,
        model=FakeModel(),
        raw_message_limit=1,
        memory_update_batch_size=2,
        recent_messages_max_count=32,
        memory_update_trigger_tokens=4,
        memory_update_max_input_tokens=20,
        memory_update_max_messages=8,
        memory_recent_protection_tokens=4,
        memory_replay_trigger_tokens=10,
        memory_replay_max_input_tokens=20,
        memory_replay_max_messages=16,
    )
    service.memory.structured_memory = updater
    service.memory.token_estimator = WordCounter()
    chat_id = service.start_chat("chat")

    service.handle_user_turn(chat_id, "user one two", defer_post_answer_memory_update=True)
    assert updater.call_messages == []
    service.finalize_post_answer_memory_update(chat_id)
    assert updater.call_messages == []

    service.handle_user_turn(chat_id, "user three four", defer_post_answer_memory_update=True)
    assert updater.call_messages == []
    service.finalize_post_answer_memory_update(chat_id)

    assert updater.call_messages == [
        [
            (1, "user", "user one two"),
            (2, "assistant", "ok"),
        ]
    ]


def test_recent_message_pool_uses_recent_messages_max_count_not_raw_message_limit(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "chat.db")
    db.create_chat("chat")
    for index in range(5):
        db.save_message("chat", "user", f"message {index}")
    updater = RecordingUpdater()
    memory = build_memory(
        db,
        updater,
        recent_messages_max_count=3,
        raw_message_limit=1,
    )

    context = memory.build_context("chat")

    assert [message.content for message in context.raw_messages] == [
        "message 2",
        "message 3",
        "message 4",
    ]


def test_legacy_raw_message_limit_env_does_not_shrink_recent_retrieval(
    monkeypatch,
) -> None:
    monkeypatch.setenv("RAW_MESSAGE_LIMIT", "1")
    monkeypatch.delenv("RECENT_MESSAGES_MAX_COUNT", raising=False)

    config = AppConfig.from_env()

    assert config.raw_message_limit == 1
    assert config.recent_messages_max_count == 32
