from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerMetrics:
    """Simple deterministic answer and evidence metrics."""

    exact_match: bool
    substring_match: bool
    normalized_substring_match: bool
    evidence_contains_answer: bool


def score_answer(
    prediction: str,
    gold_answers: tuple[str, ...],
    evidence: str,
) -> AnswerMetrics:
    """Score prediction and retrieved evidence without an LLM judge."""
    normalized_prediction = normalize_text(prediction)
    normalized_gold = [normalize_text(answer) for answer in gold_answers]
    normalized_evidence = normalize_text(evidence)
    return AnswerMetrics(
        exact_match=normalized_prediction in normalized_gold,
        substring_match=any(
            answer.lower() in prediction.lower() for answer in gold_answers
        ),
        normalized_substring_match=any(
            answer in normalized_prediction for answer in normalized_gold
        ),
        evidence_contains_answer=any(
            answer in normalized_evidence for answer in normalized_gold
        ),
    )


def normalize_text(value: str) -> str:
    """Normalize punctuation and whitespace for conservative matching."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", value.lower())).strip()
