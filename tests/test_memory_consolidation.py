"""Tests for memory consolidation resilience — vec0 failures must not block SQL writes."""

from __future__ import annotations

from pathlib import Path

from typing import Any

import pytest

from support.deterministic_services import RecordingGuard
from src.memory.langmem_structured import LangMemStructuredMemoryState

from src.database import Database
from src.memory.long_term_store import (
    DEFAULT_USER_NAMESPACE,
    LongTermMemoryWrite,
    SQLiteLongTermMemoryStore,
    category_namespace,
)
from src.memory.long_term_vector_index import (
    LongTermMemoryVectorIndex,
    VectorIndexUnavailable,
)
from src.memory.structured_memory_vector_sync import (
    StructuredMemoryVectorSync,
    StructuredMemoryVectorSyncError,
)


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


def test_vec0_failure_does_not_block_sql_upsert(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
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
    assert_logged_vector_failure(caplog, RuntimeError, "simulated vec0 insert failure")


def test_error_messages_preserve_original_exception(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
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
    logged = assert_logged_vector_failure(caplog, ValueError, "simulated vec0 upsert failure")
    assert logged.__cause__ is backend.failures[0]


def test_second_vec0_upsert_succeeds_after_first(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A real first failure leaves SQL committed; the same record can later synchronize."""

    class FailOnceBackend(TrackingVectorBackend):
        def __init__(self):
            super().__init__()
            self.attempts = 0

        def add_vectors(self, rows):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("transient vec0 failure")
            return super().add_vectors(rows)

    backend = FailOnceBackend()
    database = Database(tmp_path / "test.db")
    store = SQLiteLongTermMemoryStore(
        database, vector_sync=StructuredMemoryVectorSync(FakeLongTermMemoryVectorIndex(backend))
    )
    store.upsert(_memory_write("prefs:retry", "First memory"))
    first = store.get(DEFAULT_USER_NAMESPACE, "prefs:retry")
    assert first is not None
    assert first.value == "First memory"
    assert backend.vectors == {}
    assert_logged_vector_failure(caplog, RuntimeError, "transient vec0 failure")

    store.upsert(_memory_write("prefs:retry", "Recovered memory"))
    recovered = store.get(DEFAULT_USER_NAMESPACE, "prefs:retry")
    assert recovered is not None
    assert recovered.rowid == first.rowid
    assert recovered.value == "Recovered memory"
    assert backend.attempts == 2
    assert list(backend.vectors) == [first.rowid]
    assert len(store.list(DEFAULT_USER_NAMESPACE)) == 1
    assert len([r for r in caplog.records if r.name == "src.memory.long_term_store"]) == 1


def test_consolidation_log_status_with_vec0_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """LangMem acceptance and persisted provenance survive a logged derived-vector failure."""
    database = Database(tmp_path / "test.db")
    database.create_chat("chat-1")
    message_id = database.save_message("chat-1", "user", "I prefer concise answers.")
    backend = FailingUpsertBackend()
    store = SQLiteLongTermMemoryStore(
        database, vector_sync=StructuredMemoryVectorSync(FakeLongTermMemoryVectorIndex(backend))
    )

    class Manager:
        def __init__(self):
            self.calls = []

        def invoke(self, payload):
            self.calls.append(payload)
            return [
                {
                    "category": "user_preferences",
                    "key": "style",
                    "value": "User prefers concise answers.",
                    "source_message_ids": [message_id],
                }
            ]

    manager, guard = Manager(), RecordingGuard()
    state = LangMemStructuredMemoryState(
        manager=manager, long_term_store=store, connection_guard=guard
    )
    result = state.update(existing_memory={}, messages=database.messages_for_chat("chat-1"))

    assert result.accepted is True
    assert result.rejection_reason is None
    assert guard.calls == 1
    assert len(manager.calls) == 1
    stored = store.get(category_namespace("user_preferences"), "user_preferences:style")
    assert stored is not None
    assert stored.value == "User prefers concise answers."
    assert stored.source_message_ids == [message_id]
    assert_logged_vector_failure(caplog, ValueError, "simulated vec0 upsert failure")


def assert_logged_vector_failure(caplog, cause_type, message):
    records = [record for record in caplog.records if record.name == "src.memory.long_term_store"]
    assert len(records) == 1
    assert records[0].levelname == "ERROR"
    assert "vec0 sync failed" in records[0].getMessage()
    assert records[0].exc_info is not None
    error = records[0].exc_info[1]
    assert isinstance(error, StructuredMemoryVectorSyncError)
    assert isinstance(error.__cause__, cause_type)
    assert message in str(error.__cause__)
    return error
