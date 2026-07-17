from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from src.documents.loaders import (
    TextDocumentIndexer,
    index_loaded_document,
    load_document_file,
)
from src.retrieval.langchain_chroma_retriever import LangChainChromaRetriever


DOCUMENT_SUMMARY_SYSTEM_PROMPT = """You create concise document summaries for retrieval.

Return ONLY a plain text summary. Do not include markdown formatting.
Do not continue the conversation. Do not invent facts.

Summarize the document content in 3-6 sentences covering:
- What the document is (type, purpose, author if mentioned)
- Main topics and sections
- Key facts, findings, or conclusions

Keep it under 300 words."""


class SummaryModel(Protocol):
    """Minimal chat model protocol for document summary generation."""

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        """Return a chat completion as text."""
        ...


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
    """Responsibility wrapper for loading, indexing, and summarizing documents."""

    def __init__(
        self,
        indexer: TextDocumentIndexer | None = None,
        summary_model: SummaryModel | None = None,
        summary_database: object | None = None,
    ) -> None:
        self.indexer = indexer
        self.summary_model = summary_model
        self.summary_database = summary_database

    def index_file(
        self,
        path: str | Path,
        display_name: str | None = None,
        *,
        document_id: str | None = None,
    ) -> DocumentIngestionResult:
        """Load a local file and index it through the configured document backend."""
        loaded = load_document_file(path, display_name=display_name)
        if document_id:
            loaded.metadata["document_id"] = document_id
        indexer = self.indexer or LangChainChromaRetriever.from_env()
        raw_result = index_loaded_document(loaded, indexer)

        indexed_document_id = result_value(raw_result, "document_id", "")
        chunk_count = int(result_value(raw_result, "chunk_count", 0) or 0)
        file_name = str(loaded.metadata.get("file_name", display_name or Path(path).name))
        file_extension = str(loaded.metadata.get("file_extension", Path(file_name).suffix.lower()))
        final_document_id = str(document_id or indexed_document_id)

        # Generate document summary asynchronously after indexing
        self._generate_summary(final_document_id, loaded.text)

        return DocumentIngestionResult(
            document_id=str(document_id or indexed_document_id),
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

    def _generate_summary(self, document_id: str, text: str) -> None:
        """Generate and persist a document-level summary via LLM."""
        if self.summary_model is None or self.summary_database is None:
            return
        try:
            # Use first 8000 chars to stay well within model context
            preview = text[:8000]
            response = self.summary_model.chat(
                [
                    {"role": "system", "content": DOCUMENT_SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Document to summarize:\n\n{preview}"},
                ],
                temperature=0.0,
            )
            summary = " ".join(response.strip().split())
            if summary and len(summary) > 20:
                getattr(self.summary_database, "update_document_summary")(document_id, summary)
        except Exception:
            pass  # Summary is best-effort; indexing succeeded regardless


def result_value(result: object, key: str, default: object) -> object:
    """Read an index result value from either a mapping or an object attribute."""
    if isinstance(result, dict):
        return result.get(key, default)
    return getattr(result, key, default)
