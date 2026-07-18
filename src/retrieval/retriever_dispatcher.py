from __future__ import annotations

import os
from dataclasses import replace
from typing import Protocol

from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan
from src.database import Database
from src.documents.registry import DocumentRegistry, DocumentScopeError
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
        direct_raw_candidate_limit: int | None = None,
        summary_getter: object | None = None,
    ) -> None:
        self.database = database
        self.last_errors: list[dict[str, str]] = []
        self.gist_expander = gist_expander or GistRawSpanExpander(database)
        _defaults: dict[str, SourceRetriever] = {
            "recent_messages": RecentMessagesRetriever(database, default_limit=raw_message_limit),
            "structured_memory": StructuredMemoryRetriever(database),
            "document_memory": langchain_chroma_retriever_for_env(
                database, summary_getter=summary_getter
            ),
            "current_chat_gist": CurrentChatGistRetriever(database),
            "current_chat_span": CurrentChatSpanRetriever(database),
            "previous_chat_gist": PreviousChatGistRetriever(database),
            "raw_message_span": RawMessageSpanRetriever(
                database,
                direct_limit=direct_raw_candidate_limit,
            ),
        }
        if retrievers:
            _defaults.update(retrievers)
        self.retrievers = _defaults

    def retrieve(self, chat_id: str, route_plan: RoutePlan) -> list[MemoryCandidate]:
        """Retrieve candidates from enabled sources only."""
        self.last_errors = []
        candidates: list[MemoryCandidate] = []
        for source_plan in route_plan.sources:
            if not source_plan.enabled:
                continue

            retriever = self.retrievers.get(source_plan.source)
            if retriever is None:
                continue

            plan = source_plan
            if source_plan.source == "document_memory":
                try:
                    plan = self.scoped_source_plan(chat_id, source_plan)
                except DocumentScopeError as error:
                    self.last_errors.append(
                        {
                            "source": "document_memory",
                            "type": type(error).__name__,
                            "message": str(error),
                        }
                    )
                    continue
                # Boost limit for document-oriented intents so more chunks
                # are retrieved for structured queries (e.g. "problem 3").
                context_profile = plan.filters.get("context_profile", "")
                if context_profile == "document_question" and plan.limit is None:
                    plan = replace(plan, limit=40)
            try:
                retrieved = retriever.retrieve(chat_id=chat_id, source_plan=plan)
                if (
                    source_plan.source == "document_memory"
                    and not retrieved
                    and plan.filters.get("allowed_document_ids")
                ):
                    fallback_query = " ".join(
                        [
                            source_plan.query or route_plan.query,
                            *plan.filters.get("allowed_document_names", []),
                        ]
                    ).strip()
                    retrieved = retriever.retrieve(
                        chat_id=chat_id,
                        source_plan=replace(plan, query=fallback_query),
                    )
                candidates.extend(retrieved)
            except Exception as error:
                self.last_errors.append(
                    {
                        "source": str(source_plan.source),
                        "type": type(error).__name__,
                        "message": str(error),
                    }
                )
        return candidates + self.gist_expander.expand(
            candidates,
            query=route_plan.query,
        )

    def expand_document_neighbors(
        self,
        candidates: list[MemoryCandidate],
    ) -> list[MemoryCandidate]:
        """Expand document candidates with ±1 neighboring chunks inline.

        Must be called *after* reranking so the cross-encoder sees clean
        single-chunk text. Neighbors are fetched from the document_memory
        retriever's Chroma vectorstore. Non-document candidates pass through
        unchanged.
        """
        doc_retriever = self.retrievers.get("document_memory")
        if doc_retriever is None:
            return candidates
        from src.retrieval.langchain_chroma_retriever import _expand_neighbors

        vs = getattr(doc_retriever, "_vectorstore", None)
        if vs is None:
            return candidates
        return _expand_neighbors(candidates, vectorstore=vs())

    def scoped_source_plan(
        self,
        chat_id: str,
        source_plan: SourcePlan,
    ) -> SourcePlan:
        """Apply persisted source scope before any retriever invocation."""
        if source_plan.source != "document_memory":
            return source_plan
        if "allowed_document_ids" in source_plan.filters:
            return source_plan
        if self.database is None or self.database.get_chat(chat_id) is None:
            return source_plan
        resolution = DocumentRegistry(self.database).resolve(
            chat_id,
            source_plan.query or "",
        )
        filters = {
            **source_plan.filters,
            "allowed_document_ids": list(resolution.document_ids),
            "allowed_document_names": list(resolution.file_names),
            "document_resolution_reason": resolution.reason,
        }
        return replace(source_plan, filters=filters)


def langchain_chroma_retriever_for_env(
    database: Database,
    summary_getter: object | None = None,
) -> SourceRetriever:
    """Select the LangChain-Chroma document retrieval backend."""
    mode = os.getenv("DOCUMENT_RETRIEVAL_MODE", "langchain_chroma").strip().lower()
    if mode != "langchain_chroma":
        print(
            f"unsupported_document_retrieval_mode mode={mode!r} falling_back_to='langchain_chroma'"
        )
    del database
    return LangChainChromaRetriever.from_env(summary_getter=summary_getter)
