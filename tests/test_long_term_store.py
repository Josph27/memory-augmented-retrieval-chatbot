from __future__ import annotations

import json
from pathlib import Path

from src.core.contracts import SourcePlan
from src.database import Database
from src.memory.langmem_structured import LangMemStructuredMemoryState
from src.memory.long_term_store import (
    DEFAULT_USER_NAMESPACE,
    LangGraphInMemoryLongTermMemoryStore,
    LongTermMemoryWrite,
    SQLiteLongTermMemoryStore,
    category_namespace,
)
from src.memory.short_term import ShortTermMemory
from src.retrieval.structured_memory_retriever import StructuredMemoryRetriever


class FakeModel:
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del messages, temperature
        return ""


class FakeLangMemManager:
    def __init__(self, output: list[dict[str, object]]) -> None:
        self.output = output

    def invoke(self, input: dict[str, object]) -> list[dict[str, object]]:
        del input
        return self.output


def test_sqlite_long_term_store_roundtrip_and_namespace_search(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    store = SQLiteLongTermMemoryStore(db)
    store.upsert(
        LongTermMemoryWrite(
            namespace=DEFAULT_USER_NAMESPACE,
            memory_id="preferences:response_style",
            category="user_preferences",
            key="response_style",
            value="User prefers concise answers.",
            confidence=0.9,
            source_chat_id="chat-a",
            source_message_ids=[1, 2],
        )
    )
    store.upsert(
        LongTermMemoryWrite(
            namespace=("project", "default", "semantic_memory"),
            memory_id="user_facts:framework",
            category="user_facts",
            key="framework",
            value="The project uses Chainlit.",
            confidence=0.8,
            source_chat_id="chat-a",
            source_message_ids=[3],
        )
    )

    user_record = store.get(DEFAULT_USER_NAMESPACE, "preferences:response_style")
    assert user_record is not None
    assert user_record.value == "User prefers concise answers."

    user_records = store.list(DEFAULT_USER_NAMESPACE)
    assert [record.memory_id for record in user_records] == ["preferences:response_style"]

    search_results = store.search(DEFAULT_USER_NAMESPACE, query="concise", limit=10)
    assert [record.memory_id for record in search_results] == ["preferences:response_style"]

    namespaces = store.list_namespaces()
    assert DEFAULT_USER_NAMESPACE in namespaces
    assert ("project", "default", "semantic_memory") in namespaces
    assert category_namespace("user_facts", "chat-a") == ("memory", "user_facts")
    assert category_namespace("past_events", "chat-a") == ("memory", "past_events")


def test_langgraph_in_memory_store_adapter_roundtrip() -> None:
    store = LangGraphInMemoryLongTermMemoryStore()
    store.upsert(
        LongTermMemoryWrite(
            namespace=DEFAULT_USER_NAMESPACE,
            memory_id="preferences:response_style",
            category="user_preferences",
            key="response_style",
            value="User prefers concise answers.",
            confidence=0.9,
            source_chat_id="chat-a",
            source_message_ids=[1, 2],
        )
    )

    record = store.get(DEFAULT_USER_NAMESPACE, "preferences:response_style")
    assert record is not None
    assert record.value == "User prefers concise answers."
    assert store.list(DEFAULT_USER_NAMESPACE)
    assert store.search(DEFAULT_USER_NAMESPACE, query="concise")
    assert DEFAULT_USER_NAMESPACE in store.list_namespaces()


def test_cross_chat_structured_memory_is_visible_across_chats(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    store = SQLiteLongTermMemoryStore(db)
    db.create_chat("chat-a")
    db.create_chat("chat-b")
    first_id = db.save_message("chat-a", "user", "I prefer concise answers.")
    db.save_message("chat-a", "assistant", "Noted.")
    db.save_message("chat-a", "user", "latest")

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
                        "source_message_ids": [first_id],
                    }
                ]
            ),
            long_term_store=store,
        ),
    )
    assert memory.update_memory_if_needed("chat-a") is True

    candidates = StructuredMemoryRetriever(db).retrieve(
        chat_id="chat-b",
        source_plan=SourcePlan(source="structured_memory", query="concise"),
    )

    assert candidates
    assert candidates[0].source == "structured_memory"
    assert candidates[0].metadata["namespace"] == list(DEFAULT_USER_NAMESPACE)
    assert candidates[0].metadata["source_chat_id"] == "chat-a"
    assert candidates[0].content == "User prefers concise answers."
    assert candidates[0].source_message_ids == [first_id]


def test_chat_memory_state_compatibility_still_reads_legacy_blob(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat-a")
    db.upsert_chat_memory_state(
        "chat-a",
        json.dumps(
            {
                "memories": [
                    {
                        "id": "preferences:response_style",
                        "category": "user_preferences",
                        "key": "response_style",
                        "value": "User prefers concise answers.",
                        "source_message_ids": [1],
                        "confidence": 0.9,
                        "status": "active",
                    }
                ]
            }
        ),
    )

    candidates = StructuredMemoryRetriever(db).retrieve(
        chat_id="chat-a",
        source_plan=SourcePlan(source="structured_memory"),
    )

    assert len(candidates) == 1
    assert candidates[0].source == "structured_memory"
    assert candidates[0].content == "User prefers concise answers."
