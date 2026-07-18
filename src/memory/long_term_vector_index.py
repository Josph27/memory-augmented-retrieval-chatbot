from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from src.memory.long_term_store import (
    LongTermMemoryRecord,
    LongTermMemoryStore,
    namespace_path,
)


DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
VEC_TABLE = "vec_memories"


class VectorIndexUnavailable(RuntimeError):
    """Raised when the vector backend (sqlite-vec) is unavailable."""


class VectorIndexBackend(Protocol):
    """Protocol for vector index backends (real sqlite-vec or test fake)."""

    def add_vectors(self, rows: list[tuple[int, bytes]]) -> None:
        """Insert or replace vectors keyed by rowid."""

    def remove_vectors(self, rowids: list[int]) -> None:
        """Remove vectors by rowid."""

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        """Return (rowid, score) results for a raw text query."""


@dataclass(frozen=True)
class LongTermMemoryIndexResult:
    """Result from indexing long-term memories into a semantic store."""

    indexed_count: int
    skipped_count: int = 0


@dataclass(frozen=True)
class LongTermMemorySyncReport:
    """Result from synchronizing SQLite source records into the vector index."""

    upserted_count: int
    deleted_count: int


@dataclass(frozen=True)
class LongTermMemorySearchResult:
    """One semantic search result for a long-term memory."""

    memory_id: str
    namespace: tuple[str, ...]
    score: float | None = None
    metadata: dict[str, Any] | None = None


class LongTermMemoryVectorIndex:
    """sqlite-vec semantic index for structured long-term memories."""

    def __init__(
        self,
        database_path: str | Path = "data/chatbot.db",
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
        db: sqlite3.Connection | None = None,
        vectorstore: VectorIndexBackend | None = None,
    ) -> None:
        self._database_path = str(database_path)
        self.embedding_model_name = embedding_model_name
        self._db = db
        self._vector_store = vectorstore
        self._embeddings_cache: Any = None

    @classmethod
    def from_env(cls) -> "LongTermMemoryVectorIndex":
        """Build the sqlite-vec long-term memory index from environment values."""
        return cls(
            database_path=os.getenv("DATABASE_PATH", "data/chatbot.db"),
            embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", DEFAULT_EMBEDDING_MODEL),
        )

    # ── public API ──────────────────────────────────────────────────────

    def index_records(
        self,
        records: list[LongTermMemoryRecord],
    ) -> LongTermMemoryIndexResult:
        """Index active long-term memory records into the vec0 table."""
        active_records = [r for r in records if r.status == "active"]
        if not active_records:
            return LongTermMemoryIndexResult(indexed_count=0, skipped_count=len(records))

        assert all(r.rowid is not None for r in active_records), (
            "All active records must have a rowid"
        )

        texts = [memory_record_to_index_text(r) for r in active_records]
        if self._vector_store is not None:
            # Test mode — skip real embedding, pass dummy blob
            rows = [(r.rowid, b"") for r in active_records]  # type: ignore[misc]
            self._vector_store.add_vectors(rows)
        else:
            embeddings = self._embeddings().embed_documents(texts)
            rows = []
            for record, embedding in zip(active_records, embeddings, strict=True):
                blob = np.array(embedding, dtype=np.float32).tobytes()
                rows.append((record.rowid, blob))  # type: ignore[arg-type]
            db = self._get_db()
            if db is not None:
                db.executemany(
                    f"INSERT OR REPLACE INTO {VEC_TABLE}(rowid, embedding) VALUES (?, ?)",
                    rows,
                )
                db.commit()

        return LongTermMemoryIndexResult(
            indexed_count=len(active_records),
            skipped_count=len(records) - len(active_records),
        )

    def upsert_record(self, record: LongTermMemoryRecord) -> None:
        """Upsert one active record or remove one inactive record by rowid."""
        if record.status != "active":
            self.delete_record(record.namespace, record.memory_id)
            return
        assert record.rowid is not None, "Record must have a rowid to upsert"
        if self._vector_store is not None:
            self._vector_store.add_vectors([(record.rowid, b"")])  # type: ignore[arg-type]
            return
        embedding = self._embeddings().embed_query(memory_record_to_index_text(record))
        blob = np.array(embedding, dtype=np.float32).tobytes()
        db = self._get_db()
        if db is not None:
            db.execute(
                f"INSERT OR REPLACE INTO {VEC_TABLE}(rowid, embedding) VALUES (?, ?)",
                [record.rowid, blob],
            )
            db.commit()

    def delete_record(
        self,
        namespace: tuple[str, ...],
        memory_id: str,
    ) -> None:
        """Idempotently remove one derived vector entry by rowid."""
        db = self._get_db()
        if db is None:
            # Test injection — look up rowid from reverse record_lookup
            if self._vector_store is not None:
                rev = getattr(
                    self._vector_store,
                    "reverse_record_lookup",
                    {},
                )
                target_rowid = rev.get((namespace_path(namespace), memory_id))
                if target_rowid is not None:
                    self._vector_store.remove_vectors([target_rowid])
            return
        row = db.execute(
            "SELECT id AS rowid FROM long_term_memories WHERE namespace_path = ? AND memory_id = ?",
            (namespace_path(namespace), memory_id),
        ).fetchone()
        if row is not None:
            db.execute(
                f"DELETE FROM {VEC_TABLE} WHERE rowid = ?",
                [row["rowid"]],
            )
            db.commit()

    def rebuild_from_store(
        self,
        store: LongTermMemoryStore,
        namespaces: list[tuple[str, ...]],
    ) -> LongTermMemoryIndexResult:
        """Index all active records from selected namespaces via INSERT OR REPLACE."""
        records: list[LongTermMemoryRecord] = []
        for namespace in namespaces:
            records.extend(store.list(namespace))
        return self.index_records(records)

    def search(self, query: str, limit: int = 10) -> list[LongTermMemorySearchResult]:
        """Search indexed memories semantically."""
        if not query.strip():
            return []
        results = self._similarity_search(query=query, limit=limit)
        if not results:
            return []

        # Batch lookup rowids → (namespace_path, memory_id)
        rowids = [rowid for rowid, _ in results]
        db = self._get_db()
        lookup: dict[int, tuple[str, str]] = {}
        if self._vector_store is not None:
            # Test injection — use record_lookup from fake backend
            lookup = getattr(self._vector_store, "record_lookup", {})
        elif db is not None and rowids:
            placeholders = ",".join("?" for _ in rowids)
            rows = db.execute(
                f"SELECT id AS rowid, namespace_path, memory_id FROM long_term_memories "
                f"WHERE id IN ({placeholders})",
                rowids,
            ).fetchall()
            for row in rows:
                lookup[row["rowid"]] = (row["namespace_path"], row["memory_id"])

        converted: list[LongTermMemorySearchResult] = []
        for rowid, score in results:
            ns_path, mem_id = lookup.get(rowid, ("", ""))
            if mem_id:
                converted.append(
                    LongTermMemorySearchResult(
                        memory_id=mem_id,
                        namespace=tuple(ns_path.split("::")) if ns_path else (),
                        score=score,
                        metadata={
                            "retrieval_backend": "long_term_memory_sqlite_vec",
                        },
                    )
                )
        return converted

    # ── internals ───────────────────────────────────────────────────────

    def _similarity_search(self, query: str, limit: int) -> list[tuple[int, float]]:
        """Return (rowid, similarity_score) for the top-k matches."""
        if self._vector_store is not None:
            # Test injection path — pass raw text to fake backend
            return self._vector_store.search(query, limit)

        # Production path — embed query then search vec0
        embedding = self._embeddings().embed_query(query)
        blob = np.array(embedding, dtype=np.float32).tobytes()
        db = self._get_db()
        if db is None:
            return []
        rows = db.execute(
            f"SELECT rowid, distance FROM {VEC_TABLE} "
            "WHERE embedding MATCH ? AND k = ? "
            "ORDER BY distance",
            [blob, limit],
        ).fetchall()
        # Cosine distance ∈ [0, 2] → similarity ∈ [0, 1]
        return [(r["rowid"], max(0.0, 1.0 - r["distance"] / 2.0)) for r in rows]

    def _get_db(self) -> sqlite3.Connection | None:
        """Return the sqlite-vec powered connection, creating the vec0 table if needed."""
        if self._vector_store is not None:
            return None
        if self._db is not None:
            self._ensure_vec_table(self._db)
            return self._db
        conn = sqlite3.connect(self._database_path)
        conn.enable_load_extension(True)
        import sqlite_vec

        sqlite_vec.load(conn)
        self._ensure_vec_table(conn)
        self._db = conn
        return conn

    def _ensure_vec_table(self, conn: sqlite3.Connection) -> None:
        """Create the vec0 virtual table if it doesn't exist."""
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {VEC_TABLE} "
            "USING vec0(embedding float[384] distance_metric=cosine)"
        )

    def _embeddings(self) -> Any:
        """Return a cached HuggingFace embedding model."""
        if self._embeddings_cache is not None:
            return self._embeddings_cache
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError as error:
            raise VectorIndexUnavailable(
                "langchain-huggingface is unavailable for long-term memory vectors."
            ) from error
        try:
            model = HuggingFaceEmbeddings(model_name=self.embedding_model_name)
        except Exception as error:
            raise VectorIndexUnavailable(
                f"Could not load embedding model {self.embedding_model_name!r}: {error}"
            ) from error
        self._embeddings_cache = model
        return model


def memory_record_to_index_text(record: LongTermMemoryRecord) -> str:
    """Return compact natural-language text for semantic memory indexing."""
    return f"Memory category: {record.category}. Key: {record.key}. Value: {record.value}"
