from __future__ import annotations

from src.database import Database
from src.vectorstores.base import VectorSearchResult, VectorStoreUnavailableError
from src.vectorstores.sqlite_json_store import SQLiteJsonVectorStore


class SQLiteVecVectorStore:
    """sqlite-vec backend placeholder with graceful fallback behavior.

    The project does not require sqlite-vec for normal tests. This class checks
    availability and raises a clear error if the native extension is not
    installed/loadable.
    """

    def __init__(self, database: Database) -> None:
        try:
            import sqlite_vec  # type: ignore[import-not-found]
        except Exception as error:
            msg = "sqlite-vec is not available. Use VECTOR_BACKEND=sqlite_json or keyword retrieval."
            raise VectorStoreUnavailableError(msg) from error

        del sqlite_vec
        self.fallback = SQLiteJsonVectorStore(database)

    def upsert_chunk_embedding(
        self,
        chunk_id: int,
        embedding: list[float],
        embedding_model: str,
        metadata: dict | None = None,
    ) -> None:
        # Native sqlite-vec virtual table wiring is future work; this keeps the
        # interface usable if the dependency is present without changing schema.
        self.fallback.upsert_chunk_embedding(chunk_id, embedding, embedding_model, metadata)

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        embedding_model: str,
    ) -> list[VectorSearchResult]:
        return self.fallback.search(query_embedding, top_k, embedding_model)

    def has_embedding(self, chunk_id: int, embedding_model: str) -> bool:
        return self.fallback.has_embedding(chunk_id, embedding_model)
