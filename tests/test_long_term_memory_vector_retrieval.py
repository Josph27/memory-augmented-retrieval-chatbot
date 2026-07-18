from __future__ import annotations

from pathlib import Path

from src.core.contracts import SourcePlan
from src.database import Database
from src.memory.long_term_store import (
    DEFAULT_USER_NAMESPACE,
    LongTermMemoryWrite,
    SQLiteLongTermMemoryStore,
)
from src.memory.long_term_vector_index import (
    LongTermMemoryVectorIndex,
    VectorIndexBackend,
    VectorIndexUnavailable,
    memory_record_to_index_text,
)
from src.retrieval.structured_memory_retriever import StructuredMemoryRetriever


class FakeVectorBackend:
    """In-memory vector backend that stores text+blob pairs and does lexical search."""

    def __init__(self) -> None:
        self.vectors: dict[int, bytes] = {}  # rowid → embedding blob
        self.texts: dict[int, str] = {}  # rowid → index text (for search)
        self.record_lookup: dict[int, tuple[str, str]] = {}  # rowid → (ns_path, memory_id)
        self.removed: list[int] = []

    def add_vectors(self, rows: list[tuple[int, bytes]]) -> None:
        for rowid, blob in rows:
            self.vectors[rowid] = blob

    def set_texts(self, texts: dict[int, str]) -> None:
        """Store index texts for search simulation (not part of Protocol)."""
        self.texts = dict(texts)

    def remove_vectors(self, rowids: list[int]) -> None:
        for rowid in rowids:
            self.vectors.pop(rowid, None)
            self.texts.pop(rowid, None)
        self.removed.extend(rowids)

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        """Lexical overlap search — returns (rowid, score) pairs."""
        terms = {term.lower().strip("?.:,") for term in query.split()}
        scored: list[tuple[int, float]] = []
        for rowid, text in self.texts.items():
            if rowid not in self.vectors:
                continue
            content = text.lower()
            overlap = sum(1 for term in terms if term and term in content)
            score = overlap / max(1, len(terms)) if overlap else 0.0
            if score > 0:
                scored.append((rowid, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]


class FakeLongTermMemoryVectorIndex(LongTermMemoryVectorIndex):
    def __init__(self, backend: FakeVectorBackend) -> None:
        super().__init__(database_path=":memory:", vectorstore=backend)


class UnavailableVectorBackend:
    """Backend that always raises VectorIndexUnavailable."""

    def add_vectors(self, rows: list[tuple[int, bytes]]) -> None:
        del rows

    def remove_vectors(self, rowids: list[int]) -> None:
        del rowids

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        del query, k
        raise VectorIndexUnavailable("missing vector backend")


def test_memory_record_to_index_text_is_compact_and_semantic(tmp_path: Path) -> None:
    record = stored_memory_record(
        tmp_path=tmp_path,
        memory_id="preferences:libraries",
        key="libraries",
        value="User prefers mature open-source libraries.",
    )

    text = memory_record_to_index_text(record)

    assert "Memory category: preferences." in text
    assert "Key: libraries." in text
    assert "Value: User prefers mature open-source libraries." in text


def test_long_term_memory_vector_index_indexes_memory_records(tmp_path: Path) -> None:
    record = stored_memory_record(
        tmp_path=tmp_path,
        memory_id="preferences:libraries",
        key="libraries",
        value="User prefers mature open-source libraries.",
    )
    backend = FakeVectorBackend()
    vector_index = FakeLongTermMemoryVectorIndex(backend)
    # Store the index text so the fake can perform lexical search
    backend.set_texts({record.rowid: memory_record_to_index_text(record)})

    result = vector_index.index_records([record])

    assert result.indexed_count == 1
    assert result.skipped_count == 0
    assert len(backend.vectors) == 1
    assert record.rowid in backend.vectors


def test_structured_memory_vector_retrieval_returns_expected_memory(
    tmp_path: Path,
) -> None:
    database = seeded_memory_database(tmp_path)
    vector_index, backend = indexed_memory_vector(database)
    store = SQLiteLongTermMemoryStore(database)
    records = store.list(DEFAULT_USER_NAMESPACE)
    # Populate fake backend with index texts for search
    backend.set_texts({r.rowid: memory_record_to_index_text(r) for r in records})
    retriever = StructuredMemoryRetriever(
        database,
        mode="vector",
        vector_index=vector_index,
    )

    candidates = retriever.retrieve(
        chat_id="chat-2",
        source_plan=SourcePlan(
            source="structured_memory",
            query="Which stable libraries do I prefer?",
            limit=1,
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].source == "structured_memory"
    assert candidates[0].record_id == "preferences:libraries"
    assert "mature open-source libraries" in candidates[0].content
    assert candidates[0].metadata["retrieval_mode"] == "vector"
    assert candidates[0].metadata["vector_score"] is not None


def test_structured_memory_hybrid_retrieval_deduplicates_by_memory_id(
    tmp_path: Path,
) -> None:
    database = seeded_memory_database(tmp_path)
    vector_index, backend = indexed_memory_vector(database)
    store = SQLiteLongTermMemoryStore(database)
    records = store.list(DEFAULT_USER_NAMESPACE)
    backend.set_texts({r.rowid: memory_record_to_index_text(r) for r in records})
    retriever = StructuredMemoryRetriever(
        database,
        mode="hybrid",
        vector_index=vector_index,
    )

    candidates = retriever.retrieve(
        chat_id="chat-2",
        source_plan=SourcePlan(
            source="structured_memory",
            query="libraries",
            limit=10,
        ),
    )

    matching = [
        candidate for candidate in candidates if candidate.record_id == "preferences:libraries"
    ]
    assert len(matching) == 1
    assert "mature open-source libraries" in matching[0].content


def test_structured_memory_vector_retrieval_falls_back_to_sqlite(
    tmp_path: Path,
) -> None:
    database = seeded_memory_database(tmp_path)
    retriever = StructuredMemoryRetriever(
        database,
        mode="vector",
        vector_index=FakeLongTermMemoryVectorIndex(UnavailableVectorBackend()),
    )

    candidates = retriever.retrieve(
        chat_id="chat-2",
        source_plan=SourcePlan(
            source="structured_memory",
            query="libraries",
            limit=10,
        ),
    )

    assert any(candidate.record_id == "preferences:libraries" for candidate in candidates)
    assert all(candidate.source == "structured_memory" for candidate in candidates)


def seeded_memory_database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "chatbot.db")
    store = SQLiteLongTermMemoryStore(database)
    store.upsert(
        LongTermMemoryWrite(
            namespace=DEFAULT_USER_NAMESPACE,
            memory_id="preferences:libraries",
            category="preferences",
            key="libraries",
            value="User prefers mature open-source libraries over custom infrastructure.",
            confidence=0.9,
            source_chat_id="chat-1",
            source_message_ids=[1],
        )
    )
    store.upsert(
        LongTermMemoryWrite(
            namespace=DEFAULT_USER_NAMESPACE,
            memory_id="preferences:answers",
            category="preferences",
            key="answers",
            value="User prefers concise practical answers.",
            confidence=0.8,
            source_chat_id="chat-1",
            source_message_ids=[2],
        )
    )
    return database


def indexed_memory_vector(
    database: Database,
) -> tuple[FakeLongTermMemoryVectorIndex, FakeVectorBackend]:
    backend = FakeVectorBackend()
    vector_index = FakeLongTermMemoryVectorIndex(backend)
    store = SQLiteLongTermMemoryStore(database)
    records = store.list(DEFAULT_USER_NAMESPACE)
    # Set texts and record_lookup with rowids
    backend.set_texts({r.rowid: memory_record_to_index_text(r) for r in records})
    backend.record_lookup = {
        r.rowid: ("user::default::semantic_memory", r.memory_id) for r in records
    }
    vector_index.index_records(records)
    return vector_index, backend


def stored_memory_record(
    tmp_path: Path,
    memory_id: str,
    key: str,
    value: str,
):
    database = Database(tmp_path / "memory-vector-test.db")
    store = SQLiteLongTermMemoryStore(database)
    store.upsert(
        LongTermMemoryWrite(
            namespace=DEFAULT_USER_NAMESPACE,
            memory_id=memory_id,
            category="preferences",
            key=key,
            value=value,
            confidence=0.9,
            source_chat_id="chat-1",
            source_message_ids=[1],
        )
    )
    record = store.get(DEFAULT_USER_NAMESPACE, memory_id)
    assert record is not None
    return record
