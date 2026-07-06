from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from src.agents.context_manager_agent import ContextManagerAgent
from src.core.contracts import SourcePlan
from src.database import Database
from src.memory.langmem_structured import LangMemStructuredMemoryState
from src.memory.long_term_store import (
    DEFAULT_USER_NAMESPACE,
    LongTermMemoryWrite,
    SQLiteLongTermMemoryStore,
)
from src.memory.long_term_vector_index import LongTermMemoryVectorIndex
from src.memory.structured_memory_vector_sync import (
    StructuredMemoryVectorSync,
    StructuredMemoryVectorSyncError,
)
from src.retrieval.structured_memory_retriever import StructuredMemoryRetriever
from src.routing.route_planner import RoutePlanner


@dataclass
class FakeDocument:
    page_content: str
    metadata: dict


class UpsertingFakeVectorStore:
    """Small stable-ID vector store used without model downloads."""

    def __init__(self) -> None:
        self.documents: dict[str, FakeDocument] = {}
        self.delete_calls: list[list[str]] = []

    def add_documents(
        self,
        documents: list[FakeDocument],
        ids: list[str],
    ) -> None:
        for document_id, document in zip(ids, documents, strict=True):
            self.documents[document_id] = document

    def delete(self, ids: list[str]) -> None:
        self.delete_calls.append(list(ids))
        for document_id in ids:
            self.documents.pop(document_id, None)

    def similarity_search_with_score(
        self,
        query: str,
        k: int,
    ) -> list[tuple[FakeDocument, float]]:
        query_terms = {term.lower().strip("?.:,") for term in query.split()}
        scored = []
        for document in self.documents.values():
            overlap = sum(
                term in document.page_content.lower()
                for term in query_terms
                if term
            )
            scored.append((document, 1.0 / max(1, overlap)))
        return sorted(scored, key=lambda item: item[1])[:k]


class FakeLongTermMemoryVectorIndex(LongTermMemoryVectorIndex):
    def __init__(self, vectorstore: UpsertingFakeVectorStore) -> None:
        super().__init__(vectorstore=vectorstore)

    @staticmethod
    def _document_class():
        return FakeDocument


class UnavailableVectorIndex:
    def upsert_record(self, record) -> None:  # type: ignore[no-untyped-def]
        del record
        raise RuntimeError("vector backend unavailable")

    def delete_record(self, namespace, memory_id) -> None:  # type: ignore[no-untyped-def]
        del namespace, memory_id
        raise RuntimeError("vector backend unavailable")


class FakeLangMemManager:
    def __init__(self, output: list[dict[str, object]]) -> None:
        self.output = output

    def invoke(self, input: dict[str, object]) -> list[dict[str, object]]:
        del input
        return self.output


def memory_write(
    *,
    value: str = "User prefers mature open-source libraries.",
    status: str = "active",
) -> LongTermMemoryWrite:
    return LongTermMemoryWrite(
        namespace=DEFAULT_USER_NAMESPACE,
        memory_id="preferences:libraries",
        category="preferences",
        key="libraries",
        value=value,
        confidence=0.9,
        status=status,
        source_chat_id="chat-1",
        source_message_ids=[1],
        metadata={"backend": "test"},
    )


def synced_store(
    tmp_path: Path,
) -> tuple[
    Database,
    SQLiteLongTermMemoryStore,
    UpsertingFakeVectorStore,
    FakeLongTermMemoryVectorIndex,
]:
    database = Database(tmp_path / "chatbot.db")
    vectorstore = UpsertingFakeVectorStore()
    vector_index = FakeLongTermMemoryVectorIndex(vectorstore)
    sync = StructuredMemoryVectorSync(vector_index)
    store = SQLiteLongTermMemoryStore(database, vector_sync=sync)
    return database, store, vectorstore, vector_index


def test_langmem_production_write_syncs_insert_with_typed_metadata(
    tmp_path: Path,
) -> None:
    database, store, vectorstore, _ = synced_store(tmp_path)
    database.create_chat("chat-1")
    message_id = database.save_message(
        "chat-1",
        "user",
        "I prefer mature open-source libraries.",
    )
    state = LangMemStructuredMemoryState(
        manager=FakeLangMemManager(
            [
                {
                    "category": "preferences",
                    "key": "libraries",
                    "value": "User prefers mature open-source libraries.",
                    "source_message_ids": [message_id],
                }
            ]
        ),
        long_term_store=store,
    )

    result = state.update(
        existing_memory={},
        messages=database.messages_for_chat("chat-1"),
    )

    assert result.accepted is True
    assert len(vectorstore.documents) == 1
    document = next(iter(vectorstore.documents.values()))
    assert document.metadata["memory_id"] == "preferences:libraries"
    assert document.metadata["record_id"] == "preferences:libraries"
    assert document.metadata["source"] == "structured_memory"
    assert document.metadata["memory_type"] == "preferences"
    assert document.metadata["source_chat_id"] == "chat-1"
    assert document.metadata["source_message_ids"] == str(message_id)
    assert document.metadata["status"] == "active"


def test_update_replaces_stable_vector_entry_without_stale_text(
    tmp_path: Path,
) -> None:
    _, store, vectorstore, _ = synced_store(tmp_path)
    store.upsert(memory_write())

    store.upsert(
        memory_write(value="User now prefers maintained standard libraries.")
    )

    assert len(vectorstore.documents) == 1
    document = next(iter(vectorstore.documents.values()))
    assert "maintained standard libraries" in document.page_content
    assert "mature open-source libraries" not in document.page_content


def test_delete_and_inactive_upsert_remove_vector_entry_idempotently(
    tmp_path: Path,
) -> None:
    _, store, vectorstore, _ = synced_store(tmp_path)
    vector_id = "user::default::semantic_memory::preferences:libraries"
    store.upsert(memory_write())

    store.upsert(memory_write(status="inactive"))
    store.delete(DEFAULT_USER_NAMESPACE, "preferences:libraries")
    store.delete(DEFAULT_USER_NAMESPACE, "preferences:libraries")

    assert vector_id not in vectorstore.documents
    assert len(vectorstore.delete_calls) == 3
    record = store.get(DEFAULT_USER_NAMESPACE, "preferences:libraries")
    assert record is not None
    assert record.status == "deleted"


def test_repeated_sync_is_idempotent_by_stable_vector_id(tmp_path: Path) -> None:
    _, store, vectorstore, _ = synced_store(tmp_path)

    store.upsert(memory_write())
    store.upsert(memory_write())
    store.upsert(memory_write())

    assert list(vectorstore.documents) == [
        "user::default::semantic_memory::preferences:libraries"
    ]


def test_vector_failure_is_explicit_but_sqlite_mode_requires_no_backend(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    failing_store = SQLiteLongTermMemoryStore(
        database,
        vector_sync=StructuredMemoryVectorSync(UnavailableVectorIndex()),
    )

    with pytest.raises(
        StructuredMemoryVectorSyncError,
        match="SQLite write committed, but vector sync failed",
    ):
        failing_store.upsert(memory_write())

    committed = failing_store.get(
        DEFAULT_USER_NAMESPACE,
        "preferences:libraries",
    )
    assert committed is not None
    sqlite_only_store = SQLiteLongTermMemoryStore(
        database,
        retrieval_mode="sqlite",
    )
    sqlite_only_store.upsert(
        LongTermMemoryWrite(
            namespace=DEFAULT_USER_NAMESPACE,
            memory_id="preferences:answers",
            category="preferences",
            key="answers",
            value="User prefers concise answers.",
        )
    )
    assert sqlite_only_store.get(
        DEFAULT_USER_NAMESPACE,
        "preferences:answers",
    ) is not None


def test_backfill_repairs_missing_entries_without_duplicates(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    store = SQLiteLongTermMemoryStore(database, retrieval_mode="sqlite")
    store.upsert(memory_write())
    store.upsert(
        LongTermMemoryWrite(
            namespace=DEFAULT_USER_NAMESPACE,
            memory_id="preferences:answers",
            category="preferences",
            key="answers",
            value="User prefers concise answers.",
        )
    )
    vectorstore = UpsertingFakeVectorStore()
    sync = StructuredMemoryVectorSync(
        FakeLongTermMemoryVectorIndex(vectorstore)
    )

    first = sync.sync_all(store)
    second = sync.sync_all(store)

    assert first.upserted_count == 2
    assert second.upserted_count == 2
    assert len(vectorstore.documents) == 2
    assert all(
        document.metadata["source"] == "structured_memory"
        for document in vectorstore.documents.values()
    )


def test_synced_vector_memory_reaches_context_with_sqlite_provenance(
    tmp_path: Path,
) -> None:
    database, store, _, vector_index = synced_store(tmp_path)
    store.upsert(memory_write())
    query = "Which mature libraries do I prefer?"
    route_plan = RoutePlanner().plan(query)
    candidates = StructuredMemoryRetriever(
        database,
        mode="vector",
        vector_index=vector_index,
    ).retrieve(
        chat_id="chat-2",
        source_plan=SourcePlan(
            source="structured_memory",
            query=query,
            limit=3,
        ),
    )

    result = ContextManagerAgent().build_context_packet(
        system_prompt="Use structured memory.",
        latest_user_message={"role": "user", "content": query},
        ranked_candidates=candidates,
        route_plan=route_plan,
    )

    assert len(candidates) == 1
    assert candidates[0].record_id == "preferences:libraries"
    assert candidates[0].chat_id == "chat-1"
    assert candidates[0].source_message_ids == [1]
    assert candidates[0].metadata["retrieval_mode"] == "vector"
    assert any(
        candidate.record_id == "preferences:libraries"
        for candidate in result.context_packet.candidates
    )
    assert sum(result.context_budget.source_token_budgets.values()) <= int(
        result.context_budget.metadata["allocatable_tokens"]
    )


def test_sqlite_recall_remains_independent_of_vector_backend(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    store = SQLiteLongTermMemoryStore(database, retrieval_mode="sqlite")
    store.upsert(memory_write())

    candidates = StructuredMemoryRetriever(
        database,
        mode="sqlite",
    ).retrieve(
        "chat-2",
        SourcePlan(
            source="structured_memory",
            query="libraries",
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].record_id == "preferences:libraries"
    assert candidates[0].source == "structured_memory"
    assert candidates[0].metadata["namespace"] == list(DEFAULT_USER_NAMESPACE)
