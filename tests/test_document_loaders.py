from __future__ import annotations

from pathlib import Path

import pytest

from src.documents.loaders import (
    DocumentLoaderError,
    LoadedDocument,
    index_file_document,
    index_loaded_document,
    load_document_file,
)
from src.core.contracts import SourcePlan
from src.retrieval.langchain_chroma_retriever import LangChainChromaRetriever


class FakeIndexer:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def index_text_document(
        self,
        title: str,
        text: str,
        source: str = "manual",
        metadata: dict | None = None,
    ):
        self.calls.append(
            {
                "title": title,
                "text": text,
                "source": source,
                "metadata": metadata or {},
            }
        )
        return {"document_id": "fake-doc", "chunk_count": 1}


class FakeVectorStore:
    def __init__(self) -> None:
        self.documents = []
        self.ids = []

    def add_documents(self, documents, ids):
        self.documents.extend(documents)
        self.ids.extend(ids)

    def similarity_search_with_score(self, query: str, k: int):
        query_terms = {term.lower().strip("?.:,") for term in query.split()}
        scored = []
        for document in self.documents:
            content = document.page_content.lower()
            score = 0.1
            if any(term and term in content for term in query_terms):
                score = 0.95
            scored.append((document, score))
        return sorted(scored, key=lambda item: item[1], reverse=True)[:k]


class FakeLangChainChromaRetriever(LangChainChromaRetriever):
    def __init__(self) -> None:
        super().__init__(persist_dir="unused")
        self.fake_vector_store = FakeVectorStore()

    def _vectorstore(self):
        return self.fake_vector_store


def test_txt_loader_preserves_text_and_metadata(tmp_path: Path) -> None:
    path = tmp_path / "sample_report.txt"
    path.write_text("A unique txt fact appears here.", encoding="utf-8")

    loaded = load_document_file(path)

    assert loaded.title == "sample_report"
    assert loaded.text == "A unique txt fact appears here."
    assert loaded.source == "file"
    assert loaded.metadata["file_path"] == str(path)
    assert loaded.metadata["file_name"] == "sample_report.txt"
    assert loaded.metadata["file_extension"] == ".txt"
    assert loaded.metadata["loader_name"] == "path_read_text"


def test_markdown_loader_preserves_text_and_metadata(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("# Notes\n\nMarkdown fact.", encoding="utf-8")

    loaded = load_document_file(path)

    assert loaded.title == "notes"
    assert "# Notes" in loaded.text
    assert loaded.metadata["file_extension"] == ".md"
    assert loaded.metadata["source"] == "file"


def test_unsupported_extension_raises_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "image.png"
    path.write_text("not supported", encoding="utf-8")

    with pytest.raises(DocumentLoaderError, match="Unsupported document extension"):
        load_document_file(path)


def test_missing_file_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(DocumentLoaderError, match="does not exist"):
        load_document_file(tmp_path / "missing.txt")


def test_index_loaded_document_uses_existing_indexing_api() -> None:
    loaded = LoadedDocument(
        title="Report",
        text="Report body",
        source="file",
        metadata={"file_name": "report.txt"},
    )
    indexer = FakeIndexer()

    result = index_loaded_document(loaded, indexer)

    assert result == {"document_id": "fake-doc", "chunk_count": 1}
    assert indexer.calls == [
        {
            "title": "Report",
            "text": "Report body",
            "source": "file",
            "metadata": {"file_name": "report.txt"},
        }
    ]


def test_index_file_document_loads_then_indexes(tmp_path: Path) -> None:
    path = tmp_path / "manual.md"
    path.write_text("Manual body", encoding="utf-8")
    indexer = FakeIndexer()

    index_file_document(path, indexer)

    assert indexer.calls[0]["title"] == "manual"
    assert indexer.calls[0]["text"] == "Manual body"
    assert indexer.calls[0]["source"] == "file"
    assert indexer.calls[0]["metadata"]["file_name"] == "manual.md"


def test_loaded_file_indexes_and_retrieves_document_memory_candidate() -> None:
    path = Path("tests/fixtures/docs/sample_report.txt")
    retriever = FakeLangChainChromaRetriever()

    index_file_document(path, retriever)
    candidates = retriever.retrieve(
        chat_id="chat",
        source_plan=SourcePlan(
            source="document_memory",
            enabled=True,
            query="What is the unique planning code ALPHA-47?",
            limit=1,
        ),
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source == "document_memory"
    assert "ALPHA-47" in candidate.content
    assert candidate.metadata["file_name"] == "sample_report.txt"
    assert candidate.metadata["file_extension"] == ".txt"
    assert candidate.metadata["retrieval_backend"] == "langchain_chroma"


def test_pdf_loader_skips_when_pdf_dependency_unavailable(tmp_path: Path) -> None:
    pypdf = pytest.importorskip("pypdf")
    path = tmp_path / "empty.pdf"
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with path.open("wb") as handle:
        writer.write(handle)

    loaded = load_document_file(path)

    assert loaded.metadata["file_extension"] == ".pdf"
    assert loaded.metadata["page_count"] == 1
