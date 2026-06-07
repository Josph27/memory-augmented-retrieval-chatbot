from __future__ import annotations

from typing import Any


def answer_contains_anchor(answer: str, answer_anchor: str) -> bool:
    """Return whether the answer contains the expected anchor text."""
    return contains_text(answer, answer_anchor)


def answer_contains_expected(answer: str, expected_answer: str) -> bool:
    """Return whether the answer contains the expected answer text."""
    return contains_text(answer, expected_answer)


def context_contains_evidence(
    contexts: list[str],
    supporting_evidence: str,
) -> bool:
    """Return whether any context contains the supporting evidence."""
    return any(contains_text(context, supporting_evidence) for context in contexts)


def context_contains_answer_anchor(
    contexts: list[str],
    answer_anchor: str,
) -> bool:
    """Return whether any context contains the expected answer anchor."""
    return any(contains_text(context, answer_anchor) for context in contexts)


def ragas_compatible_row(
    question: str,
    contexts: list[str],
    answer: str,
    ground_truth: str,
    supporting_evidence: str | None = None,
    case_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a row shape compatible with future RAGAS-style evaluation."""
    row: dict[str, Any] = {
        "question": question,
        "contexts": contexts,
        "answer": answer,
        "ground_truth": ground_truth,
    }
    if supporting_evidence is not None:
        row["supporting_evidence"] = supporting_evidence
    if case_id is not None:
        row["case_id"] = case_id
    if metadata:
        row["metadata"] = metadata
    return row


def contains_text(text: str, expected: str) -> bool:
    """Case-insensitive containment with whitespace normalization."""
    normalized_text = normalize_text(text)
    normalized_expected = normalize_text(expected)
    if not normalized_expected:
        return False
    return normalized_expected in normalized_text


def normalize_text(text: str) -> str:
    """Normalize text for deterministic lightweight eval matching."""
    return " ".join(text.casefold().split())
