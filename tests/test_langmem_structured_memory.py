from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from src.connection_guard import InferenceServerUnreachable

from src.database import Database
from src.memory.langmem_structured import (
    LangMemStructuredMemoryState,
    normalize_langmem_outputs,
)
from src.memory.short_term import ShortTermMemory
from src.memory.structured_state import MemoryUpdateResult
from src.retrieval.structured_memory_retriever import StructuredMemoryRetriever
from src.core.contracts import SourcePlan


class FakeModel:
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del messages, temperature
        return ""


@dataclass(frozen=True)
class FakeExtractedMemory:
    content: dict[str, Any]


class FakeLangMemManager:
    def __init__(self, output: list[Any]) -> None:
        self.output = output
        self.calls: list[dict[str, Any]] = []

    def invoke(self, input: dict[str, Any]) -> list[Any]:
        self.calls.append(input)
        return self.output


class RecordingGuard:
    """Per-updater synthetic connectivity dependency; never patches the production class."""

    def __init__(self, *, reject: bool = False) -> None:
        self.reject = reject
        self.calls = 0

    def check(self) -> None:
        self.calls += 1
        if self.reject:
            raise InferenceServerUnreachable(
                "http://offline.invalid/v1", "synthetic guard rejection"
            )


class RecordingMemoryState(LangMemStructuredMemoryState):
    def __init__(self, *, manager, connection_guard: RecordingGuard | None = None) -> None:
        self.guard = connection_guard or RecordingGuard()
        super().__init__(manager=manager, connection_guard=self.guard)
        self.results: list[MemoryUpdateResult] = []

    def update(self, existing_memory, messages):
        result = super().update(existing_memory, messages)
        self.results.append(result)
        return result


def assert_manager_extraction(memory: ShortTermMemory, *, accepted: bool) -> RecordingMemoryState:
    updater = memory.structured_memory
    assert isinstance(updater, RecordingMemoryState)
    assert updater.guard.calls == 1
    assert len(updater.manager.calls) == 1
    assert updater.manager.calls[0]["messages"]
    assert len(updater.results) == 1
    assert updater.results[0].accepted is accepted
    return updater


def test_langmem_outputs_map_to_current_memory_record_shape() -> None:
    records, drops = normalize_langmem_outputs(
        extracted=[
            FakeExtractedMemory(
                {
                    "category": "user_preferences",
                    "key": "response_style",
                    "value": "User prefers concise answers.",
                    "confidence": 0.8,
                    "source_message_ids": [12],
                }
            )
        ],
        allowed_source_ids={12},
        source_text_by_id={12: "I prefer concise answers."},
    )

    assert drops == []
    assert records == [
        {
            "id": "user_preferences:response_style",
            "category": "user_preferences",
            "key": "response_style",
            "value": "User prefers concise answers.",
            "source_message_ids": [12],
            "confidence": 0.8,
            "status": "active",
        }
    ]


def test_langmem_normalization_rejects_invalid_category_and_transcript() -> None:
    records, drops = normalize_langmem_outputs(
        extracted=[
            {
                "category": "random",
                "key": "bad",
                "value": "Unsupported category.",
                "source_message_ids": [1],
            },
            {
                "category": "user_facts",
                "key": "transcript",
                "value": "user: hello",
                "source_message_ids": [1],
            },
        ],
        allowed_source_ids={1},
        source_text_by_id={1: "hello"},
    )

    assert records == []
    assert len(drops) == 2
    assert drops[0]["drop_reason"] == "invalid_category"
    assert drops[1]["drop_reason"] == "transcript_text"


def test_langmem_normalization_attaches_source_ids_when_missing() -> None:
    records, drops = normalize_langmem_outputs(
        extracted=[
            {
                "category": "past_events",
                "key": "deployment",
                "value": "Deployed the feature on Tuesday.",
                "confidence": 0.7,
            }
        ],
        allowed_source_ids={1, 2},
        source_text_by_id={
            1: "We deployed the feature on Tuesday.",
            2: "This unrelated message discusses colors.",
        },
    )

    assert drops == []
    assert len(records) == 1
    # When LangMem provides no source_message_ids, all allowed_source_ids are used.
    assert records[0]["source_message_ids"] == [1, 2]
    assert records[0]["id"] == "past_events:deployment"


def test_short_term_memory_uses_langmem_backend_and_stores_memory(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    first_id = db.save_message("chat", "user", "I prefer concise answers.")
    db.save_message("chat", "assistant", "Noted.")
    db.save_message("chat", "user", "Use SQLite for the MVP.")
    db.save_message("chat", "assistant", "Understood.")

    manager = FakeLangMemManager(
        [
            {
                "category": "user_preferences",
                "key": "response_style",
                "value": "User prefers concise answers.",
                "confidence": 0.8,
                "source_message_ids": [first_id],
            },
            {
                "category": "past_events",
                "key": "deployment",
                "value": "Deployed SQLite for the MVP.",
                "confidence": 0.7,
            },
        ]
    )
    memory = ShortTermMemory(
        database=db,
        model=FakeModel(),
        raw_message_limit=1,
        memory_update_batch_size=3,
        memory_update_max_messages=4,
        structured_memory_updater=RecordingMemoryState(manager=manager),
    )

    updated = memory.update_memory_if_needed("chat")

    assert updated is True
    updater = assert_manager_extraction(memory, accepted=True)
    assert updater.results[0].rejection_reason is None
    stored = json.loads(db.chat_memory_state("chat") or "{}")
    records = stored["memories"]
    assert {record["category"] for record in records} == {"user_preferences", "past_events"}
    assert {record["status"] for record in records} == {"active"}
    assert manager.calls
    assert all(message.summarized for message in db.messages_for_chat("chat")[:2])

    candidates = StructuredMemoryRetriever(db).retrieve(
        chat_id="chat",
        source_plan=SourcePlan(source="structured_memory"),
    )
    assert {candidate.source for candidate in candidates} == {"structured_memory"}
    assert {candidate.metadata["category"] for candidate in candidates} == {
        "user_preferences",
        "past_events",
    }


def test_empty_langmem_output_does_not_mark_messages_summarized(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    db.save_message("chat", "user", "My name is Alex.")
    db.save_message("chat", "assistant", "Noted.")
    db.save_message("chat", "user", "I prefer concise answers.")

    memory = ShortTermMemory(
        database=db,
        model=FakeModel(),
        raw_message_limit=1,
        memory_update_batch_size=2,
        structured_memory_updater=RecordingMemoryState(
            manager=FakeLangMemManager([]),
        ),
    )

    updated = memory.update_memory_if_needed("chat")

    assert updated is False
    updater = assert_manager_extraction(memory, accepted=False)
    assert updater.results[0].rejection_reason == "langmem_no_valid_memories"
    assert "reason=langmem_no_valid_memories" in caplog.text
    assert memory.last_processed_message_ids == []
    assert db.chat_memory_state("chat") is not None
    assert all(not message.summarized for message in db.messages_for_chat("chat"))


def test_langmem_update_preserves_existing_memory_records(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    db.upsert_chat_memory_state(
        "chat",
        json.dumps(
            {
                "memories": [
                    {
                        "id": "user_facts:name",
                        "category": "user_facts",
                        "key": "name",
                        "value": "User's name is Alex.",
                        "source_message_ids": [1],
                        "confidence": 0.9,
                        "status": "active",
                    }
                ]
            }
        ),
    )
    db.save_message("chat", "user", "I prefer concise answers.")
    db.save_message("chat", "assistant", "Noted.")
    db.save_message("chat", "user", "latest")

    memory = ShortTermMemory(
        database=db,
        model=FakeModel(),
        raw_message_limit=1,
        memory_update_batch_size=2,
        structured_memory_updater=RecordingMemoryState(
            manager=FakeLangMemManager(
                [
                    {
                        "category": "user_preferences",
                        "key": "response_style",
                        "value": "User prefers concise answers.",
                    }
                ]
            ),
        ),
    )

    assert memory.update_memory_if_needed("chat") is True
    assert_manager_extraction(memory, accepted=True)
    records = json.loads(db.chat_memory_state("chat") or "{}")["memories"]
    assert {record["id"] for record in records} == {
        "user_facts:name",
        "user_preferences:response_style",
    }


def test_processed_messages_marked_only_after_successful_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    first_id = db.save_message("chat", "user", "The project uses Chainlit.")
    db.save_message("chat", "assistant", "Noted.")
    db.save_message("chat", "user", "latest")

    memory = ShortTermMemory(
        database=db,
        model=FakeModel(),
        raw_message_limit=1,
        memory_update_batch_size=2,
        structured_memory_updater=RecordingMemoryState(
            manager=FakeLangMemManager(
                [
                    {
                        "category": "user_facts",
                        "key": "framework",
                        "value": "The project uses Chainlit.",
                        "source_message_ids": [first_id],
                    }
                ]
            ),
        ),
    )

    mark_messages = db.mark_messages_summarized
    observed_storage_before_mark: list[bool] = []

    def verify_storage_then_mark(message_ids):
        stored = json.loads(db.chat_memory_state("chat") or "{}")
        assert {record["id"] for record in stored["memories"]} == {"user_facts:framework"}
        assert all(not message.summarized for message in db.messages_for_chat("chat"))
        observed_storage_before_mark.append(True)
        return mark_messages(message_ids)

    monkeypatch.setattr(db, "mark_messages_summarized", verify_storage_then_mark)
    assert memory.update_memory_if_needed("chat") is True
    assert_manager_extraction(memory, accepted=True)
    messages = db.messages_for_chat("chat")
    assert [message.summarized for message in messages] == [True, True, False]
    assert observed_storage_before_mark == [True]


def test_failed_langmem_update_does_not_mark_messages(tmp_path: Path) -> None:
    class FailingUpdater:
        def update(self, existing_memory, messages):  # type: ignore[no-untyped-def]
            del existing_memory, messages
            return MemoryUpdateResult(
                memory_state={"memories": []},
                accepted=False,
                rejection_reason="fake_failure",
            )

    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    db.save_message("chat", "user", "My name is Alex.")
    db.save_message("chat", "assistant", "Noted.")
    db.save_message("chat", "user", "latest")

    memory = ShortTermMemory(
        database=db,
        model=FakeModel(),
        raw_message_limit=1,
        memory_update_batch_size=2,
        structured_memory_updater=FailingUpdater(),
    )

    assert memory.update_memory_if_needed("chat") is False
    assert all(not message.summarized for message in db.messages_for_chat("chat"))


def test_guard_rejection_does_not_invoke_manager_or_consume_pending_messages(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    db.save_message("chat", "user", "My name is Alex.")
    db.save_message("chat", "assistant", "Noted.")
    db.save_message("chat", "user", "latest")
    manager = FakeLangMemManager([])
    updater = RecordingMemoryState(manager=manager, connection_guard=RecordingGuard(reject=True))
    memory = ShortTermMemory(
        database=db,
        model=FakeModel(),
        raw_message_limit=1,
        memory_update_batch_size=2,
        structured_memory_updater=updater,
    )

    assert memory.update_memory_if_needed("chat") is False
    assert updater.guard.calls == 1
    assert manager.calls == []
    assert len(updater.results) == 1
    assert updater.results[0].accepted is False
    assert updater.results[0].rejection_reason.startswith("langmem_update_failed:")
    assert "synthetic guard rejection" in updater.results[0].rejection_reason
    assert "synthetic guard rejection" in caplog.text
    assert all(not message.summarized for message in db.messages_for_chat("chat"))
    assert memory.last_processed_message_ids == []


def test_failed_sql_snapshot_storage_leaves_extracted_messages_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real snapshot write seam fails after extraction but before message flags commit."""
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat")
    first_id = db.save_message("chat", "user", "I prefer concise answers.")
    db.save_message("chat", "assistant", "Noted.")
    db.save_message("chat", "user", "latest")
    manager = FakeLangMemManager(
        [
            {
                "category": "user_preferences",
                "key": "style",
                "value": "User prefers concise answers.",
                "source_message_ids": [first_id],
            }
        ]
    )
    updater = RecordingMemoryState(manager=manager)
    memory = ShortTermMemory(
        database=db,
        model=FakeModel(),
        raw_message_limit=1,
        memory_update_batch_size=2,
        structured_memory_updater=updater,
    )
    real_write = db.upsert_chat_memory_state
    writes = []

    def fail_write(chat_id, state):
        writes.append((chat_id, state))
        raise RuntimeError("synthetic SQL snapshot write failure")

    monkeypatch.setattr(db, "upsert_chat_memory_state", fail_write)
    with pytest.raises(RuntimeError, match="synthetic SQL snapshot write failure"):
        memory.update_memory_if_needed("chat")

    assert_manager_extraction(memory, accepted=True)
    assert len(writes) == 1
    assert json.loads(writes[0][1])["memories"][0]["id"] == "user_preferences:style"
    assert db.chat_memory_state("chat") is None
    assert all(not message.summarized for message in db.messages_for_chat("chat"))
    assert memory.last_processed_message_ids == []
    # Removing the failed seam exposes the successful path, preserving the same pending batch.
    monkeypatch.setattr(db, "upsert_chat_memory_state", real_write)
    assert memory.update_memory_if_needed("chat") is True
    assert len(manager.calls) == 2
    assert [message.summarized for message in db.messages_for_chat("chat")] == [True, True, False]
