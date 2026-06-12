from __future__ import annotations

from src.core.contracts import MemoryCandidate, SourcePlan
from src.database import Database, StoredMessage


class RawMessageSpanRetriever:
    """Retrieve source-of-truth raw messages for an explicit message-id span."""

    def __init__(self, database: Database) -> None:
        self.database = database

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

        return [
            MemoryCandidate(
                source="raw_message_span",
                content=format_messages(messages),
                score=1.0,
                record_id=gist_id or f"{span_chat_id}:{start_message_id}-{end_message_id}",
                chat_id=span_chat_id,
                source_message_ids=[message.id for message in messages],
                metadata={
                    "start_message_id": start_message_id,
                    "end_message_id": end_message_id,
                    "message_count": len(messages),
                    "gist_id": gist_id,
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
        gist_id = filters.get("gist_id")
        if isinstance(gist_id, int):
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

        start_message_id = filters.get("start_message_id")
        end_message_id = filters.get("end_message_id")
        span_chat_id = filters.get("chat_id", chat_id)
        if (
            isinstance(span_chat_id, str)
            and isinstance(start_message_id, int)
            and isinstance(end_message_id, int)
        ):
            return (span_chat_id, start_message_id, end_message_id, None)
        return None


def format_messages(messages: list[StoredMessage]) -> str:
    """Format raw messages compactly for span drill-down context."""
    return "\n".join(f"{message.role}: {message.content}" for message in messages)
