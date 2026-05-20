from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.database import Database, StoredMessage
from src.memory.constants import (
    MEMORY_REBUILD_BATCH_SIZE,
    MEMORY_UPDATE_BATCH_SIZE,
    RAW_MESSAGE_LIMIT,
)
from src.memory.structured_state import (
    ChatModel,
    StructuredMemoryState,
    dumps_memory_state,
    format_memory_for_prompt,
    load_memory_state,
    memory_state_is_empty,
)


MEMORY_CONTEXT_ROLE = "system"


@dataclass(frozen=True)
class ShortTermContext:
    """Context selected for a model call."""

    memory_state: dict[str, list[dict[str, Any]]]
    raw_messages: list[StoredMessage]


class ShortTermMemory:
    """Builds chat context and periodically updates structured memory."""

    def __init__(
        self,
        database: Database,
        model: ChatModel,
        raw_message_limit: int = RAW_MESSAGE_LIMIT,
        memory_update_batch_size: int = MEMORY_UPDATE_BATCH_SIZE,
    ) -> None:
        self.database = database
        self.raw_message_limit = raw_message_limit
        self.memory_update_batch_size = memory_update_batch_size
        self.structured_memory = StructuredMemoryState(model)

    def build_context(
        self,
        chat_id: str,
        latest_user_message_id: int | None = None,
        token_budget: int | None = None,
    ) -> ShortTermContext:
        """Return structured memory plus recent raw messages for the current chat.

        `token_budget` is accepted as a future extension point. The current MVP
        still uses `raw_message_limit` as the selection policy.
        """
        del token_budget
        if latest_user_message_id is None:
            raw_messages = self.database.recent_messages(chat_id, self.raw_message_limit)
        else:
            raw_messages = self.database.recent_messages_before_id(
                chat_id=chat_id,
                before_message_id=latest_user_message_id,
                limit=self.raw_message_limit,
            )

        return ShortTermContext(
            memory_state=load_memory_state(self.database.chat_memory_state(chat_id)),
            raw_messages=raw_messages,
        )

    def build_model_messages(
        self,
        system_prompt: str,
        context: ShortTermContext,
        latest_user_message: dict[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Convert selected short-term memory into chat-completions messages."""
        model_messages = [{"role": "system", "content": system_prompt}]
        if not memory_state_is_empty(context.memory_state):
            model_messages.append(
                {
                    "role": MEMORY_CONTEXT_ROLE,
                    "content": (
                        "Current structured memory:\n"
                        f"{format_memory_for_prompt(context.memory_state)}"
                    ),
                }
            )

        model_messages.extend(
            {"role": message.role, "content": message.content}
            for message in context.raw_messages
        )
        if latest_user_message is not None:
            model_messages.append(latest_user_message)
        return model_messages

    def update_memory_if_needed(self, chat_id: str) -> bool:
        """Update structured memory from one old unsummarized batch if threshold is met."""
        current_memory = load_memory_state(self.database.chat_memory_state(chat_id))
        messages = self.select_unprocessed_batch(chat_id)
        if memory_state_is_empty(current_memory) and len(messages) < self.memory_update_batch_size:
            messages = self.select_rebuild_batch(chat_id)

        if len(messages) < self.memory_update_batch_size:
            return False

        result = self.structured_memory.update(
            existing_memory=current_memory,
            messages=messages,
        )
        if not result.accepted:
            self.database.upsert_chat_memory_state(chat_id, dumps_memory_state(result.memory_state))
            return False

        self.database.upsert_chat_memory_state(chat_id, dumps_memory_state(result.memory_state))
        self.database.mark_messages_summarized([message.id for message in messages])
        return True

    def select_unprocessed_batch(self, chat_id: str) -> list[StoredMessage]:
        """Select old messages that are outside the raw window and not yet processed."""
        return self.database.old_unsummarized_messages(
            chat_id=chat_id,
            raw_message_limit=self.raw_message_limit,
            batch_size=self.memory_update_batch_size,
        )

    def select_rebuild_batch(self, chat_id: str) -> list[StoredMessage]:
        """Select older messages for recovery when memory was previously cached empty."""
        return self.database.old_messages(
            chat_id=chat_id,
            raw_message_limit=self.raw_message_limit,
            batch_size=MEMORY_REBUILD_BATCH_SIZE,
        )
