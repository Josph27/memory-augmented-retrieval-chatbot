from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from src.database import Database
from src.memory.short_term import ChatEndMemoryProcessingResult


logger = logging.getLogger(__name__)


class ChatEndMemoryProcessor(Protocol):
    """Memory service required to finalize one chat."""

    def process_all_for_chat_end(
        self,
        chat_id: str,
    ) -> ChatEndMemoryProcessingResult:
        """Process every pending message or raise on failure."""
        ...


@dataclass(frozen=True)
class ChatEndResult:
    """Outcome of successfully finalizing a chat."""

    chat_id: str
    processed_message_count: int
    batch_count: int
    inactive: bool = True


class ChatEndAction:
    """Finalize pending memory and mark a chat inactive only after success."""

    def __init__(
        self,
        database: Database,
        memory: ChatEndMemoryProcessor,
    ) -> None:
        self.database = database
        self.memory = memory

    def execute(self, chat_id: str) -> ChatEndResult:
        """Process pending messages, then transition the chat to inactive."""
        try:
            memory_result = self.memory.process_all_for_chat_end(chat_id)
        except Exception:
            logger.exception("chat end memory processing failed chat_id=%s", chat_id)
            raise

        self.database.mark_chat_inactive(chat_id)
        return ChatEndResult(
            chat_id=chat_id,
            processed_message_count=memory_result.processed_message_count,
            batch_count=memory_result.batch_count,
        )
