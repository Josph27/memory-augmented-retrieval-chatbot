from __future__ import annotations

from uuid import uuid4

from openai import OpenAIError

from src.database import Database
from src.model_wrapper import ModelWrapper


SYSTEM_PROMPT = (
    "You are a concise, helpful chatbot prototype. Use the recent conversation history as "
    "short-term memory. If information is missing, say what you need instead of inventing facts."
)


class ChatService:
    """Coordinates database persistence, short-term memory, and model calls."""

    def __init__(self, database: Database, model: ModelWrapper, recent_message_limit: int) -> None:
        self.database = database
        self.model = model
        self.recent_message_limit = recent_message_limit

    def start_chat(self) -> str:
        """Create a chat id for a Chainlit session."""
        chat_id = str(uuid4())
        self.database.create_chat(chat_id=chat_id, title="Chainlit chat")
        return chat_id

    def handle_user_message(self, chat_id: str, content: str) -> str:
        """Save a user message, call the model, and save the assistant response."""
        self.database.save_message(chat_id=chat_id, role="user", content=content)

        recent_messages = self.database.recent_messages(
            chat_id=chat_id,
            limit=self.recent_message_limit,
        )
        model_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        model_messages.extend(
            {"role": message.role, "content": message.content} for message in recent_messages
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
        return response
