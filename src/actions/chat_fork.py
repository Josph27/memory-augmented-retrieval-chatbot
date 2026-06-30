from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from src.database import Database


def generate_chat_id() -> str:
    """Return a fresh chat identifier."""
    return str(uuid4())


class ChatForkAction:
    """Create an active transactional copy of one stored chat."""

    def __init__(
        self,
        database: Database,
        id_factory: Callable[[], str] = generate_chat_id,
    ) -> None:
        self.database = database
        self.id_factory = id_factory

    def execute(self, chat_id: str) -> str:
        """Fork one chat and return the new chat id."""
        new_chat_id = self.id_factory()
        self.database.fork_chat(chat_id, new_chat_id)
        return new_chat_id
