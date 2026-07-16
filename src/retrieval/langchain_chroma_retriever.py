from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from src.core.contracts import MemoryCandidate, SourcePlan
from src.documents.splitters import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE


DEFAULT_CHROMA_PERSIST_DIR = "data/chroma"
DEFAULT_COLLECTION_NAME = "document_memory"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class LangChainChromaUnavailable(RuntimeError):
    """Raised when optional LangChain-Chroma dependencies are unavailable."""


@dataclass(frozen=True)
class LangChainIndexResult:
    """Result returned after indexing text into Chroma."""

    document_id: str
    chunk_count: int


class LangChainChromaRetriever:
    """LangChain-Chroma document retriever that returns MemoryCandidate objects."""

    def __init__(
        self,
        persist_dir: str | Path = DEFAULT_CHROMA_PERSIST_DIR,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        default_top_k: int = 4,
        fallback_retriever: object | None = None,
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.default_top_k = default_top_k
        self.fallback_retriever = fallback_retriever
        self._vector_store = None

    @classmethod
    def from_env(
        cls,
        fallback_retriever: object | None = None,
    ) -> "LangChainChromaRetriever":
        """Build a LangChain-Chroma retriever from environment variables."""
        return cls(
            persist_dir=os.getenv("LANGCHAIN_CHROMA_PERSIST_DIR", DEFAULT_CHROMA_PERSIST_DIR),
            embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", DEFAULT_EMBEDDING_MODEL),
            chunk_size=int(os.getenv("LANGCHAIN_CHUNK_SIZE", str(DEFAULT_CHUNK_SIZE))),
            chunk_overlap=int(os.getenv("LANGCHAIN_CHUNK_OVERLAP", str(DEFAULT_CHUNK_OVERLAP))),
            default_top_k=int(os.getenv("DOCUMENT_TOP_K", "40")),
            fallback_retriever=fallback_retriever,
        )

    def index_text_document(
        self,
        title: str,
        text: str,
        source: str = "manual",
        metadata: dict | None = None,
    ) -> LangChainIndexResult:
        """Split and index one text document directly into Chroma."""
        document_id = str((metadata or {}).get("document_id") or uuid4())
        splitter = self._text_splitter()
        documents = splitter.create_documents(
            [text],
            metadatas=[
                {
                    "title": title,
                    "source": source,
                    "document_id": document_id,
                    **(metadata or {}),
                }
            ],
        )
        prepared_documents = []
        ids = []
        for chunk_index, document in enumerate(documents):
            document.page_content = document.page_content.strip()
            if not document.page_content:
                continue
            document.metadata.update(
                {
                    "title": title,
                    "source": source,
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "splitter_name": "langchain_recursive",
                    "retrieval_backend": "langchain_chroma",
                }
            )
            ids.append(f"{document_id}:{chunk_index}")
            prepared_documents.append(document)
        if prepared_documents:
            self._vectorstore().add_documents(prepared_documents, ids=ids)
        return LangChainIndexResult(document_id=document_id, chunk_count=len(prepared_documents))

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        """Retrieve document MemoryCandidates through LangChain-Chroma with hybrid scoring.

        Retrieves 2x the requested limit from Chroma, then blends semantic
        similarity with a lexical overlap score to boost exact keyword matches.
        After selecting the top-k, expands each result with its ±1 neighboring
        chunks (not counted toward the limit) to provide surrounding context.
        """
        del chat_id
        query = source_plan.query or ""
        limit = source_plan.limit or self.default_top_k
        fetch_limit = max(limit * 2, limit + 8)
        allowed_ids = source_plan.filters.get("allowed_document_ids")
        if allowed_ids is not None and not allowed_ids:
            return []
        try:
            if allowed_ids is None:
                documents_with_scores = self._similarity_search(
                    query=query,
                    limit=fetch_limit,
                )
            else:
                documents_with_scores = self._similarity_search(
                    query=query,
                    limit=fetch_limit,
                    allowed_document_ids=allowed_ids,
                )
            candidates = [
                langchain_document_to_memory_candidate(document, score)
                for document, score in documents_with_scores
                if allowed_ids is None
                or str(getattr(document, "metadata", {}).get("document_id"))
                in {str(value) for value in allowed_ids}
            ]
            if query.strip():
                candidates = _hybrid_rerank(candidates, query, limit)
            else:
                candidates = candidates[:limit]
            candidates = _expand_neighbors(
                candidates,
                vectorstore=self._vectorstore(),
                allowed_document_ids=allowed_ids,
            )
            return candidates
        except LangChainChromaUnavailable as error:
            print(f"langchain_chroma_unavailable reason={error}")
            if self.fallback_retriever is None:
                return []
            return self.fallback_retriever.retrieve(chat_id="", source_plan=source_plan)

    def _similarity_search(
        self,
        query: str,
        limit: int,
        allowed_document_ids: list[str] | tuple[str, ...] | None = None,
    ):
        vectorstore = self._vectorstore()
        filter_value = None
        if allowed_document_ids:
            values = [str(value) for value in allowed_document_ids]
            filter_value = (
                {"document_id": values[0]} if len(values) == 1 else {"document_id": {"$in": values}}
            )
        if hasattr(vectorstore, "similarity_search_with_score"):
            try:
                return vectorstore.similarity_search_with_score(
                    query,
                    k=limit,
                    filter=filter_value,
                )
            except TypeError:
                return vectorstore.similarity_search_with_score(query, k=limit)
        if hasattr(vectorstore, "similarity_search_with_relevance_scores"):
            try:
                return vectorstore.similarity_search_with_relevance_scores(
                    query,
                    k=limit,
                    filter=filter_value,
                )
            except TypeError:
                return vectorstore.similarity_search_with_relevance_scores(query, k=limit)
        try:
            documents = vectorstore.similarity_search(
                query,
                k=limit,
                filter=filter_value,
            )
        except TypeError:
            documents = vectorstore.similarity_search(query, k=limit)
        return [(document, None) for document in documents]

    def _vectorstore(self):
        if self._vector_store is not None:
            return self._vector_store
        chroma_class = self._chroma_class()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._vector_store = chroma_class(
            collection_name=self.collection_name,
            embedding_function=self._embeddings(),
            persist_directory=str(self.persist_dir),
        )
        return self._vector_store

    def _embeddings(self):
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError as error:
            msg = (
                "langchain-huggingface is unavailable. Install it to use "
                "DOCUMENT_RETRIEVAL_MODE=langchain_chroma."
            )
            raise LangChainChromaUnavailable(msg) from error
        try:
            return HuggingFaceEmbeddings(model_name=self.embedding_model_name)
        except Exception as error:
            msg = f"Could not load embedding model {self.embedding_model_name!r}: {error}"
            raise LangChainChromaUnavailable(msg) from error

    @staticmethod
    def _chroma_class():
        try:
            from langchain_chroma import Chroma
        except ImportError as error:
            msg = (
                "langchain-chroma/chromadb is unavailable. Install it to use "
                "DOCUMENT_RETRIEVAL_MODE=langchain_chroma."
            )
            raise LangChainChromaUnavailable(msg) from error
        return Chroma

    def _text_splitter(self):
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except ImportError as error:
            msg = "langchain-text-splitters is unavailable."
            raise LangChainChromaUnavailable(msg) from error
        return RecursiveCharacterTextSplitter(
            chunk_size=max(1, self.chunk_size),
            chunk_overlap=min(max(0, self.chunk_overlap), max(0, self.chunk_size - 1)),
            add_start_index=True,
        )

    @staticmethod
    def _document_class():
        try:
            from langchain_core.documents import Document
        except ImportError as error:
            msg = "langchain-core is unavailable."
            raise LangChainChromaUnavailable(msg) from error
        return Document


def langchain_document_to_memory_candidate(document, score: float | None = None) -> MemoryCandidate:
    """Convert one LangChain Document into the project's MemoryCandidate shape."""
    metadata = dict(getattr(document, "metadata", {}) or {})
    normalized_score = normalize_score(score)
    metadata.update(
        {
            "retrieval_backend": "langchain_chroma",
            "retrieval_mode": "langchain_chroma",
            "similarity_score": normalized_score,
            "status": "active",
        }
    )
    return MemoryCandidate(
        source="document_memory",
        content=str(getattr(document, "page_content", "")),
        score=normalized_score,
        record_id=metadata.get("chunk_id") or metadata.get("document_id"),
        source_message_ids=[],
        metadata=metadata,
    )


def normalize_score(score: float | None) -> float | None:
    """Normalize Chroma/LangChain scores into higher-is-better when possible."""
    if score is None:
        return None
    numeric = float(score)
    if 0.0 <= numeric <= 1.0:
        return numeric
    return 1.0 / (1.0 + max(0.0, numeric))


def _hybrid_rerank(
    candidates: list[MemoryCandidate],
    query: str,
    limit: int,
) -> list[MemoryCandidate]:
    """Blend semantic scores with lexical overlap for hybrid retrieval.

    Computes a simple BM25-like lexical overlap score for each candidate
    against the query and blends it with the existing semantic score.
    This helps queries like "problem 3" find chunks containing those exact
    strings even when the embedding model encodes numbers weakly.
    """
    import re

    def _tokenize(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    def _lexical_score(text: str, q_terms: set[str]) -> float:
        text_terms = _tokenize(text)
        overlap = len(q_terms & text_terms)
        return overlap / max(1, len(q_terms)) if q_terms else 0.0

    query_terms = _tokenize(query)
    if not query_terms:
        return candidates[:limit]

    # Blend: 70% semantic, 30% lexical
    SEMANTIC_WEIGHT = 0.7
    LEXICAL_WEIGHT = 0.3

    scored: list[tuple[float, MemoryCandidate]] = []
    for candidate in candidates:
        semantic = candidate.score if candidate.score is not None else 0.5
        lexical = _lexical_score(candidate.content, query_terms)
        blended = SEMANTIC_WEIGHT * semantic + LEXICAL_WEIGHT * lexical
        scored.append((blended, candidate))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in scored[:limit]]


def _expand_neighbors(
    candidates: list[MemoryCandidate],
    *,
    vectorstore: object,
    allowed_document_ids: list[str] | tuple[str, ...] | None = None,
) -> list[MemoryCandidate]:
    """Expand each candidate with its ±1 neighboring chunks for context.

    Neighbors are appended after the main candidates and marked with
    retrieval_mode='neighbor_expansion' so downstream consumers can
    distinguish them from directly retrieved chunks.
    """
    neighbor_ids: set[str] = set()
    seen_ids = {
        str(candidate.record_id) for candidate in candidates if candidate.record_id is not None
    }

    for candidate in candidates:
        metadata = candidate.metadata
        document_id = str(metadata.get("document_id") or "")
        chunk_index = metadata.get("chunk_index")
        if not document_id or not isinstance(chunk_index, int):
            continue

        for offset in (-1, 1):
            neighbor_index = chunk_index + offset
            if neighbor_index < 0:
                continue
            neighbor_record_id = f"{document_id}:{neighbor_index}"
            if neighbor_record_id in seen_ids or neighbor_record_id in neighbor_ids:
                continue
            neighbor_ids.add(neighbor_record_id)

            try:
                results = vectorstore.get(
                    ids=[neighbor_record_id],
                )
            except Exception:
                continue

            if not results or not results.get("documents"):
                continue
            doc_text = results["documents"][0]
            doc_meta = dict(results.get("metadatas", [{}])[0] or {})
            doc_meta.update(
                {
                    "retrieval_mode": "neighbor_expansion",
                    "neighbor_of_chunk": chunk_index,
                    "neighbor_offset": offset,
                    "chunk_index": neighbor_index,
                    "document_id": document_id,
                    "status": "active",
                }
            )
            candidates.append(
                MemoryCandidate(
                    source="document_memory",
                    content=str(doc_text),
                    score=0.3,  # Low confidence — not directly matched
                    record_id=neighbor_record_id,
                    metadata=doc_meta,
                )
            )

    return candidates
