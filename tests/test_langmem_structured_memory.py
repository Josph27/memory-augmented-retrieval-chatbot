from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
        structured_memory_updater=LangMemStructuredMemoryState(manager=manager),
    )

    updated = memory.update_memory_if_needed("chat")

    assert updated is True
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


def test_empty_langmem_output_does_not_mark_messages_summarized(tmp_path: Path) -> None:
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
        structured_memory_updater=LangMemStructuredMemoryState(
            manager=FakeLangMemManager([]),
        ),
    )

    updated = memory.update_memory_if_needed("chat")

    assert updated is False
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
        structured_memory_updater=LangMemStructuredMemoryState(
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
    records = json.loads(db.chat_memory_state("chat") or "{}")["memories"]
    assert {record["id"] for record in records} == {
        "user_facts:name",
        "preferences:response_style",
    }


def test_processed_messages_marked_only_after_successful_storage(tmp_path: Path) -> None:
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
        structured_memory_updater=LangMemStructuredMemoryState(
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

    assert memory.update_memory_if_needed("chat") is True
    messages = db.messages_for_chat("chat")
    assert [message.summarized for message in messages] == [True, True, False]


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
