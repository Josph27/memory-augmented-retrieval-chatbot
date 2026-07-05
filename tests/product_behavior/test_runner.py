from __future__ import annotations

import json
from pathlib import Path

from evals.product_behavior.runner import DEFAULT_CASE_DIR, run_cases
from evals.product_behavior.report import build_summary, write_reports


def test_non_browser_product_oracles_execute_without_harness_errors() -> None:
    results, runtime_ms = run_cases(
        case_dir=DEFAULT_CASE_DIR,
        layers={"repository/service", "Chainlit handler/data-layer"},
    )

    assert len(results) == 42
    assert not [row for row in results if row["status"] == "error"]
    assert runtime_ms >= 0


def test_report_contains_all_reliability_metrics(tmp_path: Path) -> None:
    results, runtime_ms = run_cases(case_dir=DEFAULT_CASE_DIR)
    summary = write_reports(
        tmp_path,
        results=results,
        runtime_ms=runtime_ms,
        run_id="offline-test",
    )

    assert summary["total_cases"] == 50
    assert summary["not_executed"] == 8
    assert "scope_isolation_pass_rate" in summary
    assert "idempotency_pass_rate" in summary
    assert "no_collateral_damage_rate" in summary
    assert (tmp_path / "report.md").exists()
    failures = [
        json.loads(line)
        for line in (tmp_path / "failures.jsonl").read_text().splitlines()
    ]
    assert all("expected_invariant" in row for row in failures)


def test_summary_counts_not_executed_browser_cases_as_not_passed() -> None:
    results, runtime_ms = run_cases(case_dir=DEFAULT_CASE_DIR)
    summary = build_summary(results, runtime_ms)

    assert summary["total_cases"] == 50
    assert summary["browser_e2e_pass_rate"]["total"] == 8
    assert summary["browser_e2e_pass_rate"]["executed"] == 0
    assert summary["browser_e2e_pass_rate"]["rate"] is None

