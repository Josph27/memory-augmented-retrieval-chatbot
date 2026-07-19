from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from src.core.contracts import MemoryCandidate

try:  # pragma: no cover - optional dependency path
    from langgraph.store.memory import InMemoryStore as LangGraphInMemoryStore
except Exception:  # pragma: no cover - keep import optional
    LangGraphInMemoryStore = None


_LOGGER = logging.getLogger(__name__)

DEFAULT_USER_NAMESPACE = ("user", "default", "semantic_memory")
DEFAULT_PROJECT_NAMESPACE = ("project", "default", "semantic_memory")


def utc_now() -> str:
    """Return a stable UTC timestamp for memory rows."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def namespace_path(namespace: tuple[str, ...]) -> str:
    """Serialize a namespace tuple to a stable path string."""
    return "::".join(namespace)


def namespace_from_path(path: str) -> tuple[str, ...]:
    """Deserialize a namespace path string back into a tuple."""
    if not path:
        return ()
    return tuple(path.split("::"))


def matches_namespace_prefix(
    namespace: tuple[str, ...],
    prefix: tuple[str, ...],
) -> bool:
    """Return whether namespace starts with the provided prefix."""
    if len(prefix) > len(namespace):
        return False
    return namespace[: len(prefix)] == prefix


def category_namespace(category: str, source_chat_id: str | None = None) -> tuple[str, ...]:
    """Return the long-term namespace for one memory category, scoped by category."""
    del source_chat_id
    return ("memory", category)


def structured_memory_namespaces(chat_id: str | None = None) -> list[tuple[str, ...]]:
    """Return namespaces consulted for structured-memory retrieval."""
    namespaces = [
        ("memory", "past_events"),
        ("memory", "user_experiences"),
        ("memory", "user_facts"),
        ("memory", "user_state"),
        ("memory", "user_preferences"),
        ("memory", "upcoming"),
        ("memory", "procedural"),
        ("memory", "corrections"),
        ("memory", "third_party_facts"),
        ("memory", "opinions"),
    ]
    if chat_id:
        namespaces.append(("chat", chat_id, "structured_memory"))
    return namespaces


@dataclass(frozen=True)
class LongTermMemoryRecord:
    """Canonical long-term memory row stored in a namespace/key store."""

    namespace: tuple[str, ...]
    memory_id: str
    category: str
    key: str
    value: str
    confidence: float = 0.5
    status: str = "active"
    source_chat_id: str | None = None
    source_message_ids: list[int] = field(default_factory=list)
    source_gist_id: int | None = None
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    expires_at: str = ""
    rowid: int | None = None

    def is_expired(self, *, now: str | None = None) -> bool:
        """Return True if this memory has an expiration that has passed."""
        if not self.expires_at:
            return False
        from datetime import datetime, timezone

        current = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
        return self.expires_at < current

    def as_memory_record(self) -> dict[str, Any]:
        """Convert to the existing `chat_memory_state` record format."""
        return {
            "id": self.memory_id,
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "source_message_ids": list(self.source_message_ids),
            "confidence": self.confidence,
            "status": self.status,
        }

    def as_store_value(self) -> dict[str, Any]:
        """Convert to a serializable store payload."""
        return {
            "memory_id": self.memory_id,
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "status": self.status,
            "source_chat_id": self.source_chat_id,
            "source_message_ids": list(self.source_message_ids),
            "source_gist_id": self.source_gist_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
            "rowid": self.rowid,
            "expires_at": self.expires_at,
        }


@dataclass(frozen=True)
class LongTermMemoryWrite:
    """Normalized write request for a long-term memory store."""

    namespace: tuple[str, ...]
    memory_id: str
    category: str
    key: str
    value: str
    confidence: float = 0.5
    status: str = "active"
    source_chat_id: str | None = None
    source_message_ids: list[int] = field(default_factory=list)
    source_gist_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    expires_at: str = ""
    rowid: int | None = None

    def as_store_value(self) -> dict[str, Any]:
        """Convert to a serializable store payload."""
        return {
            "memory_id": self.memory_id,
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "status": self.status,
            "source_chat_id": self.source_chat_id,
            "source_message_ids": list(self.source_message_ids),
            "source_gist_id": self.source_gist_id,
            "metadata": dict(self.metadata),
            "rowid": self.rowid,
            "expires_at": self.expires_at,
        }


class LongTermMemoryStore(Protocol):
    """Protocol shared by persistent and in-memory namespace stores."""

    def upsert(self, record: LongTermMemoryWrite) -> None:
        """Insert or update a memory row."""

    def get(self, namespace: tuple[str, ...], memory_id: str) -> LongTermMemoryRecord | None:
        """Get one memory row by namespace and key."""

    def delete(self, namespace: tuple[str, ...], memory_id: str) -> None:
        """Mark one memory row inactive or delete it."""

    def list(self, namespace: tuple[str, ...]) -> list[LongTermMemoryRecord]:
        """List all memories in one namespace."""

    def search(
        self,
        namespace_prefix: tuple[str, ...],
        query: str | None = None,
        limit: int = 10,
    ) -> list[LongTermMemoryRecord]:
        """Search one namespace prefix with optional lexical filtering."""

    def list_namespaces(
        self,
        prefix: tuple[str, ...] | None = None,
        limit: int = 100,
    ) -> list[tuple[str, ...]]:
        """List namespaces known to the store."""


class StructuredMemoryVectorSync(Protocol):
    """Optional derived-index synchronization contract."""

    def sync_record(self, record: LongTermMemoryRecord) -> None:
        """Synchronize one committed SQLite record."""

    def delete_memory(
        self,
        namespace: tuple[str, ...],
        memory_id: str,
    ) -> None:
        """Remove one committed SQLite record from the derived index."""


class SQLiteLongTermMemoryStore:
    """SQLite-backed namespace store for semantic/procedural memory."""

    def __init__(
        self,
        database: Any,
        vector_sync: StructuredMemoryVectorSync | None = None,
        retrieval_mode: str | None = None,
    ) -> None:
        self.database = database
        self.vector_sync = vector_sync
        mode = (
            (retrieval_mode or os.getenv("STRUCTURED_MEMORY_RETRIEVAL_MODE", "sqlite"))
            .strip()
            .lower()
        )
        if self.vector_sync is None and mode in {"vector", "hybrid"}:
            from src.memory.structured_memory_vector_sync import (
                StructuredMemoryVectorSync as DefaultStructuredMemoryVectorSync,
            )

            self.vector_sync = DefaultStructuredMemoryVectorSync.from_env(database=self.database)

    def upsert(self, record: LongTermMemoryWrite) -> None:
        """Insert or update one memory row."""
        timestamp = utc_now()
        metadata = dict(record.metadata or {})
        if record.expires_at:
            metadata["expires_at"] = record.expires_at
        metadata_json = json.dumps(metadata, ensure_ascii=True)
        source_ids_json = json.dumps(record.source_message_ids or [], ensure_ascii=True)
        namespace_json = json.dumps(list(record.namespace), ensure_ascii=True)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO long_term_memories (
                    namespace_json,
                    namespace_path,
                    memory_id,
                    category,
                    key,
                    value,
                    confidence,
                    status,
                    source_chat_id,
                    source_message_ids_json,
                    source_gist_id,
                    created_at,
                    updated_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace_path, memory_id) DO UPDATE SET
                    category = excluded.category,
                    key = excluded.key,
                    value = excluded.value,
                    confidence = excluded.confidence,
                    status = excluded.status,
                    source_chat_id = excluded.source_chat_id,
                    source_message_ids_json = excluded.source_message_ids_json,
                    source_gist_id = excluded.source_gist_id,
                    updated_at = excluded.updated_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    namespace_json,
                    namespace_path(record.namespace),
                    record.memory_id,
                    record.category,
                    record.key,
                    record.value,
                    record.confidence,
                    record.status,
                    record.source_chat_id,
                    source_ids_json,
                    record.source_gist_id,
                    timestamp,
                    timestamp,
                    metadata_json,
                ),
            )
        stored = self.get(record.namespace, record.memory_id)
        if stored is None:
            raise RuntimeError(
                f"Structured-memory SQLite upsert missing after commit: {record.memory_id}"
            )
        if self.vector_sync is not None:
            try:
                self.vector_sync.sync_record(stored)
            except Exception:
                _LOGGER.exception(
                    "vec0 sync failed for memory_id=%s namespace=%s",
                    record.memory_id,
                    namespace_path(record.namespace),
                )

    def get(self, namespace: tuple[str, ...], memory_id: str) -> LongTermMemoryRecord | None:
        """Get one memory row by namespace and key."""
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id AS rowid,
                    namespace_path,
                    namespace_json,
                    memory_id,
                    category,
                    key,
                    value,
                    confidence,
                    status,
                    source_chat_id,
                    source_message_ids_json,
                    source_gist_id,
                    created_at,
                    updated_at,
                    metadata_json
                FROM long_term_memories
                WHERE namespace_path = ? AND memory_id = ?
                """,
                (namespace_path(namespace), memory_id),
            ).fetchone()
        return row_to_record(row) if row else None

    def delete(self, namespace: tuple[str, ...], memory_id: str) -> None:
        """Mark one memory row deleted."""
        timestamp = utc_now()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE long_term_memories
                SET status = 'deleted', updated_at = ?
                WHERE namespace_path = ? AND memory_id = ?
                """,
                (timestamp, namespace_path(namespace), memory_id),
            )
        if self.vector_sync is not None:
            self.vector_sync.delete_memory(namespace, memory_id)

    def list(self, namespace: tuple[str, ...]) -> list[LongTermMemoryRecord]:
        """List all memories in one namespace."""
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id AS rowid,
                    namespace_path,
                    namespace_json,
                    memory_id,
                    category,
                    key,
                    value,
                    confidence,
                    status,
                    source_chat_id,
                    source_message_ids_json,
                    source_gist_id,
                    created_at,
                    updated_at,
                    metadata_json
                FROM long_term_memories
                WHERE namespace_path = ?
                ORDER BY updated_at DESC, memory_id ASC
                """,
                (namespace_path(namespace),),
            ).fetchall()
        return _filter_unexpired([row_to_record(row) for row in rows])

    def search(
        self,
        namespace_prefix: tuple[str, ...],
        query: str | None = None,
        limit: int = 10,
    ) -> list[LongTermMemoryRecord]:
        """Search namespace rows with optional lexical filtering."""
        candidate_rows = self._rows_for_namespace_prefix(namespace_prefix)
        if query:
            terms = important_terms(query)
            scored: list[tuple[float, LongTermMemoryRecord]] = []
            for row in candidate_rows:
                score = lexical_score(row, terms)
                if score > 0:
                    scored.append((score, row))
            scored.sort(
                key=lambda item: (item[0], item[1].updated_at, item[1].memory_id), reverse=True
            )
            return [row for _, row in scored[:limit] if not row.is_expired()]

        candidate_rows.sort(key=lambda row: (row.updated_at, row.memory_id), reverse=True)
        return _filter_unexpired(candidate_rows)[:limit]

    def list_namespaces(
        self,
        prefix: tuple[str, ...] | None = None,
        limit: int = 100,
    ) -> list[tuple[str, ...]]:
        """List namespaces known to the SQLite store."""
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT namespace_path
                FROM long_term_memories
                ORDER BY namespace_path ASC
                """
            ).fetchall()

        namespaces = [namespace_from_path(row["namespace_path"]) for row in rows]
        if prefix is not None:
            namespaces = [
                namespace for namespace in namespaces if matches_namespace_prefix(namespace, prefix)
            ]
        return namespaces[:limit]

    def _rows_for_namespace_prefix(
        self, namespace_prefix: tuple[str, ...]
    ) -> list[LongTermMemoryRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id AS rowid,
                    namespace_path,
                    namespace_json,
                    memory_id,
                    category,
                    key,
                    value,
                    confidence,
                    status,
                    source_chat_id,
                    source_message_ids_json,
                    source_gist_id,
                    created_at,
                    updated_at,
                    metadata_json
                FROM long_term_memories
                WHERE status = 'active'
                ORDER BY updated_at DESC, memory_id ASC
                """
            ).fetchall()

        candidates = [row_to_record(row) for row in rows]
        matching = [
            record
            for record in candidates
            if matches_namespace_prefix(record.namespace, namespace_prefix)
        ]
        return _filter_unexpired(matching)


class LangGraphInMemoryLongTermMemoryStore:
    """LangGraph InMemoryStore-backed implementation for tests."""

    def __init__(self, store: Any | None = None) -> None:
        if store is None:
            if LangGraphInMemoryStore is None:  # pragma: no cover - optional path
                raise RuntimeError("langgraph.store.memory.InMemoryStore is unavailable")
            store = LangGraphInMemoryStore()
        self.store = store

    def upsert(self, record: LongTermMemoryWrite) -> None:
        self.store.put(record.namespace, record.memory_id, record.as_store_value())

    def get(self, namespace: tuple[str, ...], memory_id: str) -> LongTermMemoryRecord | None:
        item = self.store.get(namespace, memory_id)
        if item is None:
            return None
        return record_from_store_value(
            item.value, namespace=tuple(item.namespace), memory_id=item.key
        )

    def delete(self, namespace: tuple[str, ...], memory_id: str) -> None:
        self.store.delete(namespace, memory_id)

    def list(self, namespace: tuple[str, ...]) -> list[LongTermMemoryRecord]:
        items = self.store.search(namespace, limit=1000)
        return [
            record_from_store_value(item.value, namespace=tuple(item.namespace), memory_id=item.key)
            for item in items
        ]

    def search(
        self,
        namespace_prefix: tuple[str, ...],
        query: str | None = None,
        limit: int = 10,
    ) -> list[LongTermMemoryRecord]:
        items = self.store.search(namespace_prefix, query=query, limit=limit)
        return [
            record_from_store_value(item.value, namespace=tuple(item.namespace), memory_id=item.key)
            for item in items
        ]

    def list_namespaces(
        self,
        prefix: tuple[str, ...] | None = None,
        limit: int = 100,
    ) -> list[tuple[str, ...]]:
        namespaces = self.store.list_namespaces(prefix=prefix, limit=limit)
        return [tuple(namespace) for namespace in namespaces]


def record_to_write(
    record: dict[str, Any],
    *,
    namespace: tuple[str, ...],
    source_chat_id: str | None,
    source_gist_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    expires_at: str = "",
) -> LongTermMemoryWrite:
    """Convert a structured-memory record dict to a long-term write."""
    source_ids = [
        source_id
        for source_id in record.get("source_message_ids", [])
        if isinstance(source_id, int)
    ]
    return LongTermMemoryWrite(
        namespace=namespace,
        memory_id=str(record.get("id") or f"{record['category']}:{record['key']}"),
        category=str(record["category"]),
        key=str(record["key"]),
        value=str(record["value"]),
        confidence=float(record.get("confidence", 0.5)),
        status=str(record.get("status", "active")),
        source_chat_id=source_chat_id,
        source_message_ids=source_ids,
        source_gist_id=source_gist_id,
        metadata=metadata or {},
        expires_at=expires_at,
        rowid=record.get("rowid"),
    )


def record_to_candidate(record: LongTermMemoryRecord) -> MemoryCandidate:
    """Convert a long-term memory row to a MemoryCandidate."""
    return MemoryCandidate(
        source="structured_memory",
        content=record.value,
        score=record.confidence,
        record_id=record.memory_id,
        chat_id=record.source_chat_id,
        source_message_ids=list(record.source_message_ids),
        metadata={
            "namespace": list(record.namespace),
            "memory_id": record.memory_id,
            "category": record.category,
            "key": record.key,
            "status": record.status,
            "confidence": record.confidence,
            "source_chat_id": record.source_chat_id,
            "source_message_ids": list(record.source_message_ids),
            "source_gist_id": record.source_gist_id,
            **dict(record.metadata),
        },
    )


def record_to_memory_state_record(record: LongTermMemoryRecord) -> dict[str, Any]:
    """Convert a long-term memory row into the compatibility memory record format."""
    return record.as_memory_record()


def memory_state_from_records(
    records: list[LongTermMemoryRecord],
) -> dict[str, list[dict[str, Any]]]:
    """Convert store records into the existing chat_memory_state JSON shape."""
    return {"memories": [record_to_memory_state_record(record) for record in records]}


def merge_memory_records(
    existing_records: list[dict[str, Any]],
    new_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge records by id while preserving record dictionaries."""
    merged = [dict(record) for record in existing_records]
    index_by_id = {
        str(record.get("id")): index for index, record in enumerate(merged) if record.get("id")
    }
    for record in new_records:
        memory_id = str(record.get("id"))
        if memory_id in index_by_id:
            merged[index_by_id[memory_id]] = dict(record)
            continue
        index_by_id[memory_id] = len(merged)
        merged.append(dict(record))
    return merged


def dedupe_memory_records(records: list[LongTermMemoryRecord]) -> list[LongTermMemoryRecord]:
    """Deduplicate records by namespace/key keeping the latest one."""
    deduped: dict[tuple[str, ...], dict[str, LongTermMemoryRecord]] = {}
    ordered: list[LongTermMemoryRecord] = []
    for record in records:
        namespace_bucket = deduped.setdefault(record.namespace, {})
        namespace_bucket[record.memory_id] = record
    for namespace, namespace_records in deduped.items():
        del namespace
        ordered.extend(namespace_records.values())
    return ordered


def row_to_record(row: sqlite3.Row) -> LongTermMemoryRecord:
    """Convert a SQLite row to a long-term memory record."""
    metadata = safe_json_dict(row["metadata_json"])
    source_ids = safe_json_list(row["source_message_ids_json"])
    confidence = float(row["confidence"]) if row["confidence"] is not None else 0.5
    record_rowid = row["rowid"] if "rowid" in row.keys() else None
    expires_at = str(metadata.pop("expires_at", "") or "").strip()
    return LongTermMemoryRecord(
        namespace=namespace_from_path(
            row["namespace_path"] if "namespace_path" in row.keys() else row["namespace_json"]
        ),
        memory_id=row["memory_id"],
        category=row["category"],
        key=row["key"],
        value=row["value"],
        confidence=confidence,
        status=row["status"],
        source_chat_id=row["source_chat_id"],
        source_message_ids=[item for item in source_ids if isinstance(item, int)],
        source_gist_id=row["source_gist_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        metadata=metadata,
        expires_at=expires_at,
        rowid=record_rowid,
    )


def record_from_store_value(
    value: dict[str, Any],
    *,
    namespace: tuple[str, ...],
    memory_id: str,
) -> LongTermMemoryRecord:
    """Convert an InMemoryStore payload back to a record."""
    return LongTermMemoryRecord(
        namespace=namespace,
        memory_id=memory_id,
        category=str(value.get("category", "user_facts")),
        key=str(value.get("key", memory_id)),
        value=str(value.get("value", "")),
        confidence=float(value.get("confidence", 0.5) or 0.5),
        status=str(value.get("status", "active")),
        source_chat_id=value.get("source_chat_id"),
        source_message_ids=[
            item for item in value.get("source_message_ids", []) if isinstance(item, int)
        ],
        source_gist_id=value.get("source_gist_id"),
        created_at=str(value.get("created_at", "")),
        updated_at=str(value.get("updated_at", "")),
        metadata=dict(value.get("metadata", {})),
        expires_at=str(value.get("expires_at", "") or ""),
    )


def safe_json_dict(value: str | None) -> dict[str, Any]:
    """Parse a JSON dict with a safe fallback."""
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def safe_json_list(value: str | None) -> list[Any]:
    """Parse a JSON list with a safe fallback."""
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def important_terms(text: str) -> set[str]:
    """Extract lexical search terms."""
    import re

    stopwords = {
        "the",
        "user",
        "users",
        "uses",
        "use",
        "using",
        "project",
        "name",
        "fact",
        "is",
        "am",
        "are",
        "my",
        "i",
        "me",
        "not",
        "and",
        "or",
        "a",
        "an",
        "to",
        "of",
        "this",
        "that",
        "it",
    }
    return {
        token
        for token in re.findall(r"[A-Za-z0-9]+", text.lower())
        if len(token) >= 3 and token not in stopwords
    }


def lexical_score(record: LongTermMemoryRecord, terms: set[str]) -> float:
    """Score a record against lexical terms."""
    if not terms:
        return 0.0
    record_terms = important_terms(
        " ".join([record.key, record.value, json.dumps(record.metadata)])
    )
    overlap = len(record_terms & terms)
    if overlap == 0:
        return 0.0
    return overlap / max(1, len(terms))


def _filter_unexpired(
    records: list[LongTermMemoryRecord],
) -> list[LongTermMemoryRecord]:
    """Filter out records whose expires_at timestamp has passed."""
    return [record for record in records if not record.is_expired()]
