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

JUDGE_RUN_NAME="final_52_judge_pass"
JUDGE_STATE_FILE="$ROOT/artifacts/eval_runs/${JUDGE_RUN_NAME}_current_path.txt"
CHECK_ONLY=false
ANSWER_RUN_ARG=""
RUN_PATH_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      CHECK_ONLY=true
      shift
      ;;
    --answer-run-dir)
      if [[ $# -lt 2 ]]; then
        echo "missing value for --answer-run-dir" >&2
        exit 2
      fi
      ANSWER_RUN_ARG="$2"
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
      echo "usage: $0 [--check] [--answer-run-dir COMPLETED_ANSWER_RUN] [--path-file FILE]" >&2
      exit 2
      ;;
  esac
done

if [[ "$CHECK_ONLY" == true ]]; then
  if [[ -n "$RUN_PATH_FILE" ]]; then
    echo "--check cannot be combined with --path-file" >&2
    exit 2
  fi
  export HF_HUB_OFFLINE=1
  export HF_DATASETS_OFFLINE=1
  export TRANSFORMERS_OFFLINE=1
  echo "Repository root: $ROOT"
  print_env_presence OPENAI_API_KEY OPENAI_BASE_URL MODEL_NAME JUDGE_MODEL JUDGE_API_KEY JUDGE_BASE_URL
  require_env_vars OPENAI_API_KEY OPENAI_BASE_URL MODEL_NAME JUDGE_MODEL JUDGE_API_KEY
  require_path_exists "$ROOT/evals/manifests/mab_answer_heldout_v1.yaml" "MAB manifest"
  require_path_exists "$ROOT/evals/manifests/longmemeval_answer_heldout_v1.yaml" "LongMemEval manifest"
  require_path_exists "$ROOT/scripts/validate_final_answer_run.py" "answer-run validator"
  require_dir_writable "$ROOT/artifacts/eval_runs"
  verify_repo_imports
  if [[ -n "$ANSWER_RUN_ARG" ]]; then
    uv run python "$ROOT/scripts/validate_final_answer_run.py" \
      --answer-run-dir "$ANSWER_RUN_ARG" >/dev/null
    echo "ANSWER_RUN_VALIDATION: present"
  fi
  echo "CONFIG_CHECK_OK"
  exit 0
fi

if [[ -z "$ANSWER_RUN_ARG" ]]; then
  echo "missing required argument: --answer-run-dir" >&2
  exit 2
fi

enable_eval_online_mode
ANSWER_RUN_DIR="$(cd -- "$(dirname -- "$ANSWER_RUN_ARG")" && pwd)/$(basename -- "$ANSWER_RUN_ARG")"
VALIDATION_JSON="$(uv run python "$ROOT/scripts/validate_final_answer_run.py" \
  --answer-run-dir "$ANSWER_RUN_DIR")"
ANSWER_MODEL_RESOLVED="$(printf '%s' "$VALIDATION_JSON" | uv run python -c \
  'import json,sys; print(json.load(sys.stdin)["answer_model"])')"

RUN_DIR="$(final_eval_new_run_dir "$ROOT/artifacts/eval_runs" "$JUDGE_RUN_NAME")"
final_eval_create_fresh_dir "$RUN_DIR" ".final_52_judge_run"
mkdir -p "$RUN_DIR"/{logs,meta}
cp -R "$ANSWER_RUN_DIR/mab" "$RUN_DIR/mab"
cp -R "$ANSWER_RUN_DIR/longmemeval" "$RUN_DIR/longmemeval"
printf '%s\n' "$RUN_DIR" > "$JUDGE_STATE_FILE"
if [[ -n "$RUN_PATH_FILE" ]]; then
  mkdir -p "$(dirname -- "$RUN_PATH_FILE")"
  printf '%s\n' "$RUN_DIR" > "$RUN_PATH_FILE"
fi

LOG_FILE="$RUN_DIR/logs/run_final_judge.log"
STATUS_FILE="$RUN_DIR/meta/status.env"
COMMANDS_FILE="$RUN_DIR/meta/commands.txt"
ARTIFACT_PATHS_FILE="$RUN_DIR/meta/artifact_paths.txt"
CONFIG_FILE="$RUN_DIR/meta/config.env"
GIT_STATUS_FILE="$RUN_DIR/meta/git_status_short.txt"
VALIDATION_FILE="$RUN_DIR/meta/validation.json"
ANSWER_IDENTITY_FILE="$RUN_DIR/meta/answer_run_identity.txt"

printf '%s\n' "$VALIDATION_JSON" > "$VALIDATION_FILE"
{
  printf '%s  %s\n' "$(shasum -a 256 "$ANSWER_RUN_DIR/mab/results.jsonl" | awk '{print $1}')" "mab/results.jsonl"
  printf '%s  %s\n' "$(shasum -a 256 "$ANSWER_RUN_DIR/longmemeval/results.jsonl" | awk '{print $1}')" "longmemeval/results.jsonl"
} > "$ANSWER_IDENTITY_FILE"

exec > >(tee -a "$LOG_FILE") 2>&1

START_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
COMMIT="$(git rev-parse HEAD)"

cleanup() {
  local exit_code=$?
  local finish_ts marker
  finish_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  marker="RUN_FAILED"
  if [[ $exit_code -eq 0 ]]; then
    marker="RUN_COMPLETED"
  fi
  {
    printf 'START_TS=%q\n' "$START_TS"
    printf 'FINISH_TS=%q\n' "$finish_ts"
    printf 'EXIT_STATUS=%q\n' "$exit_code"
    printf 'RUN_DIR=%q\n' "$RUN_DIR"
    printf 'ANSWER_RUN_DIR=%q\n' "$ANSWER_RUN_DIR"
    printf 'BRANCH=%q\n' "$BRANCH"
    printf 'COMMIT=%q\n' "$COMMIT"
    printf 'FINAL_MARKER=%q\n' "$marker"
  } > "$STATUS_FILE"
  find "$RUN_DIR" -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.csv' -o -name '*.log' -o -name '*.txt' \) |
    sort > "$ARTIFACT_PATHS_FILE" || true
  echo "$marker"
  exit "$exit_code"
}
trap cleanup EXIT

cat > "$COMMANDS_FILE" <<EOF
bash scripts/run_final_judge.sh --answer-run-dir "$ANSWER_RUN_DIR"
uv run python -m evals.mab_answer_eval --manifest "$ROOT/evals/manifests/mab_answer_heldout_v1.yaml" --execution-mode graph --output-dir "$RUN_DIR/mab" --answer-model "$ANSWER_MODEL_RESOLVED" --judge-model "\$JUDGE_MODEL" --resume
uv run python -m evals.longmemeval_answer_eval --manifest "$ROOT/evals/manifests/longmemeval_answer_heldout_v1.yaml" --execution-mode graph --output-dir "$RUN_DIR/longmemeval" --answer-model "$ANSWER_MODEL_RESOLVED" --judge-model "\$JUDGE_MODEL" --resume
EOF

git status --short > "$GIT_STATUS_FILE"
{
  printf 'RUN_DIR=%q\n' "$RUN_DIR"
  printf 'ANSWER_RUN_DIR=%q\n' "$ANSWER_RUN_DIR"
  printf 'START_TS=%q\n' "$START_TS"
  printf 'BRANCH=%q\n' "$BRANCH"
  printf 'COMMIT=%q\n' "$COMMIT"
  printf 'EXECUTION_MODE=%q\n' "graph"
  printf 'OPENAI_BASE_URL_SET=%q\n' "${OPENAI_BASE_URL:+1}"
  printf 'OPENAI_API_KEY_SET=%q\n' "${OPENAI_API_KEY:+1}"
  printf 'JUDGE_BASE_URL_SET=%q\n' "${JUDGE_BASE_URL:+1}"
  printf 'JUDGE_MODEL_SET=%q\n' "${JUDGE_MODEL:+1}"
  printf 'JUDGE_API_KEY_SET=%q\n' "${JUDGE_API_KEY:+1}"
} > "$CONFIG_FILE"

echo "Repository root: $ROOT"
echo "Answer run directory: $ANSWER_RUN_DIR"
echo "Judge run directory: $RUN_DIR"
echo "Branch: $BRANCH"
echo "Commit: $COMMIT"
echo "Start: $START_TS"

JUDGE_BASE_URL_ARGS=()
if [[ -n "${JUDGE_BASE_URL:-}" ]]; then
  JUDGE_BASE_URL_ARGS=(--judge-base-url "$JUDGE_BASE_URL")
fi

enable_eval_online_mode
uv run python -m evals.mab_answer_eval \
  --manifest "$ROOT/evals/manifests/mab_answer_heldout_v1.yaml" \
  --execution-mode graph \
  --output-dir "$RUN_DIR/mab" \
  --answer-model "$ANSWER_MODEL_RESOLVED" \
  --judge-model "$JUDGE_MODEL" \
  "${JUDGE_BASE_URL_ARGS[@]}" \
  --resume

enable_eval_online_mode
uv run python -m evals.longmemeval_answer_eval \
  --manifest "$ROOT/evals/manifests/longmemeval_answer_heldout_v1.yaml" \
  --execution-mode graph \
  --output-dir "$RUN_DIR/longmemeval" \
  --answer-model "$ANSWER_MODEL_RESOLVED" \
  --judge-model "$JUDGE_MODEL" \
  "${JUDGE_BASE_URL_ARGS[@]}" \
  --resume

echo "Judge artifacts:"
find "$RUN_DIR" -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.csv' -o -name '*.log' \) | sort
