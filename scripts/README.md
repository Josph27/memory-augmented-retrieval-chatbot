# Operational scripts

Paths below identify entry points, not shell commands. From the repository root, invoke Python files with `uv run python <path>` and shell files with `bash <path>` unless the individual script says otherwise. Inspect `--help` where supported. Commands that inspect or modify data operate on the configured local stores: use a backup and an appropriate isolated environment when needed.

| Task | Entry point | Notes |
|---|---|---|
| Safe automated checks | `python3 scripts/run_isolated_tests.py --group offline-unit --label local --timeout 300` | See [isolation and all groups](../docs/audit/stage5/INFRASTRUCTURE.md); plain pytest collection is blocked. |
| Index a document | `scripts/index_document_file.py` | Writes the configured document index. |
| Inspect documents or memories | `scripts/inspect_document_memory.py`, `scripts/inspect_long_term_memory.py`, `scripts/inspect_raw_message_span.py` | Reads configured local stores. |
| Inspect a benchmark | `scripts/inspect_mab_context_case.py`, `scripts/inspect_eval_run.sh` | Reads existing evaluation outputs and, where applicable, local stores. |
| Rebuild previous-chat gists | `scripts/rebuild_previous_chat_gists.py` | Modifies persisted data; back up and inspect options first. |
| Rebuild structured-memory vector index | `scripts/rebuild_long_term_memory_index.py` | **Currently broken**; do not use as a recovery command. |
| Evaluation and validation | `scripts/eval_memory.py`, `scripts/validate_final_answer_run.py`, `scripts/run_final_52.sh`, `scripts/run_final_judge.sh`, `scripts/run_final_52_and_judge.sh`, `scripts/run_mab_post_fix_targeted.sh` | Some invoke models or judges and can incur cost. Read each command and [evaluation guide](../docs/EVALUATION.md) before running. |
| Diagnostic | `scripts/verify_natural_long_term_memory_flow.py`, `scripts/token_monitor.py` | Check each script's requirements before running. |

The shell evaluation wrappers use `scripts/lib/load_eval_env.sh` and `scripts/final_eval_paths.sh`; preserve their relative locations. Historical runs and generated output are evidence, not default commands.
