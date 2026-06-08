from __future__ import annotations

from pathlib import Path

from src.core.contracts import SourcePlan
from src.database import Database
from src.retrieval.langchain_chroma_retriever import (
    LangChainChromaRetriever,
    LangChainChromaUnavailable,
    documents_missing_from_store,
    langchain_document_to_memory_candidate,
    metadata_for_stored_chunk,
)
from src.retrieval.retriever_dispatcher import document_retriever_for_env


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
    def index_sqlite_chunks_if_needed(self) -> None:
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


def test_metadata_for_stored_chunk_preserves_sqlite_chunk_fields(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    document_id = database.insert_document("Notes", "test", {"kind": "note"})
    chunk_id = database.insert_document_chunk(
        document_id=document_id,
        chunk_index=3,
        text="Chunk text",
        metadata={"source": "manual", "splitter_name": "langchain_recursive"},
    )
    chunk = database.document_chunks_by_ids([chunk_id])[0]

    metadata = metadata_for_stored_chunk(chunk)

    assert metadata["document_id"] == document_id
    assert metadata["chunk_id"] == chunk_id
    assert metadata["chunk_index"] == 3
    assert metadata["title"] == "Notes"
    assert metadata["source"] == "manual"
    assert metadata["splitter_name"] == "langchain_recursive"


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

    retriever = document_retriever_for_env(database)

    assert isinstance(retriever, LangChainChromaRetriever)


def test_documents_missing_from_store_filters_existing_ids() -> None:
    class FakeVectorStore:
        def get(self, ids):
            return {"ids": [ids[0]]}

    documents = [FakeDocument("one", {}), FakeDocument("two", {})]

    missing_documents, missing_ids = documents_missing_from_store(
        FakeVectorStore(),
        documents,
        ["1", "2"],
    )

    assert missing_documents == [documents[1]]
    assert missing_ids == ["2"]
