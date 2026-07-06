from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from src.database import Database
from src.lifecycle.operation_guard import guarded_chat_operation
from src.memory.previous_chat_gist import (
    DeterministicPreviousChatGistExtractor,
    PreviousChatGistFinalizationResult,
    PreviousChatGistGenerator,
)
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


class ChatEndGistFinalizer(Protocol):
    """Episodic gist service required to finalize one chat."""

    def finalize_chat(
        self,
        chat_id: str,
    ) -> PreviousChatGistFinalizationResult:
        """Finalize pending gist segments or raise on failure."""
        ...


@dataclass(frozen=True)
class ChatEndResult:
    """Outcome of successfully finalizing a chat."""

    chat_id: str
    processed_message_count: int
    batch_count: int
    gist_count: int = 0
    gist_processed_message_count: int = 0
    gist_batch_count: int = 0
    inactive: bool = True


class ChatEndAction:
    """Finalize pending memory and mark a chat inactive only after success."""

    def __init__(
        self,
        database: Database,
        memory: ChatEndMemoryProcessor,
        gist_finalizer: ChatEndGistFinalizer | None = None,
    ) -> None:
        self.database = database
        self.memory = memory
        self.gist_finalizer = gist_finalizer or PreviousChatGistGenerator(
            database=database,
            extractor=DeterministicPreviousChatGistExtractor(),
        )

    def execute(self, chat_id: str) -> ChatEndResult:
        """Process pending messages, then transition the chat to inactive."""
        with guarded_chat_operation(self.database.path, chat_id):
            return self._execute_locked(chat_id)

    def _execute_locked(self, chat_id: str) -> ChatEndResult:
        """Finalize one chat while its shared operation lock is held."""
        try:
            memory_result = self.memory.process_all_for_chat_end(chat_id)
        except Exception:
            logger.exception("chat end memory processing failed chat_id=%s", chat_id)
            raise
        try:
            gist_result = self.gist_finalizer.finalize_chat(chat_id)
        except Exception:
            logger.exception("chat end gist finalization failed chat_id=%s", chat_id)
            raise

        self.database.mark_chat_inactive(chat_id)
        return ChatEndResult(
            chat_id=chat_id,
            processed_message_count=memory_result.processed_message_count,
            batch_count=memory_result.batch_count,
            gist_count=gist_result.created_count,
            gist_processed_message_count=gist_result.processed_message_count,
            gist_batch_count=gist_result.batch_count,
        )
