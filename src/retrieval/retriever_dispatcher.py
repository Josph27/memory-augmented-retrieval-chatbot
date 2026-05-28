from __future__ import annotations

from typing import Protocol

from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan
from src.database import Database
from src.memory.constants import RAW_MESSAGE_LIMIT
from src.retrieval.recent_messages_retriever import RecentMessagesRetriever
from src.retrieval.structured_memory_retriever import StructuredMemoryRetriever


class SourceRetriever(Protocol):
    """Protocol implemented by source-specific retrievers."""

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        """Return normalized memory candidates for one source."""
        ...


class RetrieverDispatcher:
    """Dispatch enabled route-plan sources to their retrievers."""

    def __init__(
        self,
        database: Database,
        raw_message_limit: int = RAW_MESSAGE_LIMIT,
        retrievers: dict[str, SourceRetriever] | None = None,
    ) -> None:
        self.retrievers: dict[str, SourceRetriever] = retrievers or {
            "recent_messages": RecentMessagesRetriever(database, default_limit=raw_message_limit),
            "structured_memory": StructuredMemoryRetriever(database),
        }

    def retrieve(self, chat_id: str, route_plan: RoutePlan) -> list[MemoryCandidate]:
        """Retrieve candidates from enabled sources only."""
        candidates: list[MemoryCandidate] = []
        for source_plan in route_plan.sources:
            if not source_plan.enabled:
                continue

            retriever = self.retrievers.get(source_plan.source)
            if retriever is None:
                continue

            candidates.extend(retriever.retrieve(chat_id=chat_id, source_plan=source_plan))
        return candidates
