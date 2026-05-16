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

    role: str
    content: str
    created_at: str


class Database:
    """Small SQLite adapter for chats and messages."""

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
        """Create the relational schema if it does not exist."""
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
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_chat_created
                ON messages(chat_id, created_at);
                """
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

    def save_message(self, chat_id: str, role: str, content: str) -> None:
        """Persist one chat message."""
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute(
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

    def recent_messages(self, chat_id: str, limit: int) -> list[StoredMessage]:
        """Load recent messages for short-term memory."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()

        return [
            StoredMessage(role=row["role"], content=row["content"], created_at=row["created_at"])
            for row in reversed(rows)
        ]
