from __future__ import annotations

from dataclasses import dataclass

from src.database import Database
from src.embeddings.base import TextEmbedder
from src.vectorstores.base import VectorStore


@dataclass(frozen=True)
class EmbeddingIndexResult:
    """Indexing counts for document chunks."""

    indexed: int
    skipped: int


class DocumentEmbeddingIndexer:
    """Index stored document chunks with an embedding backend."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def index_document_chunks(
        self,
        document_id: int,
        embedder: TextEmbedder,
        vector_store: VectorStore,
    ) -> EmbeddingIndexResult:
        """Embed chunks for one document, skipping existing model embeddings."""
        chunks = self.database.document_chunks_for_document(document_id)
        chunks_to_index = [
            chunk
            for chunk in chunks
            if not vector_store.has_embedding(chunk.id, embedder.model_name)
        ]
        skipped = len(chunks) - len(chunks_to_index)
        if not chunks_to_index:
            return EmbeddingIndexResult(indexed=0, skipped=skipped)

        embeddings = embedder.embed_texts([chunk.text for chunk in chunks_to_index])
        for chunk, embedding in zip(chunks_to_index, embeddings):
            vector_store.upsert_chunk_embedding(
                chunk_id=chunk.id,
                embedding=embedding,
                embedding_model=embedder.model_name,
                metadata={
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "title": chunk.document_title,
                    "dimension": len(embedding),
                },
            )
        return EmbeddingIndexResult(indexed=len(chunks_to_index), skipped=skipped)
