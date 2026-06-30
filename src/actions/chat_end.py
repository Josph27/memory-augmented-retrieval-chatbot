"""CHAT_END_ACTION: process unsummarized messages into memory and mark chat inactive."""

from __future__ import annotations

from src.database import Database
from src.memory.short_term import ShortTermMemory


class ChatEndAction:
    """Triggers PROCESS_INTO_MEMORY and marks the chat inactive."""

    def __init__(self, database: Database, memory: ShortTermMemory) -> None:
        self.database = database
        self.memory = memory

    def execute(self, chat_id: str) -> None:
        """Process all unsummarized messages into memory, then mark chat inactive."""
        self.memory.process_all_for_chat_end(chat_id)
        self.database.mark_chat_inactive(chat_id)
