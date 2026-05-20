from __future__ import annotations

from uuid import uuid4

from openai import OpenAIError

from src.database import Database
from src.memory.short_term import ShortTermMemory
from src.model_wrapper import ModelWrapper


SYSTEM_PROMPT = (
    "You are a concise, helpful chatbot prototype. Use the structured current-chat memory "
    "and recent messages as short-term memory. If information is missing, say what you need "
    "instead of inventing facts."
)


class ChatService:
    """Coordinates database persistence, short-term memory, and model calls."""

    def __init__(
        self,
        database: Database,
        model: ModelWrapper,
        raw_message_limit: int,
        memory_update_batch_size: int,
    ) -> None:
        self.database = database
        self.model = model
        self.memory = ShortTermMemory(
            database=database,
            model=model,
            raw_message_limit=raw_message_limit,
            memory_update_batch_size=memory_update_batch_size,
        )

    def start_chat(self) -> str:
        """Create a chat id for a Chainlit session."""
        chat_id = str(uuid4())
        self.database.create_chat(chat_id=chat_id, title="Chainlit chat")
        return chat_id

    def handle_user_message(self, chat_id: str, content: str) -> str:
        """Save a user message, call the model, and save the assistant response."""
        user_message_id = self.database.save_message(chat_id=chat_id, role="user", content=content)

        context = self.memory.build_context(
            chat_id=chat_id,
            latest_user_message_id=user_message_id,
        )
        model_messages = self.memory.build_model_messages(
            system_prompt=SYSTEM_PROMPT,
            context=context,
            latest_user_message={"role": "user", "content": content},
        )

        try:
            response = self.model.chat(model_messages)
        except OpenAIError as error:
            response = (
                "I could not reach the configured OpenAI-compatible model endpoint. "
                "Check OPENAI_BASE_URL, MODEL_NAME, and whether the local model server is running.\n\n"
                f"Model error: {error}"
            )

        self.database.save_message(chat_id=chat_id, role="assistant", content=response)
        try:
            self.memory.update_memory_if_needed(chat_id)
        except OpenAIError:
            # Memory updates should not break the visible chat response. The next
            # successful turn can retry because messages remain unprocessed.
            pass
        return response
