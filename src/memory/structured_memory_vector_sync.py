from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.memory.long_term_store import LongTermMemoryRecord, LongTermMemoryStore
from src.memory.long_term_vector_index import (
    LongTermMemorySyncReport,
    LongTermMemoryVectorIndex,
)


class StructuredMemoryVectorIndex(Protocol):
    """Vector operations required by structured-memory synchronization."""

    def upsert_record(self, record: LongTermMemoryRecord) -> None:
        """Upsert one active derived entry."""

    def delete_record(
        self,
        namespace: tuple[str, ...],
        memory_id: str,
    ) -> None:
        """Delete one derived entry."""


class StructuredMemoryVectorSyncError(RuntimeError):
    """Raised when SQLite succeeds but its derived vector index cannot sync."""


@dataclass
class StructuredMemoryVectorSync:
    """Synchronize SQLite source-of-truth records into a derived vector index."""

    vector_index: StructuredMemoryVectorIndex

    @classmethod
    def from_env(cls) -> "StructuredMemoryVectorSync":
        """Create the configured long-term-memory vector synchronization adapter."""
        return cls(vector_index=LongTermMemoryVectorIndex.from_env())

    def sync_record(self, record: LongTermMemoryRecord) -> None:
        """Upsert active records and remove inactive records."""
        try:
            if record.status == "active":
                self.vector_index.upsert_record(record)
            else:
                self.vector_index.delete_record(record.namespace, record.memory_id)
        except Exception as error:
            raise StructuredMemoryVectorSyncError(
                "Structured-memory SQLite write committed, but vector sync failed "
                f"for {record.memory_id!r}: {type(error).__name__}: {error}"
            ) from error

    def delete_memory(
        self,
        namespace: tuple[str, ...],
        memory_id: str,
    ) -> None:
        """Idempotently remove one derived vector entry."""
        try:
            self.vector_index.delete_record(namespace, memory_id)
        except Exception as error:
            raise StructuredMemoryVectorSyncError(
                "Structured-memory SQLite delete committed, but vector sync failed "
                f"for {memory_id!r}: {type(error).__name__}: {error}"
            ) from error

    def sync_all(
        self,
        store: LongTermMemoryStore,
        namespaces: list[tuple[str, ...]] | None = None,
    ) -> LongTermMemorySyncReport:
        """Repair/backfill all records from selected or discovered namespaces."""
        selected_namespaces = namespaces or store.list_namespaces()
        upserted_count = 0
        deleted_count = 0
        for namespace in selected_namespaces:
            for record in store.list(namespace):
                self.sync_record(record)
                if record.status == "active":
                    upserted_count += 1
                else:
                    deleted_count += 1
        return LongTermMemorySyncReport(
            upserted_count=upserted_count,
            deleted_count=deleted_count,
        )
