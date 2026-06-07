from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, replace

from src.core.contracts import MemoryCandidate, SourcePlan
from src.database import Database, StoredDocumentChunk
from src.embeddings.base import EmbedderUnavailableError, TextEmbedder
from src.embeddings.sentence_transformer_embedder import (
    DEFAULT_SENTENCE_TRANSFORMER_MODEL,
    SentenceTransformerEmbedder,
)
from src.vectorstores.base import VectorSearchResult, VectorStore, VectorStoreUnavailableError
from src.vectorstores.sqlite_json_store import SQLiteJsonVectorStore
from src.vectorstores.sqlite_vec_store import SQLiteVecVectorStore


DEFAULT_DOCUMENT_TOP_K = 4
MIN_QUERY_TOKEN_LENGTH = 2
VALID_RETRIEVAL_MODES = {"keyword", "vector", "hybrid"}


@dataclass(frozen=True)
class ScoredChunk:
    """A document chunk with a lightweight keyword score."""

    chunk: StoredDocumentChunk
    score: float
    matched_terms: list[str]


class DocumentRetriever:
    """Document chunk retriever with keyword default and optional vector modes."""

    def __init__(
        self,
        database: Database,
        default_top_k: int = DEFAULT_DOCUMENT_TOP_K,
        retrieval_mode: str = "keyword",
        embedder: TextEmbedder | None = None,
        vector_store: VectorStore | None = None,
        embedding_model_name: str = DEFAULT_SENTENCE_TRANSFORMER_MODEL,
        vector_backend: str = "sqlite_json",
    ) -> None:
        self.database = database
        self.default_top_k = default_top_k
        self.retrieval_mode = normalized_retrieval_mode(retrieval_mode)
        self.embedder = embedder
        self.vector_store = vector_store
        self.embedding_model_name = embedding_model_name
        self.vector_backend = vector_backend

    @classmethod
    def from_env(cls, database: Database) -> "DocumentRetriever":
        """Build a retriever from environment configuration."""
        return cls(
            database=database,
            default_top_k=int(os.getenv("DOCUMENT_TOP_K", str(DEFAULT_DOCUMENT_TOP_K))),
            retrieval_mode=os.getenv("DOCUMENT_RETRIEVAL_MODE", "keyword"),
            embedding_model_name=os.getenv(
                "EMBEDDING_MODEL_NAME",
                DEFAULT_SENTENCE_TRANSFORMER_MODEL,
            ),
            vector_backend=os.getenv("VECTOR_BACKEND", "sqlite_json"),
        )

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        """Return top matching document chunks as memory candidates."""
        del chat_id
        query = source_plan.query or ""
        limit = source_plan.limit or self.default_top_k
        if self.retrieval_mode == "vector":
            return self.vector_candidates_or_keyword_fallback(query=query, limit=limit)
        if self.retrieval_mode == "hybrid":
            return self.hybrid_candidates_or_keyword_fallback(query=query, limit=limit)
        return self.keyword_candidates(query=query, limit=limit)

    def keyword_candidates(self, query: str, limit: int) -> list[MemoryCandidate]:
        """Retrieve chunks by deterministic keyword scoring."""
        query_terms = query_tokens(query)
        if not query_terms:
            return []

        scored = [
            scored_chunk
            for chunk in self.database.document_chunks()
            if (scored_chunk := score_chunk(chunk, query_terms)).score > 0
        ]
        scored.sort(key=lambda item: (item.score, -item.chunk.chunk_index), reverse=True)
        return [
            candidate_from_scored_chunk(item, retrieval_mode="keyword")
            for item in scored[:limit]
        ]

    def vector_candidates_or_keyword_fallback(
        self,
        query: str,
        limit: int,
    ) -> list[MemoryCandidate]:
        """Retrieve chunks by vector similarity, falling back to keyword on setup failure."""
        try:
            return self.vector_candidates(query=query, limit=limit)
        except (EmbedderUnavailableError, VectorStoreUnavailableError) as error:
            print(f"document_vector_retrieval_unavailable reason={error}")
            return self.keyword_candidates(query=query, limit=limit)

    def hybrid_candidates_or_keyword_fallback(
        self,
        query: str,
        limit: int,
    ) -> list[MemoryCandidate]:
        """Combine keyword and vector scores, falling back to keyword on setup failure."""
        try:
            return self.hybrid_candidates(query=query, limit=limit)
        except (EmbedderUnavailableError, VectorStoreUnavailableError) as error:
            print(f"document_hybrid_retrieval_unavailable reason={error}")
            return self.keyword_candidates(query=query, limit=limit)

    def vector_candidates(self, query: str, limit: int) -> list[MemoryCandidate]:
        """Retrieve chunks by vector similarity."""
        embedder = self.resolve_embedder()
        vector_store = self.resolve_vector_store()
        query_embedding = embedder.embed_text(query)
        results = vector_store.search(
            query_embedding=query_embedding,
            top_k=limit,
            embedding_model=embedder.model_name,
        )
        return candidates_from_vector_results(
            database=self.database,
            results=results,
            embedding_model=embedder.model_name,
            retrieval_mode="vector",
        )

    def hybrid_candidates(self, query: str, limit: int) -> list[MemoryCandidate]:
        """Combine keyword and vector scores with equal weights."""
        keyword = self.keyword_candidates(query=query, limit=limit * 2)
        vector = self.vector_candidates(query=query, limit=limit * 2)
        combined: dict[int, MemoryCandidate] = {}
        keyword_scores = {int(candidate.record_id): candidate.score or 0.0 for candidate in keyword}
        vector_scores = {int(candidate.record_id): candidate.score or 0.0 for candidate in vector}
        for candidate in (*keyword, *vector):
            if candidate.record_id is None:
                continue
            chunk_id = int(candidate.record_id)
            keyword_score = keyword_scores.get(chunk_id, 0.0)
            vector_score = vector_scores.get(chunk_id, 0.0)
            final_score = 0.5 * keyword_score + 0.5 * vector_score
            metadata = dict(candidate.metadata)
            metadata.update(
                {
                    "retrieval_mode": "hybrid",
                    "keyword_score": keyword_score,
                    "vector_score": vector_score,
                    "similarity_score": final_score,
                }
            )
            combined[chunk_id] = replace(
                candidate,
                score=final_score,
                metadata=metadata,
            )
        return sorted(
            combined.values(),
            key=lambda candidate: candidate.score or 0.0,
            reverse=True,
        )[:limit]

    def resolve_embedder(self) -> TextEmbedder:
        """Return configured embedder or build the optional real backend."""
        if self.embedder is not None:
            return self.embedder
        self.embedder = SentenceTransformerEmbedder(self.embedding_model_name)
        return self.embedder

    def resolve_vector_store(self) -> VectorStore:
        """Return configured vector store or build the selected backend."""
        if self.vector_store is not None:
            return self.vector_store
        if self.vector_backend == "sqlite_vec":
            self.vector_store = SQLiteVecVectorStore(self.database)
        else:
            self.vector_store = SQLiteJsonVectorStore(self.database)
        return self.vector_store


def normalized_retrieval_mode(mode: str) -> str:
    """Normalize document retrieval mode with keyword as safe default."""
    normalized = mode.lower().strip()
    return normalized if normalized in VALID_RETRIEVAL_MODES else "keyword"


def query_tokens(query: str) -> set[str]:
    """Tokenize a query for deterministic keyword retrieval."""
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9_:.+-]+", query.lower())
        if len(token) >= MIN_QUERY_TOKEN_LENGTH
    }


def score_chunk(chunk: StoredDocumentChunk, query_terms: set[str]) -> ScoredChunk:
    """Score one chunk by term overlap and substring matches."""
    chunk_text = chunk.text.lower()
    chunk_terms = set(re.findall(r"[a-zA-Z0-9_:.+-]+", chunk_text))
    matched_terms = sorted(
        term for term in query_terms if term in chunk_terms or term in chunk_text
    )
    if not matched_terms:
        return ScoredChunk(chunk=chunk, score=0.0, matched_terms=[])

    overlap_score = len(set(matched_terms) & chunk_terms) / max(1, len(query_terms))
    substring_bonus = sum(1 for term in matched_terms if term in chunk_text) * 0.05
    score = min(1.0, overlap_score + substring_bonus)
    return ScoredChunk(chunk=chunk, score=score, matched_terms=matched_terms)


def candidate_from_scored_chunk(
    scored: ScoredChunk,
    retrieval_mode: str,
) -> MemoryCandidate:
    """Convert a scored document chunk into a pipeline candidate."""
    metadata = metadata_for_chunk(scored.chunk)
    metadata.update(
        {
            "retrieval_mode": retrieval_mode,
            "similarity_score": scored.score,
            "keyword_score": scored.score,
            "matched_terms": scored.matched_terms,
            "status": "active",
        }
    )
    return MemoryCandidate(
        source="document_memory",
        content=scored.chunk.text,
        score=scored.score,
        record_id=scored.chunk.id,
        source_message_ids=[],
        metadata=metadata,
    )


def candidates_from_vector_results(
    database: Database,
    results: list[VectorSearchResult],
    embedding_model: str,
    retrieval_mode: str,
) -> list[MemoryCandidate]:
    """Convert vector search hits into document candidates."""
    chunks = database.document_chunks_by_ids([result.chunk_id for result in results])
    chunks_by_id = {chunk.id: chunk for chunk in chunks}
    candidates: list[MemoryCandidate] = []
    for result in results:
        chunk = chunks_by_id.get(result.chunk_id)
        if chunk is None:
            continue
        metadata = metadata_for_chunk(chunk)
        metadata.update(
            {
                "retrieval_mode": retrieval_mode,
                "embedding_model": embedding_model,
                "vector_score": result.score,
                "similarity_score": result.score,
                "status": "active",
            }
        )
        candidates.append(
            MemoryCandidate(
                source="document_memory",
                content=chunk.text,
                score=result.score,
                record_id=chunk.id,
                metadata=metadata,
            )
        )
    return candidates


def metadata_for_chunk(chunk: StoredDocumentChunk) -> dict:
    """Build common metadata for a document chunk."""
    metadata = parse_metadata_json(chunk.metadata_json)
    metadata.update(
        {
            "document_id": chunk.document_id,
            "chunk_id": chunk.id,
            "chunk_index": chunk.chunk_index,
            "title": chunk.document_title,
        }
    )
    return metadata


def parse_metadata_json(metadata_json: str) -> dict:
    """Parse chunk metadata defensively."""
    try:
        parsed = json.loads(metadata_json)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
