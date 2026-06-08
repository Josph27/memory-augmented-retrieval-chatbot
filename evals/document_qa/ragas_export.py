from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class RagasExportResult(Protocol):
    """Minimal result shape needed for RAGAS-compatible export."""

    case_id: str
    context_evidence_hit: bool
    context_answer_anchor_hit: bool
    context_expected_answer_hit: bool
    answer_mode: str
    model_name: str | None
    ragas_row: dict[str, Any]


def result_to_ragas_row(
    result: RagasExportResult,
    case: dict[str, Any],
    retrieval_mode: str,
    retrieval_scope: str,
    top_k: int,
    vector_backend: str | None = None,
) -> dict[str, Any]:
    """Convert one document QA eval result to a RAGAS-compatible row."""
    base_row = result.ragas_row
    metadata = dict(base_row.get("metadata") or {})
    metadata.update(
        {
            "retrieval_mode": retrieval_mode,
            "retrieval_scope": retrieval_scope,
            "top_k": top_k,
            "vector_backend": vector_backend,
            "answer_mode": result.answer_mode,
            "model_name": result.model_name,
            "source": case.get("source"),
            "document_id": case.get("document_id"),
            "ctx_anchor_hit": result.context_answer_anchor_hit,
            "ctx_expected_hit": result.context_expected_answer_hit,
            "ctx_evidence_hit": result.context_evidence_hit,
        }
    )
    return {
        "question": str(base_row["question"]),
        "contexts": list(base_row["contexts"]),
        "answer": str(base_row["answer"]),
        "ground_truth": str(base_row["ground_truth"]),
        "case_id": str(base_row.get("case_id", result.case_id)),
        "metadata": metadata,
    }


def results_to_ragas_rows(
    results: list[RagasExportResult],
    cases: list[dict[str, Any]],
    retrieval_mode: str,
    retrieval_scope: str,
    top_k: int,
    vector_backend: str | None = None,
) -> list[dict[str, Any]]:
    """Convert aligned eval results/cases to RAGAS-compatible rows."""
    return [
        result_to_ragas_row(
            result=result,
            case=case,
            retrieval_mode=retrieval_mode,
            retrieval_scope=retrieval_scope,
            top_k=top_k,
            vector_backend=vector_backend,
        )
        for result, case in zip(results, cases, strict=True)
    ]


def write_ragas_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    """Write RAGAS-compatible rows as JSONL without requiring RAGAS."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")
