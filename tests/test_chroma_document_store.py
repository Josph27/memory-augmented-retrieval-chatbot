from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.agents.document_ingestion_agent import DocumentIngestionAgent
from src.agents.context_manager_agent import ContextManagerAgent
from src.core.contracts import SourcePlan
from src.database import Database, utc_now
from src.orchestration.demo_orchestration import run_read_only_langgraph_orchestration
from src.retrieval.langchain_chroma_retriever import LangChainChromaRetriever
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher


LEGACY_DOCUMENT_TABLES = {
    "document_chunk_embeddings",
    "document_chunks",
    "documents",
}
LIVE_TABLES = {
    "chats",
    "messages",
    "chat_gists",
    "long_term_memories",
    "chat_memory_state",
}


class DeterministicEmbeddings:
    """Small local embedding stub suitable for persistent Chroma tests."""

    @staticmethod
    def _embed(text: str) -> list[float]:
        normalized = text.lower()
        return [
            1.0 if "papaya-64217" in normalized else 0.0,
            1.0 if "unrelated" in normalized else 0.0,
            0.5,
        ]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class LocalChromaRetriever(LangChainChromaRetriever):
    def _embeddings(self) -> DeterministicEmbeddings:
        return DeterministicEmbeddings()


def sqlite_tables(path: Path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }


def table_counts(path: Path, table_names: set[str]) -> dict[str, int]:
    with sqlite3.connect(path) as connection:
        return {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in table_names
        }


def test_chroma_is_persistent_global_document_store_without_sqlite_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path = tmp_path / "chatbot.db"
    chroma_path = tmp_path / "chroma"
    database = Database(sqlite_path)
    source_path = tmp_path / "papaya.txt"
    source_path.write_text(
        "The persistent marker is papaya-64217-chroma-only-document.",
        encoding="utf-8",
    )
    first_retriever = LocalChromaRetriever(
        persist_dir=chroma_path,
        collection_name="document_memory",
    )

    result = DocumentIngestionAgent(indexer=first_retriever).index_file(source_path)

    assert result.indexed is True
    assert result.chunk_count == 1
    assert not LEGACY_DOCUMENT_TABLES & sqlite_tables(sqlite_path)
    assert first_retriever._vectorstore()._collection.count() == 1
    database.create_chat("graph-document-chat")
    database.create_document_record(
        result.document_id,
        "papaya.txt",
        status="Ready",
        source=str(source_path),
    )
    database.associate_document_with_chat(
        "graph-document-chat",
        result.document_id,
    )

    def fail_on_sqlite_access(self):  # type: ignore[no-untyped-def]
        raise AssertionError("document retrieval must not access SQLite")

    monkeypatch.setattr(Database, "connect", fail_on_sqlite_access)
    recreated = LocalChromaRetriever(
        persist_dir=chroma_path,
        collection_name="document_memory",
    )
    candidates = recreated.retrieve(
        chat_id="different-chat",
        source_plan=SourcePlan(
            source="document_memory",
            enabled=True,
            query="What is the papaya-64217 marker?",
            limit=1,
        ),
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source == "document_memory"
    assert "papaya-64217-chroma-only-document" in candidate.content
    assert candidate.metadata["document_id"] == result.document_id
    assert candidate.metadata["chunk_index"] == 0
    assert candidate.metadata["file_name"] == "papaya.txt"
    assert candidate.metadata["retrieval_backend"] == "langchain_chroma"

    monkeypatch.undo()
    count_before_graph = recreated._vectorstore()._collection.count()
    graph_result = run_read_only_langgraph_orchestration(
        chat_id="graph-document-chat",
        query="According to the uploaded document, what is the papaya-64217 marker?",
        dispatcher=RetrieverDispatcher(
            database,
            retrievers={"document_memory": recreated},
        ),
        reranker=MemoryReranker(mode="deterministic"),
        context_manager=ContextManagerAgent(),
        system_prompt="Use document evidence.",
    )

    assert any(
        item.source == "document_memory"
        for item in graph_result.context_packet.candidates
    )
    assert recreated._vectorstore()._collection.count() == count_before_graph


def test_clean_database_never_creates_legacy_document_tables(tmp_path: Path) -> None:
    path = tmp_path / "clean.db"

    Database(path)

    tables = sqlite_tables(path)
    assert LIVE_TABLES <= tables
    assert not LEGACY_DOCUMENT_TABLES & tables


def test_repeated_stable_document_id_does_not_duplicate_logical_chunks(
    tmp_path: Path,
) -> None:
    retriever = LocalChromaRetriever(
        persist_dir=tmp_path / "chroma",
        collection_name="document_memory",
    )

    first = retriever.index_text_document(
        "Report",
        "The stable marker is papaya-64217.",
        metadata={"document_id": "stable-document", "file_name": "report.txt"},
    )
    second = retriever.index_text_document(
        "Report",
        "The stable marker is papaya-64217.",
        metadata={"document_id": "stable-document", "file_name": "report.txt"},
    )

    assert first.document_id == second.document_id == "stable-document"
    assert retriever._vectorstore()._collection.count() == 1


def test_existing_database_drops_legacy_document_tables_and_preserves_live_rows(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy.db"
    database = Database(path)
    database.create_chat("chat-1", title="Preserved")
    message_id = database.save_message("chat-1", "user", "preserve this message")
    database.upsert_chat_memory_state("chat-1", '{"preserved": true}')
    database.insert_chat_gist(
        chat_id="chat-1",
        source_type="previous_chat_gist",
        gist_text="Preserved gist",
        start_message_id=message_id,
        end_message_id=message_id,
    )
    timestamp = utc_now()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO long_term_memories (
                namespace_json, namespace_path, memory_id, category, key, value,
                confidence, status, source_chat_id, source_message_ids_json,
                created_at, updated_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                '["user", "test"]',
                "user/test",
                "memory-1",
                "preference",
                "framework",
                "Chroma",
                0.9,
                "active",
                "chat-1",
                f"[{message_id}]",
                timestamp,
                timestamp,
                "{}",
            ),
        )
        connection.executescript(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL
            );
            CREATE TABLE document_chunks (
                id INTEGER PRIMARY KEY,
                document_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            );
            CREATE TABLE document_chunk_embeddings (
                id INTEGER PRIMARY KEY,
                chunk_id INTEGER NOT NULL,
                vector_json TEXT NOT NULL,
                FOREIGN KEY (chunk_id) REFERENCES document_chunks(id)
            );
            INSERT INTO documents (id, title) VALUES (1, 'Legacy');
            INSERT INTO document_chunks (id, document_id, text)
            VALUES (1, 1, 'intentionally abandoned');
            INSERT INTO document_chunk_embeddings (id, chunk_id, vector_json)
            VALUES (1, 1, '[0.1]');
            """
        )
    before = table_counts(path, LIVE_TABLES)

    Database(path)

    assert not LEGACY_DOCUMENT_TABLES & sqlite_tables(path)
    assert table_counts(path, LIVE_TABLES) == before
