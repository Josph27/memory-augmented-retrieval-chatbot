from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.memory_agent_bench.adapter import ChatModel, run_example
from evals.memory_agent_bench.raw_replay import ReplayEmbeddingBackend
from evals.memory_agent_bench.schemas import MABenchExample
from src.orchestration.demo_orchestration import NATIVE
from src.retrieval.cross_encoder_reranker import CrossEncoderBackend


def run_benchmark(
    examples: list[MABenchExample],
    *,
    answer_mode: str = "mock",
    model: ChatModel | None = None,
    finalize_sessions: bool = True,
    raw_replay_enabled: bool = False,
    raw_replay_top_k: int = 8,
    raw_replay_max_chars: int = 4000,
    raw_replay_retrieval_mode: str = "lexical",
    raw_replay_embedding_backend: ReplayEmbeddingBackend | None = None,
    raw_replay_candidate_pool_size: int = 50,
    reranker_mode: str = "deterministic",
    cross_encoder_backend: CrossEncoderBackend | None = None,
    cross_encoder_top_k: int = 10,
    cross_encoder_weight: float = 0.65,
    dataset_selection: dict[str, Any] | None = None,
    orchestration_mode: str = NATIVE,
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
            raw_replay_enabled=raw_replay_enabled,
            raw_replay_top_k=raw_replay_top_k,
            raw_replay_max_chars=raw_replay_max_chars,
            raw_replay_retrieval_mode=raw_replay_retrieval_mode,
            raw_replay_embedding_backend=raw_replay_embedding_backend,
            raw_replay_candidate_pool_size=raw_replay_candidate_pool_size,
            reranker_mode=reranker_mode,
            cross_encoder_backend=cross_encoder_backend,
            cross_encoder_top_k=cross_encoder_top_k,
            cross_encoder_weight=cross_encoder_weight,
            orchestration_mode=orchestration_mode,
        )
    ]
    return {
        "eval_name": "memory_agent_bench_adapter",
        "benchmark_name": "MemoryAgentBench",
        "answer_mode": answer_mode,
        "official_scoring": False,
        "raw_replay_enabled": raw_replay_enabled,
        "raw_replay_retrieval_mode": raw_replay_retrieval_mode,
        "raw_replay_candidate_pool_size": raw_replay_candidate_pool_size,
        "reranker_mode": reranker_mode,
        "orchestration_mode": orchestration_mode,
        "dataset_selection": dataset_selection or {},
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
        "raw_replay_enabled": bool(rows) and any(
            row["raw_replay_diagnostics"]["raw_replay_enabled"]
            for row in rows
        ),
        "raw_replay_gold_literal_rate": rate(
            row["raw_replay_diagnostics"]["raw_replay_gold_literal_found"]
            for row in rows
        ),
        "raw_replay_gold_message_rate": rate(
            row["raw_replay_diagnostics"]["raw_replay_gold_message_found"]
            for row in rows
        ),
        "raw_replay_context_reach_rate": rate(
            row["raw_replay_diagnostics"]["raw_replay_reached_context"]
            for row in rows
        ),
        "raw_replay_gold_context_rate": rate(
            row["raw_replay_diagnostics"][
                "raw_replay_gold_literal_reached_context"
            ]
            for row in rows
        ),
        "total_questions": total,
    }


def write_jsonl_report(path: Path, report: dict[str, Any]) -> None:
    """Write one summary row followed by one row per benchmark question."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "report_summary": report["summary"],
                    "dataset_selection": report.get("dataset_selection", {}),
                }
            )
            + "\n"
        )
        for row in report["results"]:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def rate(values) -> float | None:  # type: ignore[no-untyped-def]
    items = list(values)
    return sum(bool(value) for value in items) / len(items) if items else None
