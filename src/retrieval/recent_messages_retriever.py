from __future__ import annotations

from src.core.contracts import MemoryCandidate, SourcePlan
from src.database import Database
from src.memory.constants import RECENT_MESSAGES_MAX_COUNT


class RecentMessagesRetriever:
    """Retrieve recent raw messages from the current chat."""

    def __init__(
        self,
        database: Database,
        default_limit: int = RECENT_MESSAGES_MAX_COUNT,
    ) -> None:
        self.database = database
        self.default_limit = default_limit

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        """Load recent messages and normalize them as memory candidates."""
        limit = source_plan.limit or self.default_limit
        messages = self.database.recent_messages(chat_id=chat_id, limit=limit)
        candidates: list[MemoryCandidate] = []
        for index, message in enumerate(messages):
            candidates.append(
                MemoryCandidate(
                    source="recent_messages",
                    content=message.content,
                    record_id=message.id,
                    chat_id=chat_id,
                    source_message_ids=[message.id],
                    metadata={
                        "role": message.role,
                        "created_at": message.created_at,
                        "summarized": message.summarized,
                        "order": index,
                    },
                )
            )
        return candidates
