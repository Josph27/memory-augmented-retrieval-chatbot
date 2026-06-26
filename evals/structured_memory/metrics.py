from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StructuredMemoryScores:
    """Deterministic scores for one structured-memory eval case."""

    case_id: str
    memory_write_success: bool
    memory_retrieval_hit: bool
    answer_uses_memory: bool | None
    answer_avoids_false_memory: bool | None
    failed_reasons: list[str]


def contains_all(text: str, substrings: list[str]) -> bool:
    """Return whether every non-empty substring appears in text."""
    normalized = text.lower()
    return all(substring.lower() in normalized for substring in substrings if substring)


def contains_any(text: str, substrings: list[str]) -> bool:
    """Return whether any non-empty substring appears in text."""
    normalized = text.lower()
    return any(substring.lower() in normalized for substring in substrings if substring)


def score_case(
    case: dict[str, Any],
    *,
    stored_memory_text: str,
    retrieved_memory_text: str,
    answer: str,
) -> StructuredMemoryScores:
    """Score one structured cross-chat memory case with deterministic checks."""
    expected_memory = list(case.get("expected_memory_substrings") or [])
    expected_answer = list(case.get("expected_answer_substrings") or [])
    false_memory = list(case.get("false_memory_substrings") or [])
    should_write = bool(case.get("should_write_memory"))
    should_retrieve = bool(case.get("should_retrieve_memory"))
    should_answer = bool(case.get("should_answer_with_memory"))
    should_abstain = bool(case.get("should_abstain"))

    if should_write:
        memory_write_success = contains_all(stored_memory_text, expected_memory)
    else:
        memory_write_success = not stored_memory_text.strip()

    if should_retrieve:
        memory_retrieval_hit = contains_all(retrieved_memory_text, expected_memory)
    else:
        memory_retrieval_hit = not retrieved_memory_text.strip()

    answer_uses_memory: bool | None
    if should_answer:
        answer_uses_memory = contains_all(answer, expected_answer)
    else:
        answer_uses_memory = None

    answer_avoids_false_memory: bool | None
    if should_abstain:
        answer_avoids_false_memory = not contains_any(answer, false_memory)
    else:
        answer_avoids_false_memory = None

    failed_reasons = []
    if not memory_write_success:
        failed_reasons.append("memory_write_success")
    if not memory_retrieval_hit:
        failed_reasons.append("memory_retrieval_hit")
    if answer_uses_memory is False:
        failed_reasons.append("answer_uses_memory")
    if answer_avoids_false_memory is False:
        failed_reasons.append("answer_avoids_false_memory")

    return StructuredMemoryScores(
        case_id=str(case.get("case_id") or ""),
        memory_write_success=memory_write_success,
        memory_retrieval_hit=memory_retrieval_hit,
        answer_uses_memory=answer_uses_memory,
        answer_avoids_false_memory=answer_avoids_false_memory,
        failed_reasons=failed_reasons,
    )


def rate(values: list[bool | None]) -> float:
    """Return true-rate over available boolean values."""
    available = [value for value in values if value is not None]
    if not available:
        return 0.0
    return sum(1 for value in available if value) / len(available)


def summarize_scores(scores: list[StructuredMemoryScores]) -> dict[str, Any]:
    """Return summary metrics for a list of case scores."""
    return {
        "total_cases": len(scores),
        "memory_write_success": rate([score.memory_write_success for score in scores]),
        "memory_retrieval_hit": rate([score.memory_retrieval_hit for score in scores]),
        "answer_uses_memory": rate([score.answer_uses_memory for score in scores]),
        "answer_avoids_false_memory": rate(
            [score.answer_avoids_false_memory for score in scores]
        ),
        "failed_case_ids": [
            score.case_id for score in scores if score.failed_reasons
        ],
    }
