from __future__ import annotations

import re
from dataclasses import dataclass

from src.core.contracts import MemoryCandidate, SourcePlan
from src.database import Database, StoredMessage


DEFAULT_MAX_SPANS = 3
DEFAULT_WINDOW_MESSAGES = 2
STOPWORDS = {
    "a",
    "about",
    "an",
    "and",
    "did",
    "do",
    "earlier",
    "exact",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "said",
    "say",
    "the",
    "this",
    "to",
    "use",
    "what",
}
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class MessageHit:
    """One deterministic lexical message match."""

    index: int
    message_id: int
    score: float


class CurrentChatSpanRetriever:
    """Retrieve exact raw transcript windows from the current chat only."""

    def __init__(
        self,
        database: Database,
        max_spans: int = DEFAULT_MAX_SPANS,
        window_messages: int = DEFAULT_WINDOW_MESSAGES,
    ) -> None:
        self.database = database
        self.max_spans = max(1, max_spans)
        self.window_messages = max(0, window_messages)

    def retrieve(
        self,
        chat_id: str,
        source_plan: SourcePlan,
    ) -> list[MemoryCandidate]:
        """Return merged exact-message windows matching the source query."""
        query = source_plan.query or ""
        query_terms = content_terms(query)
        if not query_terms:
            return []

        messages = self.database.messages_for_chat(chat_id)
        excluded_ids = int_set_filter(source_plan.filters, "exclude_message_ids")
        excluded_text = str(
            source_plan.filters.get("exclude_message_text", query)
        ).strip()
        hits = scored_hits(
            messages=messages,
            query_terms=query_terms,
            excluded_ids=excluded_ids,
            excluded_text=excluded_text,
        )
        if not hits:
            return []

        max_spans = positive_int_filter(
            source_plan.filters,
            "max_spans",
            default=source_plan.limit or self.max_spans,
        )
        window_messages = positive_int_filter(
            source_plan.filters,
            "window_messages",
            default=self.window_messages,
            allow_zero=True,
        )
        selected_hits = hits[:max_spans]
        ranges = merge_ranges(
            [
                (
                    max(0, hit.index - window_messages),
                    min(len(messages) - 1, hit.index + window_messages),
                )
                for hit in selected_hits
            ]
        )

        candidates: list[MemoryCandidate] = []
        for start_index, end_index in ranges:
            span_messages = [
                message
                for message in messages[start_index : end_index + 1]
                if message.id not in excluded_ids
                and not is_excluded_current_query(message, excluded_text)
            ]
            if not span_messages:
                continue
            span_ids = [message.id for message in span_messages]
            matched_ids = [
                hit.message_id
                for hit in selected_hits
                if start_index <= hit.index <= end_index
            ]
            score = max(
                hit.score
                for hit in selected_hits
                if start_index <= hit.index <= end_index
            )
            candidates.append(
                MemoryCandidate(
                    source="current_chat_span",
                    content=format_exact_messages(span_messages),
                    score=score,
                    record_id=f"{chat_id}:{span_ids[0]}-{span_ids[-1]}",
                    chat_id=chat_id,
                    source_message_ids=span_ids,
                    metadata={
                        "source_chat_id": chat_id,
                        "start_message_id": span_ids[0],
                        "end_message_id": span_ids[-1],
                        "matched_message_ids": matched_ids,
                        "message_count": len(span_messages),
                        "span_kind": "current_chat_exact_raw",
                        "retrieval_reason": "deterministic_lexical_match",
                        "retrieval_mode": "sqlite_current_chat_span",
                        "status": "active",
                    },
                )
            )
        return sorted(
            candidates,
            key=lambda candidate: (
                -(candidate.score or 0.0),
                -int(candidate.metadata["end_message_id"]),
            ),
        )


def scored_hits(
    *,
    messages: list[StoredMessage],
    query_terms: set[str],
    excluded_ids: set[int],
    excluded_text: str,
) -> list[MessageHit]:
    """Score current-chat messages by deterministic lexical overlap."""
    hits: list[MessageHit] = []
    for index, message in enumerate(messages):
        if message.id in excluded_ids or is_excluded_current_query(
            message,
            excluded_text,
        ):
            continue
        overlap = len(query_terms & content_terms(message.content))
        if overlap <= 0:
            continue
        role_boost = 0.1 if message.role == "user" else 0.0
        score = min(1.0, overlap / max(1, len(query_terms)) + role_boost)
        hits.append(MessageHit(index=index, message_id=message.id, score=score))
    return sorted(
        hits,
        key=lambda hit: (-hit.score, -hit.message_id),
    )


def merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or adjacent inclusive message-index ranges."""
    if not ranges:
        return []
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if not merged or start > merged[-1][1] + 1:
            merged.append((start, end))
            continue
        previous_start, previous_end = merged[-1]
        merged[-1] = (previous_start, max(previous_end, end))
    return merged


def format_exact_messages(messages: list[StoredMessage]) -> str:
    """Format source-of-truth messages in persisted chronological order."""
    return "\n".join(f"{message.role}: {message.content}" for message in messages)


def content_terms(value: str) -> set[str]:
    """Return normalized non-stopword lexical terms."""
    return {
        token
        for token in TOKEN_PATTERN.findall(value.lower())
        if token not in STOPWORDS and len(token) > 1
    }


def is_excluded_current_query(message: StoredMessage, excluded_text: str) -> bool:
    """Return whether a user message duplicates the separately supplied query."""
    return (
        message.role == "user"
        and bool(excluded_text)
        and normalize_text(message.content) == normalize_text(excluded_text)
    )


def normalize_text(value: str) -> str:
    """Normalize text for exact current-query duplicate detection."""
    return " ".join(value.lower().split())


def int_set_filter(filters: dict[str, object], name: str) -> set[int]:
    """Read a set of integer IDs from source-plan filters."""
    value = filters.get(name, [])
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {item for item in value if type(item) is int}


def positive_int_filter(
    filters: dict[str, object],
    name: str,
    *,
    default: int,
    allow_zero: bool = False,
) -> int:
    """Read one bounded integer source-plan option."""
    value = filters.get(name)
    if type(value) is not int:
        return max(0 if allow_zero else 1, default)
    lower_bound = 0 if allow_zero else 1
    return max(lower_bound, value)
