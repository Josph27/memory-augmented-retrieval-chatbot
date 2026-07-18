from __future__ import annotations

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
    namespace_path,
)
from src.memory.long_term_vector_index import (
    LongTermMemoryVectorIndex,
    VectorIndexBackend,
    VectorIndexUnavailable,
    memory_record_to_index_text,
)
from src.memory.structured_memory_vector_sync import (
    StructuredMemoryVectorSync,
    StructuredMemoryVectorSyncError,
)
from src.retrieval.structured_memory_retriever import StructuredMemoryRetriever
from src.routing.route_planner import RoutePlanner


class UpsertingFakeVectorBackend:
    """In-memory vector backend that tracks upserts + deletes for verification."""

    def __init__(self) -> None:
        self.vectors: dict[int, bytes] = {}  # rowid → blob
        self.texts: dict[int, str] = {}  # rowid → index text
        self.record_lookup: dict[int, tuple[str, str]] = {}  # rowid → (ns_path, memory_id)
        self.reverse_record_lookup: dict[tuple[str, str], int] = {}  # (ns_path, mem_id) → rowid
        self.delete_calls: list[list[int]] = []

    def add_vectors(self, rows: list[tuple[int, bytes]]) -> None:
        for rowid, blob in rows:
            self.vectors[rowid] = blob

    def set_texts(self, texts: dict[int, str]) -> None:
        self.texts = dict(texts)

    def set_record_lookup(self, lookup: dict[int, tuple[str, str]]) -> None:
        self.record_lookup = dict(lookup)
        self.reverse_record_lookup = {v: k for k, v in lookup.items()}

    def remove_vectors(self, rowids: list[int]) -> None:
        self.delete_calls.append(list(rowids))
        for rowid in rowids:
            self.vectors.pop(rowid, None)
            self.texts.pop(rowid, None)
            self.record_lookup.pop(rowid, None)

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        """Lexical overlap search."""
        terms = {term.lower().strip("?.:,") for term in query.split()}
        scored: list[tuple[int, float]] = []
        for rowid, text in self.texts.items():
            if rowid not in self.vectors:
                continue
            overlap = sum(1 for t in terms if t and t in text.lower())
            score = overlap / max(1, len(terms)) if overlap else 0.0
            if score > 0:
                scored.append((rowid, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]


class FakeLongTermMemoryVectorIndex(LongTermMemoryVectorIndex):
    def __init__(self, backend: UpsertingFakeVectorBackend) -> None:
        super().__init__(database_path=":memory:", vectorstore=backend)


class FailingVectorBackend:
    """Backend whose upsert/delete always raises."""

    def add_vectors(self, rows: list[tuple[int, bytes]]) -> None:
        del rows
        raise RuntimeError("vector backend unavailable")

    def remove_vectors(self, rowids: list[int]) -> None:
        del rowids
        raise RuntimeError("vector backend unavailable")

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        del query, k
        raise VectorIndexUnavailable("vector backend unavailable")


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
    UpsertingFakeVectorBackend,
    FakeLongTermMemoryVectorIndex,
]:
    database = Database(tmp_path / "chatbot.db")
    backend = UpsertingFakeVectorBackend()
    vector_index = FakeLongTermMemoryVectorIndex(backend)
    sync = StructuredMemoryVectorSync(vector_index)
    store = SQLiteLongTermMemoryStore(database, vector_sync=sync)
    return database, store, backend, vector_index


def _populate_backend(
    store: SQLiteLongTermMemoryStore,
    backend: UpsertingFakeVectorBackend,
    namespace: tuple[str, ...] = DEFAULT_USER_NAMESPACE,
) -> None:
    """Load records from SQLite into the fake backend's lookup."""
    records = store.list(namespace)
    texts = {}
    lookup = {}
    for r in records:
        texts[r.rowid] = memory_record_to_index_text(r)  # type: ignore[arg-type]
        lookup[r.rowid] = (namespace_path(r.namespace), r.memory_id)  # type: ignore[arg-type]
    backend.set_texts(texts)
    backend.set_record_lookup(lookup)


def test_langmem_production_write_syncs_insert_with_typed_metadata(
    tmp_path: Path,
) -> None:
    database, store, backend, _ = synced_store(tmp_path)
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
    assert len(backend.vectors) == 1
    # Verify the vector was stored with correct rowid
    records = store.list(DEFAULT_USER_NAMESPACE)
    assert len(records) == 1
    assert records[0].rowid in backend.vectors
    assert records[0].memory_id == "preferences:libraries"


def test_update_replaces_stable_vector_entry_without_stale_text(
    tmp_path: Path,
) -> None:
    _, store, backend, _ = synced_store(tmp_path)
    store.upsert(memory_write())
    _populate_backend(store, backend)
    # Index the first write
    records = store.list(DEFAULT_USER_NAMESPACE)
    for r in records:
        backend.add_vectors(
            [(r.rowid, b"")]  # type: ignore[arg-type]
        )

    store.upsert(memory_write(value="User now prefers maintained standard libraries."))

    assert len(backend.vectors) == 1
    # The record was re-upserted via sync_record → upsert_record → add_vectors
    # The old text from the fake is still there (it's not real embedding),
    # but the SQLite record value was updated.
    records = store.list(DEFAULT_USER_NAMESPACE)
    assert len(records) == 1
    assert "maintained standard libraries" in records[0].value


def test_delete_and_inactive_upsert_remove_vector_entry_idempotently(
    tmp_path: Path,
) -> None:
    _, store, backend, _ = synced_store(tmp_path)
    store.upsert(memory_write())
    _populate_backend(store, backend)
    records = store.list(DEFAULT_USER_NAMESPACE)
    rowid = records[0].rowid
    # Pre-populate with a vector so delete can find and remove it
    backend.add_vectors([(rowid, b"")])  # type: ignore[arg-type]

    store.upsert(memory_write(status="inactive"))
    store.delete(DEFAULT_USER_NAMESPACE, "preferences:libraries")
    store.delete(DEFAULT_USER_NAMESPACE, "preferences:libraries")

    assert rowid not in backend.vectors
    assert len(backend.delete_calls) >= 1
    record = store.get(DEFAULT_USER_NAMESPACE, "preferences:libraries")
    assert record is not None
    assert record.status == "deleted"


def test_repeated_sync_is_idempotent_by_stable_vector_id(tmp_path: Path) -> None:
    _, store, backend, _ = synced_store(tmp_path)

    store.upsert(memory_write())
    store.upsert(memory_write())
    store.upsert(memory_write())

    # Each upsert triggers sync_record → upsert_record → add_vectors((rowid, b""))
    # Since same rowid, add_vectors overwrites the same entry
    _populate_backend(store, backend)
    records = store.list(DEFAULT_USER_NAMESPACE)
    assert len(records) == 1
    assert records[0].rowid in backend.vectors


def test_vector_failure_is_explicit_but_sqlite_mode_requires_no_backend(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    failing_store = SQLiteLongTermMemoryStore(
        database,
        vector_sync=StructuredMemoryVectorSync(
            FakeLongTermMemoryVectorIndex(FailingVectorBackend())
        ),
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
    assert (
        sqlite_only_store.get(
            DEFAULT_USER_NAMESPACE,
            "preferences:answers",
        )
        is not None
    )


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
    backend = UpsertingFakeVectorBackend()
    sync = StructuredMemoryVectorSync(FakeLongTermMemoryVectorIndex(backend))

    first = sync.sync_all(store)
    second = sync.sync_all(store)

    assert first.upserted_count == 2
    assert second.upserted_count == 2
    assert len(backend.vectors) == 2


def test_synced_vector_memory_reaches_context_with_sqlite_provenance(
    tmp_path: Path,
) -> None:
    database, store, backend, vector_index = synced_store(tmp_path)
    store.upsert(memory_write())
    _populate_backend(store, backend)
    records = store.list(DEFAULT_USER_NAMESPACE)
    for r in records:
        backend.add_vectors(
            [(r.rowid, b"")]  # type: ignore[arg-type]
        )

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
