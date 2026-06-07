from __future__ import annotations

from dataclasses import dataclass, field

from src.vectorstores.base import VectorSearchResult
from src.vectorstores.math import cosine_similarity


@dataclass
class StoredVector:
    """In-memory vector record."""

    embedding: list[float]
    embedding_model: str
    metadata: dict = field(default_factory=dict)


class InMemoryVectorStore:
    """Deterministic vector store for tests and local experiments."""

    def __init__(self) -> None:
        self.vectors: dict[int, StoredVector] = {}

    def upsert_chunk_embedding(
        self,
        chunk_id: int,
        embedding: list[float],
        embedding_model: str,
        metadata: dict | None = None,
    ) -> None:
        self.vectors[chunk_id] = StoredVector(
            embedding=embedding,
            embedding_model=embedding_model,
            metadata=metadata or {},
        )

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        embedding_model: str,
    ) -> list[VectorSearchResult]:
        results = [
            VectorSearchResult(
                chunk_id=chunk_id,
                score=cosine_similarity(query_embedding, stored.embedding),
                metadata=stored.metadata,
            )
            for chunk_id, stored in self.vectors.items()
            if stored.embedding_model == embedding_model
        ]
        return sorted(results, key=lambda result: result.score, reverse=True)[:top_k]

    def has_embedding(self, chunk_id: int, embedding_model: str) -> bool:
        stored = self.vectors.get(chunk_id)
        return stored is not None and stored.embedding_model == embedding_model
