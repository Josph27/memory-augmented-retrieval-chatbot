from __future__ import annotations

import sqlite3
from pathlib import Path

from src.database import Database


def test_gist_processed_schema_migration_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE chats (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE chat_gists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                gist_text TEXT NOT NULL,
                topics_json TEXT NOT NULL DEFAULT '[]',
                decisions_json TEXT NOT NULL DEFAULT '[]',
                open_tasks_json TEXT NOT NULL DEFAULT '[]',
                start_message_id INTEGER,
                end_message_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO chats (id, title, created_at, updated_at)
            VALUES ('legacy-chat', 'Legacy', 'now', 'now')
            """
        )
        connection.execute(
            """
            INSERT INTO messages (chat_id, role, content, created_at)
            VALUES ('legacy-chat', 'user', 'legacy message', 'now')
            """
        )
        connection.execute(
            """
            INSERT INTO messages (chat_id, role, content, created_at)
            VALUES ('legacy-chat', 'assistant', 'legacy reply', 'now')
            """
        )
        connection.execute(
            """
            INSERT INTO messages (chat_id, role, content, created_at)
            VALUES ('legacy-chat', 'user', 'not yet gisted', 'now')
            """
        )
        connection.execute(
            """
            INSERT INTO chat_gists (
                chat_id,
                source_type,
                gist_text,
                start_message_id,
                end_message_id,
                created_at,
                updated_at
            )
            VALUES (
                'legacy-chat',
                'current_chat_gist',
                'Existing gist',
                1,
                2,
                'now',
                'now'
            )
            """
        )

    database = Database(path)
    database.init_schema()

    with database.connect() as connection:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(messages)").fetchall()
        }
    assert "summarized" in columns
    assert "gist_processed" in columns
    messages = database.messages_for_chat("legacy-chat")
    assert all(not message.summarized for message in messages)
    assert [message.gist_processed for message in messages] == [True, True, False]
