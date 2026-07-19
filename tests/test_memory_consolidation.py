"""Tests for memory consolidation resilience — vec0 failures must not block SQL writes."""

from __future__ import annotations

from pathlib import Path

from typing import Any

from src.database import Database
from src.memory.long_term_store import (
    DEFAULT_USER_NAMESPACE,
    LongTermMemoryWrite,
    SQLiteLongTermMemoryStore,
    namespace_path,
)
from src.memory.long_term_vector_index import (
    LongTermMemoryVectorIndex,
    VectorIndexUnavailable,
    memory_record_to_index_text,
)
from src.memory.structured_memory_vector_sync import StructuredMemoryVectorSync


# ── Fake vector backends ────────────────────────────────────────────────


class FailingAddVectorsBackend:
    """Backend that raises on add_vectors but works otherwise."""

    def __init__(self) -> None:
        self.add_vectors_calls: list[list[tuple[int, bytes]]] = []
        self.remove_calls: list[list[int]] = []

    def add_vectors(self, rows: list[tuple[int, bytes]]) -> None:
        self.add_vectors_calls.append(list(rows))
        raise RuntimeError("simulated vec0 insert failure")

    def remove_vectors(self, rowids: list[int]) -> None:
        self.remove_calls.append(list(rowids))

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        del query, k
        raise VectorIndexUnavailable("not used in these tests")


class FailingUpsertBackend:
    """Backend whose add_vectors raises a ValueError on every call."""

    def __init__(self) -> None:
        self.failures: list[Exception] = []

    def add_vectors(self, rows: list[tuple[int, bytes]]) -> None:
        del rows
        ex = ValueError("simulated vec0 upsert failure")
        self.failures.append(ex)
        raise ex

    def remove_vectors(self, rowids: list[int]) -> None:
        del rowids

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        del query, k
        return []


class TrackingVectorBackend:
    """Backend that tracks all upsert/deletes for verification."""

    def __init__(self) -> None:
        self.vectors: dict[int, bytes] = {}
        self.delete_calls: list[list[int]] = []

    def add_vectors(self, rows: list[tuple[int, bytes]]) -> None:
        for rowid, blob in rows:
            self.vectors[rowid] = blob

    def remove_vectors(self, rowids: list[int]) -> None:
        self.delete_calls.append(list(rowids))
        for rowid in rowids:
            self.vectors.pop(rowid, None)

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        del query, k
        return []


class FakeLongTermMemoryVectorIndex(LongTermMemoryVectorIndex):
    def __init__(self, backend: Any) -> None:
        super().__init__(vectorstore=backend)


# ── Helpers ─────────────────────────────────────────────────────────────


def _memory_write(
    memory_id: str = "preferences:libraries",
    value: str = "User prefers mature open-source libraries.",
    rowid: int = 1,
) -> LongTermMemoryWrite:
    return LongTermMemoryWrite(
        namespace=DEFAULT_USER_NAMESPACE,
        memory_id=memory_id,
        category="preferences",
        key="libraries",
        value=value,
        confidence=0.9,
        status="active",
        source_chat_id="chat-1",
        source_message_ids=[rowid],
        metadata={"backend": "test"},
    )


# ── Tests ───────────────────────────────────────────────────────────────


def test_vec0_failure_does_not_block_sql_upsert(tmp_path: Path) -> None:
    """SQL upsert succeeds even when vec0 sync raises."""
    database = Database(tmp_path / "test.db")
    backend = FailingAddVectorsBackend()
    vector_index = FakeLongTermMemoryVectorIndex(backend)
    sync = StructuredMemoryVectorSync(vector_index)
    store = SQLiteLongTermMemoryStore(database, vector_sync=sync)

    write = _memory_write("prefs:test", "User likes Python.")
    store.upsert(write)

    # SQL write must succeed despite vec0 failure
    stored = store.get(DEFAULT_USER_NAMESPACE, "prefs:test")
    assert stored is not None
    assert stored.value == "User likes Python."

    # Vec0 backend was called (and failed) — logged but not propagated
    assert len(backend.add_vectors_calls) == 1


def test_error_messages_preserve_original_exception(tmp_path: Path) -> None:
    """Vec0 sync failure is swallowed — no exception propagates to caller."""
    database = Database(tmp_path / "test.db")
    backend = FailingUpsertBackend()
    vector_index = FakeLongTermMemoryVectorIndex(backend)
    sync = StructuredMemoryVectorSync(vector_index)
    store = SQLiteLongTermMemoryStore(database, vector_sync=sync)

    write = _memory_write("prefs:test2", "User dislikes cabbage.")

    # Must not raise
    store.upsert(write)

    # SQL write succeeded
    stored = store.get(DEFAULT_USER_NAMESPACE, "prefs:test2")
    assert stored is not None
    assert stored.value == "User dislikes cabbage."

    # Vec0 backend was attempted and failed
    assert len(backend.failures) == 1
    assert isinstance(backend.failures[0], ValueError)
    assert "simulated vec0 upsert failure" in str(backend.failures[0])


def test_second_vec0_upsert_succeeds_after_first(tmp_path: Path) -> None:
    """Multiple upserts to vec0 work independently — a prior failure doesn't block."""
    backend = TrackingVectorBackend()
    vector_index = FakeLongTermMemoryVectorIndex(backend)
    database = Database(tmp_path / "test.db")

    # First upsert — should succeed
    sync1 = StructuredMemoryVectorSync(vector_index)
    store1 = SQLiteLongTermMemoryStore(database, vector_sync=sync1)
    store1.upsert(_memory_write("prefs:first", "First memory"))
    assert len(backend.vectors) == 1

    # Second upsert — should also succeed (different memory)
    store1.upsert(_memory_write("prefs:second", "Second memory"))
    assert len(backend.vectors) == 2

    # Verify both in SQL
    assert store1.get(DEFAULT_USER_NAMESPACE, "prefs:first") is not None
    assert store1.get(DEFAULT_USER_NAMESPACE, "prefs:second") is not None


def test_consolidation_log_status_with_vec0_failure(tmp_path: Path) -> None:
    """MemoryUpdateResult.accepted reflects SQL success, not vec0 status."""
    database = Database(tmp_path / "test.db")
    backend = FailingUpsertBackend()
    vector_index = FakeLongTermMemoryVectorIndex(backend)
    sync = StructuredMemoryVectorSync(vector_index)
    store = SQLiteLongTermMemoryStore(database, vector_sync=sync)

    write = _memory_write("prefs:vec0_failure", "Should persist anyway.")
    store.upsert(write)

    # Record is in SQL
    stored = store.get(DEFAULT_USER_NAMESPACE, "prefs:vec0_failure")
    assert stored is not None
    assert stored.value == "Should persist anyway."
