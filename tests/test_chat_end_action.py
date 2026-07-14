from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from src.actions.chat_end import ChatEndAction
from src.agents.context_manager_agent import ContextManagerAgent
from src.database import Database
from src.memory.previous_chat_gist import (
    DeterministicPreviousChatGistExtractor,
    PreviousChatGistGenerator,
)
from src.memory.short_term import (
    ChatEndMemoryProcessingError,
    ChatEndMemoryProcessingResult,
    ShortTermMemory,
)
from src.memory.structured_state import MemoryUpdateResult
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.route_planner import RoutePlanner


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


class RaisingGistExtractor:
    def summarize(self, messages):  # type: ignore[no-untyped-def]
        del messages
        raise RuntimeError("gist model unavailable")


def deterministic_gist_finalizer(
    database: Database,
    max_messages_per_gist: int = 80,
) -> PreviousChatGistGenerator:
    return PreviousChatGistGenerator(
        database=database,
        extractor=DeterministicPreviousChatGistExtractor(),
        max_messages_per_gist=max_messages_per_gist,
    )


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
        message_ids[:2],
        message_ids[2:4],
        message_ids[4:],
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

    # With the new partial-failure behaviour _apply_batch returns False
    # instead of raising when an LLM call fails.  process_all_for_chat_end
    # stops at the first failure and returns a partial result.
    result = ChatEndAction(database, memory).execute("chat")
    assert result.processed_message_count == 2
    assert result.batch_count == 1

    summarized = [message.summarized for message in database.messages_for_chat("chat")]
    # Only the first batch (messages 0-1) was consumed.
    # Messages 2-4 remain pending for the next consolidate / chat-end call.
    assert summarized == [True, True, False, False, False]


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


def test_chat_end_finalizes_pending_previous_chat_gist_segments(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    message_ids = [
        database.save_message("chat", "user", "Distinctive cobalt deployment fact."),
        database.save_message("chat", "assistant", "Recorded."),
        database.save_message("chat", "user", "Also retain the rollback checklist."),
        database.save_message("chat", "assistant", "Recorded too."),
    ]
    action = ChatEndAction(
        database,
        RecordingMemoryProcessor(ChatEndMemoryProcessingResult(0, 0)),
        gist_finalizer=deterministic_gist_finalizer(
            database,
            max_messages_per_gist=2,
        ),
    )

    result = action.execute("chat")

    gists = database.chat_gists_for_chat("chat", "previous_chat_gist")
    assert result.gist_count == 2
    assert result.gist_processed_message_count == 4
    assert result.gist_batch_count == 2
    assert [chat["id"] for chat in database.list_inactive_chats()] == ["chat"]
    assert len(gists) == 2
    assert sorted((gist.start_message_id, gist.end_message_id) for gist in gists) == [
        (message_ids[0], message_ids[1]),
        (message_ids[2], message_ids[3]),
    ]
    assert all(message.gist_processed for message in database.messages_for_chat("chat"))


def test_chat_end_assistant_only_gist_batch_is_valid_noop(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    database.save_message("chat", "assistant", "No user episode to summarize.")

    result = ChatEndAction(
        database,
        RecordingMemoryProcessor(ChatEndMemoryProcessingResult(0, 0)),
    ).execute("chat")

    assert result.gist_count == 0
    assert result.gist_processed_message_count == 1
    assert database.chat_gists_for_chat("chat", "previous_chat_gist") == []
    assert database.messages_for_chat("chat")[0].gist_processed is True
    assert [chat["id"] for chat in database.list_inactive_chats()] == ["chat"]


def test_gist_finalization_failure_keeps_chat_active_without_partial_gist(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    database.save_message("chat", "user", "Remember this episode.")
    finalizer = PreviousChatGistGenerator(
        database=database,
        extractor=RaisingGistExtractor(),
    )

    with pytest.raises(RuntimeError, match="gist model unavailable"):
        ChatEndAction(
            database,
            RecordingMemoryProcessor(ChatEndMemoryProcessingResult(0, 0)),
            gist_finalizer=finalizer,
        ).execute("chat")

    assert [chat["id"] for chat in database.list_active_chats()] == ["chat"]
    assert database.chat_gists_for_chat("chat", "previous_chat_gist") == []
    assert database.messages_for_chat("chat")[0].gist_processed is False


def test_repeated_chat_end_does_not_duplicate_previous_chat_gists(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    database.save_message("chat", "user", "Remember the cobalt release.")
    database.save_message("chat", "assistant", "Recorded.")
    action = ChatEndAction(
        database,
        RecordingMemoryProcessor(ChatEndMemoryProcessingResult(0, 0)),
        gist_finalizer=deterministic_gist_finalizer(database),
    )

    first = action.execute("chat")
    second = action.execute("chat")

    assert first.gist_count == 1
    assert second.gist_count == 0
    assert second.gist_processed_message_count == 0
    assert len(database.chat_gists_for_chat("chat", "previous_chat_gist")) == 1


def test_semantically_processed_messages_still_finalize_as_gist(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    message_ids = [
        database.save_message("chat", "user", "Keep the semantic and gist states separate."),
        database.save_message("chat", "assistant", "Understood."),
    ]
    database.mark_messages_summarized(message_ids)

    result = ChatEndAction(
        database,
        RecordingMemoryProcessor(ChatEndMemoryProcessingResult(0, 0)),
        gist_finalizer=deterministic_gist_finalizer(database),
    ).execute("chat")

    messages = database.messages_for_chat("chat")
    assert result.gist_count == 1
    assert all(message.summarized for message in messages)
    assert all(message.gist_processed for message in messages)


def test_finalized_previous_chat_gist_reaches_context_packet(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", "1")
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("ended-chat")
    first_id = database.save_message(
        "ended-chat",
        "user",
        "The distinctive release codename is cobalt.",
    )
    second_id = database.save_message("ended-chat", "assistant", "Recorded.")
    ChatEndAction(
        database,
        RecordingMemoryProcessor(ChatEndMemoryProcessingResult(0, 0)),
        gist_finalizer=deterministic_gist_finalizer(database),
    ).execute("ended-chat")
    database.create_chat("current-chat")
    query = "What did we discuss last time about the release codename?"
    route_plan = RoutePlanner().plan(query)
    candidates = RetrieverDispatcher(
        database,
        retrievers={
            "previous_chat_gist": PreviousChatGistRetriever(database),
        },
    ).retrieve("current-chat", route_plan)

    context = (
        ContextManagerAgent()
        .build_context_packet(
            system_prompt="Use available memory.",
            latest_user_message={"role": "user", "content": query},
            ranked_candidates=candidates,
            route_plan=route_plan,
        )
        .context_packet
    )

    raw_spans = [
        candidate for candidate in context.candidates if candidate.source == "raw_message_span"
    ]
    assert len(raw_spans) == 1
    assert "cobalt" in raw_spans[0].content
    assert raw_spans[0].source_message_ids == [first_id, second_id]
    parent_gist_id = raw_spans[0].metadata["parent_gist_id"]
    assert parent_gist_id is not None
    assert any(
        item["record_id"] == parent_gist_id and item["reason"] == "folded_into_raw_child"
        for item in context.metadata["dropped_candidates"]
    )
    assert any(
        "Raw Message Span:" in message["content"] and "cobalt" in message["content"]
        for message in context.model_messages
    )
