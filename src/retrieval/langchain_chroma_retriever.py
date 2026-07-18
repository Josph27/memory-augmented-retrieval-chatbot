from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from src.core.contracts import MemoryCandidate, SourcePlan
from src.documents.splitters import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE


# Queries that should retrieve the pre-computed document summary instead of raw chunks.
SUMMARY_QUERY_TERMS = frozenset(
    {
        "summarize",
        "summary",
        "overview",
        "contents",
        "what are the contents",
        "what is in the document",
        "what does the document contain",
        "what does it contain",
        "what's in the",
        "tell me about the document",
        "describe the document",
    }
)


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
        fetch_limit: int = 80,
        fallback_retriever: object | None = None,
        summary_getter: object | None = None,
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.default_top_k = default_top_k
        self.fetch_limit = fetch_limit
        self.fallback_retriever = fallback_retriever
        self.summary_getter = summary_getter
        self._vector_store = None

    @classmethod
    def from_env(
        cls,
        fallback_retriever: object | None = None,
        summary_getter: object | None = None,
    ) -> "LangChainChromaRetriever":
        """Build a LangChain-Chroma retriever from environment variables."""
        return cls(
            persist_dir=os.getenv("LANGCHAIN_CHROMA_PERSIST_DIR", DEFAULT_CHROMA_PERSIST_DIR),
            embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", DEFAULT_EMBEDDING_MODEL),
            chunk_size=int(os.getenv("LANGCHAIN_CHUNK_SIZE", str(DEFAULT_CHUNK_SIZE))),
            chunk_overlap=int(os.getenv("LANGCHAIN_CHUNK_OVERLAP", str(DEFAULT_CHUNK_OVERLAP))),
            default_top_k=int(os.getenv("DOCUMENT_TOP_K", "40")),
            fetch_limit=int(os.getenv("DOCUMENT_RETRIEVAL_FETCH_LIMIT", "80")),
            fallback_retriever=fallback_retriever,
            summary_getter=summary_getter,
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
        """Retrieve document MemoryCandidates through LangChain-Chroma.

        Fetches DOCUMENT_RETRIEVAL_FETCH_LIMIT chunks from Chroma using
        embedding similarity. Lexical overlap scoring is handled by the
        downstream MemoryReranker. Neighbor chunk expansion is deferred
        until after reranking (see RetrieverDispatcher.expand_document_neighbors).

        For summary-like queries ("summarize", "contents", "overview"), returns
        the pre-computed document summary as a candidate when available.
        """
        del chat_id
        query = source_plan.query or ""
        allowed_ids = source_plan.filters.get("allowed_document_ids")

        # For summary-like queries, try the pre-computed document summary first.
        summary_candidate = _try_summary_candidate(
            query=query,
            allowed_ids=allowed_ids,
            summary_getter=self.summary_getter,
        )

        if allowed_ids is not None and not allowed_ids:
            return []
        try:
            if allowed_ids is None:
                documents_with_scores = self._similarity_search(
                    query=query,
                    limit=self.fetch_limit,
                )
            else:
                documents_with_scores = self._similarity_search(
                    query=query,
                    limit=self.fetch_limit,
                    allowed_document_ids=allowed_ids,
                )
            candidates = [
                langchain_document_to_memory_candidate(document, score)
                for document, score in documents_with_scores
                if allowed_ids is None
                or str(getattr(document, "metadata", {}).get("document_id"))
                in {str(value) for value in allowed_ids}
            ]
            # Lexical overlap scoring is handled by MemoryReranker
            # (deterministic lexical_overlap feature, weight 0.35).
            # No retriever-side hybrid rerank needed.
            # Neighbor expansion is deferred until after reranking -
            # see RetrieverDispatcher.expand_document_neighbors().
            if summary_candidate is not None:
                summary_candidate = MemoryCandidate(
                    source=summary_candidate.source,
                    content=summary_candidate.content,
                    score=summary_candidate.score,
                    record_id=summary_candidate.record_id,
                    chat_id=summary_candidate.chat_id,
                    source_message_ids=list(summary_candidate.source_message_ids),
                    metadata={
                        **summary_candidate.metadata,
                        "skip_rerank": True,
                    },
                )
                candidates.insert(0, summary_candidate)
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


def _try_summary_candidate(
    query: str,
    allowed_ids: list[str] | tuple[str, ...] | None,
    summary_getter: object | None,
) -> MemoryCandidate | None:
    """Return a pre-computed document summary candidate for summary-like queries.

    Checks if the query matches summary terms and retrieves the pre-computed
    document summary from the SQLite store via the summary_getter callable.
    """
    query_lower = query.lower().strip()
    if not any(term in query_lower for term in SUMMARY_QUERY_TERMS):
        return None
    if not allowed_ids or summary_getter is None:
        return None

    doc_id = str(allowed_ids[0])
    try:
        if hasattr(summary_getter, "document_summary"):
            summary_text = summary_getter.document_summary(doc_id)
        else:
            summary_text = summary_getter(doc_id)
    except Exception:
        return None

    if not summary_text or not str(summary_text).strip():
        return None

    return MemoryCandidate(
        source="document_memory",
        content=str(summary_text),
        score=0.95,
        record_id=f"{doc_id}:summary",
        metadata={
            "document_id": doc_id,
            "retrieval_mode": "pre_computed_summary",
            "retrieval_backend": "langchain_chroma",
            "status": "active",
        },
    )


def normalize_score(score: float | None) -> float | None:
    """Normalize Chroma/LangChain scores into higher-is-better when possible."""
    if score is None:
        return None
    numeric = float(score)
    if 0.0 <= numeric <= 1.0:
        return numeric
    return 1.0 / (1.0 + max(0.0, numeric))


def _expand_neighbors(
    candidates: list[MemoryCandidate],
    *,
    vectorstore: object,
    allowed_document_ids: list[str] | tuple[str, ...] | None = None,
) -> list[MemoryCandidate]:
    """Expand each candidate's content with ±1 neighboring chunks inline.

    Instead of creating separate low-score neighbor candidates, this merges
    the preceding and following chunk text into each candidate's content
    field.  The result is fewer, richer candidates — each one carries 3× the
    context of a raw chunk — which improves both reranker signal quality and
    LLM answer coherence.
    """
    del allowed_document_ids
    # Collect all needed neighbor IDs in one pass.
    # Each neighbor can be needed by multiple candidates (e.g. chunk 3 is the
    # right neighbor of chunk 2 AND the left neighbor of chunk 4).
    needed: dict[
        str, list[tuple[int, str, int]]
    ] = {}  # nid -> [(candidate_index, doc_id, neighbor_index), ...]
    for idx, candidate in enumerate(candidates):
        document_id = str(candidate.metadata.get("document_id") or "")
        chunk_index = candidate.metadata.get("chunk_index")
        if not document_id or not isinstance(chunk_index, int):
            continue
        for offset in (-1, 1):
            neighbor_index = chunk_index + offset
            if neighbor_index < 0:
                continue
            nid = f"{document_id}:{neighbor_index}"
            needed.setdefault(nid, []).append((idx, document_id, neighbor_index))

    if not needed:
        return candidates

    # Batch-fetch all neighbor chunks at once.
    try:
        results = vectorstore.get(ids=list(needed.keys()))
    except Exception:
        return candidates

    if not results or not results.get("documents"):
        return candidates

    # Build a lookup from record_id → text.
    neighbor_texts: dict[str, str] = {}
    for nid, doc in zip(results["ids"], results["documents"]):
        if doc:
            neighbor_texts[nid] = str(doc)

    if not neighbor_texts:
        return candidates

    # Merge neighbor text into each candidate's content inline.
    # Determine left vs right by comparing neighbor index to candidate's own chunk index.
    chunk_index_of: dict[int, int] = {}  # candidate_idx -> chunk_index
    for idx, c in enumerate(candidates):
        ci = c.metadata.get("chunk_index")
        if isinstance(ci, int):
            chunk_index_of[idx] = ci

    for nid, entries in needed.items():
        for cand_idx, doc_id, neighbor_index in entries:
            text = neighbor_texts.get(nid)
            if not text or cand_idx not in chunk_index_of:
                continue
            original_ci = chunk_index_of[cand_idx]
            is_left = neighbor_index < original_ci
            candidate = candidates[cand_idx]
            separator = "\n\n"
            merged_content = (
                text + separator + candidate.content
                if is_left
                else candidate.content + separator + text
            )
            candidates[cand_idx] = candidate.__class__(
                source=candidate.source,
                content=merged_content,
                score=candidate.score,
                record_id=candidate.record_id,
                chat_id=candidate.chat_id,
                source_message_ids=list(candidate.source_message_ids),
                metadata={
                    **candidate.metadata,
                    "sentence_window_expansion": True,
                    "neighbor_chunks_merged": 1
                    + candidate.metadata.get("neighbor_chunks_merged", 0),
                },
            )

    return candidates
