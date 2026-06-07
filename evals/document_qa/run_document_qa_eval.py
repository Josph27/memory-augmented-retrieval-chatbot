from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from metrics import (
    answer_contains_anchor,
    answer_contains_expected,
    context_contains_answer_anchor,
    context_contains_evidence,
    ragas_compatible_row,
)


DEFAULT_DATASET = Path(__file__).parent / "datasets" / "squad_style_sample.jsonl"


@dataclass(frozen=True)
class EvalResult:
    """One deterministic scaffold result."""

    case_id: str
    answer_anchor_match: bool
    expected_answer_match: bool
    context_evidence_hit: bool
    context_answer_anchor_hit: bool
    ragas_row: dict[str, Any]


def main() -> None:
    """Run the document QA scaffold eval."""
    parser = argparse.ArgumentParser(description="Run document QA scaffold eval.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to JSONL dataset.",
    )
    parser.add_argument(
        "--context-mode",
        choices=("document_text", "supporting_evidence"),
        default="document_text",
        help="Placeholder context source until real retrieval exists.",
    )
    args = parser.parse_args()

    cases = load_jsonl(args.dataset)
    results = [evaluate_case(case, context_mode=args.context_mode) for case in cases]
    print_summary(results, context_mode=args.context_mode)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL cases from disk."""
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                cases.append(json.loads(stripped))
            except json.JSONDecodeError as error:
                msg = f"Invalid JSONL at {path}:{line_number}: {error}"
                raise ValueError(msg) from error
    return cases


def evaluate_case(case: dict[str, Any], context_mode: str = "document_text") -> EvalResult:
    """Evaluate one case with oracle placeholders."""
    contexts = placeholder_contexts(case, context_mode=context_mode)
    answer = str(case["expected_answer"])
    expected_answer = str(case["expected_answer"])
    answer_anchor = str(case["answer_anchor"])
    supporting_evidence = str(case["supporting_evidence"])
    ragas_row = ragas_compatible_row(
        question=str(case["question"]),
        contexts=contexts,
        answer=answer,
        ground_truth=expected_answer,
        supporting_evidence=supporting_evidence,
        case_id=str(case["case_id"]),
        metadata={
            "document_id": case.get("document_id"),
            "category": case.get("category"),
            "mode": "scaffold_oracle_placeholder",
        },
    )
    return EvalResult(
        case_id=str(case["case_id"]),
        answer_anchor_match=answer_contains_anchor(answer, answer_anchor),
        expected_answer_match=answer_contains_expected(answer, expected_answer),
        context_evidence_hit=context_contains_evidence(contexts, supporting_evidence),
        context_answer_anchor_hit=context_contains_answer_anchor(contexts, answer_anchor),
        ragas_row=ragas_row,
    )


def placeholder_contexts(case: dict[str, Any], context_mode: str) -> list[str]:
    """Return placeholder contexts until real document retrieval exists."""
    if context_mode == "supporting_evidence":
        return [str(case["supporting_evidence"])]
    return [str(case["document_text"])]


def print_summary(results: list[EvalResult], context_mode: str) -> None:
    """Print a concise deterministic summary."""
    total = len(results)
    print("Document QA eval scaffold")
    print("Mode: scaffold / oracle-placeholder")
    print("This does not evaluate real retrieval or generation yet.")
    print(f"Placeholder context mode: {context_mode}")
    print(f"total cases: {total}")
    print(f"answer_anchor_match rate: {rate(results, 'answer_anchor_match'):.2f}")
    print(f"expected_answer_match rate: {rate(results, 'expected_answer_match'):.2f}")
    print(f"context_evidence_hit rate: {rate(results, 'context_evidence_hit'):.2f}")
    print(
        "context_answer_anchor_hit rate: "
        f"{rate(results, 'context_answer_anchor_hit'):.2f}"
    )
    failed_case_ids = [
        result.case_id
        for result in results
        if not (
            result.answer_anchor_match
            and result.expected_answer_match
            and result.context_evidence_hit
            and result.context_answer_anchor_hit
        )
    ]
    print(f"failed case IDs: {failed_case_ids}")


def rate(results: list[EvalResult], field: str) -> float:
    """Return the fraction of results where a boolean field is true."""
    if not results:
        return 0.0
    passed = sum(1 for result in results if bool(getattr(result, field)))
    return passed / len(results)


if __name__ == "__main__":
    main()
