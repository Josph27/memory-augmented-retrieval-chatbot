from __future__ import annotations

from src.documents.inspection import (
    DocumentInspectionRow,
    format_document_inspection_rows,
    rows_from_chroma_metadata,
)


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


def test_format_document_inspection_rows_is_cli_readable() -> None:
    rows = [
        DocumentInspectionRow(
            document_id="manual-doc",
            title="Manual",
            file_name="manual.txt",
            file_extension=".txt",
            source="manual",
            retrieval_backend="langchain_chroma",
            chunk_count=1,
            chunk_ids=["manual-doc:0"],
        )
    ]

    formatted = format_document_inspection_rows(rows)

    assert "indexed_documents_count=1" in formatted
    assert "[Indexed document]" in formatted
    assert "document_id=manual-doc" in formatted
    assert "title=Manual" in formatted
    assert "file_name=manual.txt" in formatted
    assert "chunk_count=1" in formatted


def test_format_document_inspection_rows_handles_empty_rows() -> None:
    assert format_document_inspection_rows([]) == "indexed_documents_count=0"
