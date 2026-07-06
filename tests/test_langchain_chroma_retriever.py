from __future__ import annotations

from pathlib import Path

from src.core.contracts import SourcePlan
from src.database import Database
from src.retrieval.langchain_chroma_retriever import (
    LangChainChromaRetriever,
    LangChainChromaUnavailable,
    langchain_document_to_memory_candidate,
)
from src.retrieval.retriever_dispatcher import langchain_chroma_retriever_for_env


class FakeDocument:
    def __init__(self, page_content: str, metadata: dict) -> None:
        self.page_content = page_content
        self.metadata = metadata


class FakeFallbackRetriever:
    def retrieve(self, chat_id: str, source_plan: SourcePlan):
        del chat_id, source_plan
        return [
            langchain_document_to_memory_candidate(
                FakeDocument("Fallback content", {"document_id": "fallback-doc"}),
                0.25,
            )
        ]


class UnavailableLangChainRetriever(LangChainChromaRetriever):
    def _similarity_search(self, query: str, limit: int):
        del query, limit
        raise LangChainChromaUnavailable("missing optional dependency")


def test_langchain_document_to_memory_candidate_preserves_metadata() -> None:
    document = FakeDocument(
        "The project uses Chroma for document retrieval.",
        {
            "document_id": "doc-1",
            "chunk_id": "chunk-1",
            "chunk_index": 2,
            "title": "Project Notes",
            "source": "test",
        },
    )

    candidate = langchain_document_to_memory_candidate(document, 0.87)

    assert candidate.source == "document_memory"
    assert candidate.content == "The project uses Chroma for document retrieval."
    assert candidate.score == 0.87
    assert candidate.record_id == "chunk-1"
    assert candidate.metadata["document_id"] == "doc-1"
    assert candidate.metadata["chunk_index"] == 2
    assert candidate.metadata["retrieval_backend"] == "langchain_chroma"
    assert candidate.metadata["retrieval_mode"] == "langchain_chroma"
    assert candidate.metadata["similarity_score"] == 0.87


def test_langchain_chroma_retriever_falls_back_when_unavailable() -> None:
    retriever = UnavailableLangChainRetriever(fallback_retriever=FakeFallbackRetriever())

    candidates = retriever.retrieve(
        chat_id="chat",
        source_plan=SourcePlan(
            source="document_memory",
            enabled=True,
            query="question",
            limit=1,
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].content == "Fallback content"


def test_dispatcher_selects_langchain_chroma_by_default(monkeypatch, tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    monkeypatch.delenv("DOCUMENT_RETRIEVAL_MODE", raising=False)

    retriever = langchain_chroma_retriever_for_env(database)

    assert isinstance(retriever, LangChainChromaRetriever)
