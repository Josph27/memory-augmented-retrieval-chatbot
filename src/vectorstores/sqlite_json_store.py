from __future__ import annotations

import json

from src.database import Database
from src.vectorstores.base import VectorSearchResult
from src.vectorstores.math import cosine_similarity


class SQLiteJsonVectorStore:
    """Fallback SQLite vector store using JSON vectors and Python cosine search.

    This is not a final vector DB. It keeps semantic retrieval testable without
    sqlite-vec and preserves a simple migration path to a native vector backend.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert_chunk_embedding(
        self,
        chunk_id: int,
        embedding: list[float],
        embedding_model: str,
        metadata: dict | None = None,
    ) -> None:
        self.database.upsert_chunk_embedding(
            chunk_id=chunk_id,
            embedding_model=embedding_model,
            vector=embedding,
            metadata=metadata,
        )

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        embedding_model: str,
    ) -> list[VectorSearchResult]:
        results: list[VectorSearchResult] = []
        for row in self.database.chunk_embeddings(embedding_model):
            vector = parse_vector(row["vector_json"])
            metadata = parse_metadata(row["metadata_json"])
            results.append(
                VectorSearchResult(
                    chunk_id=int(row["chunk_id"]),
                    score=cosine_similarity(query_embedding, vector),
                    metadata=metadata,
                )
            )
        return sorted(results, key=lambda result: result.score, reverse=True)[:top_k]

    def has_embedding(self, chunk_id: int, embedding_model: str) -> bool:
        return self.database.has_chunk_embedding(chunk_id, embedding_model)


def parse_vector(vector_json: str) -> list[float]:
    """Parse a vector JSON payload defensively."""
    try:
        parsed = json.loads(vector_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [float(value) for value in parsed if isinstance(value, int | float)]


def parse_metadata(metadata_json: str) -> dict:
    """Parse metadata JSON defensively."""
    try:
        parsed = json.loads(metadata_json)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
