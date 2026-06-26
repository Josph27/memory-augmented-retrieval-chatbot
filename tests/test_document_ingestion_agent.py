from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from src.agents.document_ingestion_agent import DocumentIngestionAgent
from src.documents.loaders import DocumentLoaderError


class FakeIndexer:
    def __init__(self, result: object | None = None) -> None:
        self.result = result or {"document_id": "fake-doc", "chunk_count": 2}
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
        return self.result


@dataclass(frozen=True)
class ObjectIndexResult:
    document_id: str
    chunk_count: int


def test_document_ingestion_agent_indexes_file_with_structured_result(
    tmp_path: Path,
) -> None:
    path = tmp_path / "report.md"
    path.write_text("# Report\n\nUnique report fact.", encoding="utf-8")
    indexer = FakeIndexer()
    agent = DocumentIngestionAgent(indexer=indexer)

    result = agent.index_file(path)

    assert result.indexed is True
    assert result.errors == []
    assert result.document_id == "fake-doc"
    assert result.file_name == "report.md"
    assert result.file_extension == ".md"
    assert result.chunk_count == 2
    assert result.metadata["title"] == "report"
    assert result.metadata["source"] == "file"
    assert result.metadata["file_name"] == "report.md"
    assert indexer.calls[0]["title"] == "report"
    assert "Unique report fact." in indexer.calls[0]["text"]


def test_document_ingestion_agent_preserves_display_name_for_temp_upload(
    tmp_path: Path,
) -> None:
    path = tmp_path / "chainlit-upload.bin"
    path.write_text("# README\n\nUpload body.", encoding="utf-8")
    indexer = FakeIndexer()
    agent = DocumentIngestionAgent(indexer=indexer)

    result = agent.index_file(path, display_name="README.md")

    assert result.file_name == "README.md"
    assert result.file_extension == ".md"
    assert result.metadata["file_path"] == str(path)
    assert result.metadata["file_name"] == "README.md"
    assert indexer.calls[0]["title"] == "README"
    assert indexer.calls[0]["metadata"]["file_extension"] == ".md"


def test_document_ingestion_agent_accepts_object_index_result(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("Notes body.", encoding="utf-8")
    indexer = FakeIndexer(result=ObjectIndexResult(document_id="object-doc", chunk_count=4))
    agent = DocumentIngestionAgent(indexer=indexer)

    result = agent.index_file(path)

    assert result.document_id == "object-doc"
    assert result.chunk_count == 4
    assert result.indexed is True


def test_document_ingestion_agent_propagates_loader_errors(tmp_path: Path) -> None:
    path = tmp_path / "unsupported.png"
    path.write_text("not a supported document", encoding="utf-8")
    agent = DocumentIngestionAgent(indexer=FakeIndexer())

    with pytest.raises(DocumentLoaderError, match="Unsupported document extension"):
        agent.index_file(path)
