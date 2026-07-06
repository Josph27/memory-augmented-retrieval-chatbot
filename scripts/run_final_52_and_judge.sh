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
ANSWER_SCRIPT="${FINAL_EVAL_ANSWER_SCRIPT:-$ROOT/scripts/run_final_52.sh}"
JUDGE_SCRIPT="${FINAL_EVAL_JUDGE_SCRIPT:-$ROOT/scripts/run_final_judge.sh}"
ANSWER_VALIDATOR="${FINAL_EVAL_ANSWER_VALIDATOR:-$ROOT/scripts/validate_final_answer_run.py}"
EVAL_RUNS_ROOT="${FINAL_EVAL_RUNS_ROOT:-$ROOT/artifacts/eval_runs}"

CHECK_ONLY=false
BACKGROUND=false
INTERNAL_RUN_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      CHECK_ONLY=true
      shift
      ;;
    --background)
      BACKGROUND=true
      shift
      ;;
    --run-dir)
      if [[ $# -lt 2 ]]; then
        echo "missing value for --run-dir" >&2
        exit 2
      fi
      INTERNAL_RUN_DIR="$2"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      echo "usage: $0 [--check|--background] [--run-dir INTERNAL_COMBINED_DIR]" >&2
      exit 2
      ;;
  esac
done

if [[ "$CHECK_ONLY" == true ]]; then
  if [[ "$BACKGROUND" == true || -n "$INTERNAL_RUN_DIR" ]]; then
    echo "--check cannot be combined with run arguments" >&2
    exit 2
  fi
  bash "$ANSWER_SCRIPT" --check
  bash "$JUDGE_SCRIPT" --check
  echo "CONFIG_CHECK_OK"
  exit 0
fi

enable_eval_online_mode

COMBINED_NAME="final_52_and_judge"
COMBINED_MARKER=".final_52_combined_run"
if [[ -n "$INTERNAL_RUN_DIR" ]]; then
  COMBINED_DIR="$(cd -- "$(dirname -- "$INTERNAL_RUN_DIR")" && pwd)/$(basename -- "$INTERNAL_RUN_DIR")"
  if [[ ! -f "$COMBINED_DIR/$COMBINED_MARKER" ]]; then
    echo "invalid combined run directory: $COMBINED_DIR" >&2
    exit 2
  fi
else
  mkdir -p "$EVAL_RUNS_ROOT"
  COMBINED_DIR="$(final_eval_new_run_dir "$EVAL_RUNS_ROOT" "$COMBINED_NAME")"
  final_eval_create_fresh_dir "$COMBINED_DIR" "$COMBINED_MARKER"
fi

if [[ "$BACKGROUND" == true ]]; then
  if [[ -n "$INTERNAL_RUN_DIR" ]]; then
    echo "--background cannot be combined with --run-dir" >&2
    exit 2
  fi
  LAUNCHER_LOG="$COMBINED_DIR/launcher.log"
  enable_eval_online_mode
  nohup caffeinate -dimsu bash "$0" --run-dir "$COMBINED_DIR" \
    >"$LAUNCHER_LOG" 2>&1 &
  LAUNCHER_PID=$!
  printf '%s\n' "$LAUNCHER_PID" > "$COMBINED_DIR/pid"
  echo "Combined run directory: $COMBINED_DIR"
  echo "PID: $LAUNCHER_PID"
  echo "Check process: ps -p $LAUNCHER_PID -o pid=,stat=,etime=,command="
  echo "Follow launcher: tail -f $LAUNCHER_LOG"
  echo "Follow answer log: tail -f \$(cat \"$COMBINED_DIR/answer_run_path.txt\")/logs/run_final_52.log"
  echo "Follow judge log: tail -f \$(cat \"$COMBINED_DIR/judge_run_path.txt\")/logs/run_final_judge.log"
  echo "Check status: cat $COMBINED_DIR/status.env"
  exit 0
fi

LOG_FILE="$COMBINED_DIR/combined.log"
STATUS_FILE="$COMBINED_DIR/status.env"
ANSWER_PATH_FILE="$COMBINED_DIR/answer_run_path.txt"
JUDGE_PATH_FILE="$COMBINED_DIR/judge_run_path.txt"

if [[ "${FINAL_EVAL_DISABLE_TEE:-0}" == "1" ]]; then
  exec >>"$LOG_FILE" 2>&1
else
  exec > >(tee -a "$LOG_FILE") 2>&1
fi

START_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
COMMIT="$(git rev-parse HEAD)"
ANSWER_RUN_DIR=""
JUDGE_RUN_DIR=""
COMBINED_EXIT_STATUS=1
FAILED_PHASE="initialization"
SUBPROCESS_EXIT_CODE=""
FAILURE_REASON="combined launcher did not complete"

cleanup() {
  local exit_code="$COMBINED_EXIT_STATUS"
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
    printf 'COMBINED_DIR=%q\n' "$COMBINED_DIR"
    printf 'ANSWER_RUN_DIR=%q\n' "$ANSWER_RUN_DIR"
    printf 'JUDGE_RUN_DIR=%q\n' "$JUDGE_RUN_DIR"
    printf 'BRANCH=%q\n' "$BRANCH"
    printf 'COMMIT=%q\n' "$COMMIT"
    printf 'FAILED_PHASE=%q\n' "$FAILED_PHASE"
    printf 'SUBPROCESS_EXIT_CODE=%q\n' "$SUBPROCESS_EXIT_CODE"
    printf 'FAILURE_REASON=%q\n' "$FAILURE_REASON"
    printf 'MAB_MANIFEST=%q\n' "$ROOT/evals/manifests/mab_answer_heldout_v1.yaml"
    printf 'LONGMEMEVAL_MANIFEST=%q\n' "$ROOT/evals/manifests/longmemeval_answer_heldout_v1.yaml"
    printf 'FINAL_MARKER=%q\n' "$marker"
  } > "$STATUS_FILE"
  echo "$marker"
  exit "$exit_code"
}
trap cleanup EXIT

echo "Combined run directory: $COMBINED_DIR"
echo "Branch: $BRANCH"
echo "Commit: $COMMIT"
echo "Start: $START_TS"

enable_eval_online_mode
set +e
bash "$ANSWER_SCRIPT" --path-file "$ANSWER_PATH_FILE"
ANSWER_EXIT_STATUS=$?
set -e
if [[ $ANSWER_EXIT_STATUS -ne 0 ]]; then
  COMBINED_EXIT_STATUS="$ANSWER_EXIT_STATUS"
  FAILED_PHASE="answer"
  SUBPROCESS_EXIT_CODE="$ANSWER_EXIT_STATUS"
  FAILURE_REASON="answer script failed"
  exit "$COMBINED_EXIT_STATUS"
fi
if [[ ! -s "$ANSWER_PATH_FILE" ]]; then
  COMBINED_EXIT_STATUS=1
  FAILED_PHASE="answer"
  SUBPROCESS_EXIT_CODE="$ANSWER_EXIT_STATUS"
  FAILURE_REASON="answer script returned zero without recording its run path"
  echo "answer phase failed: $FAILURE_REASON" >&2
  exit "$COMBINED_EXIT_STATUS"
fi
ANSWER_RUN_DIR="$(<"$ANSWER_PATH_FILE")"
ANSWER_STATUS_FILE="$ANSWER_RUN_DIR/meta/status.env"
if [[ ! -f "$ANSWER_STATUS_FILE" ]] ||
   ! grep -q '^EXIT_STATUS=0$' "$ANSWER_STATUS_FILE" ||
   ! grep -q '^FINAL_MARKER=RUN_COMPLETED$' "$ANSWER_STATUS_FILE"; then
  COMBINED_EXIT_STATUS=1
  FAILED_PHASE="answer"
  SUBPROCESS_EXIT_CODE="$ANSWER_EXIT_STATUS"
  FAILURE_REASON="answer script returned zero without RUN_COMPLETED status"
  echo "answer phase failed: $FAILURE_REASON ($ANSWER_RUN_DIR)" >&2
  exit "$COMBINED_EXIT_STATUS"
fi

enable_eval_online_mode
set +e
VALIDATION_OUTPUT="$(uv run python "$ANSWER_VALIDATOR" \
  --answer-run-dir "$ANSWER_RUN_DIR" 2>&1)"
VALIDATION_EXIT_STATUS=$?
set -e
if [[ $VALIDATION_EXIT_STATUS -ne 0 ]]; then
  COMBINED_EXIT_STATUS="$VALIDATION_EXIT_STATUS"
  FAILED_PHASE="answer"
  SUBPROCESS_EXIT_CODE="$VALIDATION_EXIT_STATUS"
  FAILURE_REASON="$VALIDATION_OUTPUT"
  echo "$VALIDATION_OUTPUT" >&2
  exit "$COMBINED_EXIT_STATUS"
fi

enable_eval_online_mode
set +e
bash "$JUDGE_SCRIPT" \
  --answer-run-dir "$ANSWER_RUN_DIR" \
  --path-file "$JUDGE_PATH_FILE"
JUDGE_EXIT_STATUS=$?
set -e
if [[ $JUDGE_EXIT_STATUS -ne 0 ]]; then
  COMBINED_EXIT_STATUS="$JUDGE_EXIT_STATUS"
  FAILED_PHASE="judge"
  SUBPROCESS_EXIT_CODE="$JUDGE_EXIT_STATUS"
  FAILURE_REASON="judge script failed"
  exit "$COMBINED_EXIT_STATUS"
fi
if [[ ! -s "$JUDGE_PATH_FILE" ]]; then
  COMBINED_EXIT_STATUS=1
  FAILED_PHASE="judge"
  SUBPROCESS_EXIT_CODE="$JUDGE_EXIT_STATUS"
  FAILURE_REASON="judge script returned zero without recording its run path"
  echo "judge phase failed: $FAILURE_REASON" >&2
  exit "$COMBINED_EXIT_STATUS"
fi
JUDGE_RUN_DIR="$(<"$JUDGE_PATH_FILE")"

if [[ "$ANSWER_RUN_DIR" == "$JUDGE_RUN_DIR" ]]; then
  COMBINED_EXIT_STATUS=1
  FAILED_PHASE="judge"
  SUBPROCESS_EXIT_CODE="$JUDGE_EXIT_STATUS"
  FAILURE_REASON="answer and judge run directories are identical"
  echo "answer and judge run directories must be separate" >&2
  exit "$COMBINED_EXIT_STATUS"
fi

COMBINED_EXIT_STATUS=0
FAILED_PHASE=""
SUBPROCESS_EXIT_CODE=0
FAILURE_REASON=""
