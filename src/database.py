from __future__ import annotations

import sqlite3
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utc_now() -> str:
    """Return a stable UTC timestamp for database rows."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class StoredMessage:
    """A chat message loaded from SQLite."""

    id: int
    chat_id: str
    role: str
    content: str
    created_at: str
    summarized: bool = False
    gist_processed: bool = False


@dataclass(frozen=True)
class StoredChat:
    """A chat thread loaded from SQLite."""

    id: str
    title: str | None
    created_at: str
    updated_at: str
    model_name: str | None


@dataclass(frozen=True)
class StoredChatGist:
    """A compressed chat-memory gist with pointers back to raw messages."""

    id: int
    chat_id: str
    source_type: str
    gist_text: str
    topics_json: str
    decisions_json: str
    open_tasks_json: str
    start_message_id: int | None
    end_message_id: int | None
    created_at: str
    updated_at: str
    metadata_json: str


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
                    updated_at TEXT NOT NULL,
                    model_name TEXT,
                    active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant')),
                    content TEXT NOT NULL,
                    summarized INTEGER NOT NULL DEFAULT 0,
                    gist_processed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS chat_memory_state (
                    chat_id TEXT PRIMARY KEY,
                    memory_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS chat_gists (
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
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_chat_created
                ON messages(chat_id, created_at);

                CREATE INDEX IF NOT EXISTS idx_chat_gists_chat_source
                ON chat_gists(chat_id, source_type);

                CREATE INDEX IF NOT EXISTS idx_chat_gists_source
                ON chat_gists(source_type);

                CREATE TABLE IF NOT EXISTS long_term_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace_json TEXT NOT NULL,
                    namespace_path TEXT NOT NULL,
                    memory_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    status TEXT NOT NULL DEFAULT 'active',
                    source_chat_id TEXT,
                    source_message_ids_json TEXT NOT NULL DEFAULT '[]',
                    source_gist_id INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(namespace_path, memory_id)
                );

                CREATE INDEX IF NOT EXISTS idx_long_term_memories_namespace
                ON long_term_memories(namespace_path, status, updated_at);

                CREATE INDEX IF NOT EXISTS idx_long_term_memories_category
                ON long_term_memories(category);

                """
            )
            self._ensure_messages_summarized_column(connection)
            self._ensure_messages_gist_processed_column(connection)
            self._ensure_chats_model_name_column(connection)
            self._ensure_chats_active_column(connection)
            self._drop_legacy_document_tables(connection)
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_chat_summarized
                ON messages(chat_id, summarized, id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_chat_gist_processed
                ON messages(chat_id, gist_processed, id)
                """
            )

    def _drop_legacy_document_tables(self, connection: sqlite3.Connection) -> None:
        """Remove the abandoned SQLite document store without touching chat memory."""
        connection.execute("SAVEPOINT drop_legacy_document_store")
        try:
            connection.execute("DROP TABLE IF EXISTS document_chunk_embeddings")
            connection.execute("DROP TABLE IF EXISTS document_chunks")
            connection.execute("DROP TABLE IF EXISTS documents")
        except Exception:
            connection.execute("ROLLBACK TO SAVEPOINT drop_legacy_document_store")
            connection.execute("RELEASE SAVEPOINT drop_legacy_document_store")
            raise
        connection.execute("RELEASE SAVEPOINT drop_legacy_document_store")

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

    def _ensure_messages_gist_processed_column(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        """Add independent episodic-gist processing state to existing databases."""
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "gist_processed" not in columns:
            connection.execute(
                "ALTER TABLE messages "
                "ADD COLUMN gist_processed INTEGER NOT NULL DEFAULT 0"
            )
            connection.execute(
                """
                UPDATE messages
                SET gist_processed = 1
                WHERE EXISTS (
                    SELECT 1
                    FROM chat_gists
                    WHERE chat_gists.chat_id = messages.chat_id
                      AND chat_gists.start_message_id IS NOT NULL
                      AND chat_gists.end_message_id IS NOT NULL
                      AND messages.id >= MIN(
                          chat_gists.start_message_id,
                          chat_gists.end_message_id
                      )
                      AND messages.id <= MAX(
                          chat_gists.start_message_id,
                          chat_gists.end_message_id
                      )
                )
                """
            )

    def _ensure_chats_model_name_column(self, connection: sqlite3.Connection) -> None:
        """Add `chats.model_name` for databases created before model profiles."""
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(chats)").fetchall()
        }
        if "model_name" not in columns:
            connection.execute("ALTER TABLE chats ADD COLUMN model_name TEXT")

    def _ensure_chats_active_column(self, connection: sqlite3.Connection) -> None:
        """Add `chats.active` for databases created before chat lifecycle support."""
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(chats)").fetchall()
        }
        if "active" not in columns:
            connection.execute(
                "ALTER TABLE chats ADD COLUMN active INTEGER NOT NULL DEFAULT 1"
            )

    def create_chat(
        self,
        chat_id: str,
        title: str | None = None,
        model_name: str | None = None,
    ) -> None:
        """Insert a chat row if Chainlit starts a new session."""
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO chats (id, title, created_at, updated_at, model_name)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = COALESCE(excluded.title, chats.title),
                    model_name = COALESCE(excluded.model_name, chats.model_name)
                """,
                (chat_id, title, timestamp, timestamp, model_name),
            )

    def get_chat(self, chat_id: str) -> StoredChat | None:
        """Load one chat thread by id."""
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, title, created_at, updated_at, model_name
                FROM chats
                WHERE id = ?
                """,
                (chat_id,),
            ).fetchone()
        return self._chat_from_row(row) if row else None

    def list_chats(
        self,
        limit: int,
        cursor: str | None = None,
        search: str | None = None,
        require_messages: bool = False,
    ) -> list[StoredChat]:
        """List chat threads for Chainlit history."""
        parameters: list[object] = []
        clauses: list[str] = []
        if require_messages:
            clauses.append("EXISTS (SELECT 1 FROM messages WHERE messages.chat_id = chats.id)")
        if cursor:
            cursor_chat = self.get_chat(cursor)
            if cursor_chat:
                clauses.append("updated_at < ?")
                parameters.append(cursor_chat.updated_at)
        if search:
            clauses.append("(title LIKE ? OR id LIKE ?)")
            pattern = f"%{search}%"
            parameters.extend([pattern, pattern])

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id, title, created_at, updated_at, model_name
                FROM chats
                {where_clause}
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()

        return [self._chat_from_row(row) for row in rows]

    def update_chat_title(self, chat_id: str, title: str) -> None:
        """Update the visible thread title."""
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE chats
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (title, timestamp, chat_id),
            )

    def update_chat_model(self, chat_id: str, model_name: str) -> None:
        """Persist the model selected for a chat."""
        with self.connect() as connection:
            connection.execute(
                "UPDATE chats SET model_name = ? WHERE id = ?",
                (model_name, chat_id),
            )

    def mark_chat_active(self, chat_id: str) -> None:
        """Mark a stored chat as active."""
        with self.connect() as connection:
            connection.execute(
                "UPDATE chats SET active = 1 WHERE id = ?",
                (chat_id,),
            )

    def mark_chat_inactive(self, chat_id: str) -> None:
        """Mark a stored chat as inactive."""
        with self.connect() as connection:
            connection.execute(
                "UPDATE chats SET active = 0 WHERE id = ?",
                (chat_id,),
            )

    def list_active_chats(self) -> list[dict]:
        """Return active chats ordered by most recent update."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, created_at, updated_at, model_name, active
                FROM chats
                WHERE active = 1
                ORDER BY updated_at DESC, created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def list_inactive_chats(self) -> list[dict]:
        """Return inactive chats ordered by most recent update."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, created_at, updated_at, model_name, active
                FROM chats
                WHERE active = 0
                ORDER BY updated_at DESC, created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def fork_chat(self, chat_id: str, new_chat_id: str) -> None:
        """Transactionally copy one chat and remap chat-local message provenance.

        The legacy per-chat compatibility cache and namespaced long-term
        memories are intentionally not copied. User/project memories remain
        shared through their existing namespaces. Inherited fork messages are
        marked semantically processed so only post-fork messages can produce
        new global structured memories.
        """
        timestamp = utc_now()
        with self.connect() as connection:
            chat = connection.execute(
                """
                SELECT title, model_name
                FROM chats
                WHERE id = ?
                """,
                (chat_id,),
            ).fetchone()
            if chat is None:
                raise ValueError(f"Chat not found: {chat_id}")

            connection.execute(
                """
                INSERT INTO chats (
                    id, title, created_at, updated_at, model_name, active
                )
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (
                    new_chat_id,
                    chat["title"],
                    timestamp,
                    timestamp,
                    chat["model_name"],
                ),
            )

            message_id_map: dict[int, int] = {}
            messages = connection.execute(
                """
                SELECT id, role, content, summarized, gist_processed, created_at
                FROM messages
                WHERE chat_id = ?
                ORDER BY id ASC
                """,
                (chat_id,),
            ).fetchall()
            for message in messages:
                cursor = connection.execute(
                    """
                    INSERT INTO messages (
                        chat_id, role, content, summarized, gist_processed, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_chat_id,
                        message["role"],
                        message["content"],
                        1,
                        message["gist_processed"],
                        message["created_at"],
                    ),
                )
                message_id_map[int(message["id"])] = int(cursor.lastrowid)

            gists = connection.execute(
                """
                SELECT
                    source_type,
                    gist_text,
                    topics_json,
                    decisions_json,
                    open_tasks_json,
                    start_message_id,
                    end_message_id,
                    created_at,
                    updated_at,
                    metadata_json
                FROM chat_gists
                WHERE chat_id = ?
                ORDER BY id ASC
                """,
                (chat_id,),
            ).fetchall()
            for gist in gists:
                start_message_id = remap_message_id(
                    gist["start_message_id"],
                    message_id_map,
                )
                end_message_id = remap_message_id(
                    gist["end_message_id"],
                    message_id_map,
                )
                metadata_json = remap_chat_local_json(
                    gist["metadata_json"],
                    message_id_map=message_id_map,
                    source_chat_id=chat_id,
                    new_chat_id=new_chat_id,
                )
                connection.execute(
                    """
                    INSERT INTO chat_gists (
                        chat_id,
                        source_type,
                        gist_text,
                        topics_json,
                        decisions_json,
                        open_tasks_json,
                        start_message_id,
                        end_message_id,
                        created_at,
                        updated_at,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_chat_id,
                        gist["source_type"],
                        gist["gist_text"],
                        gist["topics_json"],
                        gist["decisions_json"],
                        gist["open_tasks_json"],
                        start_message_id,
                        end_message_id,
                        gist["created_at"],
                        gist["updated_at"],
                        metadata_json,
                    ),
                )

    def message_count(self, chat_id: str) -> int:
        """Return the number of persisted messages for a chat."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM messages WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        return int(row["count"] if row else 0)

    def messages_for_chat(self, chat_id: str) -> list[StoredMessage]:
        """Load all raw messages for one chat in chronological order."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id, chat_id, role, content, created_at, summarized, gist_processed
                FROM messages
                WHERE chat_id = ?
                ORDER BY id ASC
                """,
                (chat_id,),
            ).fetchall()

        return [self._message_from_row(row) for row in rows]

    def messages_for_chat_span(
        self,
        chat_id: str,
        start_message_id: int,
        end_message_id: int,
    ) -> list[StoredMessage]:
        """Load raw messages for one inclusive message-id span."""
        lower = min(start_message_id, end_message_id)
        upper = max(start_message_id, end_message_id)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id, chat_id, role, content, created_at, summarized, gist_processed
                FROM messages
                WHERE chat_id = ?
                  AND id >= ?
                  AND id <= ?
                ORDER BY id ASC
                """,
                (chat_id, lower, upper),
            ).fetchall()

        return [self._message_from_row(row) for row in rows]

    def delete_chat(self, chat_id: str) -> None:
        """Delete one chat and its derived current-chat memory."""
        with self.connect() as connection:
            connection.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
            connection.execute("DELETE FROM chat_gists WHERE chat_id = ?", (chat_id,))
            connection.execute(
                "DELETE FROM chat_memory_state WHERE chat_id = ?",
                (chat_id,),
            )
            connection.execute("DELETE FROM chats WHERE id = ?", (chat_id,))

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
                SELECT
                    id, chat_id, role, content, created_at, summarized, gist_processed
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
                SELECT
                    id, chat_id, role, content, created_at, summarized, gist_processed
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
                SELECT
                    id, chat_id, role, content, created_at, summarized, gist_processed
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

    def old_ungisted_messages(
        self,
        chat_id: str,
        raw_message_limit: int,
        batch_size: int,
    ) -> list[StoredMessage]:
        """Load gist-unprocessed messages outside the recent raw window."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id, chat_id, role, content, created_at, summarized, gist_processed
                FROM messages
                WHERE chat_id = ?
                  AND gist_processed = 0
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
                SELECT
                    id, chat_id, role, content, created_at, summarized, gist_processed
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

    def mark_messages_gist_processed(self, message_ids: list[int]) -> None:
        """Mark messages as included in an episodic gist."""
        if not message_ids:
            return

        placeholders = ",".join("?" for _ in message_ids)
        with self.connect() as connection:
            connection.execute(
                f"UPDATE messages SET gist_processed = 1 WHERE id IN ({placeholders})",
                message_ids,
            )

    def insert_chat_gist(
        self,
        chat_id: str,
        source_type: str,
        gist_text: str,
        topics: list[str] | None = None,
        decisions: list[str] | None = None,
        open_tasks: list[str] | None = None,
        start_message_id: int | None = None,
        end_message_id: int | None = None,
        metadata: dict | None = None,
        gist_processed_message_ids: list[int] | None = None,
    ) -> int:
        """Insert one gist and optionally advance gist state transactionally."""
        timestamp = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO chat_gists (
                    chat_id,
                    source_type,
                    gist_text,
                    topics_json,
                    decisions_json,
                    open_tasks_json,
                    start_message_id,
                    end_message_id,
                    created_at,
                    updated_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    source_type,
                    gist_text,
                    json.dumps(topics or [], ensure_ascii=True),
                    json.dumps(decisions or [], ensure_ascii=True),
                    json.dumps(open_tasks or [], ensure_ascii=True),
                    start_message_id,
                    end_message_id,
                    timestamp,
                    timestamp,
                    json.dumps(metadata or {}, ensure_ascii=True),
                ),
            )
            if gist_processed_message_ids:
                placeholders = ",".join("?" for _ in gist_processed_message_ids)
                connection.execute(
                    f"UPDATE messages SET gist_processed = 1 "
                    f"WHERE id IN ({placeholders})",
                    gist_processed_message_ids,
                )
            return int(cursor.lastrowid)

    def chat_gist(self, gist_id: int) -> StoredChatGist | None:
        """Load one chat gist by id."""
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    chat_id,
                    source_type,
                    gist_text,
                    topics_json,
                    decisions_json,
                    open_tasks_json,
                    start_message_id,
                    end_message_id,
                    created_at,
                    updated_at,
                    metadata_json
                FROM chat_gists
                WHERE id = ?
                """,
                (gist_id,),
            ).fetchone()
        return self._chat_gist_from_row(row) if row else None

    def chat_gists_for_chat(
        self,
        chat_id: str,
        source_type: str | None = None,
    ) -> list[StoredChatGist]:
        """List gists for one chat, optionally filtered by source type."""
        parameters: list[object] = [chat_id]
        source_clause = ""
        if source_type:
            source_clause = "AND source_type = ?"
            parameters.append(source_type)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    id,
                    chat_id,
                    source_type,
                    gist_text,
                    topics_json,
                    decisions_json,
                    open_tasks_json,
                    start_message_id,
                    end_message_id,
                    created_at,
                    updated_at,
                    metadata_json
                FROM chat_gists
                WHERE chat_id = ?
                {source_clause}
                ORDER BY updated_at DESC, id DESC
                """,
                parameters,
            ).fetchall()
        return [self._chat_gist_from_row(row) for row in rows]

    def chat_gists_by_source_type(self, source_type: str) -> list[StoredChatGist]:
        """List all gists for one source type."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    chat_id,
                    source_type,
                    gist_text,
                    topics_json,
                    decisions_json,
                    open_tasks_json,
                    start_message_id,
                    end_message_id,
                    created_at,
                    updated_at,
                    metadata_json
                FROM chat_gists
                WHERE source_type = ?
                ORDER BY updated_at DESC, id DESC
                """,
                (source_type,),
            ).fetchall()
        return [self._chat_gist_from_row(row) for row in rows]

    def _chat_from_row(self, row: sqlite3.Row) -> StoredChat:
        return StoredChat(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            model_name=row["model_name"],
        )

    def _message_from_row(self, row: sqlite3.Row) -> StoredMessage:
        return StoredMessage(
            id=row["id"],
            chat_id=row["chat_id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
            summarized=bool(row["summarized"]),
            gist_processed=bool(row["gist_processed"]),
        )

    def _chat_gist_from_row(self, row: sqlite3.Row) -> StoredChatGist:
        return StoredChatGist(
            id=row["id"],
            chat_id=row["chat_id"],
            source_type=row["source_type"],
            gist_text=row["gist_text"],
            topics_json=row["topics_json"],
            decisions_json=row["decisions_json"],
            open_tasks_json=row["open_tasks_json"],
            start_message_id=row["start_message_id"],
            end_message_id=row["end_message_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata_json=row["metadata_json"],
        )


MESSAGE_ID_METADATA_KEYS = {
    "start_message_id",
    "end_message_id",
    "message_start_id",
    "message_end_id",
    "last_summarized_message_id",
}
CHAT_ID_METADATA_KEYS = {"chat_id", "source_chat_id"}


def remap_message_id(
    message_id: int | None,
    message_id_map: dict[int, int],
) -> int | None:
    """Map one optional chat-local message id or reject stale provenance."""
    if message_id is None:
        return None
    try:
        return message_id_map[int(message_id)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Cannot remap chat-local message id: {message_id}") from exc


def remap_chat_local_json(
    value: str,
    *,
    message_id_map: dict[int, int],
    source_chat_id: str,
    new_chat_id: str,
) -> str:
    """Remap message/chat provenance inside one JSON document."""
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Cannot fork invalid chat-local JSON") from exc
    remapped = remap_chat_local_provenance(
        parsed,
        message_id_map=message_id_map,
        source_chat_id=source_chat_id,
        new_chat_id=new_chat_id,
    )
    return json.dumps(remapped, ensure_ascii=True)


def remap_chat_local_provenance(
    value: Any,
    *,
    message_id_map: dict[int, int],
    source_chat_id: str,
    new_chat_id: str,
) -> Any:
    """Recursively remap recognized chat-local provenance fields."""
    if isinstance(value, list):
        return [
            remap_chat_local_provenance(
                item,
                message_id_map=message_id_map,
                source_chat_id=source_chat_id,
                new_chat_id=new_chat_id,
            )
            for item in value
        ]
    if not isinstance(value, dict):
        return value

    remapped: dict[str, Any] = {}
    for key, item in value.items():
        if key == "source_message_ids":
            if not isinstance(item, list):
                raise ValueError("source_message_ids must be a list")
            remapped[key] = [
                remap_message_id(message_id, message_id_map)
                for message_id in item
            ]
        elif key in MESSAGE_ID_METADATA_KEYS:
            remapped[key] = remap_message_id(item, message_id_map)
        elif key in CHAT_ID_METADATA_KEYS and item == source_chat_id:
            remapped[key] = new_chat_id
        else:
            remapped[key] = remap_chat_local_provenance(
                item,
                message_id_map=message_id_map,
                source_chat_id=source_chat_id,
                new_chat_id=new_chat_id,
            )
    return remapped
