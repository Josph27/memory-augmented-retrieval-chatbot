from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from src.core.contracts import SourcePlan
from src.database import Database
from src.memory.long_term_store import (
    DEFAULT_USER_NAMESPACE,
    LongTermMemoryWrite,
    SQLiteLongTermMemoryStore,
    category_namespace,
    namespace_path,
)
from src.memory.long_term_vector_index import (
    LongTermMemoryVectorIndex,
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
        super().__init__(vectorstore=backend)


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
    store = SQLiteLongTermMemoryStore(database, retrieval_mode="sqlite")
    records = store.list(category_namespace("user_preferences"))
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
    assert candidates[0].record_id == "user_preferences:libraries"
    assert "mature open-source libraries" in candidates[0].content
    assert candidates[0].metadata["retrieval_mode"] == "vector"
    assert candidates[0].metadata["vector_score"] is not None


def test_structured_memory_hybrid_retrieval_deduplicates_by_memory_id(
    tmp_path: Path,
) -> None:
    database = seeded_memory_database(tmp_path)
    vector_index, backend = indexed_memory_vector(database)
    store = SQLiteLongTermMemoryStore(database, retrieval_mode="sqlite")
    records = store.list(category_namespace("user_preferences"))
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
        candidate for candidate in candidates if candidate.record_id == "user_preferences:libraries"
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

    assert any(candidate.record_id == "user_preferences:libraries" for candidate in candidates)
    assert all(candidate.source == "structured_memory" for candidate in candidates)


def seeded_memory_database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "chatbot.db")
    store = SQLiteLongTermMemoryStore(database, retrieval_mode="sqlite")
    store.upsert(
        LongTermMemoryWrite(
            namespace=category_namespace("user_preferences"),
            memory_id="user_preferences:libraries",
            category="user_preferences",
            key="libraries",
            value="User prefers mature open-source libraries over custom infrastructure.",
            confidence=0.9,
            source_chat_id="chat-1",
            source_message_ids=[1],
        )
    )
    store.upsert(
        LongTermMemoryWrite(
            namespace=category_namespace("user_preferences"),
            memory_id="user_preferences:answers",
            category="user_preferences",
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
    store = SQLiteLongTermMemoryStore(database, retrieval_mode="sqlite")
    records = store.list(category_namespace("user_preferences"))
    # Set texts and record_lookup with rowids
    backend.set_texts({r.rowid: memory_record_to_index_text(r) for r in records})
    backend.record_lookup = {r.rowid: (namespace_path(r.namespace), r.memory_id) for r in records}
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


class DeterministicNativeEmbeddings:
    """Known 384-dimensional vectors exercise native vec0; no model/cache access."""

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * 384
        vector[2] = 0.1
        if "ALPHA_NATIVE" in text:
            vector[0] = 1.0
        elif "BETA_NATIVE" in text:
            vector[1] = 1.0
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class NativeTestVectorIndex(LongTermMemoryVectorIndex):
    def _embeddings(self):
        return DeterministicNativeEmbeddings()


@pytest.mark.parametrize("operation", ["separate", "update", "delete"])
def test_native_sqlite_vec_separates_database_roots_and_filters_namespaces(
    tmp_path: Path, operation: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("sqlite_vec", reason="Native sqlite-vec extension package unavailable")
    namespace = category_namespace("user_preferences")
    excluded_namespace = ("private", "different-scope")
    identifier = "user_preferences:marker"
    database_a, database_b = Database(tmp_path / "alpha.db"), Database(tmp_path / "beta.db")
    store_a = SQLiteLongTermMemoryStore(database_a, retrieval_mode="sqlite")
    store_b = SQLiteLongTermMemoryStore(database_b, retrieval_mode="sqlite")

    def write(store, scope, marker):
        store.upsert(
            LongTermMemoryWrite(
                namespace=scope,
                memory_id=identifier,
                category="user_preferences",
                key="marker",
                value=marker,
                source_chat_id="origin",
                source_message_ids=[7],
            )
        )

    write(store_a, namespace, "ALPHA_NATIVE selected memory")
    write(store_a, excluded_namespace, "ALPHA_NATIVE excluded namespace memory")
    write(store_b, namespace, "BETA_NATIVE separate database memory")
    index_a, index_b = (
        NativeTestVectorIndex(database=database_a),
        NativeTestVectorIndex(database=database_b),
    )
    assert index_a.rebuild_from_store(store_a, [namespace, excluded_namespace]).indexed_count == 2
    assert index_b.rebuild_from_store(store_b, [namespace]).indexed_count == 1
    first_a, first_b = store_a.get(namespace, identifier), store_b.get(namespace, identifier)
    assert first_a is not None and first_b is not None
    assert first_a.rowid == first_b.rowid  # Colliding row IDs must remain database-local.
    with index_a._vec_connect() as connection:
        definition = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='vec_memories'"
        ).fetchone()[0]
        assert "vec0" in definition and "384" in definition
        assert connection.execute("SELECT COUNT(*) FROM vec_memories").fetchone()[0] == 2
    assert {result.namespace for result in index_a.search("ALPHA_NATIVE", limit=10)} == {
        namespace,
        excluded_namespace,
    }

    def retrieve(database, index, query):
        return StructuredMemoryRetriever(database, mode="vector", vector_index=index).retrieve(
            "consumer", SourcePlan(source="structured_memory", query=query, limit=10)
        )

    alpha = retrieve(database_a, index_a, "ALPHA_NATIVE")
    beta = retrieve(database_b, index_b, "BETA_NATIVE")
    assert [(c.record_id, c.content) for c in alpha] == [
        (identifier, "ALPHA_NATIVE selected memory")
    ]
    assert [(c.record_id, c.content) for c in beta] == [
        (identifier, "BETA_NATIVE separate database memory")
    ]
    assert alpha[0].metadata["namespace"] == list(namespace)
    assert alpha[0].metadata["retrieval_mode"] == "vector"
    assert alpha[0].metadata["retrieval_backend"] == "long_term_memory_sqlite_vec"
    assert alpha[0].source_message_ids == [7]
    assert all(c.metadata["vector_score"] is not None for c in [*alpha, *beta])

    # Independent parameter cases preserve separation/delete protection if update fails.
    if operation == "update":

        def vector_rows():
            with index_a._vec_connect() as connection:
                return dict(
                    connection.execute("SELECT rowid, embedding FROM vec_memories").fetchall()
                )

        original_vectors = vector_rows()
        original_score = next(
            result.score
            for result in index_a.search("ALPHA_NATIVE", limit=10)
            if result.namespace == namespace
        )
        write(store_a, namespace, "BETA_NATIVE updated memory")
        updated = store_a.get(namespace, identifier)
        assert updated is not None and updated.rowid == first_a.rowid
        index_a.upsert_record(updated)
        assert (
            retrieve(database_a, index_a, "BETA_NATIVE")[0].content == "BETA_NATIVE updated memory"
        )
        replaced_vectors = vector_rows()
        assert len(replaced_vectors) == 2
        assert replaced_vectors[first_a.rowid] != original_vectors[first_a.rowid]
        replacement_score = next(
            result.score
            for result in index_a.search("ALPHA_NATIVE", limit=10)
            if result.namespace == namespace
        )
        assert replacement_score < original_score
        excluded = store_a.get(excluded_namespace, identifier)
        assert excluded is not None
        for _repeat in range(2):
            assert index_a.index_records([updated, excluded, updated]).indexed_count == 3
            assert vector_rows() == replaced_vectors

        class InvalidDimensions:
            def embed_query(self, text):
                return [1.0]

            def embed_documents(self, texts):
                # First insertion would change an existing vector; the second must fail.
                return [DeterministicNativeEmbeddings().embed_query("ALPHA_NATIVE"), [1.0]]

        monkeypatch.setattr(index_a, "_embeddings", lambda: InvalidDimensions())
        for replace in (
            lambda: index_a.upsert_record(updated),
            lambda: index_a.index_records([updated, excluded]),
        ):
            with pytest.raises(sqlite3.DatabaseError, match="(?i)dimension"):
                replace()
            assert vector_rows() == replaced_vectors, (
                "Failed replacement must restore deleted vectors"
            )
    elif operation == "delete":
        store_a.delete(namespace, identifier)
        index_a.delete_record(namespace, identifier)
        assert retrieve(database_a, index_a, "ALPHA_NATIVE") == []
        assert {result.namespace for result in index_a.search("ALPHA_NATIVE", limit=10)} == {
            excluded_namespace
        }
    assert (
        retrieve(database_b, index_b, "BETA_NATIVE")[0].content
        == "BETA_NATIVE separate database memory"
    )
