from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.routing.routing_agent import RoutingAgent


DEFAULT_DATASET = Path(__file__).parent / "datasets" / "routing_curated_v1.jsonl"
DEFAULT_OUTPUT_DIR = Path("artifacts") / "routing_eval"
DEFAULT_MODES = ("rule", "semantic", "semantic_full")
EVALUATED_SOURCES = (
    "recent_messages",
    "structured_memory",
    "document_memory",
    "previous_chat_gist",
    "raw_message_span",
    "current_chat_span",
)


@dataclass(frozen=True)
class RoutingCase:
    """One manually curated routing-only evaluation case."""

    case_id: str
    category: str
    query: str
    expected_sources: tuple[str, ...]
    required_sources: tuple[str, ...]
    allowed_sources: tuple[str, ...]
    forbidden_sources: tuple[str, ...]
    temporal_scope: str
    exact_evidence_required: bool
    notes: str = ""


def main() -> None:
    """Run the deterministic routing benchmark."""
    parser = argparse.ArgumentParser(description="Run routing-only evaluation.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to routing JSONL dataset.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for summary/report artifacts.",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        default=list(DEFAULT_MODES),
        help="Routing modes to evaluate.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full machine-readable report to stdout.",
    )
    args = parser.parse_args()

    cases = load_cases(args.dataset)
    report = evaluate_modes(cases=cases, modes=tuple(args.modes))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = report["timestamp"]
    json_path = args.output_dir / f"routing_eval_{timestamp}.json"
    md_path = args.output_dir / f"routing_eval_{timestamp}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print_summary(report=report, json_path=json_path, md_path=md_path)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))


def load_cases(path: Path) -> list[RoutingCase]:
    """Load repository-owned JSONL routing cases."""
    cases: list[RoutingCase] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            case = case_from_payload(payload, path=path, line_number=line_number)
            if case.case_id in seen:
                raise ValueError(f"Duplicate case_id in {path}: {case.case_id}")
            seen.add(case.case_id)
            cases.append(case)
    if not cases:
        raise ValueError(f"Routing dataset is empty: {path}")
    return cases


def case_from_payload(
    payload: dict[str, Any],
    path: Path,
    line_number: int,
) -> RoutingCase:
    """Validate and normalize one JSONL row."""
    required = ("case_id", "category", "query", "expected")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(
            f"Missing keys at {path}:{line_number}: {', '.join(missing)}"
        )
    expected = payload["expected"]
    if not isinstance(expected, dict):
        raise ValueError(f"expected must be an object at {path}:{line_number}")
    enabled_sources = normalize_sources(expected.get("enabled_sources", ()))
    source_booleans = {
        source: bool(expected.get(source, False)) for source in EVALUATED_SOURCES
    }
    boolean_sources = tuple(
        source for source in EVALUATED_SOURCES if source_booleans[source]
    )
    if set(enabled_sources) != set(boolean_sources):
        raise ValueError(
            "enabled_sources must match per-source booleans at "
            f"{path}:{line_number}"
        )
    invalid_sources = set(enabled_sources) - set(EVALUATED_SOURCES)
    if invalid_sources:
        raise ValueError(
            f"Unsupported expected sources at {path}:{line_number}: "
            + ", ".join(sorted(invalid_sources))
        )
    required_sources = normalize_sources(
        expected.get("required_sources", enabled_sources)
    )
    allowed_sources = normalize_sources(
        expected.get(
            "allowed_sources",
            default_allowed_sources(
                required_sources=required_sources,
                forbidden_sources=normalize_sources(expected.get("forbidden_sources", ())),
            ),
        )
    )
    forbidden_sources = normalize_sources(
        expected.get(
            "forbidden_sources",
            tuple(source for source in EVALUATED_SOURCES if source not in allowed_sources),
        )
    )
    validate_source_subset(
        label="required_sources",
        sources=required_sources,
        path=path,
        line_number=line_number,
    )
    validate_source_subset(
        label="allowed_sources",
        sources=allowed_sources,
        path=path,
        line_number=line_number,
    )
    validate_source_subset(
        label="forbidden_sources",
        sources=forbidden_sources,
        path=path,
        line_number=line_number,
    )
    if set(required_sources) - set(allowed_sources):
        raise ValueError(
            f"required_sources must be allowed at {path}:{line_number}"
        )
    if set(forbidden_sources) & set(allowed_sources):
        raise ValueError(
            f"allowed_sources and forbidden_sources overlap at {path}:{line_number}"
        )
    return RoutingCase(
        case_id=str(payload["case_id"]),
        category=str(payload["category"]),
        query=str(payload["query"]),
        expected_sources=enabled_sources,
        required_sources=required_sources,
        allowed_sources=allowed_sources,
        forbidden_sources=forbidden_sources,
        temporal_scope=str(expected.get("temporal_scope", "none")),
        exact_evidence_required=bool(expected.get("exact_evidence_required", False)),
        notes=str(expected.get("notes", payload.get("notes", ""))),
    )


def evaluate_modes(cases: list[RoutingCase], modes: tuple[str, ...]) -> dict[str, Any]:
    """Evaluate all requested routing modes against fixed gold labels."""
    rows: list[dict[str, Any]] = []
    for case in cases:
        for mode in modes:
            rows.append(evaluate_case(case=case, mode=mode))
    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "dataset_size": len(cases),
        "category_breakdown": category_breakdown(cases),
        "sources": list(EVALUATED_SOURCES),
        "modes": {
            mode: summarize_mode(
                rows=[row for row in rows if row["mode"] == mode],
                cases=cases,
            )
            for mode in modes
        },
        "comparisons": {
            mode: compare_against_rule(rows=rows, mode=mode)
            for mode in modes
            if mode != "rule"
        },
        "results": rows,
    }


def evaluate_case(case: RoutingCase, mode: str) -> dict[str, Any]:
    """Evaluate one query in one routing mode."""
    decision = RoutingAgent(mode=mode).route(case.query)
    trace = decision.to_trace_dict()
    predicted_sources = tuple(
        source
        for source in EVALUATED_SOURCES
        if source in set(trace["active_sources"])
    )
    predicted_temporal_scope = infer_temporal_scope(predicted_sources)
    predicted_exact = infer_exact_evidence_required(trace=trace)
    expected_sources = set(case.expected_sources)
    predicted_source_set = set(predicted_sources)
    missing_sources = sorted(expected_sources - predicted_source_set)
    extra_sources = sorted(predicted_source_set - expected_sources)
    required_sources = set(case.required_sources)
    allowed_sources = set(case.allowed_sources)
    forbidden_sources = set(case.forbidden_sources)
    optional_allowed_sources = allowed_sources - required_sources
    relaxed_temporal_sources = tuple(
        source
        for source in predicted_sources
        if source not in optional_allowed_sources
    )
    relaxed_predicted_temporal_scope = infer_temporal_scope(relaxed_temporal_sources)
    missing_required_sources = sorted(required_sources - predicted_source_set)
    forbidden_enabled_sources = sorted(forbidden_sources & predicted_source_set)
    disallowed_sources = sorted(predicted_source_set - allowed_sources)
    source_exact_match = predicted_source_set == expected_sources
    temporal_match = predicted_temporal_scope == case.temporal_scope
    relaxed_temporal_match = relaxed_predicted_temporal_scope == case.temporal_scope
    exact_match = predicted_exact == case.exact_evidence_required
    required_sources_recalled = not missing_required_sources
    no_forbidden_sources = not forbidden_enabled_sources
    no_disallowed_sources = not disallowed_sources
    relaxed_source_match = (
        required_sources_recalled and no_forbidden_sources and no_disallowed_sources
    )
    return {
        "case_id": case.case_id,
        "category": case.category,
        "query": case.query,
        "mode": mode,
        "expected_sources": list(case.expected_sources),
        "required_sources": list(case.required_sources),
        "allowed_sources": list(case.allowed_sources),
        "forbidden_sources": list(case.forbidden_sources),
        "predicted_sources": list(predicted_sources),
        "missing_sources": missing_sources,
        "extra_sources": extra_sources,
        "missing_required_sources": missing_required_sources,
        "forbidden_enabled_sources": forbidden_enabled_sources,
        "disallowed_sources": disallowed_sources,
        "expected_temporal_scope": case.temporal_scope,
        "predicted_temporal_scope": predicted_temporal_scope,
        "relaxed_predicted_temporal_scope": relaxed_predicted_temporal_scope,
        "expected_exact_evidence_required": case.exact_evidence_required,
        "predicted_exact_evidence_required": predicted_exact,
        "source_exact_match": source_exact_match,
        "required_sources_recalled": required_sources_recalled,
        "no_forbidden_sources": no_forbidden_sources,
        "no_disallowed_sources": no_disallowed_sources,
        "relaxed_source_match": relaxed_source_match,
        "temporal_match": temporal_match,
        "relaxed_temporal_match": relaxed_temporal_match,
        "exact_evidence_match": exact_match,
        "strict_correct": source_exact_match and temporal_match and exact_match,
        "relaxed_correct": (
            relaxed_source_match and relaxed_temporal_match and exact_match
        ),
        "correct": source_exact_match and temporal_match and exact_match,
        "routing_error_count": routing_error_count(
            missing_sources=missing_sources,
            extra_sources=extra_sources,
            temporal_match=temporal_match,
            exact_match=exact_match,
        ),
        "relaxed_routing_error_count": routing_error_count(
            missing_sources=missing_required_sources,
            extra_sources=forbidden_enabled_sources + disallowed_sources,
            temporal_match=relaxed_temporal_match,
            exact_match=exact_match,
        ),
        "intent": trace.get("intent"),
        "context_profile": trace.get("context_profile"),
        "routing_mode": trace.get("routing_mode"),
        "routing_fallback_reason": trace.get("routing_fallback_reason"),
    }


def summarize_mode(
    rows: list[dict[str, Any]],
    cases: list[RoutingCase],
) -> dict[str, Any]:
    """Aggregate accuracy and source metrics for one mode."""
    strict_correct = sum(1 for row in rows if row["strict_correct"])
    relaxed_correct = sum(1 for row in rows if row["relaxed_correct"])
    required_recalled = sum(1 for row in rows if row["required_sources_recalled"])
    over_retrieval_free = sum(
        1
        for row in rows
        if row["no_forbidden_sources"] and row["no_disallowed_sources"]
    )
    by_category: dict[str, dict[str, Any]] = {}
    for category in sorted({case.category for case in cases}):
        category_rows = [row for row in rows if row["category"] == category]
        category_strict = sum(1 for row in category_rows if row["strict_correct"])
        category_relaxed = sum(1 for row in category_rows if row["relaxed_correct"])
        category_required = sum(
            1 for row in category_rows if row["required_sources_recalled"]
        )
        category_over_retrieved = sum(
            1
            for row in category_rows
            if row["forbidden_enabled_sources"] or row["disallowed_sources"]
        )
        by_category[category] = {
            "strict_correct": category_strict,
            "relaxed_correct": category_relaxed,
            "required_recalled": category_required,
            "over_retrieved": category_over_retrieved,
            "total": len(category_rows),
            "strict_accuracy": safe_div(category_strict, len(category_rows)),
            "relaxed_accuracy": safe_div(category_relaxed, len(category_rows)),
            "required_recall": safe_div(category_required, len(category_rows)),
            "over_retrieval_rate": safe_div(
                category_over_retrieved,
                len(category_rows),
            ),
        }
    return {
        "correct": strict_correct,
        "strict_correct": strict_correct,
        "relaxed_correct": relaxed_correct,
        "required_recalled": required_recalled,
        "over_retrieval_free": over_retrieval_free,
        "total": len(rows),
        "accuracy": safe_div(strict_correct, len(rows)),
        "strict_accuracy": safe_div(strict_correct, len(rows)),
        "relaxed_accuracy": safe_div(relaxed_correct, len(rows)),
        "required_source_recall": safe_div(required_recalled, len(rows)),
        "over_retrieval_rate": safe_div(
            len(rows) - over_retrieval_free,
            len(rows),
        ),
        "per_category": by_category,
        "per_source": per_source_metrics(rows),
        "required_source_metrics": required_source_metrics(rows),
        "forbidden_source_metrics": forbidden_source_metrics(rows),
        "confusion_matrix": confusion_matrix(rows),
        "false_positives": [
            row
            for row in rows
            if row["forbidden_enabled_sources"]
            or row["disallowed_sources"]
            or not row["temporal_match"]
        ],
        "false_negatives": [
            row
            for row in rows
            if row["missing_required_sources"] or not row["temporal_match"]
        ],
    }


def per_source_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Compute per-source precision, recall, and F1."""
    metrics: dict[str, dict[str, Any]] = {}
    for source in EVALUATED_SOURCES:
        true_positive = false_positive = false_negative = true_negative = 0
        for row in rows:
            expected = source in row["expected_sources"]
            predicted = source in row["predicted_sources"]
            if expected and predicted:
                true_positive += 1
            elif not expected and predicted:
                false_positive += 1
            elif expected and not predicted:
                false_negative += 1
            else:
                true_negative += 1
        precision = safe_div(true_positive, true_positive + false_positive)
        recall = safe_div(true_positive, true_positive + false_negative)
        f1 = safe_div(2 * precision * recall, precision + recall)
        metrics[source] = {
            "tp": true_positive,
            "fp": false_positive,
            "fn": false_negative,
            "tn": true_negative,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return metrics


def required_source_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Compute recall against required sources only."""
    metrics: dict[str, dict[str, Any]] = {}
    for source in EVALUATED_SOURCES:
        required_total = sum(1 for row in rows if source in row["required_sources"])
        hit_total = sum(
            1
            for row in rows
            if source in row["required_sources"] and source in row["predicted_sources"]
        )
        metrics[source] = {
            "required": required_total,
            "hit": hit_total,
            "recall": safe_div(hit_total, required_total),
        }
    return metrics


def forbidden_source_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Compute precision/over-retrieval against forbidden sources."""
    metrics: dict[str, dict[str, Any]] = {}
    for source in EVALUATED_SOURCES:
        predicted_total = sum(1 for row in rows if source in row["predicted_sources"])
        forbidden_hits = sum(
            1
            for row in rows
            if source in row["forbidden_sources"] and source in row["predicted_sources"]
        )
        metrics[source] = {
            "predicted": predicted_total,
            "forbidden_hits": forbidden_hits,
            "forbidden_precision": safe_div(
                predicted_total - forbidden_hits,
                predicted_total,
            ),
            "over_retrieval_rate": safe_div(forbidden_hits, len(rows)),
        }
    return metrics


def confusion_matrix(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a compact expected-source-set vs predicted-source-set matrix."""
    counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        expected = source_set_label(row["expected_sources"])
        predicted = source_set_label(row["predicted_sources"])
        counts[(expected, predicted)] += 1
    return [
        {"expected": expected, "predicted": predicted, "count": count}
        for (expected, predicted), count in sorted(counts.items())
    ]


def compare_against_rule(rows: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    """Return cases improved/regressed by a mode relative to rule."""
    by_id_mode = {(row["case_id"], row["mode"]): row for row in rows}
    improved: list[dict[str, Any]] = []
    regressed: list[dict[str, Any]] = []
    matched = 0
    case_ids = sorted({row["case_id"] for row in rows})
    for case_id in case_ids:
        rule = by_id_mode.get((case_id, "rule"))
        current = by_id_mode.get((case_id, mode))
        if rule is None or current is None:
            continue
        if current["relaxed_correct"] and not rule["relaxed_correct"]:
            improved.append(current)
        elif rule["relaxed_correct"] and not current["relaxed_correct"]:
            regressed.append(current)
        elif current["relaxed_routing_error_count"] < rule["relaxed_routing_error_count"]:
            improved.append(current)
        elif current["relaxed_routing_error_count"] > rule["relaxed_routing_error_count"]:
            regressed.append(current)
        else:
            matched += 1
    return {
        "improved_count": len(improved),
        "regressed_count": len(regressed),
        "matched_count": matched,
        "top_improvements": improved[:20],
        "top_regressions": regressed[:20],
    }


def infer_temporal_scope(predicted_sources: tuple[str, ...]) -> str:
    """Infer a route-level temporal/scope label from selected sources."""
    sources = set(predicted_sources)
    if "document_memory" in sources:
        return "document"
    if {"previous_chat_gist", "raw_message_span"} & sources:
        return "previous"
    if "current_chat_span" in sources:
        return "current"
    if "structured_memory" in sources:
        return "durable"
    return "none"


def routing_error_count(
    missing_sources: list[str],
    extra_sources: list[str],
    temporal_match: bool,
    exact_match: bool,
) -> int:
    """Return a deterministic distance from the gold route contract."""
    return (
        len(missing_sources)
        + len(extra_sources)
        + (0 if temporal_match else 1)
        + (0 if exact_match else 1)
    )


def normalize_sources(value: Any) -> tuple[str, ...]:
    """Return a deterministic tuple of source labels from JSON data."""
    return tuple(str(item) for item in value)


def validate_source_subset(
    label: str,
    sources: tuple[str, ...],
    path: Path,
    line_number: int,
) -> None:
    """Validate that source labels are known."""
    invalid_sources = set(sources) - set(EVALUATED_SOURCES)
    if invalid_sources:
        raise ValueError(
            f"Unsupported {label} at {path}:{line_number}: "
            + ", ".join(sorted(invalid_sources))
        )


def default_allowed_sources(
    required_sources: tuple[str, ...],
    forbidden_sources: tuple[str, ...],
) -> tuple[str, ...]:
    """Derive relaxed allowed sources for legacy rows.

    `structured_memory` is allowed by default because the current production
    router intentionally keeps it broadly enabled. Rows can still forbid it
    explicitly by providing `forbidden_sources`.
    """
    allowed = {"recent_messages", "structured_memory", *required_sources}
    allowed -= set(forbidden_sources)
    return tuple(source for source in EVALUATED_SOURCES if source in allowed)


def infer_exact_evidence_required(trace: dict[str, Any]) -> bool:
    """Infer whether the route asks for exact/raw evidence."""
    active = set(trace["active_sources"])
    if "current_chat_span" in active or "raw_message_span" in active:
        return True
    metadata_value = trace.get("requires_raw_span")
    return bool(metadata_value)


def category_breakdown(cases: list[RoutingCase]) -> dict[str, int]:
    """Return case count per category."""
    counts: defaultdict[str, int] = defaultdict(int)
    for case in cases:
        counts[case.category] += 1
    return dict(sorted(counts.items()))


def source_set_label(sources: list[str] | tuple[str, ...]) -> str:
    """Return a deterministic label for a set of source names."""
    return "+".join(sorted(sources)) if sources else "none"


def safe_div(numerator: float, denominator: float) -> float:
    """Return rounded safe division."""
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def render_markdown(report: dict[str, Any]) -> str:
    """Render a concise Markdown summary."""
    lines: list[str] = [
        f"# Routing Evaluation Report ({report['timestamp']})\n\n",
        "This benchmark evaluates routing decisions only. It does not run "
        "retrieval, reranking, context assembly, answer generation, model "
        "judging, MAB, or LongMemEval.\n\n",
        f"Dataset size: {report['dataset_size']}\n\n",
        "## Category breakdown\n\n",
        "| Category | Cases |\n|---|---:|\n",
    ]
    for category, count in report["category_breakdown"].items():
        lines.append(f"| {category} | {count} |\n")
    lines.extend(
        [
            "\n## Overall metrics\n\n",
            "| Mode | Strict exact | Relaxed | Required recall | Over-retrieval rate |\n",
            "|---|---:|---:|---:|---:|\n",
        ]
    )
    for mode, summary in report["modes"].items():
        lines.append(
            f"| `{mode}` | {summary['strict_correct']}/{summary['total']} "
            f"({summary['strict_accuracy']:.4f}) | "
            f"{summary['relaxed_correct']}/{summary['total']} "
            f"({summary['relaxed_accuracy']:.4f}) | "
            f"{summary['required_source_recall']:.4f} | "
            f"{summary['over_retrieval_rate']:.4f} |\n"
        )
    lines.extend(
        [
            "\n## Strict per-source metrics\n\n",
            "| Mode | Source | Precision | Recall | F1 | TP | FP | FN |\n",
            "|---|---|---:|---:|---:|---:|---:|---:|\n",
        ]
    )
    for mode, summary in report["modes"].items():
        for source, metrics in summary["per_source"].items():
            lines.append(
                f"| `{mode}` | `{source}` | {metrics['precision']:.4f} | "
                f"{metrics['recall']:.4f} | {metrics['f1']:.4f} | "
                f"{metrics['tp']} | {metrics['fp']} | {metrics['fn']} |\n"
            )
    lines.extend(
        [
            "\n## Required-source and forbidden-source metrics\n\n",
            "| Mode | Source | Required recall | Forbidden precision | Source over-retrieval rate |\n",
            "|---|---|---:|---:|---:|\n",
        ]
    )
    for mode, summary in report["modes"].items():
        for source in report["sources"]:
            required = summary["required_source_metrics"][source]
            forbidden = summary["forbidden_source_metrics"][source]
            lines.append(
                f"| `{mode}` | `{source}` | {required['recall']:.4f} | "
                f"{forbidden['forbidden_precision']:.4f} | "
                f"{forbidden['over_retrieval_rate']:.4f} |\n"
            )
    lines.extend(
        [
            "\n## Per-category metrics\n\n",
            "| Mode | Category | Required recall | Over-retrieval rate | Strict exact | Relaxed |\n",
            "|---|---|---:|---:|---:|---:|\n",
        ]
    )
    for mode, summary in report["modes"].items():
        for category, metrics in summary["per_category"].items():
            lines.append(
                f"| `{mode}` | {category} | {metrics['required_recall']:.4f} | "
                f"{metrics['over_retrieval_rate']:.4f} | "
                f"{metrics['strict_accuracy']:.4f} | "
                f"{metrics['relaxed_accuracy']:.4f} |\n"
            )
    for mode, comparison in report["comparisons"].items():
        lines.append(f"\n## `{mode}` vs `rule`\n\n")
        lines.append(
            f"Improved: {comparison['improved_count']}; "
            f"regressed: {comparison['regressed_count']}; "
            f"matched: {comparison['matched_count']}.\n\n"
        )
        lines.append("### Top improvements\n\n")
        lines.append(render_case_list(comparison["top_improvements"]))
        lines.append("\n### Top regressions\n\n")
        lines.append(render_case_list(comparison["top_regressions"]))
    lines.append("\n## Confusion matrix\n\nSee JSON report for the full matrix.\n")
    return "".join(lines)


def render_case_list(rows: list[dict[str, Any]]) -> str:
    """Render compact case bullets."""
    if not rows:
        return "None\n"
    return "".join(
        "- `{case_id}` ({category}): {query} | expected={expected_sources} "
        "predicted={predicted_sources}\n".format(**row)
        for row in rows
    )


def print_summary(report: dict[str, Any], json_path: Path, md_path: Path) -> None:
    """Print a compact terminal summary."""
    print("Routing evaluation")
    print(f"dataset_size: {report['dataset_size']}")
    for mode, summary in report["modes"].items():
        print(
            f"{mode}: strict={summary['strict_correct']}/{summary['total']} "
            f"({summary['strict_accuracy']:.4f}) "
            f"relaxed={summary['relaxed_correct']}/{summary['total']} "
            f"({summary['relaxed_accuracy']:.4f}) "
            f"required_recall={summary['required_source_recall']:.4f} "
            f"over_retrieval={summary['over_retrieval_rate']:.4f}"
        )
    print(f"json_report: {json_path}")
    print(f"markdown_report: {md_path}")


if __name__ == "__main__":
    main()
