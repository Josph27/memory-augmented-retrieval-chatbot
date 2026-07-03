from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evals.mab_answer_eval.artifacts import (
    RESULTS_FILE,
    atomic_json,
    atomic_jsonl,
    distribution,
    latest_results,
    read_jsonl,
)


ABSTENTION_PATTERN = re.compile(
    r"\b(i don't know|i do not know|cannot determine|insufficient information|"
    r"not enough information|unable to answer)\b",
    flags=re.IGNORECASE,
)


def load_results(output_dirs: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for output_dir in output_dirs:
        rows.extend(latest_results(read_jsonl(output_dir / RESULTS_FILE)))
    return rows


def classify(row: dict[str, Any]) -> dict[str, Any]:
    status = row.get("status")
    context = row.get("context_diagnostics") or {}
    gold_candidate = bool(context.get("gold_candidate_present"))
    gold_context = bool(context.get("gold_context_present"))
    evidence_contract = bool(context.get("evidence_contract_satisfied", True))
    judge_correct = bool((row.get("judge") or {}).get("correct"))
    if status != "completed":
        primary = "pipeline_failure"
        stage = str(row.get("failed_stage") or "unknown")
    elif judge_correct:
        primary = (
            "grounded_pipeline_success"
            if gold_context
            else "correct_without_gold_context"
        )
        stage = "success"
    elif not gold_candidate:
        primary = "retrieval_failure"
        stage = "retrieval"
    elif not gold_context:
        primary = "context_selection_failure"
        stage = "context_selection"
    else:
        primary = "answer_generation_failure"
        stage = "answer_generation"
    disagreement = None
    if status == "completed":
        official_pass = bool((row.get("official_metric") or {}).get("passed"))
        if official_pass != judge_correct:
            metric_name = str((row.get("official_metric") or {}).get("name") or "")
            if official_pass and metric_name == "normalized_substring":
                disagreement = "substring false positive"
            elif not official_pass and metric_name == "normalized_exact_match":
                disagreement = "exact-match formatting false negative"
            else:
                disagreement = "requires human review"
    abstains = ABSTENTION_PATTERN.search(str(row.get("generated_answer") or "")) is not None
    return {
        "primary_category": primary,
        "first_failure_stage": stage,
        "evidence_contract_failure": not evidence_contract,
        "official_judge_disagreement": disagreement,
        "abstains": abstains,
        "drop_reason": context.get("gold_context_drop_reason") or "unknown",
    }


def compact_failure(row: dict[str, Any], diagnosis: dict[str, Any]) -> dict[str, Any]:
    context = row.get("context_diagnostics") or {}
    return {
        "dataset": row.get("dataset"),
        "case_id": row.get("case_id"),
        "question": row.get("question"),
        "reference_answer": row.get("reference_answer"),
        "generated_answer": row.get("generated_answer"),
        "official_metric": row.get("official_metric"),
        "judge": row.get("judge"),
        "question_type": row.get("question_type"),
        "enabled_sources": context.get("enabled_sources", []),
        "required_scopes": context.get("required_scopes", []),
        "gold_candidate_present": context.get("gold_candidate_present"),
        "gold_candidate_rank": context.get("gold_candidate_rank"),
        "gold_context_present": context.get("gold_context_present"),
        "selected_source_types": context.get("selected_source_types", []),
        "selected_memory_tokens": context.get("selected_memory_tokens"),
        "working_memory_budget": context.get("working_memory_budget"),
        "final_prompt_tokens": context.get("final_prompt_tokens"),
        "first_failure_stage": diagnosis["first_failure_stage"],
        "primary_category": diagnosis["primary_category"],
        "drop_reason": diagnosis["drop_reason"],
        "evidence_contract_failure": diagnosis["evidence_contract_failure"],
        "brief_judge_reason": (row.get("judge") or {}).get("brief_reason"),
    }


def human_review_items(rows: list[dict[str, Any]], diagnoses: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    shortlist: list[dict[str, Any]] = []
    successful_grounded = [
        row for row in rows
        if diagnoses[row["result_identity"]]["primary_category"] == "grounded_pipeline_success"
    ]
    successful_grounded = sorted(
        successful_grounded,
        key=lambda row: (str(row.get("dataset")), str(row.get("case_id"))),
    )[:5]
    for row in rows:
        diagnosis = diagnoses[row["result_identity"]]
        context = row.get("context_diagnostics") or {}
        include = (
            diagnosis["official_judge_disagreement"] is not None
            or (
                diagnosis["primary_category"] == "answer_generation_failure"
                and bool(context.get("gold_context_present"))
            )
            or diagnosis["evidence_contract_failure"]
            or diagnosis["primary_category"] == "correct_without_gold_context"
            or row in successful_grounded
        )
        if not include:
            continue
        shortlist.append(
            {
                "dataset": row.get("dataset"),
                "case_id": row.get("case_id"),
                "question": row.get("question"),
                "reference_answer": row.get("reference_answer"),
                "generated_answer": row.get("generated_answer"),
                "official_result": row.get("official_metric"),
                "deepseek_result": row.get("judge"),
                "brief_judge_reason": (row.get("judge") or {}).get("brief_reason"),
                "gold_candidate_present": context.get("gold_candidate_present"),
                "gold_context_present": context.get("gold_context_present"),
                "selected_source_types": context.get("selected_source_types", []),
                "first_failure_stage": diagnosis["first_failure_stage"],
            }
        )
    return shortlist


def summarize(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    diagnoses = {
        str(row.get("result_identity")): classify(row)
        for row in rows
        if row.get("result_identity")
    }
    completed = [row for row in rows if row.get("status") == "completed"]
    failures = [row for row in rows if row.get("status") != "completed"]
    grouped_dataset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped_question_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stage_counts = Counter()
    category_counts = Counter()
    evidence_contract_failures = 0
    official_disagreements = 0
    abstention_totals = Counter()
    for row in rows:
        dataset = str(row.get("dataset") or "unknown")
        question_type = str(row.get("question_type") or "unknown")
        grouped_dataset[dataset].append(row)
        grouped_question_type[question_type].append(row)
        diagnosis = diagnoses.get(str(row.get("result_identity")), {})
        stage_counts.update([diagnosis.get("first_failure_stage", "unknown")])
        category_counts.update([diagnosis.get("primary_category", "unknown")])
        evidence_contract_failures += int(
            diagnosis.get("evidence_contract_failure", False)
        )
        official_disagreements += int(
            diagnosis.get("official_judge_disagreement") is not None
        )
        if diagnosis.get("abstains"):
            abstention_totals["total"] += 1
            context = row.get("context_diagnostics") or {}
            if bool((row.get("judge") or {}).get("correct")):
                abstention_totals["correct"] += 1
            else:
                abstention_totals["incorrect"] += 1
                if context.get("gold_context_present"):
                    abstention_totals["incorrect_gold_context_present"] += 1
                elif context.get("gold_candidate_present"):
                    abstention_totals["incorrect_gold_candidate_present"] += 1
                elif diagnosis.get("evidence_contract_failure"):
                    abstention_totals["incorrect_evidence_contract_failure"] += 1
                else:
                    abstention_totals["incorrect_gold_candidate_absent"] += 1

    def dataset_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
        completed_items = [row for row in items if row.get("status") == "completed"]
        return {
            "cases": len(items),
            "official_pass_rate": rate(
                [bool((row.get("official_metric") or {}).get("passed")) for row in completed_items]
            ),
            "deepseek_correctness_rate": rate(
                [bool((row.get("judge") or {}).get("correct")) for row in completed_items]
            ),
            "deepseek_completeness_rate": rate(
                [bool((row.get("judge") or {}).get("complete")) for row in completed_items]
            ),
            "agreement_rate": rate(
                [
                    bool((row.get("official_metric") or {}).get("passed"))
                    == bool((row.get("judge") or {}).get("correct"))
                    for row in completed_items
                ]
            ),
        }

    summary = {
        "total_cases": len(rows),
        "completed_cases": len(completed),
        "generation_failures": sum(row.get("failed_stage") == "generation" for row in failures),
        "judge_failures": sum(row.get("failed_stage") == "judge" for row in failures),
        "official_pass_rate": rate(
            [bool((row.get("official_metric") or {}).get("passed")) for row in completed]
        ),
        "deepseek_correctness_rate": rate(
            [bool((row.get("judge") or {}).get("correct")) for row in completed]
        ),
        "deepseek_completeness_rate": rate(
            [bool((row.get("judge") or {}).get("complete")) for row in completed]
        ),
        "official_deepseek_agreement_rate": rate(
            [
                bool((row.get("official_metric") or {}).get("passed"))
                == bool((row.get("judge") or {}).get("correct"))
                for row in completed
            ]
        ),
        "results_by_dataset": {
            key: dataset_summary(value) for key, value in sorted(grouped_dataset.items())
        },
        "results_by_question_type": {
            key: dataset_summary(value)
            for key, value in sorted(grouped_question_type.items())
        },
        "failure_stage_distribution": dict(sorted(stage_counts.items())),
        "category_distribution": dict(sorted(category_counts.items())),
        "evidence_contract_failures": evidence_contract_failures,
        "official_deepseek_disagreements": official_disagreements,
        "abstentions": dict(sorted(abstention_totals.items())),
        "answer_latency_ms": distribution(
            [float((row.get("latency_ms") or {}).get("generation", 0.0)) for row in completed]
        ),
        "judge_latency_ms": distribution(
            [float((row.get("latency_ms") or {}).get("judge", 0.0)) for row in completed]
        ),
        "selected_memory_tokens": distribution(
            [
                float((row.get("context_diagnostics") or {}).get("selected_memory_tokens", 0.0))
                for row in completed
            ]
        ),
        "final_prompt_tokens": distribution(
            [
                float((row.get("context_diagnostics") or {}).get("final_prompt_tokens", 0.0))
                for row in completed
            ]
        ),
    }
    return summary, diagnoses


def rate(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze held-out answer-eval runs.")
    parser.add_argument("--input-dir", action="append", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows = load_results(args.input_dir)
    summary, diagnoses = summarize(rows)

    completed = [row for row in rows if row.get("status") == "completed"]
    failed_cases = [
        compact_failure(row, diagnoses[str(row.get("result_identity"))])
        for row in rows
        if diagnoses.get(str(row.get("result_identity")), {}).get("primary_category")
        in {"retrieval_failure", "context_selection_failure", "answer_generation_failure", "pipeline_failure"}
    ]
    disagreements = [
        {
            **compact_failure(row, diagnoses[str(row.get("result_identity"))]),
            "disagreement": diagnoses[str(row.get("result_identity"))][
                "official_judge_disagreement"
            ],
        }
        for row in completed
        if diagnoses[str(row.get("result_identity"))]["official_judge_disagreement"] is not None
    ]
    answer_use = [
        compact_failure(row, diagnoses[str(row.get("result_identity"))])
        for row in completed
        if diagnoses[str(row.get("result_identity"))]["primary_category"]
        == "answer_generation_failure"
    ]
    retrieval = [
        compact_failure(row, diagnoses[str(row.get("result_identity"))])
        for row in completed
        if diagnoses[str(row.get("result_identity"))]["primary_category"]
        == "retrieval_failure"
    ]
    context_selection = [
        compact_failure(row, diagnoses[str(row.get("result_identity"))])
        for row in completed
        if diagnoses[str(row.get("result_identity"))]["primary_category"]
        == "context_selection_failure"
    ]
    abstention_failures = [
        compact_failure(row, diagnoses[str(row.get("result_identity"))])
        for row in completed
        if diagnoses[str(row.get("result_identity"))]["abstains"]
        and not bool((row.get("judge") or {}).get("correct"))
    ]
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_jsonl(output_dir / RESULTS_FILE, rows)
    atomic_json(output_dir / "summary.json", summary)
    atomic_jsonl(output_dir / "failures.jsonl", failed_cases)
    atomic_jsonl(output_dir / "disagreements.jsonl", disagreements)
    atomic_jsonl(output_dir / "answer_use_failures.jsonl", answer_use)
    atomic_jsonl(output_dir / "retrieval_failures.jsonl", retrieval)
    atomic_jsonl(output_dir / "context_selection_failures.jsonl", context_selection)
    atomic_jsonl(output_dir / "abstention_failures.jsonl", abstention_failures)
    atomic_jsonl(output_dir / "human_review_shortlist.jsonl", human_review_items(rows, diagnoses))
    atomic_json(
        output_dir / "run_metadata.json",
        {
            "input_dirs": [str(path) for path in args.input_dir],
            "completed_cases": len(completed),
        },
    )
    print(json.dumps(summary, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
