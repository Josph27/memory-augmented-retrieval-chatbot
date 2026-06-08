from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.context.context_budget_allocator import ContextBudgetAllocator
from src.context.context_builder import ContextBuilder
from src.core.contracts import SourcePlan
from src.database import Database
from src.documents.ingestion import DocumentIngestionService, split_text_into_chunks
from src.documents.splitters import (
    ChunkingConfig,
    LangChainRecursiveSplitter,
    LangChainSplitterUnavailable,
    split_document_text,
)
from src.retrieval.document_retriever import DocumentRetriever
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.retrieval.reranker import MemoryReranker
from src.routing.route_planner import RoutePlanner


def test_split_text_into_chunks_preserves_paragraphs() -> None:
    text = "First paragraph about SQLite.\n\nSecond paragraph about Chainlit."

    chunks = split_text_into_chunks(text, target_chars=35, max_chars=100)

    assert len(chunks) == 2
    assert chunks[0] == "First paragraph about SQLite."
    assert chunks[1] == "Second paragraph about Chainlit."


def test_custom_splitter_returns_chunk_metadata() -> None:
    chunks = split_document_text(
        "First paragraph about SQLite.\n\nSecond paragraph about Chainlit.",
        ChunkingConfig(chunker="custom", target_chars=35, max_chars=100),
    )

    assert len(chunks) == 2
    assert chunks[0].text == "First paragraph about SQLite."
    assert chunks[0].metadata["splitter_name"] == "custom_paragraph"
    assert chunks[0].metadata["chunk_size"] == 35
    assert chunks[0].metadata["chunk_overlap"] == 0
    assert chunks[0].metadata["fallback_used"] is False
    assert chunks[0].metadata["start_char"] == 0


def test_langchain_splitter_adapter_works_when_installed() -> None:
    pytest.importorskip("langchain_text_splitters")
    chunks = LangChainRecursiveSplitter(
        ChunkingConfig(
            chunker="langchain_recursive",
            chunk_size=30,
            chunk_overlap=10,
        )
    ).split("alpha beta gamma delta epsilon zeta eta theta iota kappa")

    assert len(chunks) > 1
    assert chunks[0].metadata["splitter_name"] == "langchain_recursive"
    assert chunks[0].metadata["chunk_size"] == 30
    assert chunks[0].metadata["chunk_overlap"] == 10
    assert chunks[0].metadata["fallback_used"] is False


def test_langchain_splitter_falls_back_to_custom_when_unavailable(monkeypatch) -> None:
    def unavailable() -> type:
        raise LangChainSplitterUnavailable("not installed")

    monkeypatch.setattr("src.documents.splitters.import_recursive_character_splitter", unavailable)

    chunks = split_document_text(
        "First paragraph about SQLite.\n\nSecond paragraph about Chainlit.",
        ChunkingConfig(chunker="langchain_recursive", target_chars=35, max_chars=100),
    )

    assert len(chunks) == 2
    assert chunks[0].metadata["splitter_name"] == "custom_paragraph"
    assert chunks[0].metadata["fallback_used"] is True
    assert chunks[0].metadata["requested_splitter"] == "langchain_recursive"


def test_document_ingestion_stores_document_and_chunks(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    service = DocumentIngestionService(database, target_chars=40, max_chars=100)

    result = service.ingest_text_document(
        title="Project Notes",
        text="SQLite stores rows.\n\nChainlit handles the UI.",
        source="test",
        metadata={"kind": "notes"},
    )

    chunks = database.document_chunks()
    assert result.document_id > 0
    assert result.chunk_count == 2
    assert len(chunks) == 2
    assert chunks[0].document_id == result.document_id
    assert chunks[0].document_title == "Project Notes"
    assert chunks[0].text == "SQLite stores rows."
    metadata = json.loads(chunks[0].metadata_json)
    assert metadata["title"] == "Project Notes"
    assert metadata["source"] == "test"
    assert metadata["splitter_name"] == "custom_paragraph"
    assert metadata["chunk_size"] == 40
    assert metadata["fallback_used"] is False


def test_document_retriever_returns_relevant_chunk_with_metadata(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    DocumentIngestionService(database, target_chars=80).ingest_text_document(
        title="Storage Notes",
        text="SQLite stores raw messages.\n\nThe UI is built with Chainlit.",
        source="test",
    )

    candidates = DocumentRetriever(database).retrieve(
        chat_id="chat",
        source_plan=SourcePlan(
            source="document_memory",
            enabled=True,
            query="Which database stores raw messages?",
            limit=2,
        ),
    )

    assert candidates
    assert candidates[0].source == "document_memory"
    assert "SQLite stores raw messages" in candidates[0].content
    assert candidates[0].metadata["title"] == "Storage Notes"
    assert candidates[0].metadata["chunk_id"] == candidates[0].record_id
    assert candidates[0].metadata["similarity_score"] > 0
    assert "database" in candidates[0].metadata["matched_terms"] or "stores" in candidates[
        0
    ].metadata["matched_terms"]


def test_document_retrieval_flows_through_dispatcher_when_enabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DOCUMENT_RETRIEVAL_MODE", "keyword")
    database = Database(tmp_path / "chatbot.db")
    DocumentIngestionService(database).ingest_text_document(
        title="Model Notes",
        text="The configured local model is qwen2.5:3b.",
        source="test",
    )
    route_plan = RoutePlanner().plan("According to the document, which model is configured?")

    candidates = RetrieverDispatcher(database).retrieve("chat", route_plan)

    document_candidates = [
        candidate for candidate in candidates if candidate.source == "document_memory"
    ]
    assert document_candidates
    assert "qwen2.5:3b" in document_candidates[0].content


def test_document_candidates_reach_context_packet_document_section(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DOCUMENT_RETRIEVAL_MODE", "keyword")
    database = Database(tmp_path / "chatbot.db")
    DocumentIngestionService(database).ingest_text_document(
        title="Context Notes",
        text="The latest user message must appear exactly once at the end.",
        source="test",
    )
    route_plan = RoutePlanner().plan("According to the document, where is the latest user message?")
    retrieved = RetrieverDispatcher(database).retrieve("chat", route_plan)
    ranked = MemoryReranker().rank(retrieved, route_plan.ranking_profile)
    budget = ContextBudgetAllocator().allocate(
        route_plan=route_plan,
        ranked_candidates=ranked,
        model_context_limit=1000,
        answer_reserve=100,
        system_prompt="system",
    )

    packet = ContextBuilder().build(
        system_prompt="system",
        latest_user_message={"role": "user", "content": route_plan.query},
        ranked_candidates=ranked,
        context_budget=budget,
        route_plan=route_plan,
    )

    contents = [message["content"] for message in packet.model_messages]
    assert any(content.startswith("Document Memory:") for content in contents)
    assert contents[-1] == route_plan.query
    assert contents.count(route_plan.query) == 1
