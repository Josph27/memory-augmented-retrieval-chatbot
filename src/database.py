from __future__ import annotations

import sqlite3
import json
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
    chat_id: str
    role: str
    content: str
    created_at: str
    summarized: bool = False


@dataclass(frozen=True)
class StoredChat:
    """A chat thread loaded from SQLite."""

    id: str
    title: str | None
    created_at: str
    updated_at: str
    model_name: str | None


@dataclass(frozen=True)
class StoredDocumentChunk:
    """A plain-text document chunk loaded from SQLite."""

    id: int
    document_id: int
    document_title: str
    chunk_index: int
    text: str
    created_at: str
    metadata_json: str


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
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")

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
                    model_name TEXT
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

                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS document_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS document_chunk_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_id INTEGER NOT NULL,
                    embedding_model TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    vector_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(chunk_id, embedding_model),
                    FOREIGN KEY (chunk_id) REFERENCES document_chunks(id) ON DELETE CASCADE
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

                CREATE INDEX IF NOT EXISTS idx_document_chunks_document
                ON document_chunks(document_id, chunk_index);

                CREATE INDEX IF NOT EXISTS idx_document_chunk_embeddings_model
                ON document_chunk_embeddings(embedding_model);

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
            self._ensure_chats_model_name_column(connection)
            self._ensure_long_term_memories_use_count_column(connection)
            self._ensure_chat_gists_retrieved_lt_mem_list_column(connection)
            self._ensure_chat_gists_new_memories_column(connection)
            self._ensure_chats_active_column(connection)
            self._ensure_long_term_memories_last_used_column(connection)
            self._ensure_documents_active_column(connection)
            self._ensure_document_chunks_active_column(connection)
            self._ensure_document_chunks_chroma_id_column(connection)
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_chat_summarized
                ON messages(chat_id, summarized, id)
                """
            )

    def _ensure_messages_summarized_column(self, connection: sqlite3.Connection) -> None:
        """Add `messages.summarized` for databases created before Short-Term Memory v2."""
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "summarized" not in columns:
            connection.execute(
                "ALTER TABLE messages ADD COLUMN summarized INTEGER NOT NULL DEFAULT 0"
            )

    def _ensure_chats_model_name_column(self, connection: sqlite3.Connection) -> None:
        """Add `chats.model_name` for databases created before model profiles."""
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(chats)").fetchall()}
        if "model_name" not in columns:
            connection.execute("ALTER TABLE chats ADD COLUMN model_name TEXT")

    def _ensure_chats_active_column(self, connection: sqlite3.Connection) -> None:
        """Add `chats.active` for active/inactive chat tracking."""
        try:
            connection.execute("ALTER TABLE chats ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
        except sqlite3.OperationalError:
            pass  # column already exists

    def _ensure_long_term_memories_last_used_column(self, connection: sqlite3.Connection) -> None:
        """Add `long_term_memories.last_used` for retrieval-time tracking."""
        try:
            connection.execute("ALTER TABLE long_term_memories ADD COLUMN last_used TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

    def _ensure_long_term_memories_use_count_column(self, connection: sqlite3.Connection) -> None:
        """Add `long_term_memories.use_count` for usage-tracking migrations."""
        try:
            connection.execute(
                "ALTER TABLE long_term_memories ADD COLUMN use_count INTEGER NOT NULL DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass  # column already exists

    def _ensure_chat_gists_retrieved_lt_mem_list_column(
        self, connection: sqlite3.Connection
    ) -> None:
        """Add `chat_gists.retrieved_lt_mem_list_json` for GIST retrieval tracking."""
        try:
            connection.execute(
                "ALTER TABLE chat_gists ADD COLUMN retrieved_lt_mem_list_json"
                " TEXT NOT NULL DEFAULT '[]'"
            )
        except sqlite3.OperationalError:
            pass  # column already exists

    def _ensure_chat_gists_new_memories_column(self, connection: sqlite3.Connection) -> None:
        """Add `chat_gists.new_memories_json` for GIST memory-link tracking."""
        try:
            connection.execute(
                "ALTER TABLE chat_gists ADD COLUMN new_memories_json TEXT NOT NULL DEFAULT '[]'"
            )
        except sqlite3.OperationalError:
            pass  # column already exists

    def increment_use_count(self, connection: sqlite3.Connection, memory_ids: list[int]) -> None:
        """Increment the use_count and refresh last_used for a set of long-term memory rows."""
        if not memory_ids:
            return
        placeholders = ",".join("?" for _ in memory_ids)
        params = [utc_now()] + list(memory_ids)
        connection.execute(
            f"UPDATE long_term_memories SET use_count = use_count + 1, last_used = ? WHERE id IN ({placeholders})",
            params,
        )

    def _ensure_documents_active_column(self, connection: sqlite3.Connection) -> None:
        """Add `documents.active` for document suppression support."""
        try:
            connection.execute("ALTER TABLE documents ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
        except sqlite3.OperationalError:
            pass  # column already exists

    def _ensure_document_chunks_active_column(self, connection: sqlite3.Connection) -> None:
        """Add `document_chunks.active` for per-chunk suppression."""
        try:
            connection.execute(
                "ALTER TABLE document_chunks ADD COLUMN active INTEGER NOT NULL DEFAULT 1"
            )
        except sqlite3.OperationalError:
            pass  # column already exists

    def _ensure_document_chunks_chroma_id_column(self, connection: sqlite3.Connection) -> None:
        """Add `document_chunks.chroma_id` for Chroma metadata sync."""
        try:
            connection.execute("ALTER TABLE document_chunks ADD COLUMN chroma_id TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

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
        """List chat threads for Chainlit history (active only)."""
        parameters: list[object] = []
        clauses: list[str] = ["active = 1"]
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

    def mark_chat_inactive(self, chat_id: str) -> None:
        """Mark a chat as inactive (e.g. after CHAT_END_ACTION)."""
        with self.connect() as connection:
            connection.execute("UPDATE chats SET active = 0 WHERE id = ?", (chat_id,))

    def mark_chat_active(self, chat_id: str) -> None:
        """Mark a chat as active."""
        with self.connect() as connection:
            connection.execute("UPDATE chats SET active = 1 WHERE id = ?", (chat_id,))

    def list_active_chats(self) -> list[dict]:
        """Return all active chats ordered by last update."""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM chats WHERE active = 1 ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    def list_inactive_chats(self) -> list[dict]:
        """Return all inactive chats ordered by last update."""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM chats WHERE active = 0 ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Document management
    # ------------------------------------------------------------------

    def suppress_document(self, doc_id: int) -> None:
        """Set active=0 on a document and all its chunks."""
        with self.connect() as conn:
            conn.execute("UPDATE documents SET active = 0 WHERE id = ?", (doc_id,))
            conn.execute("UPDATE document_chunks SET active = 0 WHERE document_id = ?", (doc_id,))

    def delete_document(self, doc_id: int) -> None:
        """Delete a document and cascade to chunks and embeddings."""
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM document_chunk_embeddings WHERE chunk_id IN"
                " (SELECT id FROM document_chunks WHERE document_id = ?)",
                (doc_id,),
            )
            conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    def list_documents(self, active_only: bool = True) -> list[dict]:
        """List documents with optional active-only filter."""
        with self.connect() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM documents WHERE active = 1 ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
            return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Manual memory management
    # ------------------------------------------------------------------

    MAX_MANUAL_MEMORY_CHARS = 2000

    def insert_manual_memory(
        self,
        *,
        namespace: str,
        key: str,
        value: str,
        category: str = "user_facts",
        confidence: float = 1.0,
    ) -> int:
        """Insert a manually created memory. Returns the memory id."""
        if len(value) > self.MAX_MANUAL_MEMORY_CHARS:
            value = value[: self.MAX_MANUAL_MEMORY_CHARS]
        now = utc_now()
        namespace_json = json.dumps({"path": namespace.split(".")}, ensure_ascii=True)
        with self.connect() as conn:
            cursor = conn.execute(
                """INSERT INTO long_term_memories (
                       namespace_json, namespace_path, memory_id, category, key, value,
                       confidence, status, source_chat_id, source_message_ids_json,
                       created_at, updated_at, metadata_json
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', 'manual', '[]', ?, ?, '{}')""",
                (namespace_json, namespace, key, category, key, value, confidence, now, now),
            )
            return int(cursor.lastrowid)

    def delete_memory_by_id(self, memory_id: int) -> None:
        """Soft-delete a memory by row id (sets status to 'deleted')."""
        with self.connect() as conn:
            conn.execute(
                "UPDATE long_term_memories SET status = 'deleted', updated_at = ? WHERE id = ?",
                (utc_now(), memory_id),
            )

    def list_all_memories(self, search: str | None = None) -> list[dict]:
        """List active memories with optional search filter."""
        with self.connect() as conn:
            if search:
                rows = conn.execute(
                    "SELECT * FROM long_term_memories WHERE status = 'active' "
                    "AND (key LIKE ? OR value LIKE ?) ORDER BY updated_at DESC",
                    (f"%{search}%", f"%{search}%"),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM long_term_memories WHERE status = 'active' "
                    "ORDER BY updated_at DESC"
                ).fetchall()
            return [dict(row) for row in rows]

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
                SELECT id, chat_id, role, content, created_at, summarized
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
                SELECT id, chat_id, role, content, created_at, summarized
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
                SELECT id, chat_id, role, content, created_at, summarized
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
                SELECT id, chat_id, role, content, created_at, summarized
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
                SELECT id, chat_id, role, content, created_at, summarized
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
                SELECT id, chat_id, role, content, created_at, summarized
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

    def insert_document(
        self,
        title: str,
        source: str,
        metadata: dict | None = None,
    ) -> int:
        """Insert a plain-text document record."""
        timestamp = utc_now()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=True)
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO documents (title, source, created_at, metadata_json)
                VALUES (?, ?, ?, ?)
                """,
                (title, source, timestamp, metadata_json),
            )
            return int(cursor.lastrowid)

    def insert_document_chunk(
        self,
        document_id: int,
        chunk_index: int,
        text: str,
        metadata: dict | None = None,
    ) -> int:
        """Insert one plain-text document chunk."""
        timestamp = utc_now()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=True)
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO document_chunks (
                    document_id, chunk_index, text, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (document_id, chunk_index, text, timestamp, metadata_json),
            )
            return int(cursor.lastrowid)

    def document_chunks(self) -> list[StoredDocumentChunk]:
        """Load all document chunks for simple local keyword retrieval."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    document_chunks.id,
                    document_chunks.document_id,
                    documents.title AS document_title,
                    document_chunks.chunk_index,
                    document_chunks.text,
                    document_chunks.created_at,
                    document_chunks.metadata_json
                FROM document_chunks
                JOIN documents ON documents.id = document_chunks.document_id
                ORDER BY document_chunks.document_id, document_chunks.chunk_index
                """
            ).fetchall()

        return [self._document_chunk_from_row(row) for row in rows]

    def document_chunks_for_document(self, document_id: int) -> list[StoredDocumentChunk]:
        """Load all chunks for one document."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    document_chunks.id,
                    document_chunks.document_id,
                    documents.title AS document_title,
                    document_chunks.chunk_index,
                    document_chunks.text,
                    document_chunks.created_at,
                    document_chunks.metadata_json
                FROM document_chunks
                JOIN documents ON documents.id = document_chunks.document_id
                WHERE document_chunks.document_id = ?
                ORDER BY document_chunks.chunk_index
                """,
                (document_id,),
            ).fetchall()

        return [self._document_chunk_from_row(row) for row in rows]

    def document_chunks_by_ids(self, chunk_ids: list[int]) -> list[StoredDocumentChunk]:
        """Load chunks by id, preserving the input order when possible."""
        if not chunk_ids:
            return []
        placeholders = ",".join("?" for _ in chunk_ids)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    document_chunks.id,
                    document_chunks.document_id,
                    documents.title AS document_title,
                    document_chunks.chunk_index,
                    document_chunks.text,
                    document_chunks.created_at,
                    document_chunks.metadata_json
                FROM document_chunks
                JOIN documents ON documents.id = document_chunks.document_id
                WHERE document_chunks.id IN ({placeholders})
                """,
                chunk_ids,
            ).fetchall()

        chunks_by_id = {row["id"]: self._document_chunk_from_row(row) for row in rows}
        return [chunks_by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in chunks_by_id]

    def upsert_chunk_embedding(
        self,
        chunk_id: int,
        embedding_model: str,
        vector: list[float],
        metadata: dict | None = None,
    ) -> None:
        """Store a chunk embedding as JSON for the fallback vector backend."""
        timestamp = utc_now()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=True)
        vector_json = json.dumps(vector, ensure_ascii=True)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO document_chunk_embeddings (
                    chunk_id, embedding_model, dimension, vector_json, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id, embedding_model) DO UPDATE SET
                    dimension = excluded.dimension,
                    vector_json = excluded.vector_json,
                    created_at = excluded.created_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    chunk_id,
                    embedding_model,
                    len(vector),
                    vector_json,
                    timestamp,
                    metadata_json,
                ),
            )

    def has_chunk_embedding(self, chunk_id: int, embedding_model: str) -> bool:
        """Return whether an embedding exists for a chunk/model pair."""
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM document_chunk_embeddings
                WHERE chunk_id = ? AND embedding_model = ?
                """,
                (chunk_id, embedding_model),
            ).fetchone()
        return row is not None

    def chunk_embeddings(self, embedding_model: str) -> list[sqlite3.Row]:
        """Load stored JSON embeddings for one model."""
        with self.connect() as connection:
            return connection.execute(
                """
                SELECT chunk_id, vector_json, metadata_json
                FROM document_chunk_embeddings
                WHERE embedding_model = ?
                """,
                (embedding_model,),
            ).fetchall()

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
    ) -> int:
        """Insert one chat gist without generating or validating its content."""
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
        )

    def _document_chunk_from_row(self, row: sqlite3.Row) -> StoredDocumentChunk:
        return StoredDocumentChunk(
            id=row["id"],
            document_id=row["document_id"],
            document_title=row["document_title"],
            chunk_index=row["chunk_index"],
            text=row["text"],
            created_at=row["created_at"],
            metadata_json=row["metadata_json"],
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
