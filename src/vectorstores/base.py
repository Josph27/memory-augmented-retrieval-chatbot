from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class VectorStoreUnavailableError(RuntimeError):
    """Raised when an optional vector store backend cannot be used."""


@dataclass(frozen=True)
class VectorSearchResult:
    """One vector search hit."""

    chunk_id: int
    score: float
    metadata: dict = field(default_factory=dict)


class VectorStore(Protocol):
    """Minimal vector store interface."""

    def upsert_chunk_embedding(
        self,
        chunk_id: int,
        embedding: list[float],
        embedding_model: str,
        metadata: dict | None = None,
    ) -> None:
        """Insert or replace a chunk embedding."""
        ...

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        embedding_model: str,
    ) -> list[VectorSearchResult]:
        """Return nearest chunks for the query embedding."""
        ...

    def has_embedding(self, chunk_id: int, embedding_model: str) -> bool:
        """Return whether a chunk has an embedding for a model."""
        ...
