from __future__ import annotations

import os

from src.core.contracts import MemoryCandidate, SourcePlan
from src.database import Database
from src.memory.long_term_store import (
    LongTermMemoryRecord,
    SQLiteLongTermMemoryStore,
    dedupe_memory_records,
    namespace_path,
    record_to_candidate,
    structured_memory_namespaces,
)
from src.memory.long_term_vector_index import LongTermMemoryVectorIndex
from src.memory.memory_trace import print_retrieved_memory_traces
from src.memory.structured_state import active_memories, load_memory_state
from src.memory.long_term_vector_index import VectorIndexUnavailable


STRUCTURED_MEMORY_RETRIEVAL_MODES = {"sqlite", "vector", "hybrid"}


class StructuredMemoryRetriever:
    """Retrieve active structured memory records for the current chat."""

    def __init__(
        self,
        database: Database,
        mode: str | None = None,
        vector_index: LongTermMemoryVectorIndex | None = None,
    ) -> None:
        self.database = database
        self.long_term_store = SQLiteLongTermMemoryStore(database)
        self.mode = normalize_structured_memory_retrieval_mode(
            mode or os.getenv("STRUCTURED_MEMORY_RETRIEVAL_MODE", "sqlite")
        )
        self.vector_index = vector_index

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        """Load active structured memory and normalize records as candidates."""
        if self.mode == "vector":
            return self._retrieve_vector_or_fallback(chat_id, source_plan)
        if self.mode == "hybrid":
            return self._retrieve_hybrid(chat_id, source_plan)
        return self._retrieve_sqlite(chat_id, source_plan)

    def _retrieve_sqlite(
        self,
        chat_id: str,
        source_plan: SourcePlan,
    ) -> list[MemoryCandidate]:
        """Retrieve structured memories with the existing SQLite behavior."""
        query = source_plan.query
        store_records = []
        for namespace in structured_memory_namespaces(chat_id):
            if query:
                store_records.extend(
                    self.long_term_store.search(
                        namespace_prefix=namespace,
                        query=query,
                        limit=source_plan.limit or 10,
                    )
                )
            else:
                store_records.extend(self.long_term_store.list(namespace))

        store_records = [
            record for record in dedupe_memory_records(store_records) if record.status == "active"
        ]
        if store_records:
            print_retrieved_memory_traces(chat_id, store_records)
            return [record_to_candidate(record) for record in store_records]

        # Primary path returned empty — supplement chat_memory_state with DB records
        # so manually reactivated memories are not lost when the LangMem snapshot is stale.
        del source_plan
        memory_state = load_memory_state(self.database.chat_memory_state(chat_id))
        db_records: list[LongTermMemoryRecord] = []
        for namespace in structured_memory_namespaces(chat_id):
            db_records.extend(self.long_term_store.list(namespace))
        db_active = {record.memory_id: record for record in db_records if record.status == "active"}
        candidates: list[MemoryCandidate] = []
        seen_ids: set[str] = set()
        for record in active_memories(memory_state):
            seen_ids.add(str(record["id"]))
            source_message_ids = record.get("source_message_ids", [])
            confidence = record.get("confidence")
            candidates.append(
                MemoryCandidate(
                    source="structured_memory",
                    content=str(record["value"]),
                    score=float(confidence) if isinstance(confidence, int | float) else None,
                    record_id=str(record["id"]),
                    chat_id=chat_id,
                    source_message_ids=[
                        source_id for source_id in source_message_ids if isinstance(source_id, int)
                    ],
                    metadata={
                        "category": record["category"],
                        "key": record["key"],
                        "status": record["status"],
                        "confidence": confidence,
                    },
                )
            )
        # Append DB-active records not already present in chat_memory_state
        for memory_id, db_record in db_active.items():
            if memory_id in seen_ids:
                continue
            candidates.append(record_to_candidate(db_record))
        return candidates

    def _retrieve_vector_or_fallback(
        self,
        chat_id: str,
        source_plan: SourcePlan,
    ) -> list[MemoryCandidate]:
        """Retrieve through vector index, falling back to existing SQLite behavior."""
        try:
            records = self._vector_records(chat_id, source_plan)
        except VectorIndexUnavailable as error:
            print(f"structured_memory_vector_unavailable reason={error}")
            return self._retrieve_sqlite(chat_id, source_plan)
        except Exception as error:
            print(f"structured_memory_vector_failed reason={type(error).__name__}: {error}")
            return self._retrieve_sqlite(chat_id, source_plan)

        active_records = [record for record in records if record.status == "active"]
        if not active_records:
            return self._retrieve_sqlite(chat_id, source_plan)
        print_retrieved_memory_traces(chat_id, active_records)
        return [
            vector_record_to_candidate(record) for record in dedupe_memory_records(active_records)
        ]

    def _retrieve_hybrid(
        self,
        chat_id: str,
        source_plan: SourcePlan,
    ) -> list[MemoryCandidate]:
        """Combine vector and SQLite records, deduplicating by namespace/memory id."""
        sqlite_candidates = self._retrieve_sqlite(chat_id, source_plan)
        try:
            vector_records = self._vector_records(chat_id, source_plan)
        except VectorIndexUnavailable as error:
            print(f"structured_memory_vector_unavailable reason={error}")
            return sqlite_candidates
        except Exception as error:
            print(f"structured_memory_vector_failed reason={type(error).__name__}: {error}")
            return sqlite_candidates

        combined_records = [
            *[
                candidate_to_record(candidate)
                for candidate in sqlite_candidates
                if candidate.source == "structured_memory"
            ],
            *vector_records,
        ]
        records = [
            record
            for record in dedupe_memory_records(combined_records)
            if record.status == "active"
        ]
        if not records:
            return sqlite_candidates
        print_retrieved_memory_traces(chat_id, records)
        return [hybrid_record_to_candidate(record) for record in records][: source_plan.limit or 10]

    def _vector_index(self) -> LongTermMemoryVectorIndex:
        """Return the cached long-term memory vector index, creating it once."""
        if self.vector_index is None:
            self.vector_index = LongTermMemoryVectorIndex.from_env(database=self.database)
        return self.vector_index

    def _vector_records(
        self,
        chat_id: str,
        source_plan: SourcePlan,
    ) -> list[LongTermMemoryRecord]:
        """Load store records referenced by vector search results."""
        query = source_plan.query or ""
        index = self._vector_index()
        results = index.search(query=query, limit=source_plan.limit or 10)
        records = []
        allowed_namespaces = {
            namespace_path(namespace) for namespace in structured_memory_namespaces(chat_id)
        }
        for result in results:
            if namespace_path(result.namespace) not in allowed_namespaces:
                continue
            record = self.long_term_store.get(result.namespace, result.memory_id)
            if record is None:
                continue
            metadata = dict(record.metadata)
            metadata.update(
                {
                    "retrieval_mode": "vector",
                    "vector_score": result.score,
                    "retrieval_backend": "long_term_memory_sqlite_vec",
                }
            )
            records.append(
                LongTermMemoryRecord(
                    namespace=record.namespace,
                    memory_id=record.memory_id,
                    category=record.category,
                    key=record.key,
                    value=record.value,
                    confidence=record.confidence,
                    status=record.status,
                    source_chat_id=record.source_chat_id,
                    source_message_ids=list(record.source_message_ids),
                    source_gist_id=record.source_gist_id,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                    metadata=metadata,
                )
            )
        return records


def normalize_structured_memory_retrieval_mode(mode: str) -> str:
    """Return a supported structured memory retrieval mode."""
    normalized = (mode or "sqlite").strip().lower()
    return normalized if normalized in STRUCTURED_MEMORY_RETRIEVAL_MODES else "sqlite"


def vector_record_to_candidate(record: LongTermMemoryRecord) -> MemoryCandidate:
    """Convert a vector-retrieved record to a MemoryCandidate."""
    candidate = record_to_candidate(record)
    metadata = dict(candidate.metadata)
    vector_score = metadata.get("vector_score")
    score = float(vector_score) if isinstance(vector_score, int | float) else candidate.score
    metadata["retrieval_mode"] = "vector"
    metadata.setdefault("retrieval_backend", "long_term_memory_sqlite_vec")
    return MemoryCandidate(
        source=candidate.source,
        content=candidate.content,
        score=score,
        record_id=candidate.record_id,
        chat_id=candidate.chat_id,
        source_message_ids=list(candidate.source_message_ids),
        metadata=metadata,
    )


def hybrid_record_to_candidate(record: LongTermMemoryRecord) -> MemoryCandidate:
    """Convert a hybrid-retrieved record to a MemoryCandidate."""
    candidate = record_to_candidate(record)
    metadata = dict(candidate.metadata)
    metadata["retrieval_mode"] = "hybrid"
    return MemoryCandidate(
        source=candidate.source,
        content=candidate.content,
        score=candidate.score,
        record_id=candidate.record_id,
        chat_id=candidate.chat_id,
        source_message_ids=list(candidate.source_message_ids),
        metadata=metadata,
    )


def candidate_to_record(candidate: MemoryCandidate) -> LongTermMemoryRecord:
    """Convert a structured MemoryCandidate back to a record for deduplication."""
    metadata = dict(candidate.metadata)
    namespace_value = metadata.get("namespace")
    if isinstance(namespace_value, list | tuple):
        namespace = tuple(str(item) for item in namespace_value)
    elif isinstance(namespace_value, str):
        namespace = tuple(namespace_value.split("::"))
    else:
        namespace = ("candidate", str(candidate.chat_id or "unknown"))
    return LongTermMemoryRecord(
        namespace=namespace,
        memory_id=str(metadata.get("memory_id") or candidate.record_id),
        category=str(metadata.get("category") or "unknown"),
        key=str(metadata.get("key") or candidate.record_id),
        value=candidate.content,
        confidence=float(candidate.score if candidate.score is not None else 0.5),
        status=str(metadata.get("status") or "active"),
        source_chat_id=metadata.get("source_chat_id") or candidate.chat_id,
        source_message_ids=list(candidate.source_message_ids),
        source_gist_id=metadata.get("source_gist_id"),
        metadata=metadata,
    )
