from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.document_qa.ragas_export import (
    result_to_ragas_row,
    results_to_ragas_rows,
    write_ragas_jsonl,
)
from evals.document_qa.run_ragas_eval import load_jsonl


@dataclass(frozen=True)
class FakeEvalResult:
    case_id: str
    context_evidence_hit: bool
    context_answer_anchor_hit: bool
    context_expected_answer_hit: bool
    answer_mode: str
    model_name: str | None
    ragas_row: dict[str, Any]


def fake_result() -> FakeEvalResult:
    """Build a minimal eval result for export tests."""
    return FakeEvalResult(
        case_id="case-1",
        context_evidence_hit=True,
        context_answer_anchor_hit=True,
        context_expected_answer_hit=False,
        answer_mode="model",
        model_name="fake-model",
        ragas_row={
            "question": "What color is the access key?",
            "contexts": ["The access key is blue."],
            "answer": "blue",
            "ground_truth": "blue",
            "case_id": "case-1",
            "metadata": {"category": "synthetic"},
        },
    )


def fake_case() -> dict[str, Any]:
    """Build a minimal dataset case for export tests."""
    return {
        "case_id": "case-1",
        "source": "unit-test",
        "document_id": "doc-1",
    }


def test_result_to_ragas_row_adds_required_fields_and_metadata() -> None:
    row = result_to_ragas_row(
        result=fake_result(),
        case=fake_case(),
        retrieval_mode="langchain_chroma",
        retrieval_scope="corpus",
        top_k=3,
        vector_backend=None,
    )

    assert row["question"] == "What color is the access key?"
    assert row["contexts"] == ["The access key is blue."]
    assert row["answer"] == "blue"
    assert row["ground_truth"] == "blue"
    assert row["case_id"] == "case-1"
    assert row["metadata"]["retrieval_mode"] == "langchain_chroma"
    assert row["metadata"]["retrieval_scope"] == "corpus"
    assert row["metadata"]["top_k"] == 3
    assert row["metadata"]["vector_backend"] is None
    assert row["metadata"]["answer_mode"] == "model"
    assert row["metadata"]["source"] == "unit-test"
    assert row["metadata"]["document_id"] == "doc-1"
    assert row["metadata"]["ctx_anchor_hit"] is True
    assert row["metadata"]["ctx_expected_hit"] is False
    assert row["metadata"]["ctx_evidence_hit"] is True


def test_results_to_ragas_rows_preserves_alignment() -> None:
    rows = results_to_ragas_rows(
        results=[fake_result()],
        cases=[fake_case()],
        retrieval_mode="langchain_chroma",
        retrieval_scope="isolated",
        top_k=1,
    )

    assert len(rows) == 1
    assert rows[0]["metadata"]["retrieval_mode"] == "langchain_chroma"
    assert rows[0]["metadata"]["top_k"] == 1


def test_write_ragas_jsonl_writes_without_ragas_dependency(tmp_path: Path) -> None:
    output_path = tmp_path / "ragas_rows.jsonl"
    rows = [
        result_to_ragas_row(
            result=fake_result(),
            case=fake_case(),
            retrieval_mode="langchain_chroma",
            retrieval_scope="corpus",
            top_k=2,
        )
    ]

    write_ragas_jsonl(rows, output_path)

    raw_lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == 1
    assert json.loads(raw_lines[0])["metadata"]["ctx_evidence_hit"] is True
    assert load_jsonl(output_path) == rows
