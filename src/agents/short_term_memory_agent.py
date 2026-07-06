from __future__ import annotations

from src.memory.short_term import ShortTermContext, ShortTermMemory


class ShortTermMemoryAgent:
    """Agent adapter for current-chat structured memory and recent raw messages."""

    def __init__(self, memory: ShortTermMemory) -> None:
        self.memory = memory

    def build_context(
        self,
        chat_id: str,
        latest_user_message_id: int | None = None,
    ) -> ShortTermContext:
        """Load the current short-term context for a turn."""
        return self.memory.build_context(
            chat_id=chat_id,
            latest_user_message_id=latest_user_message_id,
        )

    def update_memory_if_needed(self, chat_id: str) -> bool:
        """Run the existing structured-memory update policy."""
        return self.memory.update_memory_if_needed(chat_id)
