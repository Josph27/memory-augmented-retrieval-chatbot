#!/usr/bin/env bash
set -euo pipefail

LOAD_EVAL_ENV_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${LOAD_EVAL_ENV_DIR}/../.." && pwd)"

export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$REPO_ROOT/.cache/uv}"

eval_repo_root() {
  printf '%s\n' "$REPO_ROOT"
}

load_eval_env() {
  local env_file="$REPO_ROOT/.env"
  if [[ ! -f "$env_file" ]]; then
    return 0
  fi

  local export_file
  export_file="$(mktemp "${TMPDIR:-/tmp}/eval-env.XXXXXX")"
  uv run python - <<'PY' "$env_file" "$export_file"
from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

from dotenv import dotenv_values

env_path = Path(sys.argv[1])
export_path = Path(sys.argv[2])
values = dotenv_values(env_path)
lines: list[str] = []
for key, value in values.items():
    if not key or value is None:
        continue
    if key in os.environ:
        continue
    lines.append(f"export {key}={shlex.quote(value)}")
export_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
PY
  # shellcheck source=/dev/null
  source "$export_file"
  rm -f "$export_file"
}

enable_eval_online_mode() {
  unset HF_HUB_OFFLINE
  unset HF_DATASETS_OFFLINE
  unset TRANSFORMERS_OFFLINE
  export PYTHON_DOTENV_DISABLED=1
}

print_env_presence() {
  local name
  for name in "$@"; do
    if [[ -n "${!name:-}" ]]; then
      printf '%s: present\n' "$name"
    else
      printf '%s: MISSING\n' "$name"
    fi
  done
}

require_env_vars() {
  local missing=0
  local name
  for name in "$@"; do
    if [[ -z "${!name:-}" ]]; then
      printf 'missing required environment variable: %s\n' "$name" >&2
      missing=1
    fi
  done
  if [[ $missing -ne 0 ]]; then
    return 1
  fi
}

require_path_exists() {
  local path="$1"
  local label="${2:-path}"
  if [[ ! -e "$path" ]]; then
    printf 'missing required %s: %s\n' "$label" "$path" >&2
    return 1
  fi
}

require_dir_writable() {
  local path="$1"
  mkdir -p "$path"
  if [[ ! -w "$path" ]]; then
    printf 'directory is not writable: %s\n' "$path" >&2
    return 1
  fi
}

verify_repo_imports() {
  (
    cd "$REPO_ROOT"
    uv run python -c 'import evals'
  )
}
