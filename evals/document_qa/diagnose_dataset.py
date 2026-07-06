from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any


DEFAULT_DATASET = Path(__file__).parent / "datasets" / "nq_subset.jsonl"
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


@dataclass(frozen=True)
class DatasetDiagnostics:
    """Summary diagnostics for document QA retrieval datasets."""

    cases: int
    unique_documents: int
    duplicate_document_texts: int
    duplicate_questions: int
    estimated_chunks: int
    avg_document_text_length: float
    avg_chunk_length: float
    avg_chunks_per_document: float
    answer_anchor_length_distribution: dict[str, int]
    answer_in_first_500_pct: float


def main() -> None:
    """Print diagnostics for a document QA JSONL dataset."""
    parser = argparse.ArgumentParser(description="Diagnose a document QA JSONL dataset.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=int(os.getenv("LANGCHAIN_CHUNK_SIZE", str(DEFAULT_CHUNK_SIZE))),
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=int(os.getenv("LANGCHAIN_CHUNK_OVERLAP", str(DEFAULT_CHUNK_OVERLAP))),
    )
    args = parser.parse_args()

    rows = load_jsonl(args.dataset)
    diagnostics = diagnose_rows(
        rows,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print("Document QA dataset diagnostics")
    print(f"dataset: {args.dataset}")
    print(f"cases: {diagnostics.cases}")
    print(f"documents indexed: {diagnostics.unique_documents}")
    print(f"estimated chunks indexed: {diagnostics.estimated_chunks}")
    print(f"average document_text length: {diagnostics.avg_document_text_length:.1f} chars")
    print(f"average chunk length: {diagnostics.avg_chunk_length:.1f} chars")
    print(f"average chunks per document: {diagnostics.avg_chunks_per_document:.2f}")
    print(f"duplicate document_text values: {diagnostics.duplicate_document_texts}")
    print(f"duplicate questions: {diagnostics.duplicate_questions}")
    print(
        "answer_anchor length distribution: "
        f"{json.dumps(diagnostics.answer_anchor_length_distribution, sort_keys=True)}"
    )
    print(
        "answer appears in first 500 chars: "
        f"{diagnostics.answer_in_first_500_pct:.1f}%"
    )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL rows."""
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def diagnose_rows(
    rows: list[dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> DatasetDiagnostics:
    """Compute retrieval benchmark diagnostics from JSONL rows."""
    document_texts = [str(row.get("document_text", "")) for row in rows]
    unique_document_texts = list(dict.fromkeys(document_texts))
    questions = [str(row.get("question", "")) for row in rows]
    answer_anchors = [str(row.get("answer_anchor", "")) for row in rows]
    chunks_by_document = [
        split_text_like_langchain(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for text in unique_document_texts
    ]
    chunks = [chunk for document_chunks in chunks_by_document for chunk in document_chunks]
    answer_in_first_500 = [
        anchor.lower() in text[:500].lower()
        for text, anchor in zip(document_texts, answer_anchors, strict=True)
        if anchor
    ]
    return DatasetDiagnostics(
        cases=len(rows),
        unique_documents=len(unique_document_texts),
        duplicate_document_texts=duplicate_count(document_texts),
        duplicate_questions=duplicate_count(questions),
        estimated_chunks=len(chunks),
        avg_document_text_length=mean([len(text) for text in document_texts] or [0]),
        avg_chunk_length=mean([len(chunk) for chunk in chunks] or [0]),
        avg_chunks_per_document=mean([len(chunks) for chunks in chunks_by_document] or [0]),
        answer_anchor_length_distribution=anchor_length_distribution(answer_anchors),
        answer_in_first_500_pct=100.0
        * (sum(answer_in_first_500) / len(answer_in_first_500) if answer_in_first_500 else 0.0),
    )


def split_text_like_langchain(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Split with LangChain's recursive splitter when available, otherwise approximate."""
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=max(1, chunk_size),
            chunk_overlap=min(max(0, chunk_overlap), max(0, chunk_size - 1)),
            add_start_index=True,
        )
        return [document.page_content for document in splitter.create_documents([text])]
    except Exception:
        return fallback_chunks(text, chunk_size=max(1, chunk_size))


def fallback_chunks(text: str, chunk_size: int) -> list[str]:
    """Simple fixed-size fallback for diagnostics only."""
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)] or [""]


def duplicate_count(values: list[str]) -> int:
    """Return number of rows belonging to duplicate value groups."""
    counts = Counter(values)
    return sum(count for count in counts.values() if count > 1)


def anchor_length_distribution(anchors: list[str]) -> dict[str, int]:
    """Bucket answer anchor lengths by word count."""
    buckets = {"1_word": 0, "2_3_words": 0, "4_8_words": 0, "9_plus_words": 0}
    for anchor in anchors:
        word_count = len(anchor.split())
        if word_count <= 1:
            buckets["1_word"] += 1
        elif word_count <= 3:
            buckets["2_3_words"] += 1
        elif word_count <= 8:
            buckets["4_8_words"] += 1
        else:
            buckets["9_plus_words"] += 1
    return buckets


if __name__ == "__main__":
    main()
