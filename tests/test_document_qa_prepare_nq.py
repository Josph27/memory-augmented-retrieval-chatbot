from __future__ import annotations

import pytest

from evals.document_qa.prepare_nq_subset import (
    convert_dataset,
    evidence_for_answer,
    nq_example_to_row,
)


def valid_example() -> dict:
    """Return a small NQ-style example."""
    return {
        "id": "nq-example-1",
        "question": "Who created the Meridian protocol?",
        "context": (
            "The archived document discusses several internal systems. "
            "The Meridian protocol was created by Ada Chen for deployment audits. "
            "The final section lists unrelated access policies."
        ),
        "short_answer": "Ada Chen",
    }


def test_nq_example_to_row_converts_valid_example() -> None:
    row = nq_example_to_row(
        valid_example(),
        index=7,
        dataset_name="example/nq",
        split="train",
    )

    assert row["case_id"] == "nq_train_0007"
    assert row["source"] == "natural_questions:example/nq"
    assert row["document_id"] == "nq-example-1"
    assert row["question"] == "Who created the Meridian protocol?"
    assert row["expected_answer"] == "Ada Chen"
    assert row["answer_anchor"] == "Ada Chen"
    assert row["category"] == "natural_questions"
    assert "Ada Chen" in row["document_text"]
    assert "Ada Chen" in row["supporting_evidence"]


def test_nq_example_to_row_handles_natural_questions_short_shape() -> None:
    example = {
        "contexts": "The title was released in 1999 by Example Records.",
        "answers": [
            {
                "input_text": "short",
                "span_text": "1999",
                "span_start": 23,
                "span_end": 27,
            }
        ],
        "id": "nq-short-1",
        "questions": [{"input_text": "When was the title released?"}],
    }

    row = nq_example_to_row(
        example,
        index=2,
        dataset_name="cjlovering/natural-questions-short",
        split="train",
    )

    assert row["question"] == "When was the title released?"
    assert row["expected_answer"] == "1999"
    assert row["document_text"] == "The title was released in 1999 by Example Records."


def test_nq_example_to_row_skips_missing_question() -> None:
    example = valid_example()
    example["question"] = ""

    with pytest.raises(ValueError, match="missing question"):
        nq_example_to_row(example, index=0, dataset_name="example/nq", split="train")


def test_nq_example_to_row_skips_missing_context() -> None:
    example = valid_example()
    example["context"] = ""

    with pytest.raises(ValueError, match="missing document text"):
        nq_example_to_row(example, index=0, dataset_name="example/nq", split="train")


def test_nq_example_to_row_skips_missing_answer() -> None:
    example = valid_example()
    example["short_answer"] = ""

    with pytest.raises(ValueError, match="missing answer"):
        nq_example_to_row(example, index=0, dataset_name="example/nq", split="train")


def test_nq_example_to_row_skips_answer_not_in_context_when_required() -> None:
    example = valid_example()
    example["short_answer"] = "Grace Hopper"

    with pytest.raises(ValueError, match="answer anchor not found"):
        nq_example_to_row(
            example,
            index=0,
            dataset_name="example/nq",
            split="train",
            require_answer_in_context=True,
        )


def test_nq_example_allows_answer_not_in_context_when_not_required() -> None:
    example = valid_example()
    example["short_answer"] = "Grace Hopper"

    row = nq_example_to_row(
        example,
        index=0,
        dataset_name="example/nq",
        split="train",
        require_answer_in_context=False,
    )

    assert row["answer_anchor"] == "Grace Hopper"


def test_evidence_for_answer_returns_excerpt_around_anchor() -> None:
    document_text = "prefix " * 120 + "Luminara" + " suffix" * 120

    evidence = evidence_for_answer(document_text, "Luminara", window_chars=80)

    assert "Luminara" in evidence
    assert len(evidence) < len(document_text)


def test_convert_dataset_counts_written_and_skipped_examples() -> None:
    missing_question = valid_example()
    missing_question["question"] = ""

    rows, stats = convert_dataset(
        dataset=[valid_example(), missing_question],
        dataset_name="example/nq",
        split="train",
        limit=10,
        seed=13,
        require_answer_in_context=True,
    )

    assert len(rows) == 1
    assert stats == {"scanned": 2, "written": 1, "skipped": 1}
