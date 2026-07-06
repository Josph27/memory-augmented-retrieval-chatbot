from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> int:
    """Print indexed document metadata from the Chroma document-memory store."""
    from src.config import AppConfig
    from src.documents.inspection import (
        DocumentInspectionUnavailable,
        chroma_document_inspection_rows,
        format_document_inspection_rows,
    )
    from src.retrieval.langchain_chroma_retriever import DEFAULT_COLLECTION_NAME

    parser = argparse.ArgumentParser(description="Inspect indexed document memory.")
    parser.add_argument("--document-id", help="Filter by document id.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum rows per backend.")
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION_NAME,
        help="Chroma collection name.",
    )
    args = parser.parse_args()

    config = AppConfig.from_env()
    print(f"chroma_persist_dir={config.langchain_chroma_persist_dir}")

    print("[LangChain-Chroma]")
    try:
        rows = filtered_rows(
            chroma_document_inspection_rows(
                persist_dir=config.langchain_chroma_persist_dir,
                collection_name=args.collection,
            ),
            document_id=args.document_id,
            limit=args.limit,
        )
    except DocumentInspectionUnavailable as error:
        print(f"unavailable={error}")
    else:
        print(format_document_inspection_rows(rows))
    return 0


def filtered_rows(rows, document_id: str | None, limit: int):  # type: ignore[no-untyped-def]
    """Apply simple CLI filtering to document inspection rows."""
    if document_id:
        rows = [row for row in rows if row.document_id == document_id]
    return rows[: max(0, limit)]


if __name__ == "__main__":
    raise SystemExit(main())
