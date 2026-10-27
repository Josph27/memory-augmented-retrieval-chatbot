from __future__ import annotations

import sqlite3
from pathlib import Path

from src.database import Database


def test_new_chats_are_active_and_can_transition_lifecycle(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat-1", title="First")
    database.create_chat("chat-2", title="Second")

    assert {chat["id"] for chat in database.list_active_chats()} == {
        "chat-1",
        "chat-2",
    }
    assert database.list_inactive_chats() == []

    database.mark_chat_inactive("chat-1")

    assert [chat["id"] for chat in database.list_active_chats()] == ["chat-2"]
    assert [chat["id"] for chat in database.list_inactive_chats()] == ["chat-1"]
    assert database.list_inactive_chats()[0]["active"] == 0

    database.mark_chat_active("chat-1")

    assert {chat["id"] for chat in database.list_active_chats()} == {
        "chat-1",
        "chat-2",
    }
    assert database.list_inactive_chats() == []


def test_list_chats_still_includes_inactive_chats(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("active-chat", title="Active")
    database.create_chat("inactive-chat", title="Inactive")
    database.mark_chat_inactive("inactive-chat")

    listed_ids = {chat.id for chat in database.list_chats(limit=10)}

    assert listed_ids == {"active-chat", "inactive-chat"}


def test_existing_database_migrates_active_column_idempotently(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE chats (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                model_name TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO chats (id, title, created_at, updated_at, model_name)
            VALUES ('legacy-chat', 'Legacy', '2026-01-01', '2026-01-01', NULL)
            """
        )

    database = Database(path)
    Database(path)

    with database.connect() as connection:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(chats)").fetchall()
        }
        row = connection.execute(
            "SELECT active FROM chats WHERE id = 'legacy-chat'"
        ).fetchone()

    assert "active" in columns
    assert row is not None
    assert row["active"] == 1
    assert [chat["id"] for chat in database.list_active_chats()] == ["legacy-chat"]


def test_message_processing_flags_remain_independent_and_exclude_recent_window(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    ids = [database.save_message("chat", "user", str(i)) for i in range(5)]
    database.mark_messages_summarized([ids[0]])
    database.mark_messages_gist_processed([ids[1]])
    database.mark_messages_summarized([])
    database.mark_messages_gist_processed([])

    summary = database.old_unsummarized_messages("chat", raw_message_limit=2, batch_size=10)
    gist = database.old_ungisted_messages("chat", raw_message_limit=2, batch_size=10)
    assert [row.id for row in summary] == [ids[1], ids[2]]
    assert [row.id for row in gist] == [ids[0], ids[2]]
    assert [row.id for row in database.old_unsummarized_messages("chat", 2, 1)] == [ids[1]]
    assert [row.id for row in database.old_ungisted_messages("chat", 2, 1)] == [ids[0]]
    assert not database.is_chat_active("missing")
    database.mark_chat_active("missing")
    database.mark_chat_inactive("missing")
    assert [row["id"] for row in database.list_active_chats()] == ["chat"]
    assert database.list_inactive_chats() == []
