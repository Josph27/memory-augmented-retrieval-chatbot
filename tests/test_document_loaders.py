from __future__ import annotations

from pathlib import Path

import pytest

from src.documents.loaders import (
    DocumentLoaderError,
    LoadedDocument,
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


def test_loader_uses_display_name_for_chainlit_bin_upload(tmp_path: Path) -> None:
    path = tmp_path / "chainlit-upload.bin"
    path.write_text("# README\n\nMarkdown fact.", encoding="utf-8")

    loaded = load_document_file(path, display_name="README.md")

    assert loaded.title == "README"
    assert "# README" in loaded.text
    assert loaded.metadata["file_path"] == str(path)
    assert loaded.metadata["file_name"] == "README.md"
    assert loaded.metadata["file_extension"] == ".md"


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


def test_loaded_file_indexes_with_source_metadata(tmp_path: Path) -> None:
    path = tmp_path / "manual.md"
    path.write_text("Manual body", encoding="utf-8")
    indexer = FakeIndexer()

    index_loaded_document(load_document_file(path), indexer)

    assert indexer.calls[0]["title"] == "manual"
    assert indexer.calls[0]["text"] == "Manual body"
    assert indexer.calls[0]["source"] == "file"
    assert indexer.calls[0]["metadata"]["file_name"] == "manual.md"


def test_loaded_upload_indexes_with_display_name(tmp_path: Path) -> None:
    path = tmp_path / "upload.bin"
    path.write_text("Temporary markdown body", encoding="utf-8")
    indexer = FakeIndexer()

    index_loaded_document(load_document_file(path, display_name="README.md"), indexer)

    assert indexer.calls[0]["title"] == "README"
    assert indexer.calls[0]["text"] == "Temporary markdown body"
    assert indexer.calls[0]["metadata"]["file_name"] == "README.md"
    assert indexer.calls[0]["metadata"]["file_extension"] == ".md"


def test_loaded_file_indexes_and_retrieves_document_memory_candidate() -> None:
    path = Path("tests/fixtures/docs/sample_report.txt")
    retriever = FakeLangChainChromaRetriever()

    index_loaded_document(load_document_file(path), retriever)
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


def test_pdf_loader_extracts_text_and_page_metadata(tmp_path: Path) -> None:
    path = tmp_path / "text-report.pdf"
    text = "PDF_PROTECTION_7249: the retained loader extracts this fact."
    try:
        import fitz
    except ImportError:
        pypdf = pytest.importorskip(
            "pypdf", reason="Neither PyMuPDF nor pypdf text-PDF fixture backend is available"
        )
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

        writer = pypdf.PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        content = DecodedStreamObject()
        content.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(content)
        writer.write(str(path))
    else:
        with fitz.open() as document:
            page = document.new_page()
            page.insert_text((72, 72), text)
            document.save(str(path))

    loaded = load_document_file(path)

    assert text in loaded.text
    assert loaded.title == "text-report"
    assert loaded.source == "file"
    assert loaded.metadata["file_extension"] == ".pdf"
    assert loaded.metadata["page_count"] == 1
    assert loaded.metadata["file_name"] == "text-report.pdf"
    assert loaded.metadata["file_path"] == str(path)
    assert loaded.metadata["loader_name"] in {"pypdf", "pymupdf"}


def test_index_document_cli_loads_once_and_indexes_that_snapshot(tmp_path, monkeypatch, capsys) -> None:
    import sys
    from types import SimpleNamespace

    from scripts import index_document_file as cli
    import src.documents.loaders as loaders

    path = tmp_path / "report.txt"
    path.write_text("original document", encoding="utf-8")
    real_load = loaders.load_document_file
    loads = []
    indexed = []

    def load_once(file_path):
        loaded = real_load(file_path)
        loads.append(loaded)
        return loaded

    class Indexer:
        def index_text_document(self, **kwargs):
            indexed.append(kwargs)
            return SimpleNamespace(document_id="doc-1", chunk_count=1)

    def create_indexer():
        # Simulate the input changing while the backend is initialized.
        path.write_text("later document", encoding="utf-8")
        return Indexer()

    monkeypatch.setattr(loaders, "load_document_file", load_once)
    monkeypatch.setattr(LangChainChromaRetriever, "from_env", create_indexer)
    monkeypatch.setattr(sys, "argv", ["index_document_file.py", str(path)])
    cli.main()

    assert len(loads) == 1
    assert indexed == [{"title": "report", "text": "original document",
                        "source": "file", "metadata": loads[0].metadata}]
    assert capsys.readouterr().out.strip() == (
        f"indexed_document_file path={path} title='report' document_id=doc-1 chunk_count=1"
    )


def test_index_document_cli_rejects_missing_file_before_backend(tmp_path, monkeypatch, capsys) -> None:
    import sys

    from scripts import index_document_file as cli

    def unexpected_backend():
        pytest.fail("backend must not start when input cannot be loaded")

    monkeypatch.setattr(LangChainChromaRetriever, "from_env", unexpected_backend)
    monkeypatch.setattr(sys, "argv", ["index_document_file.py", str(tmp_path / "missing.txt")])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    assert "Could not index document file: Document file does not exist:" in capsys.readouterr().out
