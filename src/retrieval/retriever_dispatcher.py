from __future__ import annotations

import os
from typing import Protocol

from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan
from src.database import Database
from src.memory.constants import RAW_MESSAGE_LIMIT
from src.retrieval.document_retriever import DocumentRetriever
from src.retrieval.langchain_chroma_retriever import LangChainChromaRetriever
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
        legacy_document_retriever = DocumentRetriever.from_env(database)
        self.retrievers: dict[str, SourceRetriever] = retrievers or {
            "recent_messages": RecentMessagesRetriever(database, default_limit=raw_message_limit),
            "structured_memory": StructuredMemoryRetriever(database),
            "document_memory": document_retriever_for_env(database, legacy_document_retriever),
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


def document_retriever_for_env(
    database: Database,
    legacy_document_retriever: DocumentRetriever | None = None,
) -> SourceRetriever:
    """Select primary LangChain-Chroma or legacy document retrieval backend."""
    legacy = legacy_document_retriever or DocumentRetriever.from_env(database)
    mode = os.getenv("DOCUMENT_RETRIEVAL_MODE", "langchain_chroma").strip().lower()
    if mode == "langchain_chroma":
        return LangChainChromaRetriever.from_env(
            database=database,
            fallback_retriever=DocumentRetriever(database=database, retrieval_mode="keyword"),
        )
    return legacy
