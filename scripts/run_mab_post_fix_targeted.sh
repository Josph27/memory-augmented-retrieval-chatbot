#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=lib/load_eval_env.sh
source "${SCRIPT_DIR}/lib/load_eval_env.sh"
cd "$ROOT"

HF_HUB_OFFLINE_EXPLICIT="${HF_HUB_OFFLINE+x}"
HF_DATASETS_OFFLINE_EXPLICIT="${HF_DATASETS_OFFLINE+x}"
TRANSFORMERS_OFFLINE_EXPLICIT="${TRANSFORMERS_OFFLINE+x}"

load_eval_env

export ANSWER_MODEL="${ANSWER_MODEL:-${MODEL_NAME:-}}"
export PYTHONUNBUFFERED=1
if [[ -z "$HF_HUB_OFFLINE_EXPLICIT" ]]; then
  export HF_HUB_OFFLINE=0
fi
if [[ -z "$HF_DATASETS_OFFLINE_EXPLICIT" ]]; then
  export HF_DATASETS_OFFLINE=0
fi
if [[ -z "$TRANSFORMERS_OFFLINE_EXPLICIT" ]]; then
  export TRANSFORMERS_OFFLINE=0
fi

DEFAULT_MANIFEST="$ROOT/evals/manifests/mab_post_fix_targeted_v1.json"
MANIFEST_INPUT="$DEFAULT_MANIFEST"
OUTPUT_PARENT="$ROOT/artifacts/eval_runs"
STATE_FILE="$OUTPUT_PARENT/mab_post_fix_targeted_current_path.txt"
MARKER_NAME=".mab_post_fix_targeted_run"

usage() {
  cat >&2 <<EOF
usage:
  $0 [--manifest PATH] [--check]
  $0 [--manifest PATH]
  $0 [--manifest PATH] --background
  $0 [--manifest PATH] --run-dir PATH
EOF
}

resolve_manifest_path() {
  local requested="$1"
  local candidate
  if [[ "$requested" == /* ]]; then
    candidate="$requested"
  else
    candidate="$ROOT/$requested"
  fi
  if [[ ! -f "$candidate" ]]; then
    printf 'manifest not found: %s\n' "$candidate" >&2
    return 1
  fi
  (
    cd -- "$(dirname -- "$candidate")"
    printf '%s/%s\n' "$PWD" "$(basename -- "$candidate")"
  )
}

validate_configuration() {
  require_env_vars \
    OPENAI_API_KEY \
    OPENAI_BASE_URL \
    ANSWER_MODEL \
    JUDGE_API_KEY \
    JUDGE_MODEL
  require_path_exists "$MANIFEST" "targeted manifest"
  require_dir_writable "$OUTPUT_PARENT"
}

manifest_hash() {
  uv run python - "$MANIFEST" <<'PY'
from pathlib import Path
import sys

from evals.mab_answer_eval.manifest import load_manifest

print(load_manifest(Path(sys.argv[1])).manifest_hash)
PY
}

manifest_name() {
  uv run python - "$MANIFEST" <<'PY'
from pathlib import Path
import sys

from evals.mab_answer_eval.manifest import load_manifest

print(load_manifest(Path(sys.argv[1])).name)
PY
}

validate_manifest_locally() {
  uv run python - "$MANIFEST" <<'PY'
from pathlib import Path
import sys

from evals.mab_answer_eval.manifest import load_manifest

manifest = load_manifest(Path(sys.argv[1]))
case_ids = [case.case_id for case in manifest.cases]
if len(case_ids) != len(set(case_ids)):
    raise SystemExit("targeted manifest contains duplicate case IDs")
if not case_ids:
    raise SystemExit("targeted manifest contains no cases")
PY
}

run_dir_is_compatible() {
  local run_dir="$1"
  local expected_hash="$2"
  local marker="$run_dir/$MARKER_NAME"
  if [[ -f "$marker" ]] && grep -Fxq "MANIFEST_HASH=$expected_hash" "$marker"; then
    return 0
  fi
  uv run python - "$run_dir" "$expected_hash" <<'PY'
from pathlib import Path
import json
import sys

run_dir = Path(sys.argv[1])
expected_hash = sys.argv[2]

metadata_path = run_dir / "run_metadata.json"
if metadata_path.exists():
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raise SystemExit(1)
    if metadata.get("manifest_hash") == expected_hash:
        raise SystemExit(0)

results_path = run_dir / "results.jsonl"
if results_path.exists():
    hashes: set[str] = set()
    try:
        with results_path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                value = row.get("manifest_hash")
                if isinstance(value, str):
                    hashes.add(value)
    except (json.JSONDecodeError, OSError):
        raise SystemExit(1)
    if hashes == {expected_hash}:
        raise SystemExit(0)

raise SystemExit(1)
PY
}

prepare_run_dir() {
  local requested="$1"
  local expected_hash="$2"
  local run_dir

  mkdir -p "$requested"
  run_dir="$(cd -- "$requested" && pwd)"
  if [[ -n "$(find "$run_dir" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    if ! run_dir_is_compatible "$run_dir" "$expected_hash"; then
      printf 'refusing unrelated non-empty run directory: %s\n' "$run_dir" >&2
      printf 'use an empty directory or a compatible interrupted targeted run\n' >&2
      return 1
    fi
  fi
  printf 'MANIFEST_HASH=%s\n' "$expected_hash" > "$run_dir/$MARKER_NAME"
  printf '%s\n' "$run_dir"
}

MODE="run"
REQUESTED_RUN_DIR=""
MODE_SET=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      if [[ $MODE_SET -ne 0 ]]; then
        printf 'only one of --check, --background, or --run-dir may be used\n' >&2
        exit 2
      fi
      MODE="check"
      MODE_SET=1
      shift
      ;;
    --background)
      if [[ $MODE_SET -ne 0 ]]; then
        printf 'only one of --check, --background, or --run-dir may be used\n' >&2
        exit 2
      fi
      MODE="background"
      MODE_SET=1
      shift
      ;;
    --run-dir)
      if [[ $MODE_SET -ne 0 || $# -lt 2 || -z "${2:-}" ]]; then
        usage
        exit 2
      fi
      MODE="run"
      MODE_SET=1
      REQUESTED_RUN_DIR="$2"
      shift 2
      ;;
    --manifest)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        usage
        exit 2
      fi
      MANIFEST_INPUT="$2"
      shift 2
      ;;
    *)
      printf 'unknown argument: %s\n' "$1" >&2
      usage
      exit 2
      ;;
  esac
done

MANIFEST="$(resolve_manifest_path "$MANIFEST_INPUT")"
MANIFEST_BASENAME="$(basename -- "$MANIFEST")"
RUN_PREFIX="${MANIFEST_BASENAME%.*}"

if [[ "$MODE" == "check" ]]; then
  print_env_presence \
    OPENAI_API_KEY \
    OPENAI_BASE_URL \
    ANSWER_MODEL \
    JUDGE_API_KEY \
    JUDGE_MODEL \
    JUDGE_BASE_URL \
    HF_TOKEN
  validate_configuration
  verify_repo_imports
  validate_manifest_locally
  TARGET_MANIFEST_HASH="$(manifest_hash)"
  TARGET_MANIFEST_NAME="$(manifest_name)"
  printf 'TARGET_MANIFEST: present\n'
  printf 'TARGET_MANIFEST_PARSE: present\n'
  printf 'TARGET_MANIFEST_PATH: %s\n' "$MANIFEST"
  printf 'TARGET_MANIFEST_NAME: %s\n' "$TARGET_MANIFEST_NAME"
  printf 'TARGET_MANIFEST_HASH: %s\n' "$TARGET_MANIFEST_HASH"
  printf 'OUTPUT_PARENT_WRITABLE: present\n'
  printf 'CONFIG_CHECK_OK\n'
  exit 0
fi

validate_configuration
verify_repo_imports
validate_manifest_locally
TARGET_MANIFEST_HASH="$(manifest_hash)"
TARGET_MANIFEST_NAME="$(manifest_name)"

if [[ -z "$REQUESTED_RUN_DIR" ]]; then
  TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  REQUESTED_RUN_DIR="$OUTPUT_PARENT/${RUN_PREFIX}_${TIMESTAMP}"
elif [[ "$REQUESTED_RUN_DIR" != /* ]]; then
  REQUESTED_RUN_DIR="$ROOT/$REQUESTED_RUN_DIR"
fi
RUN_DIR="$(prepare_run_dir "$REQUESTED_RUN_DIR" "$TARGET_MANIFEST_HASH")"
printf '%s\n' "$RUN_DIR" > "$STATE_FILE"

if [[ "$MODE" == "background" ]]; then
  if ! command -v caffeinate >/dev/null 2>&1; then
    printf 'caffeinate is required for --background mode\n' >&2
    exit 2
  fi
  LAUNCHER_LOG="$RUN_DIR/launcher.log"
  nohup caffeinate -dimsu \
    bash "$ROOT/scripts/run_mab_post_fix_targeted.sh" \
    --manifest "$MANIFEST" --run-dir "$RUN_DIR" \
    > "$LAUNCHER_LOG" 2>&1 &
  LAUNCHER_PID=$!
  printf '%s\n' "$LAUNCHER_PID" > "$RUN_DIR/pid"
  printf 'Run directory: %s\n' "$RUN_DIR"
  printf 'PID: %s\n' "$LAUNCHER_PID"
  printf 'Launcher log: %s\n' "$LAUNCHER_LOG"
  printf 'Check process: ps -p %s -o pid=,stat=,etime=,command=\n' "$LAUNCHER_PID"
  printf 'Follow launcher: tail -f %q\n' "$LAUNCHER_LOG"
  printf 'Follow run log: tail -f %q\n' "$RUN_DIR/run.log"
  printf 'Check status: cat %q\n' "$RUN_DIR/status.env"
  exit 0
fi

LOG_FILE="$RUN_DIR/run.log"
STATUS_FILE="$RUN_DIR/status.env"
COMMAND_FILE="$RUN_DIR/command.txt"
START_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
COMMIT="$(git rev-parse HEAD)"

write_status() {
  local finish_ts="$1"
  local exit_status="$2"
  local marker="$3"
  {
    printf 'START_TS=%q\n' "$START_TS"
    printf 'FINISH_TS=%q\n' "$finish_ts"
    printf 'EXIT_STATUS=%q\n' "$exit_status"
    printf 'RUN_DIR=%q\n' "$RUN_DIR"
    printf 'BRANCH=%q\n' "$BRANCH"
    printf 'COMMIT=%q\n' "$COMMIT"
    printf 'MANIFEST_PATH=%q\n' "$MANIFEST"
    printf 'MANIFEST_NAME=%q\n' "$TARGET_MANIFEST_NAME"
    printf 'MANIFEST_HASH=%q\n' "$TARGET_MANIFEST_HASH"
    printf 'FINAL_MARKER=%q\n' "$marker"
  } > "$STATUS_FILE"
}

cleanup() {
  local exit_code=$?
  local finish_ts
  local marker="RUN_FAILED"
  finish_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [[ $exit_code -eq 0 ]]; then
    marker="RUN_COMPLETED"
  fi
  write_status "$finish_ts" "$exit_code" "$marker"
  printf '%s\n' "$marker"
  exit "$exit_code"
}
trap cleanup EXIT

write_status "" "" "RUNNING"

COMMAND=(
  uv run python -m evals.mab_answer_eval
  --manifest "$MANIFEST"
  --execution-mode graph
  --output-dir "$RUN_DIR"
  --answer-model "$ANSWER_MODEL"
  --judge-model "$JUDGE_MODEL"
  --resume
)
printf '%q ' "${COMMAND[@]}" > "$COMMAND_FILE"
printf '\n' >> "$COMMAND_FILE"

exec > >(tee -a "$LOG_FILE") 2>&1

printf 'Run directory: %s\n' "$RUN_DIR"
printf 'Manifest: %s\n' "$MANIFEST"
printf 'Branch: %s\n' "$BRANCH"
printf 'Commit: %s\n' "$COMMIT"
printf 'Start: %s\n' "$START_TS"
print_env_presence \
  OPENAI_API_KEY \
  OPENAI_BASE_URL \
  ANSWER_MODEL \
  JUDGE_API_KEY \
  JUDGE_MODEL \
  JUDGE_BASE_URL \
  HF_TOKEN

"${COMMAND[@]}"
