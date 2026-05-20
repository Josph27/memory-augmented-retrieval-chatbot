from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def utc_now() -> str:
    """Return a stable UTC timestamp for database rows."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class StoredMessage:
    """A chat message loaded from SQLite."""

    id: int
    role: str
    content: str
    created_at: str
    summarized: bool = False


class Database:
    """Small SQLite adapter for chats, messages, and structured memory."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Open a connection with row dictionaries enabled."""
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init_schema(self) -> None:
        """Create and migrate the relational schema if it does not exist."""
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant')),
                    content TEXT NOT NULL,
                    summarized INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS chat_memory_state (
                    chat_id TEXT PRIMARY KEY,
                    memory_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_chat_created
                ON messages(chat_id, created_at);

                """
            )
            self._ensure_messages_summarized_column(connection)
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_chat_summarized
                ON messages(chat_id, summarized, id)
                """
            )

    def _ensure_messages_summarized_column(self, connection: sqlite3.Connection) -> None:
        """Add `messages.summarized` for databases created before Short-Term Memory v2."""
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "summarized" not in columns:
            connection.execute(
                "ALTER TABLE messages ADD COLUMN summarized INTEGER NOT NULL DEFAULT 0"
            )

    def create_chat(self, chat_id: str, title: str | None = None) -> None:
        """Insert a chat row if Chainlit starts a new session."""
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO chats (id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (chat_id, title, timestamp, timestamp),
            )

    def save_message(self, chat_id: str, role: str, content: str) -> int:
        """Persist one chat message."""
        timestamp = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages (chat_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (chat_id, role, content, timestamp),
            )
            connection.execute(
                "UPDATE chats SET updated_at = ? WHERE id = ?",
                (timestamp, chat_id),
            )
            return int(cursor.lastrowid)

    def recent_messages(self, chat_id: str, limit: int) -> list[StoredMessage]:
        """Load recent messages for short-term memory."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, role, content, created_at, summarized
                FROM messages
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()

        return [self._message_from_row(row) for row in reversed(rows)]

    def recent_messages_before_id(
        self,
        chat_id: str,
        before_message_id: int,
        limit: int,
    ) -> list[StoredMessage]:
        """Load recent messages before a specific message id."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, role, content, created_at, summarized
                FROM messages
                WHERE chat_id = ?
                  AND id < ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (chat_id, before_message_id, limit),
            ).fetchall()

        return [self._message_from_row(row) for row in reversed(rows)]

    def old_unsummarized_messages(
        self,
        chat_id: str,
        raw_message_limit: int,
        batch_size: int,
    ) -> list[StoredMessage]:
        """Load unsummarized messages older than the raw recent-message window."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, role, content, created_at, summarized
                FROM messages
                WHERE chat_id = ?
                  AND summarized = 0
                  AND id NOT IN (
                      SELECT id
                      FROM messages
                      WHERE chat_id = ?
                      ORDER BY id DESC
                      LIMIT ?
                  )
                ORDER BY id ASC
                LIMIT ?
                """,
                (chat_id, chat_id, raw_message_limit, batch_size),
            ).fetchall()

        return [self._message_from_row(row) for row in rows]

    def old_messages(
        self,
        chat_id: str,
        raw_message_limit: int,
        batch_size: int,
    ) -> list[StoredMessage]:
        """Load old messages outside the raw recent-message window."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, role, content, created_at, summarized
                FROM messages
                WHERE chat_id = ?
                  AND id NOT IN (
                      SELECT id
                      FROM messages
                      WHERE chat_id = ?
                      ORDER BY id DESC
                      LIMIT ?
                  )
                ORDER BY id ASC
                LIMIT ?
                """,
                (chat_id, chat_id, raw_message_limit, batch_size),
            ).fetchall()

        return [self._message_from_row(row) for row in rows]

    def chat_memory_state(self, chat_id: str) -> str | None:
        """Load the structured memory JSON for a chat, if one exists."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT memory_json FROM chat_memory_state WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()

        return row["memory_json"] if row else None

    def upsert_chat_memory_state(self, chat_id: str, memory_json: str) -> None:
        """Insert or replace the structured memory JSON for a chat."""
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO chat_memory_state (chat_id, memory_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    memory_json = excluded.memory_json,
                    updated_at = excluded.updated_at
                """,
                (chat_id, memory_json, timestamp),
            )

    def mark_messages_summarized(self, message_ids: list[int]) -> None:
        """Mark messages as processed into the derived memory cache."""
        if not message_ids:
            return

        placeholders = ",".join("?" for _ in message_ids)
        with self.connect() as connection:
            connection.execute(
                f"UPDATE messages SET summarized = 1 WHERE id IN ({placeholders})",
                message_ids,
            )

    def _message_from_row(self, row: sqlite3.Row) -> StoredMessage:
        return StoredMessage(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
            summarized=bool(row["summarized"]),
        )
