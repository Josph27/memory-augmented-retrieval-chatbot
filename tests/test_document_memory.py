from __future__ import annotations

from pathlib import Path

import pytest

from src.context.context_budget_allocator import ContextBudgetAllocator
from src.context.context_builder import ContextBuilder
from src.core.contracts import SourcePlan
from src.database import Database
from src.documents.splitters import (
    ChunkingConfig,
    LangChainRecursiveSplitter,
    LangChainSplitterUnavailable,
    split_document_text,
    split_text_into_chunks,
)
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.retrieval.reranker import MemoryReranker
from src.routing.route_planner import RoutePlanner


class FakeDocumentMemoryRetriever:
    def __init__(self, content: str) -> None:
        self.content = content

    def retrieve(self, chat_id: str, source_plan: SourcePlan):
        del chat_id, source_plan
        from src.core.contracts import MemoryCandidate

        return [
            MemoryCandidate(
                source="document_memory",
                content=self.content,
                record_id="fake-document",
                metadata={
                    "title": "Fake Document",
                    "retrieval_backend": "langchain_chroma",
                    "status": "active",
                },
            )
        ]


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


def test_document_retrieval_flows_through_dispatcher_when_enabled(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    route_plan = RoutePlanner().plan("According to the document, which model is configured?")

    candidates = RetrieverDispatcher(
        database,
        retrievers={
            "document_memory": FakeDocumentMemoryRetriever(
                "The configured local model is qwen2.5:3b."
            )
        },
    ).retrieve("chat", route_plan)

    document_candidates = [
        candidate for candidate in candidates if candidate.source == "document_memory"
    ]
    assert document_candidates
    assert "qwen2.5:3b" in document_candidates[0].content


def test_document_candidates_reach_context_packet_document_section(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    route_plan = RoutePlanner().plan("According to the document, where is the latest user message?")
    retrieved = RetrieverDispatcher(
        database,
        retrievers={
            "document_memory": FakeDocumentMemoryRetriever(
                "The latest user message must appear exactly once at the end."
            )
        },
    ).retrieve("chat", route_plan)
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
    assert any("Document Memory:" in content for content in contents)
    assert route_plan.query in contents[-1]
    assert sum(route_plan.query in content for content in contents) >= 1
