from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from evals.document_qa.answer_generation import answer_is_unknown
from evals.longmemeval_adapter.schema import LongMemEvalCase


@dataclass(frozen=True)
class CaseScore:
    """Unofficial deterministic metrics for one adapter case."""

    answer_exact_gold: bool
    answer_contains_gold: bool
    abstain_correct: bool | None
    retrieval_hit: bool | None
    passed: bool


def score_case(
    case: LongMemEvalCase,
    answer: str,
    retrieved_contents: Iterable[str],
) -> CaseScore:
    """Score one pilot case with transparent, non-official checks."""
    normalized_answer = normalize_text(answer)
    normalized_gold = normalize_text(case.gold_answer)
    answer_exact = bool(normalized_gold) and normalized_answer == normalized_gold
    answer_contains = bool(normalized_gold) and normalized_gold in normalized_answer
    abstain_correct = (
        answer_is_unknown(answer) if case.expected_abstain else None
    )
    retrieval_hit = evidence_hit(case.expected_evidence, retrieved_contents)
    passed = (
        abstain_correct is True
        if case.expected_abstain
        else answer_contains
    )
    if retrieval_hit is False:
        passed = False
    return CaseScore(
        answer_exact_gold=answer_exact,
        answer_contains_gold=answer_contains,
        abstain_correct=abstain_correct,
        retrieval_hit=retrieval_hit,
        passed=passed,
    )


def evidence_hit(
    expected_evidence: tuple[str, ...],
    retrieved_contents: Iterable[str],
) -> bool | None:
    """Return whether every configured evidence fragment was retrieved."""
    if not expected_evidence:
        return None
    context = normalize_text("\n".join(retrieved_contents))
    return all(normalize_text(fragment) in context for fragment in expected_evidence)


def summarize_scores(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate unofficial adapter metrics."""
    abstain = [
        result["abstain_correct"]
        for result in results
        if result["abstain_correct"] is not None
    ]
    retrieval = [
        result["retrieval_hit"]
        for result in results
        if result["retrieval_hit"] is not None
    ]
    return {
        "total_cases": len(results),
        "pass_rate": rate(result["passed"] for result in results),
        "contains_gold_rate": rate(
            result["answer_contains_gold"] for result in results
        ),
        "exact_gold_rate": rate(
            result["answer_exact_gold"] for result in results
        ),
        "abstain_accuracy": rate(abstain) if abstain else None,
        "retrieval_hit_rate": rate(retrieval) if retrieval else None,
        "average_latency_ms": average(
            float(result["latency_ms"]) for result in results
        ),
        "failed_case_ids": [
            result["case_id"] for result in results if not result["passed"]
        ],
        "results_by_question_type": summarize_by_question_type(results),
    }


def summarize_by_question_type(
    results: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Group pass and contains-gold rates by available question type."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        key = str(result.get("question_type") or "unknown")
        grouped.setdefault(key, []).append(result)
    return {
        key: {
            "cases": len(rows),
            "pass_rate": rate(row["passed"] for row in rows),
            "contains_gold_rate": rate(
                row["answer_contains_gold"] for row in rows
            ),
        }
        for key, rows in sorted(grouped.items())
    }


def normalize_text(value: str) -> str:
    """Normalize case, punctuation, and whitespace for simple pilot scoring."""
    return " ".join(re.findall(r"\w+", value.casefold(), flags=re.UNICODE))


def rate(values: Iterable[object]) -> float:
    """Return truthy fraction, or zero for an empty sequence."""
    items = list(values)
    return sum(bool(item) for item in items) / len(items) if items else 0.0


def average(values: Iterable[float]) -> float:
    """Return a rounded arithmetic mean."""
    items = list(values)
    return round(sum(items) / len(items), 2) if items else 0.0
