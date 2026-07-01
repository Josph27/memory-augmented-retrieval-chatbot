from __future__ import annotations

import os
import re

from src.core.contracts import MemoryCandidate, SourcePlan
from src.database import Database, StoredMessage

DEFAULT_RAW_SPAN_MAX_CHARS = 4000
TRUNCATION_MARKER = "\n[raw message span truncated]"
EARLIER_OMISSION_MARKER = "[... earlier messages omitted ...]"
INTERVENING_OMISSION_MARKER = "[... intervening messages omitted ...]"
LATER_OMISSION_MARKER = "[... later messages omitted ...]"
ANCHOR_START_OMISSION_MARKER = "[raw message span truncated before anchor]"
ANCHOR_END_OMISSION_MARKER = "[raw message span truncated after anchor]"
QUERY_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")


class RawMessageSpanRetriever:
    """Retrieve source-of-truth raw messages for an explicit message-id span."""

    def __init__(self, database: Database, max_chars: int | None = None) -> None:
        self.database = database
        self.max_chars = (
            raw_span_max_chars_from_env() if max_chars is None else max_chars
        )

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        """Return a raw message span candidate when span filters are provided."""
        span = self._span_from_plan(chat_id=chat_id, source_plan=source_plan)
        if span is None:
            return []

        span_chat_id, start_message_id, end_message_id, gist_id = span
        messages = self.database.messages_for_chat_span(
            chat_id=span_chat_id,
            start_message_id=start_message_id,
            end_message_id=end_message_id,
        )
        if not messages:
            return []

        anchor_ids = anchor_message_ids_for_plan(
            messages=messages,
            source_plan=source_plan,
        )
        content = format_raw_span_with_anchor(
            messages,
            anchor_message_ids=anchor_ids,
            max_chars=self.max_chars,
            query=source_plan.query,
        )
        truncated = len(content) < len(format_messages(messages))
        return [
            MemoryCandidate(
                source="raw_message_span",
                content=content,
                score=1.0,
                record_id=gist_id or f"{span_chat_id}:{start_message_id}-{end_message_id}",
                chat_id=span_chat_id,
                source_message_ids=[message.id for message in messages],
                metadata={
                    "source_chat_id": span_chat_id,
                    "start_message_id": start_message_id,
                    "end_message_id": end_message_id,
                    "message_count": len(messages),
                    "gist_id": gist_id,
                    "anchor_message_ids": sorted(anchor_ids),
                    "truncated": truncated,
                    "retrieval_mode": "raw_span_lookup",
                    "status": "active",
                },
            )
        ]

    def _span_from_plan(
        self,
        chat_id: str,
        source_plan: SourcePlan,
    ) -> tuple[str, int, int, int | None] | None:
        """Read span filters or resolve them from a gist id."""
        filters = source_plan.filters
        gist_id = int_filter(filters, "gist_id")
        if gist_id is not None:
            gist = self.database.chat_gist(gist_id)
            if (
                gist is not None
                and gist.start_message_id is not None
                and gist.end_message_id is not None
            ):
                return (
                    gist.chat_id,
                    gist.start_message_id,
                    gist.end_message_id,
                    gist.id,
                )

        start_message_id = int_filter(
            filters,
            "start_message_id",
            "message_start_id",
            "start_id",
        )
        end_message_id = int_filter(
            filters,
            "end_message_id",
            "message_end_id",
            "end_id",
        )
        span_chat_id = filters.get("chat_id", chat_id)
        if (
            isinstance(span_chat_id, str)
            and start_message_id is not None
            and end_message_id is not None
        ):
            return (span_chat_id, start_message_id, end_message_id, None)
        return None


def source_plan_for_gist_candidate(candidate: MemoryCandidate) -> SourcePlan | None:
    """Build an explicit raw-span source plan from a gist candidate."""
    if candidate.source not in {"current_chat_gist", "previous_chat_gist"}:
        return None

    gist_id = candidate.record_id if isinstance(candidate.record_id, int) else None
    if gist_id is not None:
        return SourcePlan(
            source="raw_message_span",
            enabled=True,
            reason="Fetch raw messages linked from gist candidate.",
            filters={"gist_id": gist_id},
        )

    start_message_id = int_filter(candidate.metadata, "start_message_id")
    end_message_id = int_filter(candidate.metadata, "end_message_id")
    if (
        candidate.chat_id is not None
        and start_message_id is not None
        and end_message_id is not None
    ):
        return SourcePlan(
            source="raw_message_span",
            enabled=True,
            reason="Fetch raw messages linked from gist candidate metadata.",
            filters={
                "chat_id": candidate.chat_id,
                "start_message_id": start_message_id,
                "end_message_id": end_message_id,
            },
        )

    return None


def format_messages(
    messages: list[StoredMessage],
    max_chars: int | None = None,
) -> str:
    """Format raw messages compactly for span drill-down context."""
    text = "\n".join(f"{message.role}: {message.content}" for message in messages)
    return truncate_text(text, max_chars=max_chars)


def format_raw_span_with_anchor(
    messages: list[StoredMessage],
    *,
    anchor_message_ids: set[int],
    max_chars: int,
    query: str | None = None,
) -> str:
    """Format a bounded raw span while retaining selected evidence messages."""
    if not messages:
        return ""
    full_text = format_messages(messages)
    if max_chars <= 0 or len(full_text) <= max_chars:
        return full_text

    anchor_indexes = [
        index
        for index, message in enumerate(messages)
        if message.id in anchor_message_ids
    ]
    if not anchor_indexes:
        anchor_indexes = [best_query_message_index(messages, query)]

    selected = set(anchor_indexes)
    anchor_only = render_selected_messages(messages, selected)
    if len(anchor_only) > max_chars:
        primary_index = best_anchor_index(messages, anchor_indexes, query)
        return truncate_anchor_message(
            messages[primary_index],
            query=query,
            max_chars=max_chars,
            has_earlier=primary_index > 0,
            has_later=primary_index < len(messages) - 1,
        )

    neighbor_indexes = sorted(
        (index for index in range(len(messages)) if index not in selected),
        key=lambda index: (
            min(abs(index - anchor_index) for anchor_index in anchor_indexes),
            index,
        ),
    )
    for index in neighbor_indexes:
        proposed = selected | {index}
        rendered = render_selected_messages(messages, proposed)
        if len(rendered) <= max_chars:
            selected = proposed
    return render_selected_messages(messages, selected)


def render_selected_messages(
    messages: list[StoredMessage],
    selected_indexes: set[int],
) -> str:
    """Render selected messages chronologically with explicit omission markers."""
    selected = sorted(selected_indexes)
    lines: list[str] = []
    if selected[0] > 0:
        lines.append(EARLIER_OMISSION_MARKER)
    previous: int | None = None
    for index in selected:
        if previous is not None and index > previous + 1:
            lines.append(INTERVENING_OMISSION_MARKER)
        message = messages[index]
        lines.append(f"{message.role}: {message.content}")
        previous = index
    if selected[-1] < len(messages) - 1:
        lines.append(LATER_OMISSION_MARKER)
    return "\n".join(lines)


def truncate_anchor_message(
    message: StoredMessage,
    *,
    query: str | None,
    max_chars: int,
    has_earlier: bool,
    has_later: bool,
) -> str:
    """Keep a query-relevant window when one anchor alone exceeds the cap."""
    prefix = f"{message.role}: "
    leading_markers = [EARLIER_OMISSION_MARKER] if has_earlier else []
    trailing_markers = [LATER_OMISSION_MARKER] if has_later else []
    anchor_markers = [
        ANCHOR_START_OMISSION_MARKER,
        ANCHOR_END_OMISSION_MARKER,
    ]
    fixed_lines = [*leading_markers, *anchor_markers, *trailing_markers]
    fixed_chars = sum(len(line) for line in fixed_lines) + len(fixed_lines)
    available = max(1, max_chars - len(prefix) - fixed_chars)
    center = query_match_center(message.content, query)
    start = max(0, center - available // 2)
    start = min(start, max(0, len(message.content) - available))
    excerpt = message.content[start : start + available]
    lines = [
        *leading_markers,
        ANCHOR_START_OMISSION_MARKER,
        f"{prefix}{excerpt}",
        ANCHOR_END_OMISSION_MARKER,
        *trailing_markers,
    ]
    rendered = "\n".join(lines)
    return rendered[:max_chars]


def anchor_message_ids_for_plan(
    *,
    messages: list[StoredMessage],
    source_plan: SourcePlan,
) -> set[int]:
    """Resolve explicit anchor IDs, then fall back to the best query match."""
    explicit = int_set_filter(source_plan.filters, "anchor_message_ids")
    available_ids = {message.id for message in messages}
    explicit &= available_ids
    if explicit:
        return explicit
    if source_plan.query:
        return {messages[best_query_message_index(messages, source_plan.query)].id}
    return available_ids


def best_query_message_index(
    messages: list[StoredMessage],
    query: str | None,
) -> int:
    """Return the strongest deterministic lexical message anchor."""
    query_terms = query_tokens(query or "")
    return max(
        range(len(messages)),
        key=lambda index: (
            len(query_terms & query_tokens(messages[index].content)),
            messages[index].role == "user",
            messages[index].id,
        ),
    )


def best_anchor_index(
    messages: list[StoredMessage],
    anchor_indexes: list[int],
    query: str | None,
) -> int:
    """Choose one primary anchor only when all anchors cannot fit together."""
    query_terms = query_tokens(query or "")
    return max(
        anchor_indexes,
        key=lambda index: (
            len(query_terms & query_tokens(messages[index].content)),
            messages[index].role == "user",
            messages[index].id,
        ),
    )


def query_match_center(content: str, query: str | None) -> int:
    """Locate a query-relevant term for overlong single-anchor windowing."""
    lowered = content.lower()
    terms = sorted(query_tokens(query or ""), key=len, reverse=True)
    positions = [
        (lowered.find(term), len(term))
        for term in terms
        if lowered.find(term) >= 0
    ]
    if not positions:
        return len(content) // 2
    position, length = max(positions, key=lambda item: item[1])
    return position + length // 2


def query_tokens(value: str) -> set[str]:
    """Return stable lexical terms for selecting a raw-message anchor."""
    return set(QUERY_TOKEN_PATTERN.findall(value.lower()))


def truncate_text(text: str, max_chars: int | None = None) -> str:
    """Return text capped to max_chars with an explicit truncation marker."""
    if max_chars is None or max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= len(TRUNCATION_MARKER):
        return TRUNCATION_MARKER[:max_chars]
    return text[: max_chars - len(TRUNCATION_MARKER)].rstrip() + TRUNCATION_MARKER


def raw_span_max_chars_from_env() -> int:
    """Read the raw message span context cap from the environment."""
    raw_value = os.getenv("RAW_MESSAGE_SPAN_MAX_CHARS", "").strip()
    if not raw_value:
        return DEFAULT_RAW_SPAN_MAX_CHARS
    try:
        value = int(raw_value)
    except ValueError:
        return DEFAULT_RAW_SPAN_MAX_CHARS
    return value if value > 0 else DEFAULT_RAW_SPAN_MAX_CHARS


def int_filter(filters: dict[str, object], *names: str) -> int | None:
    """Read an integer filter while rejecting bool values."""
    for name in names:
        value = filters.get(name)
        if type(value) is int:
            return value
    return None


def int_set_filter(filters: dict[str, object], name: str) -> set[int]:
    """Read integer IDs from a source-plan filter."""
    value = filters.get(name, [])
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {item for item in value if type(item) is int}
