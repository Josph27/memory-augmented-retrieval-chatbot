from __future__ import annotations

import chainlit as cl

from src.chat_service import ChatService
from src.config import AppConfig
from src.database import Database
from src.model_wrapper import ModelWrapper


config = AppConfig.from_env()
database = Database(config.database_path)
model = ModelWrapper(config)
chat_service = ChatService(
    database=database,
    model=model,
    raw_message_limit=config.raw_message_limit,
    memory_update_batch_size=config.memory_update_batch_size,
)


@cl.on_chat_start
async def on_chat_start() -> None:
    """Create a persistent chat row for the current Chainlit session."""
    chat_id = chat_service.start_chat()
    cl.user_session.set("chat_id", chat_id)

    await cl.Message(
        content=(
            "Chat is ready. Messages are stored in SQLite. Older turns update structured "
            "JSON memory while recent turns remain available as raw short-term memory."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle one browser chat message."""
    chat_id = cl.user_session.get("chat_id")
    if not chat_id:
        chat_id = chat_service.start_chat()
        cl.user_session.set("chat_id", chat_id)

    response = chat_service.handle_user_message(chat_id=chat_id, content=message.content)
    await cl.Message(content=response).send()
