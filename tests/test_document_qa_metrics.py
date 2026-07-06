from __future__ import annotations

from evals.document_qa.metrics import (
    answer_contains_anchor,
    answer_contains_expected,
    context_contains_answer_anchor,
    context_contains_evidence,
    ragas_compatible_row,
)


def test_answer_metrics_are_case_and_whitespace_insensitive() -> None:
    answer = "The answer is   SQLite."

    assert answer_contains_anchor(answer, "sqlite")
    assert answer_contains_expected(answer, "answer is sqlite")
    assert not answer_contains_anchor(answer, "postgres")


def test_context_metrics_check_any_context() -> None:
    contexts = [
        "Unrelated context.",
        "Raw messages are treated as the source of truth.",
    ]

    assert context_contains_evidence(
        contexts,
        "messages are treated as the source of truth",
    )
    assert context_contains_answer_anchor(contexts, "source of truth")
    assert not context_contains_answer_anchor(contexts, "vector database")


def test_ragas_compatible_row_shape() -> None:
    row = ragas_compatible_row(
        question="What stores raw messages?",
        contexts=["The app stores raw messages in SQLite."],
        answer="SQLite",
        ground_truth="SQLite",
        supporting_evidence="stores raw messages in SQLite",
        case_id="case-1",
        metadata={"category": "storage"},
    )

    assert row["question"] == "What stores raw messages?"
    assert row["contexts"] == ["The app stores raw messages in SQLite."]
    assert row["answer"] == "SQLite"
    assert row["ground_truth"] == "SQLite"
    assert row["supporting_evidence"] == "stores raw messages in SQLite"
    assert row["case_id"] == "case-1"
    assert row["metadata"]["category"] == "storage"
