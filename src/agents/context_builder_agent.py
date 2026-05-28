from __future__ import annotations

from src.core.contracts import ContextPacket
from src.memory.short_term import ShortTermContext, ShortTermMemory
from src.memory.structured_state import format_memory_for_prompt, memory_state_is_empty


class ContextBuilderAgent:
    """Agent adapter for assembling model context from selected memory."""

    def __init__(self, memory: ShortTermMemory) -> None:
        self.memory = memory

    def build(
        self,
        chat_id: str,
        system_prompt: str,
        context: ShortTermContext,
        latest_user_message: dict[str, str],
    ) -> tuple[list[dict[str, str]], ContextPacket]:
        """Build model messages and a trace-friendly context packet."""
        model_messages = self.memory.build_model_messages(
            system_prompt=system_prompt,
            context=context,
            latest_user_message=latest_user_message,
        )
        structured_memory = None
        if not memory_state_is_empty(context.memory_state):
            structured_memory = format_memory_for_prompt(context.memory_state)

        packet = ContextPacket(
            chat_id=chat_id,
            system_prompt=system_prompt,
            structured_memory=structured_memory,
            recent_message_ids=[message.id for message in context.raw_messages],
            model_messages=model_messages,
        )
        return model_messages, packet
