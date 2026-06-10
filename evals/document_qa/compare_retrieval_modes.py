from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

try:
    from .run_document_qa_eval import (
        DEFAULT_DATASET,
        EvalResult,
        EvalResources,
        RetrievalModeUnavailable,
        ANSWER_MODE_CHOICES,
        build_eval_resources,
        evaluate_case,
        load_jsonl,
        rate,
    )
except ImportError:
    from run_document_qa_eval import (
        DEFAULT_DATASET,
        EvalResult,
        EvalResources,
        RetrievalModeUnavailable,
        ANSWER_MODE_CHOICES,
        build_eval_resources,
        evaluate_case,
        load_jsonl,
        rate,
    )


DEFAULT_MODES = ("langchain_chroma",)


@dataclass(frozen=True)
class ModeComparisonResult:
    """Aggregated retrieval metrics for one context mode."""

    mode: str
    total_cases: int
    answer_anchor_match_rate: float
    expected_answer_match_rate: float
    context_evidence_hit_rate: float
    context_answer_anchor_hit_rate: float
    context_expected_answer_hit_rate: float
    answer_mode: str
    model_name: str | None
    answer_unknown_rate: float
    skipped: bool
    failed_case_ids: list[str]
    unknown_case_ids: list[str]
    unavailable_reason: str | None = None


def main() -> None:
    """Compare retrieval metrics across context modes."""
    parser = argparse.ArgumentParser(description="Compare document QA retrieval modes.")
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
        "--limit",
        type=int,
        default=None,
        help="Optional number of dataset cases to evaluate.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=4,
        help="Number of retrieved document chunks for retrieval modes.",
    )
    parser.add_argument(
        "--retrieval-scope",
        choices=("isolated", "corpus"),
        default="isolated",
        help="Use one document per case or retrieve from a shared dataset corpus.",
    )
    parser.add_argument(
        "--answer-mode",
        choices=ANSWER_MODE_CHOICES,
        default="oracle",
        help="Use oracle placeholder answers or generate answers with the configured model.",
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

    resource_cache: dict[str, EvalResources | RetrievalModeUnavailable] = {}
    results = [
        evaluate_mode(
            mode=mode,
            cases=cases,
            top_k=args.top_k,
            retrieval_scope=args.retrieval_scope,
            answer_mode=args.answer_mode,
            resource_cache=resource_cache,
        )
        for mode in args.modes
    ]
    print_comparison_table(results)
    if args.json:
        print(json.dumps([result_to_dict(result) for result in results], indent=2))


def evaluate_mode(
    mode: str,
    cases: list[dict],
    top_k: int = 4,
    retrieval_scope: str = "isolated",
    answer_mode: str = "oracle",
    resource_cache: dict[str, EvalResources | RetrievalModeUnavailable] | None = None,
) -> ModeComparisonResult:
    """Run one context mode and aggregate deterministic metrics."""
    try:
        resources = resources_for_mode(
            mode=mode,
            retrieval_scope=retrieval_scope,
            cases=cases,
            answer_mode=answer_mode,
            resource_cache=resource_cache,
        )
        results = [
            evaluate_case(
                case,
                context_mode=mode,
                top_k=top_k,
                resources=resources,
                retrieval_scope=retrieval_scope,
                answer_mode=answer_mode,
            )
            for case in cases
        ]
    except RetrievalModeUnavailable as error:
        return ModeComparisonResult(
            mode=mode,
            total_cases=len(cases),
            answer_anchor_match_rate=0.0,
            expected_answer_match_rate=0.0,
            context_evidence_hit_rate=0.0,
            context_answer_anchor_hit_rate=0.0,
            context_expected_answer_hit_rate=0.0,
            answer_mode=answer_mode,
            model_name=None,
            answer_unknown_rate=0.0,
            skipped=True,
            failed_case_ids=[],
            unknown_case_ids=[],
            unavailable_reason=str(error),
        )
    return aggregate_mode_results(mode=mode, results=results)


def resources_for_mode(
    mode: str,
    retrieval_scope: str,
    cases: list[dict],
    answer_mode: str,
    resource_cache: dict[str, EvalResources | RetrievalModeUnavailable] | None,
) -> EvalResources:
    """Return shared resources for comparison modes."""
    if retrieval_scope == "corpus":
        cache_key = f"corpus:{mode}:{answer_mode}"
    else:
        return build_eval_resources(
            mode,
            retrieval_scope=retrieval_scope,
            cases=cases,
            answer_mode=answer_mode,
        )

    if resource_cache is None:
        return build_eval_resources(
            mode,
            retrieval_scope=retrieval_scope,
            cases=cases,
            answer_mode=answer_mode,
        )

    cached = resource_cache.get(cache_key)
    if isinstance(cached, RetrievalModeUnavailable):
        raise cached
    if isinstance(cached, EvalResources):
        return cached

    try:
        resources = build_eval_resources(
            context_mode=mode,
            retrieval_scope=retrieval_scope,
            cases=cases,
            answer_mode=answer_mode,
        )
    except RetrievalModeUnavailable as error:
        resource_cache[cache_key] = error
        raise
    resource_cache[cache_key] = resources
    return resources


def aggregate_mode_results(mode: str, results: list[EvalResult]) -> ModeComparisonResult:
    """Aggregate per-case eval results into one row."""
    failed_case_ids = [
        result.case_id
        for result in results
        if not (
            result.answer_anchor_match
            and result.expected_answer_match
            and result.context_evidence_hit
            and result.context_answer_anchor_hit
            and result.context_expected_answer_hit
        )
    ]
    unknown_case_ids = [result.case_id for result in results if result.answer_unknown]
    return ModeComparisonResult(
        mode=mode,
        total_cases=len(results),
        answer_anchor_match_rate=rate(results, "answer_anchor_match"),
        expected_answer_match_rate=rate(results, "expected_answer_match"),
        context_evidence_hit_rate=rate(results, "context_evidence_hit"),
        context_answer_anchor_hit_rate=rate(results, "context_answer_anchor_hit"),
        context_expected_answer_hit_rate=rate(results, "context_expected_answer_hit"),
        answer_mode=results[0].answer_mode if results else "oracle",
        model_name=results[0].model_name if results else None,
        answer_unknown_rate=rate(results, "answer_unknown"),
        skipped=False,
        failed_case_ids=failed_case_ids,
        unknown_case_ids=unknown_case_ids,
    )


def print_comparison_table(results: list[ModeComparisonResult]) -> None:
    """Print side-by-side retrieval metrics."""
    headers = [
        "mode",
        "answer_mode",
        "cases",
        "ctx_evidence",
        "ctx_anchor",
        "ctx_expected",
        "ans_anchor",
        "exp_answer",
        "unknown",
        "skipped",
        "failed",
        "reason",
    ]
    rows = [comparison_row(result) for result in results]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        if rows
        else len(headers[index])
        for index in range(len(headers))
    ]
    print("Document QA retrieval mode comparison")
    print(format_row(headers, widths))
    print(format_row(["-" * width for width in widths], widths))
    for row in rows:
        print(format_row(row, widths))


def comparison_row(result: ModeComparisonResult) -> list[str]:
    """Convert one comparison result into printable cells."""
    reason = result.unavailable_reason or ""
    if len(reason) > 80:
        reason = f"{reason[:77]}..."
    return [
        result.mode,
        result.answer_mode,
        str(result.total_cases),
        f"{result.context_evidence_hit_rate:.2f}",
        f"{result.context_answer_anchor_hit_rate:.2f}",
        f"{result.context_expected_answer_hit_rate:.2f}",
        f"{result.answer_anchor_match_rate:.2f}",
        f"{result.expected_answer_match_rate:.2f}",
        f"{result.answer_unknown_rate:.2f}",
        "yes" if result.skipped else "no",
        ",".join(result.failed_case_ids) if result.failed_case_ids else "[]",
        reason,
    ]


def format_row(cells: list[str], widths: list[int]) -> str:
    """Format a simple fixed-width table row."""
    return " | ".join(cell.ljust(width) for cell, width in zip(cells, widths, strict=True))


def result_to_dict(result: ModeComparisonResult) -> dict:
    """Return a JSON-serializable result."""
    return {
        "mode": result.mode,
        "total_cases": result.total_cases,
        "context_evidence_hit_rate": result.context_evidence_hit_rate,
        "context_answer_anchor_hit_rate": result.context_answer_anchor_hit_rate,
        "context_expected_answer_hit_rate": result.context_expected_answer_hit_rate,
        "answer_anchor_match_rate": result.answer_anchor_match_rate,
        "expected_answer_match_rate": result.expected_answer_match_rate,
        "answer_mode": result.answer_mode,
        "model_name": result.model_name,
        "answer_unknown_rate": result.answer_unknown_rate,
        "skipped": result.skipped,
        "failed_case_ids": result.failed_case_ids,
        "unknown_case_ids": result.unknown_case_ids,
        "unavailable_reason": result.unavailable_reason,
    }


if __name__ == "__main__":
    main()
