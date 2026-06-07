from __future__ import annotations

from pathlib import Path

import pytest

from src.core.contracts import SourcePlan
from src.database import Database
from src.documents.embedding_indexer import DocumentEmbeddingIndexer
from src.documents.ingestion import DocumentIngestionService
from src.embeddings.fake_embedder import FakeEmbedder
from src.retrieval.document_retriever import DocumentRetriever
from src.vectorstores.base import VectorStoreUnavailableError
from src.vectorstores.in_memory_store import InMemoryVectorStore
from src.vectorstores.sqlite_vec_store import SQLiteVecVectorStore


def ingest_two_chunk_document(database: Database) -> int:
    """Create a small document with fruit and database chunks."""
    result = DocumentIngestionService(database, target_chars=80).ingest_text_document(
        title="Mixed Notes",
        text=(
            "Apples and bananas are fruit used in the pantry.\n\n"
            "SQLite stores chatbot messages in local tables."
        ),
        source="test",
    )
    return result.document_id


def test_fake_embedder_is_deterministic() -> None:
    embedder = FakeEmbedder(dimension=8)

    first = embedder.embed_text("banana apple")
    second = embedder.embed_text("banana apple")

    assert first == second
    assert len(first) == 8


def test_in_memory_vector_store_search_ranks_by_similarity() -> None:
    embedder = FakeEmbedder(dimension=16)
    store = InMemoryVectorStore()
    store.upsert_chunk_embedding(1, embedder.embed_text("banana apple"), embedder.model_name)
    store.upsert_chunk_embedding(2, embedder.embed_text("sqlite database"), embedder.model_name)

    results = store.search(
        query_embedding=embedder.embed_text("banana"),
        top_k=2,
        embedding_model=embedder.model_name,
    )

    assert results[0].chunk_id == 1
    assert results[0].score >= results[1].score


def test_embedding_indexer_indexes_and_skips_existing_chunks(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    document_id = ingest_two_chunk_document(database)
    embedder = FakeEmbedder()
    store = InMemoryVectorStore()
    indexer = DocumentEmbeddingIndexer(database)

    first = indexer.index_document_chunks(document_id, embedder, store)
    second = indexer.index_document_chunks(document_id, embedder, store)

    assert first.indexed == 2
    assert first.skipped == 0
    assert second.indexed == 0
    assert second.skipped == 2


def test_vector_retrieval_returns_expected_chunk(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    document_id = ingest_two_chunk_document(database)
    embedder = FakeEmbedder()
    store = InMemoryVectorStore()
    DocumentEmbeddingIndexer(database).index_document_chunks(document_id, embedder, store)

    candidates = DocumentRetriever(
        database=database,
        retrieval_mode="vector",
        embedder=embedder,
        vector_store=store,
    ).retrieve(
        chat_id="chat",
        source_plan=SourcePlan(
            source="document_memory",
            enabled=True,
            query="banana pantry",
            limit=2,
        ),
    )

    assert candidates
    assert "bananas" in candidates[0].content
    assert candidates[0].metadata["retrieval_mode"] == "vector"
    assert candidates[0].metadata["embedding_model"] == embedder.model_name
    assert candidates[0].metadata["vector_score"] > 0


def test_hybrid_retrieval_combines_keyword_and_vector_scores(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    document_id = ingest_two_chunk_document(database)
    embedder = FakeEmbedder()
    store = InMemoryVectorStore()
    DocumentEmbeddingIndexer(database).index_document_chunks(document_id, embedder, store)

    candidates = DocumentRetriever(
        database=database,
        retrieval_mode="hybrid",
        embedder=embedder,
        vector_store=store,
    ).retrieve(
        chat_id="chat",
        source_plan=SourcePlan(
            source="document_memory",
            enabled=True,
            query="SQLite messages",
            limit=2,
        ),
    )

    assert candidates
    assert "SQLite" in candidates[0].content
    assert candidates[0].metadata["retrieval_mode"] == "hybrid"
    assert "keyword_score" in candidates[0].metadata
    assert "vector_score" in candidates[0].metadata


def test_keyword_retrieval_still_works_without_vector_dependencies(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    ingest_two_chunk_document(database)

    candidates = DocumentRetriever(database=database).retrieve(
        chat_id="chat",
        source_plan=SourcePlan(
            source="document_memory",
            enabled=True,
            query="SQLite local tables",
            limit=2,
        ),
    )

    assert candidates
    assert candidates[0].metadata["retrieval_mode"] == "keyword"
    assert "SQLite" in candidates[0].content


def test_sqlite_vec_store_searches_vectors_when_available(tmp_path: Path) -> None:
    pytest.importorskip("sqlite_vec")
    database = Database(tmp_path / "chatbot.db")
    document_id = ingest_two_chunk_document(database)
    embedder = FakeEmbedder()
    try:
        store = SQLiteVecVectorStore(database)
    except VectorStoreUnavailableError as error:
        pytest.skip(str(error))

    DocumentEmbeddingIndexer(database).index_document_chunks(document_id, embedder, store)

    results = store.search(
        query_embedding=embedder.embed_text("banana pantry"),
        top_k=2,
        embedding_model=embedder.model_name,
    )

    assert results
    assert results[0].score > 0
    chunks = database.document_chunks_by_ids([results[0].chunk_id])
    assert chunks
    assert "bananas" in chunks[0].text
    assert database.has_chunk_embedding(results[0].chunk_id, embedder.model_name)


def test_document_retriever_uses_sqlite_vec_backend_when_available(tmp_path: Path) -> None:
    pytest.importorskip("sqlite_vec")
    database = Database(tmp_path / "chatbot.db")
    document_id = ingest_two_chunk_document(database)
    embedder = FakeEmbedder()
    try:
        store = SQLiteVecVectorStore(database)
    except VectorStoreUnavailableError as error:
        pytest.skip(str(error))

    DocumentEmbeddingIndexer(database).index_document_chunks(document_id, embedder, store)
    candidates = DocumentRetriever(
        database=database,
        retrieval_mode="vector",
        embedder=embedder,
        vector_store=store,
    ).retrieve(
        chat_id="chat",
        source_plan=SourcePlan(
            source="document_memory",
            enabled=True,
            query="SQLite local tables",
            limit=2,
        ),
    )

    assert candidates
    assert candidates[0].source == "document_memory"
    assert candidates[0].metadata["retrieval_mode"] == "vector"
    assert "vector_score" in candidates[0].metadata
