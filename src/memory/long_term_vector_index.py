from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.memory.long_term_store import (
    LongTermMemoryRecord,
    LongTermMemoryStore,
    namespace_path,
)
from src.retrieval.langchain_chroma_retriever import (
    DEFAULT_CHROMA_PERSIST_DIR,
    DEFAULT_EMBEDDING_MODEL,
    LangChainChromaUnavailable,
    normalize_score,
)


DEFAULT_LONG_TERM_MEMORY_COLLECTION = "long_term_memory"


@dataclass(frozen=True)
class LongTermMemoryIndexResult:
    """Result from indexing long-term memories into a semantic store."""

    indexed_count: int
    skipped_count: int = 0


@dataclass(frozen=True)
class LongTermMemorySearchResult:
    """One semantic search result for a long-term memory."""

    memory_id: str
    namespace: tuple[str, ...]
    score: float | None = None
    metadata: dict[str, Any] | None = None


class LongTermMemoryVectorIndex:
    """LangChain-Chroma semantic index for structured long-term memories."""

    def __init__(
        self,
        persist_dir: str | Path = DEFAULT_CHROMA_PERSIST_DIR,
        collection_name: str = DEFAULT_LONG_TERM_MEMORY_COLLECTION,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
        vectorstore: object | None = None,
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model_name
        self._vector_store = vectorstore

    @classmethod
    def from_env(cls) -> "LongTermMemoryVectorIndex":
        """Build the semantic long-term memory index from environment values."""
        return cls(
            persist_dir=os.getenv(
                "LONG_TERM_MEMORY_CHROMA_PERSIST_DIR",
                os.getenv("LANGCHAIN_CHROMA_PERSIST_DIR", DEFAULT_CHROMA_PERSIST_DIR),
            ),
            collection_name=os.getenv(
                "LONG_TERM_MEMORY_COLLECTION",
                DEFAULT_LONG_TERM_MEMORY_COLLECTION,
            ),
            embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", DEFAULT_EMBEDDING_MODEL),
        )

    def index_records(
        self,
        records: list[LongTermMemoryRecord],
    ) -> LongTermMemoryIndexResult:
        """Index active long-term memory records into Chroma."""
        active_records = [record for record in records if record.status == "active"]
        if not active_records:
            return LongTermMemoryIndexResult(indexed_count=0, skipped_count=len(records))

        document_class = self._document_class()
        documents = [
            document_class(
                page_content=memory_record_to_index_text(record),
                metadata=memory_record_to_index_metadata(record),
            )
            for record in active_records
        ]
        ids = [memory_record_vector_id(record) for record in active_records]
        self._vectorstore().add_documents(documents, ids=ids)
        return LongTermMemoryIndexResult(
            indexed_count=len(active_records),
            skipped_count=len(records) - len(active_records),
        )

    def rebuild_from_store(
        self,
        store: LongTermMemoryStore,
        namespaces: list[tuple[str, ...]],
    ) -> LongTermMemoryIndexResult:
        """Index all active records from the selected namespaces."""
        records: list[LongTermMemoryRecord] = []
        for namespace in namespaces:
            records.extend(store.list(namespace))
        return self.index_records(records)

    def search(self, query: str, limit: int = 10) -> list[LongTermMemorySearchResult]:
        """Search indexed memories semantically."""
        if not query.strip():
            return []
        results = self._similarity_search(query=query, limit=limit)
        converted = []
        for document, score in results:
            result = document_to_search_result(document, score)
            if result is not None:
                converted.append(result)
        return converted

    def _similarity_search(self, query: str, limit: int):
        vectorstore = self._vectorstore()
        if hasattr(vectorstore, "similarity_search_with_score"):
            return vectorstore.similarity_search_with_score(query, k=limit)
        if hasattr(vectorstore, "similarity_search_with_relevance_scores"):
            return vectorstore.similarity_search_with_relevance_scores(query, k=limit)
        return [(document, None) for document in vectorstore.similarity_search(query, k=limit)]

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
            msg = "langchain-huggingface is unavailable for long-term memory vectors."
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
            msg = "langchain-chroma/chromadb is unavailable for long-term memory vectors."
            raise LangChainChromaUnavailable(msg) from error
        return Chroma

    @staticmethod
    def _document_class():
        try:
            from langchain_core.documents import Document
        except ImportError as error:
            msg = "langchain-core is unavailable for long-term memory vectors."
            raise LangChainChromaUnavailable(msg) from error
        return Document


def memory_record_to_index_text(record: LongTermMemoryRecord) -> str:
    """Return compact natural-language text for semantic memory indexing."""
    chunk_size = _lt_mem_chunk_size()
    value = record.value
    if len(value) > chunk_size:
        value = value[:chunk_size]
    return f"Memory category: {record.category}. Key: {record.key}. Value: {value}"


def _lt_mem_chunk_size() -> int:
    """Return the lt_mem_embedding_chunk_size from env, default 256."""
    return int(os.getenv("LT_MEM_EMBEDDING_CHUNK_SIZE", "256"))


def memory_record_to_index_metadata(record: LongTermMemoryRecord) -> dict[str, Any]:
    """Return vector metadata for a long-term memory record."""
    return {
        "memory_id": record.memory_id,
        "namespace": namespace_path(record.namespace),
        "category": record.category,
        "memory_type": record.category,
        "key": record.key,
        "source_chat_id": record.source_chat_id or "",
        "chat_id": record.source_chat_id or "",
        "source_message_ids": ",".join(str(item) for item in record.source_message_ids),
        "source_gist_id": record.source_gist_id if record.source_gist_id is not None else "",
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "retrieval_backend": "long_term_memory_chroma",
    }


def memory_record_vector_id(record: LongTermMemoryRecord) -> str:
    """Return stable vector id for one long-term memory record."""
    return f"{namespace_path(record.namespace)}::{record.memory_id}"

    def delete_by_memory_id(self, memory_id: str) -> None:
        """Remove a Chroma document by metadata filter.

        Per oracle F6: must be called BEFORE SQLite row deletion.
        """
        try:
            collection = self._get_or_create_collection()
            collection.delete(where={"memory_id": memory_id})
        except Exception:
            pass  # Chroma unavailable — non-critical

    def embed_and_index(self, memory: dict) -> str:
        """Embed memory text and upsert into Chroma.

        Per oracle F6: must be called AFTER SQLite insert.
        Per oracle F2: verifies embedding dimension before upsert.
        """
        import uuid

        text = f"{memory.get('key', '')} {memory.get('value', '')}"
        if not text.strip():
            return ""
        try:
            model = self._get_embedding_model()
            embedding = model.encode([text])[0]
            collection = self._get_or_create_collection()
            dim_expected = collection.metadata.get("dimension", 384)
            if len(embedding) != dim_expected:
                raise ValueError(
                    f"Embedding dimension mismatch: got {len(embedding)}, expected {dim_expected}"
                )
            doc_id = str(uuid.uuid4())
            collection.upsert(
                ids=[doc_id],
                embeddings=[embedding.tolist()],
                documents=[text],
                metadatas=[{"memory_id": memory.get("id", ""), "key": memory.get("key", "")}],
            )
            return doc_id
        except Exception:
            return ""  # Chroma unavailable — non-critical


def document_to_search_result(
    document: object,
    score: float | None = None,
) -> LongTermMemorySearchResult | None:
    """Convert one LangChain Document result into a memory search result."""
    metadata = dict(getattr(document, "metadata", {}) or {})
    memory_id = metadata.get("memory_id")
    namespace = metadata.get("namespace")
    if not isinstance(memory_id, str) or not isinstance(namespace, str):
        return None
    return LongTermMemorySearchResult(
        memory_id=memory_id,
        namespace=tuple(namespace.split("::")) if namespace else (),
        score=normalize_score(score),
        metadata=metadata,
    )
