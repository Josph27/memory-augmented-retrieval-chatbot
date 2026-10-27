from __future__ import annotations

from src.memory.long_term_store import (
    DEFAULT_USER_NAMESPACE,
    LongTermMemoryRecord,
    LongTermMemoryWrite,
)
from src.memory.memory_trace import (
    document_memory_candidate_trace_rows,
    format_retrieved_memory_trace,
    format_saved_memory_trace,
    memory_candidate_to_trace_row,
    memory_record_to_inspector_row,
    memory_write_to_trace_row,
)
from src.core.contracts import MemoryCandidate


def test_format_saved_memory_trace_includes_demo_fields() -> None:
    record = LongTermMemoryWrite(
        namespace=DEFAULT_USER_NAMESPACE,
        memory_id="preferences:library_preference",
        category="preferences",
        key="library_preference",
        value="User prefers mature libraries.",
        confidence=0.9,
        source_chat_id="chat-1",
        source_message_ids=[1],
    )

    formatted = format_saved_memory_trace("chat-1", record)

    assert "[Memory saved]" in formatted
    assert "chat_id=chat-1" in formatted
    assert "memory_id=preferences:library_preference" in formatted
    assert "namespace=user::default::semantic_memory" in formatted
    assert "category=preferences" in formatted
    assert "value=User prefers mature libraries." in formatted
    assert "source_message_ids=[1]" in formatted


def test_format_retrieved_memory_trace_includes_source_chat() -> None:
    record = LongTermMemoryRecord(
        namespace=DEFAULT_USER_NAMESPACE,
        memory_id="preferences:library_preference",
        category="preferences",
        key="library_preference",
        value="User prefers mature libraries.",
        confidence=0.9,
        source_chat_id="chat-1",
        source_message_ids=[1],
    )

    formatted = format_retrieved_memory_trace("chat-2", record)

    assert "[Memory retrieved]" in formatted
    assert "current_chat_id=chat-2" in formatted
    assert "source=structured_memory" in formatted
    assert "memory_id=preferences:library_preference" in formatted
    assert "source_chat_id=chat-1" in formatted
    assert "source_message_ids=[1]" in formatted


def test_memory_record_to_inspector_row_is_script_ready() -> None:
    record = LongTermMemoryRecord(
        namespace=DEFAULT_USER_NAMESPACE,
        memory_id="preferences:library_preference",
        category="preferences",
        key="library_preference",
        value="User prefers mature libraries.",
        confidence=0.9,
        source_chat_id="chat-1",
        source_message_ids=[1],
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:01:00+00:00",
    )

    row = memory_record_to_inspector_row(record)

    assert row == {
        "namespace": "user::default::semantic_memory",
        "memory_id": "preferences:library_preference",
        "category": "preferences",
        "key": "library_preference",
        "value": "User prefers mature libraries.",
        "source_chat_id": "chat-1",
        "source_message_ids": [1],
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:01:00+00:00",
    }


def test_saved_memory_trace_row_includes_provenance() -> None:
    record = LongTermMemoryWrite(
        namespace=DEFAULT_USER_NAMESPACE, memory_id="preferences:library_preference",
        category="preferences", key="library_preference", value="User prefers mature libraries.",
        confidence=0.9, source_chat_id="chat-1", source_message_ids=[1],
    )
    row = memory_write_to_trace_row(record)
    assert row["memory_id"] == "preferences:library_preference"
    assert row["category"] == "preferences"
    assert row["key"] == "library_preference"
    assert row["namespace"] == "user::default::semantic_memory"
    assert row["value"] == "User prefers mature libraries."
    assert row["source_chat_id"] == "chat-1"
    assert row["source_message_ids"] == [1]


def test_retrieved_memory_trace_row_contains_provenance() -> None:
    candidate = MemoryCandidate(
        source="structured_memory",
        content="User prefers mature libraries.",
        record_id="preferences:library_preference",
        chat_id="chat-1",
        source_message_ids=[1],
        metadata={
            "memory_id": "preferences:library_preference",
            "namespace": ["user", "default", "semantic_memory"],
            "category": "preferences",
            "key": "library_preference",
            "source_chat_id": "chat-1",
        },
    )
    rows = [memory_candidate_to_trace_row(candidate)]

    assert rows[0]["record_id"] == "preferences:library_preference"
    assert rows[0]["source_chat_id"] == "chat-1"
    assert rows[0]["value"] == "User prefers mature libraries."
    assert rows[0]["source_message_ids"] == [1]


def test_document_retrieval_trace_row_contains_provenance() -> None:
    candidate = MemoryCandidate(
        source="document_memory",
        content="README says the project uses Chainlit and SQLite for the chatbot demo.",
        score=0.92,
        record_id="doc-1",
        metadata={
            "document_id": "doc-1",
            "chunk_index": 2,
            "file_name": "README.md",
            "file_extension": ".md",
            "retrieval_backend": "langchain_chroma",
            "retrieval_mode": "langchain_chroma",
            "similarity_score": 0.92,
        },
    )
    rows = document_memory_candidate_trace_rows([candidate])

    assert rows[0]["file_name"] == "README.md"
    assert rows[0]["document_id"] == "doc-1"
    assert rows[0]["chunk_index"] == 2
    assert rows[0]["retrieval_backend"] == "langchain_chroma"
    assert "README says the project uses Chainlit" in rows[0]["content"]
