from __future__ import annotations

import os
from typing import Protocol

from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan
from src.database import Database
from src.memory.constants import RECENT_MESSAGES_MAX_COUNT
from src.retrieval.current_chat_gist_retriever import CurrentChatGistRetriever
from src.retrieval.current_chat_span_retriever import CurrentChatSpanRetriever
from src.retrieval.gist_raw_span_expander import GistRawSpanExpander
from src.retrieval.langchain_chroma_retriever import LangChainChromaRetriever
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.retrieval.raw_message_span_retriever import RawMessageSpanRetriever
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
        raw_message_limit: int = RECENT_MESSAGES_MAX_COUNT,
        retrievers: dict[str, SourceRetriever] | None = None,
        gist_expander: GistRawSpanExpander | None = None,
    ) -> None:
        self.gist_expander = gist_expander or GistRawSpanExpander(database)
        self.retrievers: dict[str, SourceRetriever] = retrievers or {
            "recent_messages": RecentMessagesRetriever(database, default_limit=raw_message_limit),
            "structured_memory": StructuredMemoryRetriever(database),
            "document_memory": langchain_chroma_retriever_for_env(database),
            "current_chat_gist": CurrentChatGistRetriever(database),
            "current_chat_span": CurrentChatSpanRetriever(database),
            "previous_chat_gist": PreviousChatGistRetriever(database),
            "raw_message_span": RawMessageSpanRetriever(database),
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
        return candidates + self.gist_expander.expand(
            candidates,
            query=route_plan.query,
        )


def langchain_chroma_retriever_for_env(database: Database) -> SourceRetriever:
    """Select the LangChain-Chroma document retrieval backend."""
    mode = os.getenv("DOCUMENT_RETRIEVAL_MODE", "langchain_chroma").strip().lower()
    if mode != "langchain_chroma":
        print(
            "unsupported_document_retrieval_mode "
            f"mode={mode!r} falling_back_to='langchain_chroma'"
        )
    del database
    return LangChainChromaRetriever.from_env()
