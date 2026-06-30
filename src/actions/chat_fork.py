"""CHAT_FORK_ACTION: duplicate a chat and all its data into a new active chat."""

from __future__ import annotations

from uuid import uuid4

from src.database import Database, utc_now


class ChatForkAction:
    """Duplicates all chat data into a new active chat."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def execute(self, chat_id: str) -> str:
        """Fork chat. Returns new chat_id. Wrapped in transaction for atomicity."""
        new_chat_id = str(uuid4())

        with self.database.connect() as conn:
            old = conn.execute(
                "SELECT title, model_name FROM chats WHERE id = ?", (chat_id,)
            ).fetchone()
            if old is None:
                raise ValueError(f"chat {chat_id} not found")

            now = utc_now()
            conn.execute(
                "INSERT INTO chats (id, title, created_at, updated_at, model_name, active) "
                "VALUES (?, ?, ?, ?, ?, 1)",
                (
                    new_chat_id,
                    old["title"] or f"Fork of {chat_id[:8]}",
                    now,
                    now,
                    old["model_name"],
                ),
            )

            # Copy messages
            conn.execute(
                "INSERT INTO messages (chat_id, role, content, summarized, created_at) "
                "SELECT ?, role, content, summarized, created_at FROM messages WHERE chat_id = ?",
                (new_chat_id, chat_id),
            )

            # Copy chat_memory_state
            memory = conn.execute(
                "SELECT memory_json FROM chat_memory_state WHERE chat_id = ?", (chat_id,)
            ).fetchone()
            if memory:
                conn.execute(
                    "INSERT INTO chat_memory_state (chat_id, memory_json, updated_at) "
                    "VALUES (?, ?, ?)",
                    (new_chat_id, memory["memory_json"], now),
                )

            # Copy chat_gists
            conn.execute(
                "INSERT INTO chat_gists (chat_id, source_type, gist_text, topics_json, "
                "decisions_json, open_tasks_json, retrieved_lt_mem_list_json, new_memories_json, "
                "start_message_id, end_message_id, created_at, updated_at, metadata_json) "
                "SELECT ?, source_type, gist_text, topics_json, decisions_json, open_tasks_json, "
                "retrieved_lt_mem_list_json, new_memories_json, start_message_id, end_message_id, "
                "created_at, updated_at, metadata_json FROM chat_gists WHERE chat_id = ?",
                (new_chat_id, chat_id),
            )

        return new_chat_id
