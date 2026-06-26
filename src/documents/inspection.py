from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.database import Database, StoredDocumentChunk
from src.retrieval.langchain_chroma_retriever import DEFAULT_COLLECTION_NAME


@dataclass(frozen=True)
class DocumentInspectionRow:
    """Display row for indexed document/chunk state."""

    document_id: str
    title: str | None
    file_name: str | None
    file_extension: str | None
    source: str | None
    retrieval_backend: str
    chunk_count: int
    chunk_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentInspectionUnavailable(RuntimeError):
    """Raised when an optional document inspection backend is unavailable."""


def sqlite_document_inspection_rows(database: Database) -> list[DocumentInspectionRow]:
    """Summarize legacy SQLite document_chunks metadata."""
    grouped: dict[str, list[StoredDocumentChunk]] = {}
    for chunk in database.document_chunks():
        grouped.setdefault(str(chunk.document_id), []).append(chunk)

    rows = []
    for document_id, chunks in grouped.items():
        chunks = sorted(chunks, key=lambda chunk: chunk.chunk_index)
        metadata = first_metadata(chunks)
        rows.append(
            DocumentInspectionRow(
                document_id=document_id,
                title=chunks[0].document_title if chunks else None,
                file_name=string_or_none(metadata.get("file_name")),
                file_extension=string_or_none(metadata.get("file_extension")),
                source=string_or_none(metadata.get("source")),
                retrieval_backend="sqlite_document_chunks",
                chunk_count=len(chunks),
                chunk_ids=[str(chunk.id) for chunk in chunks],
                metadata=metadata,
            )
        )
    return sorted(rows, key=lambda row: row.document_id)


def chroma_document_inspection_rows(
    persist_dir: str | Path,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> list[DocumentInspectionRow]:
    """Summarize LangChain-Chroma document metadata without running retrieval."""
    try:
        import chromadb
    except ImportError as error:
        raise DocumentInspectionUnavailable(
            "chromadb is unavailable; install it to inspect LangChain-Chroma metadata."
        ) from error

    try:
        client = chromadb.PersistentClient(path=str(persist_dir))
        collection = client.get_collection(collection_name)
        result = collection.get(include=["metadatas"])
    except Exception as error:
        raise DocumentInspectionUnavailable(
            f"Could not inspect Chroma collection {collection_name!r}: {error}"
        ) from error

    ids = [str(item) for item in result.get("ids", [])]
    metadatas = [
        metadata if isinstance(metadata, dict) else {}
        for metadata in result.get("metadatas", [])
    ]
    return rows_from_chroma_metadata(ids=ids, metadatas=metadatas)


def rows_from_chroma_metadata(
    ids: list[str],
    metadatas: list[dict[str, Any]],
) -> list[DocumentInspectionRow]:
    """Group Chroma chunk metadata into document-level inspection rows."""
    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for item_id, metadata in zip(ids, metadatas, strict=False):
        document_id = string_or_none(metadata.get("document_id")) or item_id
        grouped.setdefault(document_id, []).append((item_id, metadata))

    rows = []
    for document_id, entries in grouped.items():
        entries = sorted(entries, key=lambda item: chunk_index_sort_key(item[1]))
        metadata = dict(entries[0][1]) if entries else {}
        rows.append(
            DocumentInspectionRow(
                document_id=document_id,
                title=string_or_none(metadata.get("title")),
                file_name=string_or_none(metadata.get("file_name")),
                file_extension=string_or_none(metadata.get("file_extension")),
                source=string_or_none(metadata.get("source")),
                retrieval_backend=string_or_none(metadata.get("retrieval_backend"))
                or "langchain_chroma",
                chunk_count=len(entries),
                chunk_ids=[item_id for item_id, _metadata in entries],
                metadata=metadata,
            )
        )
    return sorted(rows, key=lambda row: row.document_id)


def format_document_inspection_rows(rows: list[DocumentInspectionRow]) -> str:
    """Format document inspection rows for CLI output."""
    if not rows:
        return "indexed_documents_count=0"

    lines = [f"indexed_documents_count={len(rows)}"]
    for row in rows:
        lines.extend(
            [
                "[Indexed document]",
                f"document_id={row.document_id}",
                f"title={row.title}",
                f"file_name={row.file_name}",
                f"file_extension={row.file_extension}",
                f"source={row.source}",
                f"retrieval_backend={row.retrieval_backend}",
                f"chunk_count={row.chunk_count}",
                f"chunk_ids={row.chunk_ids}",
            ]
        )
    return "\n".join(lines)


def first_metadata(chunks: list[StoredDocumentChunk]) -> dict[str, Any]:
    """Return the first parseable chunk metadata dictionary."""
    for chunk in chunks:
        metadata = parse_metadata_json(chunk.metadata_json)
        if metadata:
            return metadata
    return {}


def parse_metadata_json(metadata_json: str) -> dict[str, Any]:
    """Parse metadata JSON defensively for inspection."""
    try:
        parsed = json.loads(metadata_json)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def string_or_none(value: Any) -> str | None:
    """Return a string display value or None."""
    if value is None:
        return None
    return str(value)


def chunk_index_sort_key(metadata: dict[str, Any]) -> int:
    """Return a stable chunk-index sort key."""
    try:
        return int(metadata.get("chunk_index", 0))
    except (TypeError, ValueError):
        return 0
