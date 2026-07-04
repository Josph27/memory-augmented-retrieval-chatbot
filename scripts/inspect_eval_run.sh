#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
STATE_FILE="$ROOT/artifacts/eval_runs/final_52_lifecycle_v2_current_path.txt"

if [[ $# -gt 1 ]]; then
  echo "usage: $0 [answer-run-dir]" >&2
  exit 2
fi

if [[ $# -eq 1 ]]; then
  RUN_DIR="$1"
elif [[ -f "$STATE_FILE" ]]; then
  RUN_DIR="$(<"$STATE_FILE")"
else
  echo "no existing answer-run state file found at $STATE_FILE" >&2
  exit 2
fi

if [[ ! -d "$RUN_DIR" ]]; then
  echo "answer run directory does not exist: $RUN_DIR" >&2
  exit 2
fi

LOG_FILE="$RUN_DIR/logs/run_final_52.log"
STATUS_FILE="$RUN_DIR/meta/status.env"
RESULTS_MAB="$RUN_DIR/mab/results.jsonl"
RESULTS_LONG="$RUN_DIR/longmemeval/results.jsonl"

echo "RUN_DIR: $RUN_DIR"
echo "RESULTS_MAB: $RESULTS_MAB"
echo "RESULTS_LONG: $RESULTS_LONG"

if [[ -f "$STATUS_FILE" ]]; then
  echo
  echo "STATUS_FILE: $STATUS_FILE"
  sed -n '1,120p' "$STATUS_FILE"
else
  echo
  echo "STATUS_FILE: missing"
fi

if [[ -f "$LOG_FILE" ]]; then
  echo
  echo "LOG_FILE: $LOG_FILE"
else
  echo
  echo "LOG_FILE: missing"
fi

echo
python3 - <<'PY' "$RUN_DIR"
from __future__ import annotations

import json
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
files = {
    "mab": run_dir / "mab" / "results.jsonl",
    "longmemeval": run_dir / "longmemeval" / "results.jsonl",
}
expected = {"mab": 33, "longmemeval": 19}

latest_completed = None
totals = {"completed": 0, "expected": 0}

for name, path in files.items():
    rows: list[dict] = []
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
    latest_by_identity: dict[str, dict] = {}
    for row in rows:
        identity = str(row.get("result_identity") or "")
        if identity:
            latest_by_identity[identity] = row
    latest_rows = list(latest_by_identity.values())
    completed = [
        row for row in latest_rows
        if row.get("status") in {"answer_completed", "completed"}
        and row.get("generated_answer") is not None
    ]
    totals["completed"] += len(completed)
    totals["expected"] += expected[name]
    last = completed[-1] if completed else None
    if last is not None:
        latest_completed = {
            "dataset_group": name,
            "case_id": last.get("case_id"),
            "status": last.get("status"),
            "official_metric": last.get("official_metric"),
        }
    print(f"{name.upper()}_COMPLETED={len(completed)}")
    print(f"{name.upper()}_EXPECTED={expected[name]}")

print(f"TOTAL_COMPLETED={totals['completed']}")
print(f"TOTAL_EXPECTED={totals['expected']}")
if latest_completed is None:
    print("LATEST_COMPLETED_CASE=none")
else:
    print("LATEST_COMPLETED_CASE=" + json.dumps(latest_completed, ensure_ascii=True))
PY

echo
if [[ -f "$LOG_FILE" ]]; then
  echo "MOST_RECENT_ERROR_LINES:"
  grep -nE 'Traceback|ERROR|Error|RUN_FAILED|exception' "$LOG_FILE" | tail -n 20 || true
fi

echo
echo "DISK_USAGE:"
du -sh "$RUN_DIR" "$RUN_DIR/mab" "$RUN_DIR/longmemeval" 2>/dev/null || true
