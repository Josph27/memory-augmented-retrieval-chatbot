from __future__ import annotations

import os
from typing import Any

from src.core.contracts import MemoryCandidate
from src.memory.long_term_store import LongTermMemoryRecord, LongTermMemoryWrite, namespace_path


def demo_memory_trace_enabled() -> bool:
    """Return whether demo memory tracing is enabled."""
    return os.getenv("DEMO_MEMORY_TRACE", "").strip().lower() in {"1", "true", "yes", "on"}


def format_saved_memory_trace(chat_id: str, record: LongTermMemoryWrite) -> str:
    """Format one saved-memory trace block."""
    return "\n".join(
        [
            "[Memory saved]",
            f"chat_id={chat_id}",
            f"memory_id={record.memory_id}",
            f"namespace={namespace_path(record.namespace)}",
            f"category={record.category}",
            f"key={record.key}",
            f"value={record.value}",
            f"confidence={record.confidence}",
            f"status={record.status}",
            f"source_chat_id={record.source_chat_id}",
            f"source_message_ids={record.source_message_ids}",
        ]
    )


def format_retrieved_memory_trace(
    current_chat_id: str,
    record: LongTermMemoryRecord,
) -> str:
    """Format one retrieved-memory trace block."""
    return "\n".join(
        [
            "[Memory retrieved]",
            f"current_chat_id={current_chat_id}",
            "source=structured_memory",
            f"memory_id={record.memory_id}",
            f"namespace={namespace_path(record.namespace)}",
            f"category={record.category}",
            f"key={record.key}",
            f"value={record.value}",
            f"source_chat_id={record.source_chat_id}",
            f"source_message_ids={record.source_message_ids}",
        ]
    )


def print_saved_memory_trace(chat_id: str, record: LongTermMemoryWrite) -> None:
    """Print one saved-memory trace block when demo tracing is enabled."""
    if demo_memory_trace_enabled():
        print(format_saved_memory_trace(chat_id, record))


def print_retrieved_memory_traces(
    current_chat_id: str,
    records: list[LongTermMemoryRecord],
) -> None:
    """Print retrieved-memory trace blocks when demo tracing is enabled."""
    if not demo_memory_trace_enabled():
        return
    for record in records:
        print(format_retrieved_memory_trace(current_chat_id, record))


def memory_record_to_inspector_row(record: LongTermMemoryRecord) -> dict[str, Any]:
    """Convert a long-term record to a script-friendly display row."""
    return {
        "namespace": namespace_path(record.namespace),
        "memory_id": record.memory_id,
        "category": record.category,
        "key": record.key,
        "value": record.value,
        "source_chat_id": record.source_chat_id,
        "source_message_ids": list(record.source_message_ids),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def memory_write_to_trace_row(record: LongTermMemoryWrite) -> dict[str, Any]:
    """Convert a saved memory write to a UI/log trace row."""
    return {
        "namespace": namespace_path(record.namespace),
        "memory_id": record.memory_id,
        "category": record.category,
        "key": record.key,
        "value": record.value,
        "confidence": record.confidence,
        "status": record.status,
        "source_chat_id": record.source_chat_id,
        "source_message_ids": list(record.source_message_ids),
    }


def memory_candidate_to_trace_row(candidate: MemoryCandidate) -> dict[str, Any]:
    """Convert a structured MemoryCandidate to a UI/log trace row."""
    metadata = dict(candidate.metadata or {})
    return {
        "source": candidate.source,
        "record_id": candidate.record_id,
        "memory_id": metadata.get("memory_id") or candidate.record_id,
        "namespace": namespace_display(metadata.get("namespace")),
        "category": metadata.get("category"),
        "key": metadata.get("key"),
        "value": candidate.content,
        "source_chat_id": metadata.get("source_chat_id") or candidate.chat_id,
        "source_message_ids": list(candidate.source_message_ids),
    }


def structured_memory_candidate_trace_rows(
    candidates: list[MemoryCandidate],
) -> list[dict[str, Any]]:
    """Return trace rows for structured-memory candidates only."""
    return [
        memory_candidate_to_trace_row(candidate)
        for candidate in candidates
        if candidate.source == "structured_memory"
    ]


def document_memory_candidate_trace_rows(
    candidates: list[MemoryCandidate],
) -> list[dict[str, Any]]:
    """Return trace rows for document-memory candidates only."""
    return [
        document_candidate_to_trace_row(candidate)
        for candidate in candidates
        if candidate.source == "document_memory"
    ]


def document_candidate_to_trace_row(candidate: MemoryCandidate) -> dict[str, Any]:
    """Convert a document MemoryCandidate to a UI/log trace row."""
    metadata = dict(candidate.metadata or {})
    return {
        "source": candidate.source,
        "record_id": candidate.record_id,
        "document_id": metadata.get("document_id"),
        "chunk_id": metadata.get("chunk_id"),
        "chunk_index": metadata.get("chunk_index"),
        "title": metadata.get("title"),
        "file_name": metadata.get("file_name"),
        "file_extension": metadata.get("file_extension"),
        "retrieval_backend": metadata.get("retrieval_backend"),
        "retrieval_mode": metadata.get("retrieval_mode"),
        "similarity_score": metadata.get("similarity_score") or candidate.score,
        "content": candidate.content,
    }


def format_saved_memories_markdown(rows: list[dict[str, Any]]) -> str:
    """Format saved memory rows for a Chainlit debug message."""
    if not rows:
        return ""
    parts = ["🧠 Long-term memory saved"]
    for row in rows:
        parts.extend(
            [
                "",
                f"[{row.get('category')}] {row.get('key') or row.get('memory_id')}",
                f"Memory ID: `{row.get('memory_id')}`",
                f"Value: {row.get('value')}",
                f"Source chat: `{row.get('source_chat_id')}`",
                f"Source messages: {row.get('source_message_ids')}",
            ]
        )
    return "\n".join(parts)


def format_retrieved_documents_markdown(rows: list[dict[str, Any]]) -> str:
    """Format retrieved document rows for a Chainlit debug message."""
    if not rows:
        return ""
    parts = ["📄 Document memory retrieved"]
    for index, row in enumerate(rows, start=1):
        title = row.get("file_name") or row.get("title") or row.get("document_id")
        parts.extend(
            [
                "",
                f"Chunk {index}: `{title}`",
                f"Document ID: `{row.get('document_id')}`",
                f"Chunk index: `{row.get('chunk_index')}`",
                f"Backend: `{row.get('retrieval_backend')}`",
                f"Score: `{row.get('similarity_score')}`",
                f"Content: {preview_text(str(row.get('content') or ''))}",
            ]
        )
    return "\n".join(parts)


def format_retrieved_memories_markdown(rows: list[dict[str, Any]]) -> str:
    """Format retrieved memory rows for a Chainlit debug message."""
    if not rows:
        return ""
    parts = ["🔎 Long-term memory retrieved"]
    for row in rows:
        parts.extend(
            [
                "",
                "MemoryCandidate(source=structured_memory)",
                f"Record: `{row.get('record_id') or row.get('memory_id')}`",
                f"Category: `{row.get('category')}`",
                f"Key: `{row.get('key')}`",
                f"From chat: `{row.get('source_chat_id')}`",
                f"Content: {row.get('value')}",
                f"Source messages: {row.get('source_message_ids')}",
            ]
        )
    return "\n".join(parts)


def preview_text(text: str, limit: int = 500) -> str:
    """Return a compact single-line preview for UI trace messages."""
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."


def namespace_display(value: Any) -> str | None:
    """Display namespace metadata whether it is stored as a list, tuple, or string."""
    if isinstance(value, list | tuple):
        return "::".join(str(part) for part in value)
    if isinstance(value, str):
        return value
    return None
