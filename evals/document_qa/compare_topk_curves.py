from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

try:
    from .compare_retrieval_modes import (
        DEFAULT_MODES,
        ModeComparisonResult,
        evaluate_mode,
        format_row,
    )
    from .run_document_qa_eval import (
        DEFAULT_DATASET,
        VECTOR_BACKEND_CHOICES,
        load_jsonl,
        normalize_vector_backend,
    )
except ImportError:
    from compare_retrieval_modes import (
        DEFAULT_MODES,
        ModeComparisonResult,
        evaluate_mode,
        format_row,
    )
    from run_document_qa_eval import (
        DEFAULT_DATASET,
        VECTOR_BACKEND_CHOICES,
        load_jsonl,
        normalize_vector_backend,
    )


@dataclass(frozen=True)
class TopKCurveResult:
    """One retrieval hit-rate row for a mode/backend/k combination."""

    mode: str
    backend: str
    k: int
    cases: int
    context_evidence_hit_rate: float
    context_answer_anchor_hit_rate: float
    context_expected_answer_hit_rate: float
    skipped: bool
    failed_case_ids: list[str]
    unavailable_reason: str | None = None


def main() -> None:
    """Compare retrieval hit rates across k values."""
    parser = argparse.ArgumentParser(description="Compare document QA hit@k curves.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to JSONL dataset.",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        default=list(DEFAULT_MODES),
        help="Context modes to compare.",
    )
    parser.add_argument(
        "--retrieval-scope",
        choices=("isolated", "corpus"),
        default="corpus",
        help="Use one document per case or retrieve from a shared dataset corpus.",
    )
    parser.add_argument(
        "--top-k-values",
        nargs="+",
        type=int,
        default=[1, 3, 5, 10],
        help="One or more top-k values to evaluate.",
    )
    parser.add_argument(
        "--vector-backend",
        choices=VECTOR_BACKEND_CHOICES,
        default=None,
        help="Vector backend for vector/hybrid modes. Defaults to VECTOR_BACKEND env.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of dataset cases to evaluate.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary after the table.",
    )
    args = parser.parse_args()

    cases = load_jsonl(args.dataset)
    if args.limit is not None:
        cases = cases[: max(0, args.limit)]

    results = evaluate_topk_curves(
        modes=args.modes,
        cases=cases,
        top_k_values=args.top_k_values,
        retrieval_scope=args.retrieval_scope,
        vector_backend=args.vector_backend,
    )
    print_topk_table(results)
    if args.json:
        print(json.dumps([result_to_dict(result) for result in results], indent=2))


def evaluate_topk_curves(
    modes: list[str],
    cases: list[dict],
    top_k_values: list[int],
    retrieval_scope: str = "corpus",
    vector_backend: str | None = None,
) -> list[TopKCurveResult]:
    """Evaluate each mode across the requested k values."""
    backend = normalize_vector_backend(vector_backend)
    results: list[TopKCurveResult] = []
    for mode in modes:
        for top_k in normalized_top_k_values(top_k_values):
            comparison = evaluate_mode(
                mode=mode,
                cases=cases,
                top_k=top_k,
                retrieval_scope=retrieval_scope,
                vector_backend=backend,
                answer_mode="oracle",
                resource_cache={},
            )
            results.append(topk_result_from_comparison(comparison, top_k, backend))
    return results


def normalized_top_k_values(top_k_values: list[int]) -> list[int]:
    """Return positive unique k values preserving input order."""
    normalized: list[int] = []
    for value in top_k_values:
        if value <= 0 or value in normalized:
            continue
        normalized.append(value)
    return normalized


def topk_result_from_comparison(
    comparison: ModeComparisonResult,
    top_k: int,
    backend: str,
) -> TopKCurveResult:
    """Convert an existing mode comparison row into a hit@k row."""
    return TopKCurveResult(
        mode=comparison.mode,
        backend=backend_for_mode(comparison.mode, backend),
        k=top_k,
        cases=comparison.total_cases,
        context_evidence_hit_rate=comparison.context_evidence_hit_rate,
        context_answer_anchor_hit_rate=comparison.context_answer_anchor_hit_rate,
        context_expected_answer_hit_rate=comparison.context_expected_answer_hit_rate,
        skipped=comparison.skipped,
        failed_case_ids=comparison.failed_case_ids,
        unavailable_reason=comparison.unavailable_reason,
    )


def backend_for_mode(mode: str, backend: str) -> str:
    """Return the vector backend label for table output."""
    if mode == "langchain_chroma":
        return "chroma"
    if mode in {"vector_retrieval", "hybrid_retrieval"}:
        return backend
    return "-"


def print_topk_table(results: list[TopKCurveResult]) -> None:
    """Print hit@k rows."""
    headers = [
        "mode",
        "backend",
        "k",
        "cases",
        "ctx_evidence",
        "ctx_anchor",
        "ctx_expected",
        "skipped",
        "reason",
    ]
    rows = [topk_row(result) for result in results]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        if rows
        else len(headers[index])
        for index in range(len(headers))
    ]
    print("Document QA retrieval hit@k curves")
    print(format_row(headers, widths))
    print(format_row(["-" * width for width in widths], widths))
    for row in rows:
        print(format_row(row, widths))


def topk_row(result: TopKCurveResult) -> list[str]:
    """Convert a top-k result into printable cells."""
    reason = result.unavailable_reason or ""
    if len(reason) > 80:
        reason = f"{reason[:77]}..."
    return [
        result.mode,
        result.backend,
        str(result.k),
        str(result.cases),
        f"{result.context_evidence_hit_rate:.2f}",
        f"{result.context_answer_anchor_hit_rate:.2f}",
        f"{result.context_expected_answer_hit_rate:.2f}",
        "yes" if result.skipped else "no",
        reason,
    ]


def result_to_dict(result: TopKCurveResult) -> dict:
    """Return JSON-ready hit@k data."""
    return {
        "mode": result.mode,
        "backend": result.backend,
        "k": result.k,
        "cases": result.cases,
        "context_evidence_hit_rate": result.context_evidence_hit_rate,
        "context_answer_anchor_hit_rate": result.context_answer_anchor_hit_rate,
        "context_expected_answer_hit_rate": result.context_expected_answer_hit_rate,
        "skipped": result.skipped,
        "failed_case_ids": result.failed_case_ids,
        "unavailable_reason": result.unavailable_reason,
    }


if __name__ == "__main__":
    main()
