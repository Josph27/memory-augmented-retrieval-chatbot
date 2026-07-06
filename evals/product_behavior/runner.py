from __future__ import annotations

import argparse
import json
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

from evals.product_behavior.loader import load_cases
from evals.product_behavior.models import (
    OracleObservation,
    ProductBehaviorResult,
)
from evals.product_behavior.oracle import evaluate_case
from evals.product_behavior.report import write_json, write_jsonl, write_reports


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASE_DIR = Path(__file__).resolve().parent / "cases"


def run_cases(
    *,
    case_dir: Path = DEFAULT_CASE_DIR,
    categories: set[str] | None = None,
    layers: set[str] | None = None,
) -> tuple[list[dict], float]:
    cases = load_cases(case_dir)
    selected = [
        case
        for case in cases
        if (not categories or case.category in categories)
        and (not layers or case.execution_layer in layers)
    ]
    run_started = time.perf_counter()
    results: list[dict] = []
    for case in selected:
        started = time.perf_counter()
        try:
            observation = evaluate_case(case, ROOT)
        except Exception as error:
            observation = OracleObservation(
                status="error",
                actual={},
                root_cause="Benchmark oracle raised unexpectedly.",
                error=(
                    f"{type(error).__name__}: {error}\n"
                    f"{traceback.format_exc(limit=8)}"
                )[:4000],
            )
        result = ProductBehaviorResult(
            case=case,
            observation=observation,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        results.append(result.to_dict())
    runtime_ms = (time.perf_counter() - run_started) * 1000
    return results, runtime_ms


def main() -> None:
    parser = argparse.ArgumentParser(description="Run product behavior benchmark.")
    parser.add_argument("--case-dir", type=Path, default=DEFAULT_CASE_DIR)
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/product_behavior")
    parser.add_argument("--run-id")
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--layer", action="append", default=[])
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    cases = load_cases(args.case_dir)
    if args.list:
        print(
            json.dumps(
                [
                    {
                        "id": case.id,
                        "category": case.category,
                        "execution_layer": case.execution_layer,
                    }
                    for case in cases
                ],
                indent=2,
            )
        )
        return

    run_id = args.run_id or datetime.now(UTC).strftime("product_behavior_%Y%m%dT%H%M%SZ")
    output_dir = args.output_root / run_id
    if output_dir.exists() and any(output_dir.iterdir()):
        parser.error(f"refusing to overwrite non-empty output directory: {output_dir}")
    results, runtime_ms = run_cases(
        case_dir=args.case_dir,
        categories=set(args.category),
        layers=set(args.layer),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "results.jsonl", results)
    summary = write_reports(
        output_dir,
        results=results,
        runtime_ms=runtime_ms,
        run_id=run_id,
    )
    metadata = {
        "run_id": run_id,
        "case_definition_count": len(cases),
        "executed_result_count": len(results),
        "categories": sorted(set(args.category)),
        "layers": sorted(set(args.layer)),
        "production_changes": False,
        "model_calls": 0,
        "judge_calls": 0,
        "runtime_ms": round(runtime_ms, 3),
    }
    write_json(output_dir / "run_metadata.json", metadata)
    print(json.dumps({"output_dir": str(output_dir), **summary}, indent=2))


if __name__ == "__main__":
    main()

