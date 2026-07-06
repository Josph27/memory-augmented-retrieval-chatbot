#!/usr/bin/env python3
"""Validate a completed final answer-only run without loading datasets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


class AnswerRunValidationError(ValueError):
    """A concise validation failure suitable for shell wrappers."""


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise AnswerRunValidationError(f"missing required results file: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AnswerRunValidationError(
                f"invalid JSON at {path}:{line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise AnswerRunValidationError(
                f"expected object at {path}:{line_number}"
            )
        rows.append(value)
    return rows


def expected_case_ids(path: Path) -> list[str]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return [str(case["case_id"]) for case in value["cases"]]


def latest_answers(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = str(row.get("case_id", ""))
        if (
            case_id
            and row.get("generated_answer") is not None
            and row.get("status") in {"answer_completed", "completed"}
        ):
            latest[case_id] = row
    return latest


def validate(root: Path, answer_run_dir: Path) -> dict[str, Any]:
    status_path = answer_run_dir / "meta" / "status.env"
    if not status_path.is_file():
        raise AnswerRunValidationError(
            f"missing answer-run status: {status_path}"
        )
    status = status_path.read_text(encoding="utf-8")
    if "EXIT_STATUS=0" not in status or "FINAL_MARKER=RUN_COMPLETED" not in status:
        raise AnswerRunValidationError(
            f"answer run is not complete: {answer_run_dir}"
        )

    specifications = (
        (
            "mab",
            root / "evals/manifests/mab_answer_heldout_v1.yaml",
            answer_run_dir / "mab/results.jsonl",
        ),
        (
            "longmemeval",
            root / "evals/manifests/longmemeval_answer_heldout_v1.yaml",
            answer_run_dir / "longmemeval/results.jsonl",
        ),
    )
    result: dict[str, Any] = {"ok": True, "answer_run_dir": str(answer_run_dir)}
    models: set[str] = set()
    for name, manifest_path, results_path in specifications:
        expected = expected_case_ids(manifest_path)
        latest = latest_answers(read_jsonl(results_path))
        missing = [case_id for case_id in expected if case_id not in latest]
        if missing:
            raise AnswerRunValidationError(
                f"incomplete {name} answers; missing: {missing}"
            )
        unexpected = sorted(set(latest) - set(expected))
        if unexpected:
            raise AnswerRunValidationError(
                f"unexpected {name} cases: {unexpected}"
            )
        models.update(str(latest[case_id].get("answer_model")) for case_id in expected)
        result[f"{name}_answer_count"] = len(expected)

    if len(models) != 1:
        raise AnswerRunValidationError(
            f"answer model mismatch: {sorted(models)}"
        )
    result["answer_model"] = next(iter(models))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answer-run-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    answer_run_dir = args.answer_run_dir.expanduser().resolve()
    try:
        result = validate(root, answer_run_dir)
    except (AnswerRunValidationError, OSError) as exc:
        print(f"answer-run validation failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
