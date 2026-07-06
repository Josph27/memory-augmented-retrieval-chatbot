#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/load_eval_env.sh
source "${SCRIPT_DIR}/lib/load_eval_env.sh"
# shellcheck source=final_eval_paths.sh
source "${SCRIPT_DIR}/final_eval_paths.sh"
ROOT="$(eval_repo_root)"
cd "$ROOT"

load_eval_env

export PYTHONUNBUFFERED=1

RUN_NAME="final_52_lifecycle_v2"
STATE_FILE="$ROOT/artifacts/eval_runs/${RUN_NAME}_current_path.txt"
RUN_MARKER=".final_52_answer_run"
CHECK_ONLY=false
EXPLICIT_RESUME_DIR=""
RUN_PATH_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      CHECK_ONLY=true
      shift
      ;;
    --run-dir)
      if [[ $# -lt 2 ]]; then
        echo "missing value for --run-dir" >&2
        exit 2
      fi
      EXPLICIT_RESUME_DIR="$2"
      shift 2
      ;;
    --path-file)
      if [[ $# -lt 2 ]]; then
        echo "missing value for --path-file" >&2
        exit 2
      fi
      RUN_PATH_FILE="$2"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      echo "usage: $0 [--check] [--run-dir INCOMPLETE_RUN_DIR] [--path-file FILE]" >&2
      exit 2
      ;;
  esac
done

if [[ "$CHECK_ONLY" == true ]]; then
  if [[ -n "$EXPLICIT_RESUME_DIR" || -n "$RUN_PATH_FILE" ]]; then
    echo "--check cannot be combined with run arguments" >&2
    exit 2
  fi
  export HF_HUB_OFFLINE=1
  export HF_DATASETS_OFFLINE=1
  export TRANSFORMERS_OFFLINE=1
  echo "Repository root: $ROOT"
  print_env_presence OPENAI_API_KEY OPENAI_BASE_URL MODEL_NAME
  require_env_vars OPENAI_API_KEY OPENAI_BASE_URL MODEL_NAME
  require_path_exists "$ROOT/evals/manifests/mab_answer_heldout_v1.yaml" "MAB manifest"
  require_path_exists "$ROOT/evals/manifests/longmemeval_answer_heldout_v1.yaml" "LongMemEval manifest"
  require_dir_writable "$ROOT/artifacts/eval_runs"
  verify_repo_imports
  echo "CONFIG_CHECK_OK"
  exit 0
fi

enable_eval_online_mode

if [[ -n "$EXPLICIT_RESUME_DIR" ]]; then
  RUN_DIR="$(cd -- "$(dirname -- "$EXPLICIT_RESUME_DIR")" && pwd)/$(basename -- "$EXPLICIT_RESUME_DIR")"
  final_eval_require_incomplete_answer_run "$RUN_DIR" "$RUN_MARKER"
else
  RUN_DIR="$(final_eval_new_run_dir "$ROOT/artifacts/eval_runs" "$RUN_NAME")"
  final_eval_create_fresh_dir "$RUN_DIR" "$RUN_MARKER"
  printf '%s\n' "$RUN_DIR" > "$STATE_FILE"
fi
if [[ -n "$RUN_PATH_FILE" ]]; then
  mkdir -p "$(dirname -- "$RUN_PATH_FILE")"
  printf '%s\n' "$RUN_DIR" > "$RUN_PATH_FILE"
fi

mkdir -p "$RUN_DIR"/{logs,meta,mab,longmemeval}

LOG_FILE="$RUN_DIR/logs/run_final_52.log"
STATUS_FILE="$RUN_DIR/meta/status.env"
COMMANDS_FILE="$RUN_DIR/meta/commands.txt"
ARTIFACT_PATHS_FILE="$RUN_DIR/meta/artifact_paths.txt"
CONFIG_FILE="$RUN_DIR/meta/config.env"
GIT_STATUS_FILE="$RUN_DIR/meta/git_status_short.txt"
RUN_WRAPPER="$RUN_DIR/meta/answer_only_runner.py"

exec > >(tee -a "$LOG_FILE") 2>&1

START_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
COMMIT="$(git rev-parse HEAD)"
RUN_EXIT_STATUS=1
FAILED_PHASE="initialization"
SUBPROCESS_EXIT_CODE=""
FAILURE_REASON="answer wrapper did not complete"

cleanup() {
  local exit_code="$RUN_EXIT_STATUS"
  local finish_ts
  finish_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local marker="RUN_FAILED"
  if [[ $exit_code -eq 0 ]]; then
    marker="RUN_COMPLETED"
  fi

  {
    printf 'START_TS=%q\n' "$START_TS"
    printf 'FINISH_TS=%q\n' "$finish_ts"
    printf 'EXIT_STATUS=%q\n' "$exit_code"
    printf 'RUN_DIR=%q\n' "$RUN_DIR"
    printf 'BRANCH=%q\n' "$BRANCH"
    printf 'COMMIT=%q\n' "$COMMIT"
    printf 'FAILED_PHASE=%q\n' "$FAILED_PHASE"
    printf 'SUBPROCESS_EXIT_CODE=%q\n' "$SUBPROCESS_EXIT_CODE"
    printf 'FAILURE_REASON=%q\n' "$FAILURE_REASON"
    printf 'FINAL_MARKER=%q\n' "$marker"
  } > "$STATUS_FILE"

  find "$RUN_DIR" -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.csv' -o -name '*.log' -o -name '*.txt' \) | sort > "$ARTIFACT_PATHS_FILE" || true

  echo "$marker"
  exit "$exit_code"
}
trap cleanup EXIT

cat > "$COMMANDS_FILE" <<EOF
bash scripts/run_final_52.sh${EXPLICIT_RESUME_DIR:+ --run-dir "$EXPLICIT_RESUME_DIR"}${RUN_PATH_FILE:+ --path-file "$RUN_PATH_FILE"}
uv run python "$RUN_WRAPPER" --kind mab --manifest "$ROOT/evals/manifests/mab_answer_heldout_v1.yaml" --output-dir "$RUN_DIR/mab" --execution-mode graph${EXPLICIT_RESUME_DIR:+ --resume}
uv run python "$RUN_WRAPPER" --kind long --manifest "$ROOT/evals/manifests/longmemeval_answer_heldout_v1.yaml" --output-dir "$RUN_DIR/longmemeval" --execution-mode graph${EXPLICIT_RESUME_DIR:+ --resume}
EOF

git status --short > "$GIT_STATUS_FILE"

{
  printf 'RUN_NAME=%q\n' "$RUN_NAME"
  printf 'RUN_DIR=%q\n' "$RUN_DIR"
  printf 'START_TS=%q\n' "$START_TS"
  printf 'BRANCH=%q\n' "$BRANCH"
  printf 'COMMIT=%q\n' "$COMMIT"
  printf 'MAB_MANIFEST=%q\n' "$ROOT/evals/manifests/mab_answer_heldout_v1.yaml"
  printf 'LONGMEMEVAL_MANIFEST=%q\n' "$ROOT/evals/manifests/longmemeval_answer_heldout_v1.yaml"
  printf 'EXECUTION_MODE=%q\n' "graph"
  printf 'EXPLICIT_RESUME=%q\n' "${EXPLICIT_RESUME_DIR:+1}"
  printf 'HF_HUB_OFFLINE_SET=%q\n' "${HF_HUB_OFFLINE:+1}"
  printf 'HF_DATASETS_OFFLINE_SET=%q\n' "${HF_DATASETS_OFFLINE:+1}"
  printf 'TRANSFORMERS_OFFLINE_SET=%q\n' "${TRANSFORMERS_OFFLINE:+1}"
  printf 'PYTHONUNBUFFERED=%q\n' "$PYTHONUNBUFFERED"
  printf 'OPENAI_BASE_URL_SET=%q\n' "${OPENAI_BASE_URL:+1}"
  printf 'OPENAI_API_KEY_SET=%q\n' "${OPENAI_API_KEY:+1}"
  printf 'MODEL_NAME_SET=%q\n' "${MODEL_NAME:+1}"
  printf 'ANSWER_MODEL_SET=%q\n' "${ANSWER_MODEL:+1}"
  printf 'JUDGE_BASE_URL_SET=%q\n' "${JUDGE_BASE_URL:+1}"
  printf 'JUDGE_MODEL_SET=%q\n' "${JUDGE_MODEL:+1}"
  printf 'JUDGE_API_KEY_SET=%q\n' "${JUDGE_API_KEY:+1}"
  printf 'SECONDARY_JUDGE_MODEL_SET=%q\n' "${SECONDARY_JUDGE_MODEL:+1}"
} > "$CONFIG_FILE"

cat > "$RUN_WRAPPER" <<'PY'
from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from evals.mab_answer_eval.artifacts import RESULTS_FILE, append_jsonl, latest_results, read_jsonl
from evals.mab_answer_eval.metrics import score_official_for_case
from evals.mab_answer_eval.runner import (
    ANSWER_PARAMETERS,
    EvaluationAnswerModel,
    MABAnswerExecutor,
    RunOptions as MABRunOptions,
    answer_cache_key,
    application_configuration_hash,
    artifact_paths,
    base_record as mab_base_record,
)
from evals.mab_answer_eval.schemas import EvaluationModels
from evals.mab_answer_eval.manifest import load_manifest as load_mab_manifest, resolve_cases as resolve_mab_cases
from evals.longmemeval_answer_eval import (
    ANSWER_CACHE_VERSION as LONG_ANSWER_CACHE_VERSION,
    ANSWER_PARAMETERS as LONG_ANSWER_PARAMETERS,
    EVALUATION_VERSION as LONG_EVALUATION_VERSION,
    EvaluationAnswerModel as LongEvaluationAnswerModel,
    LongMemEvalAnswerExecutor,
    RunOptions as LongRunOptions,
    artifact_paths as shared_artifact_paths,
    base_record as long_base_record,
    find_answer as long_find_answer,
    load_manifest as load_long_manifest,
    resolve_cases as resolve_long_cases,
    stable_hash,
)
from evals.mab_answer_eval.artifacts import atomic_json
from evals.mab_answer_eval.schemas import EvaluationModels as SharedEvaluationModels
from src.config import AppConfig
from src.model_wrapper import ModelWrapper


def write_answer_only_metadata(output_dir: Path, metadata: dict) -> None:
    atomic_json(output_dir / "run_metadata.json", metadata)
    atomic_json(output_dir / "answer_only_summary.json", metadata)


def find_answer_only(rows: list[dict], answer_key: str) -> dict | None:
    for row in reversed(rows):
        if (
            row.get("answer_cache_key") == answer_key
            and row.get("generated_answer") is not None
            and row.get("status") in {"answer_completed", "completed"}
        ):
            return row
    return None


def run_mab(manifest_path: Path, output_dir: Path, execution_mode: str, resume: bool, answer_model: str | None) -> dict:
    config = AppConfig.from_env()
    manifest = load_mab_manifest(manifest_path)
    model_name = answer_model or config.model_name
    if execution_mode != manifest.execution_mode:
        raise ValueError("execution mode must match frozen manifest")
    resolved = resolve_mab_cases(manifest)
    history_question_counts: dict[tuple[str, str, int], int] = {}
    for case in manifest.cases:
        key = (case.split, case.source_dataset, case.row_index)
        history_question_counts[key] = history_question_counts.get(key, 0) + 1
    executor = MABAnswerExecutor(
        model=EvaluationAnswerModel(ModelWrapper(config, model_name=model_name)),
        config=config,
        execution_mode=execution_mode,
        history_question_counts=history_question_counts,
    )
    options = MABRunOptions(output_dir=output_dir, execution_mode=execution_mode, resume=resume)
    models = EvaluationModels(model_name, "__answer_only__", None, judge_endpoint=None)
    results_path = output_dir / RESULTS_FILE
    prior_rows = read_jsonl(results_path) if resume else []
    run_id = str(uuid4())
    application_hash = application_configuration_hash(config)
    generation_calls = 0
    skipped_completed = 0
    for resolved_case in resolved:
        answer_key = answer_cache_key(
            manifest,
            resolved_case,
            execution_mode=execution_mode,
            answer_model=model_name,
            application_hash=application_hash,
        )
        cached = find_answer_only(prior_rows, answer_key)
        if cached is not None:
            skipped_completed += 1
            continue
        generation_calls += 1
        execution = executor.execute(resolved_case)
        official, normalization = score_official_for_case(
            resolved_case.spec,
            execution.generated_answer,
            resolved_case.example.answers[0],
        )
        record = mab_base_record(
            run_id,
            manifest,
            resolved_case,
            models,
            options,
            identity=str(
                stable_hash(
                    {
                        "manifest_hash": manifest.manifest_hash,
                        "case_id": resolved_case.spec.case_id,
                        "evaluation_version": "lifecycle_v2",
                        "execution_mode": execution_mode,
                        "answer_model": model_name,
                    }
                )
            ),
            answer_key=answer_key,
        )
        record.update(
            {
                "generated_answer": execution.generated_answer,
                "context_diagnostics": execution.context_diagnostics,
                "selected_evidence_hash": stable_hash(execution.selected_evidence_for_judge),
                "latency_ms": {**execution.latency_ms, "judge": 0.0},
                "status": "answer_completed",
                "error": None,
                "answer_metadata": execution.raw_metadata,
                "official_metric": official.to_dict(),
                "normalized_answer": normalization.get("normalized_answer"),
                "output_normalization": normalization,
                "judge_model": "__answer_only__",
                "judge_endpoint": None,
                "secondary_judge_model": None,
            }
        )
        append_jsonl(results_path, record)
        prior_rows.append(record)
    latest = latest_results(prior_rows)
    metadata = {
        "evaluation_level": "answer",
        "run_mode": "answer_only",
        "evaluation_version": "lifecycle_v2",
        "manifest_name": manifest.name,
        "manifest_hash": manifest.manifest_hash,
        "cases": len(resolved),
        "execution_mode": execution_mode,
        "answer_model": model_name,
        "generation_calls_this_invocation": generation_calls,
        "judge_calls_this_invocation": 0,
        "skipped_completed": skipped_completed,
        "completed_or_cached_answers": sum(1 for row in latest if row.get("status") in {"answer_completed", "completed"}),
        "output_paths": artifact_paths(output_dir),
        "answer_parameters": ANSWER_PARAMETERS,
        "resume": resume,
    }
    write_answer_only_metadata(output_dir, metadata)
    return metadata


def run_long(manifest_path: Path, output_dir: Path, execution_mode: str, resume: bool, answer_model: str | None) -> dict:
    config = AppConfig.from_env()
    manifest = load_long_manifest(manifest_path)
    model_name = answer_model or config.model_name
    if execution_mode != manifest.execution_mode:
        raise ValueError("execution mode must match frozen manifest")
    resolved = resolve_long_cases(manifest)
    executor = LongMemEvalAnswerExecutor(
        model=LongEvaluationAnswerModel(ModelWrapper(config, model_name=model_name)),
        config=config,
        execution_mode=execution_mode,
    )
    options = LongRunOptions(output_dir=output_dir, execution_mode=execution_mode, resume=resume)
    models = SharedEvaluationModels(model_name, "__answer_only__", None, judge_endpoint=None)
    results_path = output_dir / RESULTS_FILE
    prior_rows = read_jsonl(results_path) if resume else []
    run_id = str(uuid4())
    application_hash = stable_hash(
        {
            "model_name": config.model_name,
            "application_context_cap": config.application_context_cap,
            "base_memory_budget": config.base_memory_budget,
            "chat_memory_cap": config.chat_memory_cap,
            "document_memory_cap": config.document_memory_cap,
            "multi_scope_memory_cap": config.multi_scope_memory_cap,
            "long_document_memory_cap": config.long_document_memory_cap,
            "required_evidence_headroom_ratio": config.required_evidence_headroom_ratio,
            "minimum_optional_candidate_utility": config.minimum_optional_candidate_utility,
        }
    )
    generation_calls = 0
    skipped_completed = 0
    for resolved_case in resolved:
        answer_key = stable_hash(
            {
                "version": LONG_ANSWER_CACHE_VERSION,
                "manifest_hash": manifest.manifest_hash,
                "case_id": resolved_case.spec.case_id,
                "execution_mode": execution_mode,
                "answer_model": model_name,
                "generation_parameters": LONG_ANSWER_PARAMETERS,
                "application_configuration_hash": application_hash,
                "evaluation_version": LONG_EVALUATION_VERSION,
            }
        )
        cached = long_find_answer(prior_rows, answer_key=answer_key) if resume else None
        if cached is not None and cached.get("status") in {"answer_completed", "completed"}:
            skipped_completed += 1
            continue
        generation_calls += 1
        execution = executor.execute(resolved_case)
        record = long_base_record(
            run_id,
            manifest,
            resolved_case,
            models,
            options,
            identity=stable_hash(
                {
                    "manifest_hash": manifest.manifest_hash,
                    "case_id": resolved_case.spec.case_id,
                    "evaluation_version": LONG_EVALUATION_VERSION,
                    "execution_mode": execution_mode,
                    "answer_model": model_name,
                }
            ),
            answer_key=answer_key,
        )
        record.update(
            {
                "generated_answer": execution.generated_answer,
                "context_diagnostics": execution.context_diagnostics,
                "selected_evidence_hash": stable_hash(execution.selected_evidence_for_judge),
                "latency_ms": {**execution.latency_ms, "judge": 0.0},
                "status": "answer_completed",
                "error": None,
                "answer_metadata": execution.raw_metadata,
                "official_metric": execution.official_metric.to_dict(),
                "judge_model": "__answer_only__",
                "judge_endpoint": None,
                "secondary_judge_model": None,
            }
        )
        append_jsonl(results_path, record)
        prior_rows.append(record)
    latest = latest_results(prior_rows)
    metadata = {
        "evaluation_level": "answer",
        "run_mode": "answer_only",
        "evaluation_version": LONG_EVALUATION_VERSION,
        "manifest_name": manifest.name,
        "manifest_hash": manifest.manifest_hash,
        "cases": len(resolved),
        "execution_mode": execution_mode,
        "answer_model": model_name,
        "generation_calls_this_invocation": generation_calls,
        "judge_calls_this_invocation": 0,
        "skipped_completed": skipped_completed,
        "completed_or_cached_answers": sum(1 for row in latest if row.get("status") in {"answer_completed", "completed"}),
        "output_paths": shared_artifact_paths(output_dir),
        "answer_parameters": LONG_ANSWER_PARAMETERS,
        "resume": resume,
        "dataset_path": str(manifest.dataset_path),
    }
    write_answer_only_metadata(output_dir, metadata)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("mab", "long"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execution-mode", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--answer-model")
    args = parser.parse_args()
    if args.kind == "mab":
        report = run_mab(args.manifest, args.output_dir, args.execution_mode, args.resume, args.answer_model)
    else:
        report = run_long(args.manifest, args.output_dir, args.execution_mode, args.resume, args.answer_model)
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
PY

echo "Repository root: $ROOT"
echo "Run directory: $RUN_DIR"
echo "Branch: $BRANCH"
echo "Commit: $COMMIT"
echo "Start: $START_TS"
echo
echo "Running MAB answer-only lifecycle-v2 pass..."
enable_eval_online_mode
set +e
if [[ -n "$EXPLICIT_RESUME_DIR" ]]; then
  uv run python "$RUN_WRAPPER" \
    --kind mab \
    --manifest "$ROOT/evals/manifests/mab_answer_heldout_v1.yaml" \
    --output-dir "$RUN_DIR/mab" \
    --execution-mode graph \
    --resume
else
  uv run python "$RUN_WRAPPER" \
    --kind mab \
    --manifest "$ROOT/evals/manifests/mab_answer_heldout_v1.yaml" \
    --output-dir "$RUN_DIR/mab" \
    --execution-mode graph
fi
MAB_EXIT_STATUS=$?
set -e
if [[ $MAB_EXIT_STATUS -ne 0 ]]; then
  RUN_EXIT_STATUS="$MAB_EXIT_STATUS"
  FAILED_PHASE="mab_answer"
  SUBPROCESS_EXIT_CODE="$MAB_EXIT_STATUS"
  FAILURE_REASON="MAB answer subprocess failed"
  exit "$RUN_EXIT_STATUS"
fi

echo
echo "Running LongMemEval answer-only lifecycle-v2 pass..."
enable_eval_online_mode
set +e
if [[ -n "$EXPLICIT_RESUME_DIR" ]]; then
  uv run python "$RUN_WRAPPER" \
    --kind long \
    --manifest "$ROOT/evals/manifests/longmemeval_answer_heldout_v1.yaml" \
    --output-dir "$RUN_DIR/longmemeval" \
    --execution-mode graph \
    --resume
else
  uv run python "$RUN_WRAPPER" \
    --kind long \
    --manifest "$ROOT/evals/manifests/longmemeval_answer_heldout_v1.yaml" \
    --output-dir "$RUN_DIR/longmemeval" \
    --execution-mode graph
fi
LONG_EXIT_STATUS=$?
set -e
if [[ $LONG_EXIT_STATUS -ne 0 ]]; then
  RUN_EXIT_STATUS="$LONG_EXIT_STATUS"
  FAILED_PHASE="longmemeval_answer"
  SUBPROCESS_EXIT_CODE="$LONG_EXIT_STATUS"
  FAILURE_REASON="LongMemEval answer subprocess failed"
  exit "$RUN_EXIT_STATUS"
fi

echo
echo "Answer-only run artifacts:"
find "$RUN_DIR" -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.csv' -o -name '*.log' \) | sort

RUN_EXIT_STATUS=0
FAILED_PHASE=""
SUBPROCESS_EXIT_CODE=0
FAILURE_REASON=""
