from __future__ import annotations

from pathlib import Path

from src.database import Database
from src.documents.inspection import (
    format_document_inspection_rows,
    rows_from_chroma_metadata,
    sqlite_document_inspection_rows,
)


def test_sqlite_document_inspection_rows_group_chunks(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    document_id = database.insert_document(
        title="README",
        source="file",
        metadata={"file_name": "README.md"},
    )
    first_chunk_id = database.insert_document_chunk(
        document_id=document_id,
        chunk_index=0,
        text="First chunk",
        metadata={
            "file_name": "README.md",
            "file_extension": ".md",
            "source": "file",
        },
    )
    second_chunk_id = database.insert_document_chunk(
        document_id=document_id,
        chunk_index=1,
        text="Second chunk",
        metadata={
            "file_name": "README.md",
            "file_extension": ".md",
            "source": "file",
        },
    )

    rows = sqlite_document_inspection_rows(database)

    assert len(rows) == 1
    row = rows[0]
    assert row.document_id == str(document_id)
    assert row.title == "README"
    assert row.file_name == "README.md"
    assert row.file_extension == ".md"
    assert row.source == "file"
    assert row.retrieval_backend == "sqlite_document_chunks"
    assert row.chunk_count == 2
    assert row.chunk_ids == [str(first_chunk_id), str(second_chunk_id)]


def test_rows_from_chroma_metadata_group_by_document_id() -> None:
    rows = rows_from_chroma_metadata(
        ids=["doc-1:1", "doc-1:0", "doc-2:0"],
        metadatas=[
            {
                "document_id": "doc-1",
                "chunk_index": 1,
                "title": "Report",
                "file_name": "report.txt",
                "file_extension": ".txt",
                "source": "file",
                "retrieval_backend": "langchain_chroma",
            },
            {
                "document_id": "doc-1",
                "chunk_index": 0,
                "title": "Report",
                "file_name": "report.txt",
                "file_extension": ".txt",
                "source": "file",
                "retrieval_backend": "langchain_chroma",
            },
            {
                "document_id": "doc-2",
                "chunk_index": 0,
                "title": "Notes",
                "file_name": "notes.md",
                "file_extension": ".md",
                "source": "file",
                "retrieval_backend": "langchain_chroma",
            },
        ],
    )

    assert [row.document_id for row in rows] == ["doc-1", "doc-2"]
    assert rows[0].file_name == "report.txt"
    assert rows[0].chunk_count == 2
    assert rows[0].chunk_ids == ["doc-1:0", "doc-1:1"]
    assert rows[1].file_extension == ".md"
    assert rows[1].chunk_count == 1


def test_format_document_inspection_rows_is_cli_readable(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    document_id = database.insert_document(title="Manual", source="manual")
    database.insert_document_chunk(
        document_id=document_id,
        chunk_index=0,
        text="Manual chunk",
        metadata={"file_name": "manual.txt", "file_extension": ".txt"},
    )
    rows = sqlite_document_inspection_rows(database)

    formatted = format_document_inspection_rows(rows)

    assert "indexed_documents_count=1" in formatted
    assert "[Indexed document]" in formatted
    assert f"document_id={document_id}" in formatted
    assert "title=Manual" in formatted
    assert "file_name=manual.txt" in formatted
    assert "chunk_count=1" in formatted


def test_format_document_inspection_rows_handles_empty_rows() -> None:
    assert format_document_inspection_rows([]) == "indexed_documents_count=0"
