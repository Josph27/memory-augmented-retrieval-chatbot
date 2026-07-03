from __future__ import annotations

import json
import math
import os
import tempfile
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


RESULTS_FILE = "results.jsonl"
SUMMARY_FILE = "summary.json"
FAILURES_FILE = "failures.jsonl"
DISAGREEMENTS_FILE = "disagreements.jsonl"
JUDGE_COMPARISON_FILE = "judge_comparison.json"
RUN_METADATA_FILE = "run_metadata.json"


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=True, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSONL at {path}:{line_number}") from error
            if not isinstance(value, dict):
                raise ValueError(f"expected object at {path}:{line_number}")
            rows.append(value)
    return rows


def latest_results(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        identity = str(row.get("result_identity", ""))
        if not identity:
            continue
        if identity not in latest:
            order.append(identity)
        latest[identity] = row
    return [latest[key] for key in order]


def write_compact_artifacts(
    output_dir: Path,
    *,
    results: list[dict[str, Any]],
    run_metadata: dict[str, Any],
) -> None:
    completed = [row for row in results if row.get("status") == "completed"]
    failures = [row for row in results if row.get("status") == "failed"]
    disagreements = [
        row
        for row in completed
        if bool(row.get("official_metric", {}).get("passed"))
        != bool(row.get("judge", {}).get("correct"))
    ]
    atomic_json(output_dir / SUMMARY_FILE, summarize(completed, failures))
    atomic_json(output_dir / RUN_METADATA_FILE, run_metadata)
    atomic_jsonl(output_dir / FAILURES_FILE, map(compact_failure, failures))
    atomic_jsonl(
        output_dir / DISAGREEMENTS_FILE,
        map(compact_disagreement, disagreements),
    )


def summarize(
    completed: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> dict[str, Any]:
    totals = completed + failures
    official_rows = [
        row for row in totals if isinstance(row.get("official_metric"), dict)
    ]
    answered_rows = [
        row
        for row in totals
        if isinstance(row.get("latency_ms"), dict)
        and isinstance(row.get("context_diagnostics"), dict)
    ]
    official = [bool(row["official_metric"]["passed"]) for row in official_rows]
    judged = [bool(row["judge"]["correct"]) for row in completed]
    faithful = [
        bool(row["judge"]["faithful_to_selected_context"])
        for row in completed
        if row["judge"].get("faithful_to_selected_context") is not None
    ]
    abstentions = [
        bool(row["judge"]["appropriate_abstention"])
        for row in completed
        if row["judge"].get("appropriate_abstention") is not None
    ]
    agreements = [
        bool(row["official_metric"]["passed"]) == bool(row["judge"]["correct"])
        for row in completed
    ]
    datasets = Counter(str(row.get("dataset")) for row in totals)
    question_types = Counter(str(row.get("question_type")) for row in totals)
    return {
        "total_cases": len(totals),
        "completed": len(completed),
        "generation_failures": sum(
            row.get("failed_stage") == "generation" for row in failures
        ),
        "judge_failures": sum(
            row.get("failed_stage") == "judge" for row in failures
        ),
        "official_pass_rate": rate(official),
        "judge_correctness_rate": rate(judged),
        "faithfulness_rate": rate(faithful),
        "abstention_accuracy": rate(abstentions),
        "official_judge_agreement_rate": rate(agreements),
        "latency_ms": distribution(
            [float(row["latency_ms"]["total"]) for row in answered_rows]
        ),
        "generation_latency_ms": distribution(
            [float(row["latency_ms"]["generation"]) for row in answered_rows]
        ),
        "judge_latency_ms": distribution(
            [float(row["latency_ms"]["judge"]) for row in completed]
        ),
        "selected_memory_tokens": distribution(
            [
                float(row["context_diagnostics"]["selected_memory_tokens"])
                for row in answered_rows
            ]
        ),
        "final_prompt_tokens": distribution(
            [
                float(row["context_diagnostics"]["final_prompt_tokens"])
                for row in answered_rows
            ]
        ),
        "counts_by_dataset": dict(sorted(datasets.items())),
        "counts_by_question_type": dict(sorted(question_types.items())),
    }


def distribution(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "p95": None}
    ordered = sorted(values)
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {"mean": round(mean(ordered), 3), "p95": round(ordered[p95_index], 3)}


def rate(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def compact_failure(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": row.get("case_id"),
        "dataset": row.get("dataset"),
        "execution_mode": row.get("execution_mode"),
        "failed_stage": row.get("failed_stage"),
        "error": row.get("error"),
        "context_diagnostics": row.get("context_diagnostics"),
    }


def compact_disagreement(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": row.get("case_id"),
        "dataset": row.get("dataset"),
        "official_metric": row.get("official_metric"),
        "judge": {
            "correct": row.get("judge", {}).get("correct"),
            "brief_reason": row.get("judge", {}).get("brief_reason"),
        },
    }


def write_judge_comparison(
    output_dir: Path,
    *,
    rows: list[dict[str, Any]],
    active_judge_model: str,
    active_judge_endpoint: str | None,
) -> None:
    by_identity: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row.get("judge"), dict):
            continue
        by_identity.setdefault(str(row.get("result_identity")), []).append(row)
    cases: list[dict[str, Any]] = []
    for identity_rows in by_identity.values():
        current = next(
            (
                row
                for row in reversed(identity_rows)
                if row.get("judge_model") == active_judge_model
                and row.get("judge_endpoint") == active_judge_endpoint
            ),
            None,
        )
        if current is None:
            continue
        previous = next(
            (
                row
                for row in reversed(identity_rows)
                if row.get("status") == "completed"
                and (
                    row.get("judge_model") != active_judge_model
                    or row.get("judge_endpoint") != active_judge_endpoint
                )
            ),
            None,
        )
        cases.append(
            {
                "case_id": current.get("case_id"),
                "previous_judge_model": (
                    previous.get("judge_model") if previous else None
                ),
                "previous_correct": (
                    previous.get("judge", {}).get("correct") if previous else None
                ),
                "current_judge_model": active_judge_model,
                "current_judge_endpoint": active_judge_endpoint,
                "current_correct": (
                    current["judge"].get("correct")
                    if current.get("status") == "completed"
                    else None
                ),
                "current_complete": (
                    current["judge"].get("complete")
                    if current.get("status") == "completed"
                    else None
                ),
                "current_parse_status": current["judge"].get("raw_parse_status"),
                "current_status": current.get("status"),
                "agreement": (
                    current.get("status") == "completed"
                    and previous is not None
                    and previous.get("judge", {}).get("correct")
                    == current["judge"].get("correct")
                ),
            }
        )
    atomic_json(
        output_dir / JUDGE_COMPARISON_FILE,
        {
            "active_judge_model": active_judge_model,
            "active_judge_endpoint": active_judge_endpoint,
            "cases": cases,
        },
    )


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        json.dump(value, handle, indent=2, ensure_ascii=True, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def atomic_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=True, sort_keys=True) + "\n")
        temporary = Path(handle.name)
    temporary.replace(path)
