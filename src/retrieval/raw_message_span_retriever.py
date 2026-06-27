from __future__ import annotations

import os

from src.core.contracts import MemoryCandidate, SourcePlan
from src.database import Database, StoredMessage

DEFAULT_RAW_SPAN_MAX_CHARS = 4000
TRUNCATION_MARKER = "\n[raw message span truncated]"


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

        content = format_messages(messages, max_chars=self.max_chars)
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
