from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from evals.memory_agent_bench.loader import load_huggingface_examples
from evals.memory_agent_bench.runner import run_benchmark
from evals.memory_agent_bench.schemas import MABenchExample
from src.retrieval.cross_encoder_reranker import CrossEncoderBackend


OFFICIAL_DATASET_ID = "ai-hyz/MemoryAgentBench"
SELECTED_SUITES = ("ruler_qa1", "test_time_learning", "aligned")
MAX_QUESTION_CHARS = 500
MAX_GOLD_ITEMS = 4
MAX_GOLD_CHARS = 160


@dataclass(frozen=True)
class SelectedSuiteComponent:
    split: str
    include_sources: tuple[str, ...] = ()
    default_question_limit: int = 1


SUITE_COMPONENTS = {
    "ruler_qa1": (
        SelectedSuiteComponent(
            split="Accurate_Retrieval",
            include_sources=("ruler_qa1_197K",),
            default_question_limit=20,
        ),
    ),
    "test_time_learning": (
        SelectedSuiteComponent(
            split="Test_Time_Learning",
            default_question_limit=1,
        ),
    ),
    "aligned": (
        SelectedSuiteComponent(
            split="Accurate_Retrieval",
            include_sources=("ruler_qa1_197K",),
            default_question_limit=20,
        ),
        SelectedSuiteComponent(
            split="Test_Time_Learning",
            default_question_limit=1,
        ),
    ),
}


def load_selected_suite(
    suite: str,
    *,
    dataset_id: str = OFFICIAL_DATASET_ID,
    limit: int = 50,
    question_limit: int | None = None,
    context_chunk_chars: int = 4000,
    loader: Callable[..., list[MABenchExample]] = load_huggingface_examples,
) -> tuple[list[MABenchExample], dict[str, Any]]:
    if suite not in SELECTED_SUITES:
        raise ValueError(f"unknown selected suite: {suite}")
    examples: list[MABenchExample] = []
    component_stats: list[dict[str, Any]] = []
    for component in SUITE_COMPONENTS[suite]:
        stats: dict[str, Any] = {}
        loaded = loader(
            dataset_id,
            split=component.split,
            limit=limit,
            question_limit=(
                question_limit
                if question_limit is not None
                else component.default_question_limit
            ),
            context_chunk_chars=context_chunk_chars,
            include_source_datasets=component.include_sources,
            selection_stats=stats,
        )
        examples.extend(loaded)
        component_stats.append(
            {
                "split": component.split,
                "include_sources": list(component.include_sources),
                **stats,
            }
        )
    return examples, {
        "selected_suite": suite,
        "dataset_id": dataset_id,
        "components": component_stats,
        "native_path": True,
        "raw_replay_enabled": False,
        "cross_encoder_enabled": False,
    }


def run_selected_suite(
    suite: str,
    *,
    dataset_id: str = OFFICIAL_DATASET_ID,
    limit: int = 50,
    question_limit: int | None = None,
    context_chunk_chars: int = 4000,
    reranker_mode: str = "deterministic",
    cross_encoder_backend: CrossEncoderBackend | None = None,
    cross_encoder_top_k: int = 10,
    cross_encoder_weight: float = 0.65,
) -> dict[str, Any]:
    started = perf_counter()
    examples, selection = load_selected_suite(
        suite,
        dataset_id=dataset_id,
        limit=limit,
        question_limit=question_limit,
        context_chunk_chars=context_chunk_chars,
    )
    selection["cross_encoder_enabled"] = reranker_mode == "cross_encoder"
    native_report = run_benchmark(
        examples,
        answer_mode="mock",
        raw_replay_enabled=False,
        reranker_mode=reranker_mode,
        cross_encoder_backend=cross_encoder_backend,
        cross_encoder_top_k=cross_encoder_top_k,
        cross_encoder_weight=cross_encoder_weight,
        dataset_selection=selection,
    )
    report = selected_report(suite, native_report)
    report["reranker_mode"] = reranker_mode
    report["cross_encoder_enabled"] = reranker_mode == "cross_encoder"
    report["runtime_seconds"] = round(perf_counter() - started, 3)
    return report


def selected_report(suite: str, native_report: dict[str, Any]) -> dict[str, Any]:
    rows = [
        selected_case_row(suite, row)
        for row in native_report.get("results", [])
    ]
    failure_reasons = Counter(
        row["failure_reason"]
        for row in rows
        if row["failure_reason"] != "none_literal_gold_reached_context"
    )
    sources = sorted({source for row in rows for source in row["sources_observed"]})
    return {
        "selected_suite": suite,
        "answer_mode": "mock",
        "native_path": True,
        "raw_replay_enabled": False,
        "num_cases": len(rows),
        "completed": sum(row["completed"] for row in rows),
        "pipeline_error_count": sum(bool(row["error"]) for row in rows),
        "gold_candidates_count": sum(row["gold_in_candidates"] for row in rows),
        "gold_context_count": sum(row["gold_in_context"] for row in rows),
        "provenance_count": sum(row["provenance_present"] for row in rows),
        "sources_observed": sources,
        "failure_reasons": dict(sorted(failure_reasons.items())),
        "dataset_selection": native_report.get("dataset_selection", {}),
        "results": rows,
    }


def selected_case_row(suite: str, row: dict[str, Any]) -> dict[str, Any]:
    diagnostics = row.get("evidence_diagnostics", {})
    errors = row.get("workflow_trace", {}).get("errors", [])
    gold_answers = row.get("gold_answers", [])
    return {
        "selected_suite": suite,
        "split": row.get("competency"),
        "source": row.get("source_dataset"),
        "row_index": row.get("row_index"),
        "question_index": row.get("question_index"),
        "question": str(row.get("question", ""))[:MAX_QUESTION_CHARS],
        "completed": not errors,
        "error": "; ".join(map(str, errors))[:300] if errors else None,
        "gold_answer_summary": [
            str(answer)[:MAX_GOLD_CHARS]
            for answer in gold_answers[:MAX_GOLD_ITEMS]
        ],
        "gold_in_candidates": bool(
            diagnostics.get("retrieved_candidate_ids_with_gold_text")
        ),
        "gold_in_context": bool(
            diagnostics.get("context_candidate_ids_with_gold_text")
        ),
        "sources_observed": list(row.get("sources", [])),
        "provenance_present": bool(row.get("provenance_present")),
        "context_char_size": int(row.get("context_char_size", 0)),
        "failure_reason": diagnostics.get("failure_stage", "unknown"),
        "notes": list(row.get("notes", []))[:3],
    }


def write_selected_jsonl(path: Path, report: dict[str, Any]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {key: value for key, value in report.items() if key != "results"}
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"selected_suite_summary": summary}) + "\n")
        for row in report["results"]:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
