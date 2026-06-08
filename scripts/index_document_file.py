from __future__ import annotations

import argparse
import sys
from pathlib import Path


def ensure_repo_root_on_path() -> None:
    """Allow running this script directly from the repository root."""
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def main() -> None:
    """Load a local file and index it into the LangChain-Chroma document backend."""
    ensure_repo_root_on_path()

    from src.documents.loaders import DocumentLoaderError, index_file_document, load_document_file
    from src.retrieval.langchain_chroma_retriever import (
        LangChainChromaRetriever,
        LangChainChromaUnavailable,
    )

    parser = argparse.ArgumentParser(description="Index a local file into document memory.")
    parser.add_argument("path", type=Path, help="Path to a .txt, .md, or .pdf file.")
    args = parser.parse_args()

    try:
        loaded = load_document_file(args.path)
        retriever = LangChainChromaRetriever.from_env()
        result = index_file_document(args.path, retriever)
    except (DocumentLoaderError, LangChainChromaUnavailable) as error:
        print(f"Could not index document file: {error}")
        raise SystemExit(1) from error

    print(
        "indexed_document_file "
        f"path={loaded.metadata['file_path']} "
        f"title={loaded.title!r} "
        f"document_id={result.document_id} "
        f"chunk_count={result.chunk_count}"
    )


if __name__ == "__main__":
    main()
