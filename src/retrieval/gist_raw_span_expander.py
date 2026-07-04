from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TypeVar

from src.core.contracts import MemoryCandidate
from src.database import Database, StoredMessage
from src.retrieval.current_chat_span_retriever import content_terms
from src.retrieval.raw_message_span_retriever import (
    DEFAULT_RAW_SPAN_MAX_CHARS,
    format_messages,
    format_raw_span_with_anchor,
)


DEFAULT_GIST_EXPANSION_MAX_MESSAGES = 12
MAX_DIAGNOSTIC_MESSAGE_IDS = 20
GIST_SOURCES = {"current_chat_gist", "previous_chat_gist"}
ValueT = TypeVar("ValueT")


@dataclass
class GistSpanRequest:
    """One or more gist candidates pointing to a raw chat span."""

    chat_id: str
    start_message_id: int
    end_message_id: int
    parents: list[MemoryCandidate] = field(default_factory=list)


class GistRawSpanExpander:
    """Expand retrieved gist orientation into bounded exact SQLite evidence."""

    def __init__(
        self,
        database: Database | None,
        max_messages: int = DEFAULT_GIST_EXPANSION_MAX_MESSAGES,
        max_chars: int = DEFAULT_RAW_SPAN_MAX_CHARS,
    ) -> None:
        self.database = database
        self.max_messages = max(1, max_messages)
        self.max_chars = max(1, max_chars)

    def expand(
        self,
        candidates: list[MemoryCandidate],
        query: str,
    ) -> list[MemoryCandidate]:
        """Return deduplicated bounded raw spans for gist candidates with provenance."""
        if self.database is None:
            return []
        requests = [
            request
            for candidate in candidates
            if candidate.source in GIST_SOURCES
            if (request := self._request_for(candidate)) is not None
        ]
        expanded: list[MemoryCandidate] = []
        for request in merge_requests(requests):
            messages = self.database.messages_for_chat_span(
                chat_id=request.chat_id,
                start_message_id=request.start_message_id,
                end_message_id=request.end_message_id,
            )
            if not messages:
                continue
            included = bounded_messages(
                messages,
                query=query,
                max_messages=self.max_messages,
            )
            if not included:
                continue
            anchor_ids = best_message_ids(included, query)
            content = format_raw_span_with_anchor(
                included,
                anchor_message_ids=anchor_ids,
                max_chars=self.max_chars,
                query=query,
            )
            full_content = format_messages(included)
            included_ids = [message.id for message in included]
            selection_reason = (
                "all_provenance_messages_fit"
                if len(included) == len(messages)
                else "query_centered_contiguous_window"
            )
            parent_ids = unique_values(
                parent.record_id
                for parent in request.parents
                if parent.record_id is not None
            )
            parent_sources = unique_values(parent.source for parent in request.parents)
            parent_scores = [
                parent.score
                for parent in request.parents
                if parent.score is not None
            ]
            expanded.append(
                MemoryCandidate(
                    source="raw_message_span",
                    content=content,
                    score=max(parent_scores, default=0.5),
                    record_id=(
                        f"gist-expanded:{request.chat_id}:"
                        f"{included_ids[0]}-{included_ids[-1]}"
                    ),
                    chat_id=request.chat_id,
                    source_message_ids=included_ids,
                    metadata={
                        "source_chat_id": request.chat_id,
                        "start_message_id": included_ids[0],
                        "end_message_id": included_ids[-1],
                        "original_start_message_id": request.start_message_id,
                        "original_end_message_id": request.end_message_id,
                        "parent_gist_id": parent_ids[0] if len(parent_ids) == 1 else None,
                        "parent_gist_ids": parent_ids,
                        "parent_source": (
                            parent_sources[0] if len(parent_sources) == 1 else None
                        ),
                        "parent_sources": parent_sources,
                        "anchor_message_ids": sorted(anchor_ids),
                        "provenance_message_count": len(messages),
                        "included_message_ids": included_ids[
                            :MAX_DIAGNOSTIC_MESSAGE_IDS
                        ],
                        "omitted_message_ids_count": max(
                            0,
                            len(messages) - len(included),
                        ),
                        "selection_reason": selection_reason,
                        "window_char_count": len(content),
                        "derived_from_source": (
                            parent_sources[0] if len(parent_sources) == 1 else None
                        ),
                        "message_count": len(included),
                        "original_message_count": len(messages),
                        "truncated": (
                            len(included) < len(messages) or content != full_content
                        ),
                        "retrieval_mode": "gist_provenance_expansion",
                        "retrieval_path": "gist_expansion",
                        "retrieval_paths": ["gist_expansion"],
                        "span_kind": "gist_expanded_exact_raw",
                        "status": "active",
                    },
                )
            )
        return expanded

    def _request_for(self, candidate: MemoryCandidate) -> GistSpanRequest | None:
        """Resolve one gist candidate's best available persisted provenance."""
        chat_id = candidate.chat_id
        start_id = int_metadata(candidate.metadata, "start_message_id")
        end_id = int_metadata(candidate.metadata, "end_message_id")

        if isinstance(candidate.record_id, int):
            gist = self.database.chat_gist(candidate.record_id) if self.database else None
            if gist is not None:
                chat_id = gist.chat_id
                start_id = gist.start_message_id
                end_id = gist.end_message_id

        if (start_id is None or end_id is None) and candidate.source_message_ids:
            start_id = min(candidate.source_message_ids)
            end_id = max(candidate.source_message_ids)

        if not chat_id or start_id is None or end_id is None:
            return None
        return GistSpanRequest(
            chat_id=chat_id,
            start_message_id=min(start_id, end_id),
            end_message_id=max(start_id, end_id),
            parents=[candidate],
        )


def merge_requests(requests: list[GistSpanRequest]) -> list[GistSpanRequest]:
    """Merge overlapping gist ranges without collapsing adjacent segments."""
    merged: list[GistSpanRequest] = []
    for request in sorted(
        requests,
        key=lambda item: (item.chat_id, item.start_message_id, item.end_message_id),
    ):
        if (
            not merged
            or merged[-1].chat_id != request.chat_id
            or request.start_message_id > merged[-1].end_message_id
        ):
            merged.append(request)
            continue
        previous = merged[-1]
        previous.end_message_id = max(
            previous.end_message_id,
            request.end_message_id,
        )
        previous.parents.extend(request.parents)
    return merged


def bounded_messages(
    messages: list[StoredMessage],
    *,
    query: str,
    max_messages: int,
) -> list[StoredMessage]:
    """Select a bounded chronological window around the best lexical message."""
    if len(messages) <= max_messages:
        return messages
    query_terms = content_terms(query)
    best_index = max(
        range(len(messages)),
        key=lambda index: (
            len(query_terms & content_terms(messages[index].content)),
            messages[index].id,
        ),
    )
    start = max(0, best_index - max_messages // 2)
    start = min(start, len(messages) - max_messages)
    return messages[start : start + max_messages]


def best_message_ids(
    messages: list[StoredMessage],
    query: str,
) -> set[int]:
    """Return the query-best raw message IDs that char truncation must retain."""
    query_terms = content_terms(query)
    if not query_terms:
        return {messages[-1].id}
    best_overlap = max(
        len(query_terms & content_terms(message.content))
        for message in messages
    )
    if best_overlap <= 0:
        return {messages[-1].id}
    return {
        message.id
        for message in messages
        if len(query_terms & content_terms(message.content)) == best_overlap
    }


def int_metadata(metadata: dict[str, object], name: str) -> int | None:
    """Read a non-boolean integer from candidate metadata."""
    value = metadata.get(name)
    return value if type(value) is int else None


def unique_values(values: Iterable[ValueT]) -> list[ValueT]:
    """Return stable unique values without requiring hashability."""
    unique = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique
