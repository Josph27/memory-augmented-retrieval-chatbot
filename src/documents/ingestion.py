from __future__ import annotations

from dataclasses import dataclass

from src.database import Database
from src.documents.splitters import (
    DEFAULT_MAX_CHARS,
    DEFAULT_TARGET_CHARS,
    ChunkingConfig,
    split_document_text,
    split_text_into_chunks as _split_text_into_chunks,
)


@dataclass(frozen=True)
class DocumentIngestionResult:
    """Result returned after storing a plain-text document."""

    document_id: int
    chunk_count: int


class DocumentIngestionService:
    """Store plain-text documents as local SQLite chunks."""

    def __init__(
        self,
        database: Database,
        target_chars: int = DEFAULT_TARGET_CHARS,
        max_chars: int = DEFAULT_MAX_CHARS,
        chunking_config: ChunkingConfig | None = None,
    ) -> None:
        self.database = database
        self.target_chars = target_chars
        self.max_chars = max_chars
        self.chunking_config = chunking_config or ChunkingConfig.from_env(
            target_chars=target_chars,
            max_chars=max_chars,
        )

    def ingest_text_document(
        self,
        title: str,
        text: str,
        source: str = "manual",
        metadata: dict | None = None,
    ) -> DocumentIngestionResult:
        """Split and store one plain-text document."""
        chunks = split_document_text(text=text, config=self.chunking_config)
        document_id = self.database.insert_document(
            title=title,
            source=source,
            metadata=metadata,
        )
        for index, chunk in enumerate(chunks):
            chunk_metadata = {
                "title": title,
                "source": source,
                **chunk.metadata,
            }
            self.database.insert_document_chunk(
                document_id=document_id,
                chunk_index=index,
                text=chunk.text,
                metadata=chunk_metadata,
            )
        return DocumentIngestionResult(
            document_id=document_id,
            chunk_count=len(chunks),
        )


def split_text_into_chunks(
    text: str,
    target_chars: int = DEFAULT_TARGET_CHARS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[str]:
    """Backward-compatible import path for the custom paragraph splitter."""
    return _split_text_into_chunks(text=text, target_chars=target_chars, max_chars=max_chars)
