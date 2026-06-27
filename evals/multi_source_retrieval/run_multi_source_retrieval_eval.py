from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan  # noqa: E402
from src.retrieval.retriever_dispatcher import RetrieverDispatcher  # noqa: E402


DEFAULT_DATASET = Path(__file__).parent / "datasets" / "source_selection_sample.jsonl"
ALL_SOURCE_LABELS = (
    "recent_messages",
    "structured_memory",
    "document_memory",
    "current_chat_gist",
    "previous_chat_gist",
    "raw_message_span",
)


@dataclass(frozen=True)
class MultiSourceCaseResult:
    """Evaluation result for one multi-source retrieval case."""

    case_id: str
    source_selection_correct: bool
    retrieval_hit: bool
    forbidden_source_violation: bool
    abstain_correct: bool | None
    enabled_sources: list[str]
    retrieved_sources: list[str]
    hit_count: int
    failed_reasons: list[str]
    trace: dict[str, Any]


class FixtureRetriever:
    """Deterministic source retriever backed by in-memory candidates."""

    def __init__(self, candidates: list[MemoryCandidate]) -> None:
        self.candidates = candidates

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        del chat_id
        limit = source_plan.limit or len(self.candidates)
        return self.candidates[:limit]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic multi-source retrieval/source-selection eval."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--mode",
        choices=("mock",),
        default="mock",
        help="mock mode uses deterministic fixture candidates and no model/API calls.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, help="Optional JSON trace report path.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    return parser.parse_args()


def load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Load multi-source retrieval cases from JSONL."""
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            cases.append(json.loads(line))
            if limit is not None and len(cases) >= limit:
                break
    return cases


def run_cases(cases: list[dict[str, Any]], top_k: int = 5) -> list[MultiSourceCaseResult]:
    """Run all multi-source retrieval cases in deterministic mock mode."""
    return [run_case(case, top_k=top_k) for case in cases]


def run_case(case: dict[str, Any], top_k: int = 5) -> MultiSourceCaseResult:
    """Run one case through RoutePlan + RetrieverDispatcher using fake retrievers."""
    route_plan = route_plan_for_case(case, top_k=top_k)
    candidates = fixture_candidates(case)
    dispatcher = RetrieverDispatcher(
        database=cast(Any, None),
        retrievers=fixture_retrievers_by_source(candidates),
    )
    retrieved = dispatcher.retrieve(chat_id="multi-source-eval", route_plan=route_plan)
    return score_case(case=case, route_plan=route_plan, retrieved_candidates=retrieved)


def route_plan_for_case(case: dict[str, Any], top_k: int) -> RoutePlan:
    """Build an explicit source plan from one dataset case."""
    enabled_sources = set(str(source) for source in case.get("enabled_sources", []))
    query = str(case.get("query") or "")
    sources = [
        SourcePlan(
            source=cast(Any, source),
            enabled=source in enabled_sources,
            reason=(
                "Enabled by multi-source retrieval eval fixture."
                if source in enabled_sources
                else "Disabled by multi-source retrieval eval fixture."
            ),
            query=query if source in enabled_sources else None,
            limit=top_k,
        )
        for source in ALL_SOURCE_LABELS
    ]
    return RoutePlan(
        query=query,
        sources=sources,
        intent=str(case.get("case_id") or "multi_source_eval"),
        confidence=1.0,
        requires_retrieval=True,
        ranking_profile="eval_fixture_order",
        context_profile="multi_source_retrieval_eval",
        metadata={"eval_mode": "mock"},
    )


def fixture_candidates(case: dict[str, Any]) -> list[MemoryCandidate]:
    """Convert dataset fixture candidates to MemoryCandidate objects."""
    candidates = []
    for raw_candidate in case.get("candidate_fixtures", []):
        if not isinstance(raw_candidate, dict):
            continue
        candidates.append(
            MemoryCandidate(
                source=cast(Any, raw_candidate.get("source", "unknown")),
                content=str(raw_candidate.get("content") or ""),
                score=(
                    float(raw_candidate["score"])
                    if isinstance(raw_candidate.get("score"), int | float)
                    else None
                ),
                record_id=raw_candidate.get("record_id"),
                chat_id=raw_candidate.get("chat_id"),
                source_message_ids=[
                    item
                    for item in raw_candidate.get("source_message_ids", [])
                    if isinstance(item, int)
                ],
                metadata=dict(raw_candidate.get("metadata") or {}),
            )
        )
    return candidates


def fixture_retrievers_by_source(
    candidates: list[MemoryCandidate],
) -> dict[str, FixtureRetriever]:
    """Group fixture candidates into fake retrievers by source."""
    by_source: dict[str, list[MemoryCandidate]] = {
        source: [] for source in ALL_SOURCE_LABELS
    }
    for candidate in candidates:
        by_source.setdefault(candidate.source, []).append(candidate)
    return {
        source: FixtureRetriever(source_candidates)
        for source, source_candidates in by_source.items()
    }


def score_case(
    case: dict[str, Any],
    route_plan: RoutePlan,
    retrieved_candidates: list[MemoryCandidate],
) -> MultiSourceCaseResult:
    """Score source selection, retrieval hits, forbidden source use, and abstain."""
    expected_sources = set(str(source) for source in case.get("expected_sources", []))
    forbidden_sources = set(str(source) for source in case.get("forbidden_sources", []))
    expected_substrings = [
        str(item).lower() for item in case.get("expected_candidate_contains", [])
    ]
    expected_min_hits = int(case.get("expected_min_hits", len(expected_substrings)))
    enabled_sources = [source.source for source in route_plan.sources if source.enabled]
    retrieved_sources = [candidate.source for candidate in retrieved_candidates]

    source_selection_correct = expected_sources.issubset(set(enabled_sources)) and not (
        forbidden_sources & set(enabled_sources)
    )
    forbidden_source_violation = bool(forbidden_sources & set(retrieved_sources))
    retrieved_text = "\n".join(candidate.content for candidate in retrieved_candidates).lower()
    hit_count = sum(1 for substring in expected_substrings if substring in retrieved_text)
    retrieval_hit = (
        len(retrieved_candidates) == 0
        if expected_min_hits == 0 and not expected_substrings
        else hit_count >= expected_min_hits
    )
    abstain_correct = None
    if not expected_sources and expected_min_hits == 0:
        abstain_correct = len(retrieved_candidates) == 0

    failed_reasons = []
    if not source_selection_correct:
        failed_reasons.append("source_selection_mismatch")
    if not retrieval_hit:
        failed_reasons.append("retrieval_hit_miss")
    if forbidden_source_violation:
        failed_reasons.append("forbidden_source_retrieved")
    if abstain_correct is False:
        failed_reasons.append("abstain_failed")

    return MultiSourceCaseResult(
        case_id=str(case.get("case_id") or ""),
        source_selection_correct=source_selection_correct,
        retrieval_hit=retrieval_hit,
        forbidden_source_violation=forbidden_source_violation,
        abstain_correct=abstain_correct,
        enabled_sources=enabled_sources,
        retrieved_sources=retrieved_sources,
        hit_count=hit_count,
        failed_reasons=failed_reasons,
        trace=trace_for_case(case, route_plan, retrieved_candidates, failed_reasons),
    )


def trace_for_case(
    case: dict[str, Any],
    route_plan: RoutePlan,
    retrieved_candidates: list[MemoryCandidate],
    failed_reasons: list[str],
) -> dict[str, Any]:
    """Return JSON-ready trace for one eval case."""
    return {
        "case_id": str(case.get("case_id") or ""),
        "query": str(case.get("query") or ""),
        "notes": str(case.get("notes") or ""),
        "routing": {
            "intent": route_plan.intent,
            "confidence": route_plan.confidence,
            "active_sources": [
                source.source for source in route_plan.sources if source.enabled
            ],
            "disabled_sources": [
                source.source for source in route_plan.sources if not source.enabled
            ],
            "source_plans": [
                {
                    "source": source.source,
                    "enabled": source.enabled,
                    "reason": source.reason,
                    "limit": source.limit,
                }
                for source in route_plan.sources
            ],
            "metadata": dict(route_plan.metadata),
        },
        "retrieved_candidates": [
            candidate_to_trace(candidate) for candidate in retrieved_candidates
        ],
        "failed_reasons": list(failed_reasons),
    }


def candidate_to_trace(candidate: MemoryCandidate) -> dict[str, Any]:
    """Return a JSON-ready candidate trace row."""
    return {
        "source": candidate.source,
        "record_id": candidate.record_id,
        "chat_id": candidate.chat_id,
        "score": candidate.score,
        "content": candidate.content,
        "source_message_ids": list(candidate.source_message_ids),
        "metadata": dict(candidate.metadata),
    }


def summarize_results(results: list[MultiSourceCaseResult]) -> dict[str, Any]:
    """Summarize eval results as rates and failed case ids."""
    total = len(results)
    return {
        "total_cases": total,
        "source_selection_accuracy": rate(
            result.source_selection_correct for result in results
        ),
        "retrieval_hit_at_k": rate(result.retrieval_hit for result in results),
        "forbidden_source_violations": sum(
            1 for result in results if result.forbidden_source_violation
        ),
        "abstain_correctness": rate(
            result.abstain_correct
            for result in results
            if result.abstain_correct is not None
        ),
        "failed_case_ids": [
            result.case_id for result in results if result.failed_reasons
        ],
    }


def rate(values: Any) -> float:
    """Return the fraction of truthy values, or 0 for an empty iterable."""
    items = list(values)
    if not items:
        return 0.0
    return sum(1 for item in items if item) / len(items)


def report_payload(results: list[MultiSourceCaseResult], top_k: int) -> dict[str, Any]:
    """Return JSON-ready report payload."""
    return {
        "eval_name": "multi_source_retrieval",
        "mode": "mock",
        "top_k": top_k,
        "summary": summarize_results(results),
        "cases": [
            {
                "case_id": result.case_id,
                "source_selection_correct": result.source_selection_correct,
                "retrieval_hit": result.retrieval_hit,
                "forbidden_source_violation": result.forbidden_source_violation,
                "abstain_correct": result.abstain_correct,
                "enabled_sources": result.enabled_sources,
                "retrieved_sources": result.retrieved_sources,
                "hit_count": result.hit_count,
                "failed_reasons": result.failed_reasons,
                "trace": result.trace,
            }
            for result in results
        ],
    }


def print_summary(results: list[MultiSourceCaseResult], top_k: int, json_output: bool) -> None:
    """Print readable or JSON summary."""
    payload = report_payload(results, top_k=top_k)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    print("multi_source_retrieval_eval mode=mock")
    for key, value in payload["summary"].items():
        print(f"{key}={value}")
    for result in results:
        status = "PASS" if not result.failed_reasons else "FAIL"
        print(
            "case_result "
            f"case_id={result.case_id} "
            f"status={status} "
            f"enabled_sources={result.enabled_sources} "
            f"retrieved_sources={result.retrieved_sources} "
            f"failed_reasons={result.failed_reasons}"
        )


def write_report(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON report to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    args = parse_args()
    cases = load_jsonl(args.dataset, limit=args.limit)
    results = run_cases(cases, top_k=args.top_k)
    payload = report_payload(results, top_k=args.top_k)
    if args.output:
        write_report(args.output, payload)
        print(f"wrote_report={args.output}")
    print_summary(results, top_k=args.top_k, json_output=args.json)
    return 1 if payload["summary"]["failed_case_ids"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
