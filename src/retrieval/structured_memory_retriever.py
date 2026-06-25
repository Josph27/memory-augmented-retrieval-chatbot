from __future__ import annotations

from src.core.contracts import MemoryCandidate, SourcePlan
from src.database import Database
from src.memory.long_term_store import (
    SQLiteLongTermMemoryStore,
    dedupe_memory_records,
    record_to_candidate,
    structured_memory_namespaces,
)
from src.memory.memory_trace import print_retrieved_memory_traces
from src.memory.structured_state import active_memories, load_memory_state


class StructuredMemoryRetriever:
    """Retrieve active structured memory records for the current chat."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.long_term_store = SQLiteLongTermMemoryStore(database)

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        """Load active structured memory and normalize records as candidates."""
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

        store_records = [record for record in dedupe_memory_records(store_records) if record.status == "active"]
        if store_records:
            print_retrieved_memory_traces(chat_id, store_records)
            return [record_to_candidate(record) for record in store_records]

        del source_plan
        memory_state = load_memory_state(self.database.chat_memory_state(chat_id))
        candidates: list[MemoryCandidate] = []
        for record in active_memories(memory_state):
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
        return candidates
