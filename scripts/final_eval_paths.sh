#!/usr/bin/env bash

final_eval_new_run_dir() {
  local parent="$1"
  local prefix="$2"
  local timestamp
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  printf '%s/%s_%s_%s\n' "$parent" "$prefix" "$timestamp" "$$"
}

final_eval_create_fresh_dir() {
  local run_dir="$1"
  local marker_name="$2"
  if [[ -e "$run_dir" ]]; then
    printf 'refusing to reuse existing run directory: %s\n' "$run_dir" >&2
    return 1
  fi
  mkdir "$run_dir"
  : > "$run_dir/$marker_name"
}

final_eval_require_incomplete_answer_run() {
  local run_dir="$1"
  local marker_name="$2"
  local status_file="$run_dir/meta/status.env"
  if [[ ! -d "$run_dir" ]]; then
    printf 'resume directory does not exist: %s\n' "$run_dir" >&2
    return 1
  fi
  if [[ ! -f "$run_dir/$marker_name" && \
        ! -d "$run_dir/mab" && \
        ! -d "$run_dir/longmemeval" ]]; then
    printf 'directory is not a compatible final answer run: %s\n' "$run_dir" >&2
    return 1
  fi
  if [[ -f "$status_file" ]] && \
     grep -Eq '^FINAL_MARKER=(RUN_COMPLETED|\"RUN_COMPLETED\")$' "$status_file"; then
    printf 'refusing to resume completed answer run: %s\n' "$run_dir" >&2
    return 1
  fi
}
