from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


def build_summary(results: list[dict[str, Any]], runtime_ms: float) -> dict[str, Any]:
    statuses = Counter(str(row["status"]) for row in results)
    summary = {
        "total_cases": len(results),
        "passed": statuses["passed"],
        "failed": statuses["failed"],
        "errors": statuses["error"],
        "not_executed": statuses["not_executed"],
        "overall_pass_rate": rate(statuses["passed"], len(results)),
        "category_pass_rate": grouped_rates(results, "category"),
        "execution_layer_pass_rate": grouped_rates(results, "execution_layer"),
        "deterministic_pass_rate": subset_rate(
            results,
            lambda row: bool(row["deterministic"]),
        ),
        "browser_e2e_pass_rate": subset_rate(
            results,
            lambda row: row["execution_layer"] == "browser E2E",
            executed_only=True,
        ),
        "llm_dependent_pass_rate": subset_rate(
            results,
            lambda row: not bool(row["deterministic"]),
            executed_only=True,
        ),
        "scope_isolation_pass_rate": tagged_rate(results, "scope_isolation"),
        "idempotency_pass_rate": tagged_rate(results, "idempotency"),
        "no_collateral_damage_rate": tagged_rate(results, "no_collateral_damage"),
        "runtime_ms": round(runtime_ms, 3),
        "case_runtime_ms": distribution(
            [float(row.get("duration_ms", 0.0)) for row in results]
        ),
        "llm_reliability": {"pass@1": None, "pass^3": None, "cases": 0},
    }
    return summary


def grouped_rates(
    results: list[dict[str, Any]],
    key: str,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[str(row[key])].append(row)
    return {
        name: {
            "passed": sum(row["status"] == "passed" for row in rows),
            "total": len(rows),
            "not_executed": sum(row["status"] == "not_executed" for row in rows),
            "rate": rate(
                sum(row["status"] == "passed" for row in rows),
                len(rows),
            ),
        }
        for name, rows in sorted(grouped.items())
    }


def subset_rate(
    results: list[dict[str, Any]],
    predicate,  # type: ignore[no-untyped-def]
    *,
    executed_only: bool = False,
) -> dict[str, Any]:
    rows = [row for row in results if predicate(row)]
    executed = [row for row in rows if row["status"] != "not_executed"]
    denominator = len(executed) if executed_only else len(rows)
    return {
        "passed": sum(row["status"] == "passed" for row in executed),
        "total": len(rows),
        "executed": len(executed),
        "rate": rate(
            sum(row["status"] == "passed" for row in executed),
            denominator,
        ),
    }


def tagged_rate(results: list[dict[str, Any]], tag: str) -> dict[str, Any]:
    return subset_rate(results, lambda row: tag in row.get("tags", []))


def rate(passed: int, total: int) -> float | None:
    return round(passed / total, 4) if total else None


def distribution(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "p95": None}
    ordered = sorted(values)
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "mean": round(mean(ordered), 3),
        "p95": round(ordered[p95_index], 3),
    }


def render_markdown(
    summary: dict[str, Any],
    results: list[dict[str, Any]],
    *,
    run_id: str,
) -> str:
    lines = [
        "# Product Behavior Benchmark Baseline",
        "",
        f"- Run ID: `{run_id}`",
        f"- Cases: **{summary['total_cases']}**",
        f"- Passed: **{summary['passed']}**",
        f"- Failed: **{summary['failed']}**",
        f"- Errors: **{summary['errors']}**",
        f"- Browser not executed: **{summary['not_executed']}**",
        f"- Overall pass rate: **{percent(summary['overall_pass_rate'])}**",
        f"- Runtime: **{summary['runtime_ms']} ms**",
        "",
        "## Category results",
        "",
        "| Category | Passed | Total | Not executed | Rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for category, value in summary["category_pass_rate"].items():
        lines.append(
            f"| {category} | {value['passed']} | {value['total']} | "
            f"{value['not_executed']} | {percent(value['rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Reliability metrics",
            "",
            f"- Deterministic: {metric(summary['deterministic_pass_rate'])}",
            f"- Browser E2E: {metric(summary['browser_e2e_pass_rate'])}",
            f"- LLM-dependent: {metric(summary['llm_dependent_pass_rate'])}",
            f"- Scope isolation: {metric(summary['scope_isolation_pass_rate'])}",
            f"- Idempotency: {metric(summary['idempotency_pass_rate'])}",
            f"- No collateral damage: {metric(summary['no_collateral_damage_rate'])}",
            "- LLM pass@1 / pass^3: not applicable; this baseline made no model calls.",
            "",
            "## Failed cases by root cause",
            "",
        ]
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        if row["status"] == "passed":
            continue
        grouped[str(row.get("root_cause") or row["status"])].append(row)
    for cause, rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        lines.append(f"### {cause}")
        lines.append("")
        for row in rows:
            lines.append(
                f"- `{row['case_id']}` ({row['status']}): "
                f"{json.dumps(row['actual_result'], ensure_ascii=False, sort_keys=True)}"
            )
        lines.append("")
    lines.extend(
        [
            "## Untestable gaps",
            "",
            "- The eight browser scenarios are implemented as explicit E2E cases but were "
            "not executed because no browser harness was available.",
            "- No real-model scenarios were included in this baseline, so pass@1 and "
            "pass^3 are not applicable.",
            "- Cross-user isolation cannot be exercised because the product exposes one "
            "fixed local user and stores no chat owner.",
            "- Document readiness, association, ambiguity, and scoped retrieval cannot be "
            "fully exercised because the authoritative Chroma path has no product document "
            "registry.",
            "- Send/End and Upload/Send race invariants lack a shared production concurrency "
            "seam; these remain capability failures rather than simulated passes.",
            "",
            "## Recommended next fix order",
            "",
            "1. Add ownership and scope enforcement where data leakage is possible.",
            "2. Define atomic Send/End behavior and per-chat lifecycle concurrency.",
            "3. Add a document lifecycle registry with Ready/Failed status and chat association.",
            "4. Pass explicit allowed document IDs into retrieval.",
            "5. Add filename, pronoun, latest-document, and ambiguity resolution.",
            "6. Add typed retrieval/answer failure states and retry idempotency.",
            "7. Execute the frozen browser suite and address visual polish last.",
            "",
            "## Case inventory",
            "",
            "| Case | Category | Layer | Status |",
            "|---|---|---|---|",
        ]
    )
    for row in results:
        lines.append(
            f"| `{row['case_id']}` | {row['category']} | "
            f"{row['execution_layer']} | {row['status']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Browser cases are not treated as passing when browser execution is unavailable.",
            "- Unsupported product capabilities remain failed rather than weakening expectations.",
            "- This run used deterministic repository/service and Chainlit data-layer probes only.",
            "- No production behavior, MAB, LongMemEval, or model configuration was changed.",
        ]
    )
    return "\n".join(lines) + "\n"


def metric(value: dict[str, Any]) -> str:
    return (
        f"{value['passed']}/{value['total']} "
        f"(executed {value['executed']}, rate {percent(value['rate'])})"
    )


def percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def write_reports(
    output_dir: Path,
    *,
    results: list[dict[str, Any]],
    runtime_ms: float,
    run_id: str,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = build_summary(results, runtime_ms)
    write_json(output_dir / "summary.json", summary)
    (output_dir / "report.md").write_text(
        render_markdown(summary, results, run_id=run_id),
        encoding="utf-8",
    )
    write_jsonl(
        output_dir / "failures.jsonl",
        [row for row in results if row["status"] != "passed"],
    )
    return summary


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
            for value in values
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate product benchmark reports.")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--runtime-ms", type=float, default=0.0)
    args = parser.parse_args()
    results = [
        json.loads(line)
        for line in args.results.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    summary = write_reports(
        args.output_dir,
        results=results,
        runtime_ms=args.runtime_ms,
        run_id=args.run_id,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
