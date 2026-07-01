from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.memory_agent_bench.adapter import ChatModel, run_example
from evals.memory_agent_bench.schemas import MABenchExample


def run_benchmark(
    examples: list[MABenchExample],
    *,
    answer_mode: str = "mock",
    model: ChatModel | None = None,
    finalize_sessions: bool = True,
) -> dict[str, Any]:
    """Run examples and return an honest adapter report."""
    if answer_mode not in {"mock", "model"}:
        raise ValueError("answer_mode must be 'mock' or 'model'")
    if answer_mode == "model" and model is None:
        raise ValueError("model answer mode requires an explicit configured model")
    rows = [
        row
        for example in examples
        for row in run_example(
            example,
            mock_answer=answer_mode == "mock",
            model=model,
            finalize_sessions=finalize_sessions,
        )
    ]
    return {
        "eval_name": "memory_agent_bench_adapter",
        "benchmark_name": "MemoryAgentBench",
        "answer_mode": answer_mode,
        "official_scoring": False,
        "total_examples": len(examples),
        "total_questions": len(rows),
        "summary": summarize(rows),
        "results": rows,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate deterministic adapter diagnostics."""
    total = len(rows)
    return {
        "normalized_substring_match_rate": rate(
            row["answer_metric"]["normalized_substring_match"] for row in rows
        ),
        "evidence_contains_answer_rate": rate(
            row["evidence_metric"]["gold_in_context"] for row in rows
        ),
        "provenance_present_rate": rate(
            row["provenance_present"] for row in rows
        ),
        "generated_answer_grounding_tested": bool(rows) and all(
            row["generated_answer_grounding_tested"] for row in rows
        ),
        "total_questions": total,
    }


def write_jsonl_report(path: Path, report: dict[str, Any]) -> None:
    """Write one summary row followed by one row per benchmark question."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"report_summary": report["summary"]}) + "\n")
        for row in report["results"]:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def rate(values) -> float | None:  # type: ignore[no-untyped-def]
    items = list(values)
    return sum(bool(value) for value in items) / len(items) if items else None
