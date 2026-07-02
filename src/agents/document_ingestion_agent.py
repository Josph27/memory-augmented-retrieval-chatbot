from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.documents.loaders import (
    TextDocumentIndexer,
    index_loaded_document,
    load_document_file,
)
from src.retrieval.langchain_chroma_retriever import LangChainChromaRetriever


@dataclass(frozen=True)
class DocumentIngestionResult:
    """Structured result for document ingestion into document memory."""

    document_id: str
    file_name: str
    file_extension: str
    chunk_count: int
    indexed: bool
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentIngestionAgent:
    """Responsibility wrapper for loading and indexing local documents."""

    def __init__(
        self,
        indexer: TextDocumentIndexer | None = None,
    ) -> None:
        self.indexer = indexer

    def index_file(
        self,
        path: str | Path,
        display_name: str | None = None,
    ) -> DocumentIngestionResult:
        """Load a local file and index it through the configured document backend."""
        loaded = load_document_file(path, display_name=display_name)
        indexer = self.indexer or LangChainChromaRetriever.from_env()
        raw_result = index_loaded_document(loaded, indexer)

        document_id = result_value(raw_result, "document_id", "")
        chunk_count = int(result_value(raw_result, "chunk_count", 0) or 0)
        file_name = str(loaded.metadata.get("file_name", display_name or Path(path).name))
        file_extension = str(loaded.metadata.get("file_extension", Path(file_name).suffix.lower()))

        return DocumentIngestionResult(
            document_id=str(document_id),
            file_name=file_name,
            file_extension=file_extension,
            chunk_count=chunk_count,
            indexed=True,
            errors=[],
            metadata={
                "title": loaded.title,
                "source": loaded.source,
                **loaded.metadata,
            },
        )


def result_value(result: object, key: str, default: object) -> object:
    """Read an index result value from either a mapping or an object attribute."""
    if isinstance(result, dict):
        return result.get(key, default)
    return getattr(result, key, default)
