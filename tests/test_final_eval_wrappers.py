from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PATH_LIBRARY = ROOT / "scripts/final_eval_paths.sh"
ANSWER_SCRIPT = ROOT / "scripts/run_final_52.sh"
JUDGE_SCRIPT = ROOT / "scripts/run_final_judge.sh"
COMBINED_SCRIPT = ROOT / "scripts/run_final_52_and_judge.sh"


def run_bash(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def combined_environment(
    tmp_path: Path,
    answer_script: Path,
    judge_script: Path,
    validator: Path,
) -> dict[str, str]:
    return {
        **os.environ,
        "FINAL_EVAL_RUNS_ROOT": str(tmp_path / "runs"),
        "FINAL_EVAL_ANSWER_SCRIPT": str(answer_script),
        "FINAL_EVAL_JUDGE_SCRIPT": str(judge_script),
        "FINAL_EVAL_ANSWER_VALIDATOR": str(validator),
        "FINAL_EVAL_DISABLE_TEE": "1",
        "HF_HUB_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "UV_CACHE_DIR": str(ROOT / ".cache/uv"),
    }


def combined_status(tmp_path: Path) -> dict[str, str]:
    status_paths = list((tmp_path / "runs").glob("*/status.env"))
    assert len(status_paths) == 1
    return dict(
        line.split("=", maxsplit=1)
        for line in status_paths[0].read_text(encoding="utf-8").splitlines()
        if "=" in line
    )


def combined_log(tmp_path: Path) -> str:
    log_paths = list((tmp_path / "runs").glob("*/combined.log"))
    assert len(log_paths) == 1
    return log_paths[0].read_text(encoding="utf-8")


def test_fresh_run_directories_are_distinct_and_never_reused(
    tmp_path: Path,
) -> None:
    commands = (
        f"source {PATH_LIBRARY!s}; "
        f"path=$(final_eval_new_run_dir {tmp_path!s} final); "
        'final_eval_create_fresh_dir "$path" .marker; printf "%s" "$path"'
    )
    first = run_bash(commands)
    second = run_bash(commands)

    assert first.returncode == 0
    assert second.returncode == 0
    assert first.stdout != second.stdout
    assert Path(first.stdout).is_dir()
    assert Path(second.stdout).is_dir()
    reused = run_bash(
        f"source {PATH_LIBRARY!s}; "
        f"final_eval_create_fresh_dir {first.stdout} .marker"
    )
    assert reused.returncode != 0
    assert "refusing to reuse existing run directory" in reused.stderr


def test_explicit_resume_rejects_completed_or_unrelated_directories(
    tmp_path: Path,
) -> None:
    completed = tmp_path / "completed"
    (completed / "meta").mkdir(parents=True)
    (completed / ".final_52_answer_run").touch()
    (completed / "meta/status.env").write_text(
        "EXIT_STATUS=0\nFINAL_MARKER=RUN_COMPLETED\n",
        encoding="utf-8",
    )
    rejected = run_bash(
        f"source {PATH_LIBRARY!s}; "
        f"final_eval_require_incomplete_answer_run {completed!s} "
        ".final_52_answer_run"
    )
    assert rejected.returncode != 0
    assert "refusing to resume completed answer run" in rejected.stderr

    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    rejected = run_bash(
        f"source {PATH_LIBRARY!s}; "
        f"final_eval_require_incomplete_answer_run {unrelated!s} "
        ".final_52_answer_run"
    )
    assert rejected.returncode != 0
    assert "not a compatible final answer run" in rejected.stderr


def test_explicit_resume_accepts_only_incomplete_compatible_run(
    tmp_path: Path,
) -> None:
    incomplete = tmp_path / "incomplete"
    (incomplete / "meta").mkdir(parents=True)
    (incomplete / ".final_52_answer_run").touch()
    (incomplete / "meta/status.env").write_text(
        "EXIT_STATUS=130\nFINAL_MARKER=RUN_FAILED\n",
        encoding="utf-8",
    )
    accepted = run_bash(
        f"source {PATH_LIBRARY!s}; "
        f"final_eval_require_incomplete_answer_run {incomplete!s} "
        ".final_52_answer_run"
    )
    assert accepted.returncode == 0


def test_answer_wrapper_has_no_implicit_pointer_resume() -> None:
    text = ANSWER_SCRIPT.read_text(encoding="utf-8")
    assert 'elif [[ -f "$STATE_FILE" ]]' not in text
    assert 'RUN_DIR="$(<"$STATE_FILE")"' not in text
    assert "--run-dir" in text
    assert 'final_eval_create_fresh_dir "$RUN_DIR"' in text
    assert "RESUME_ARGS" not in text
    assert 'if [[ -n "$EXPLICIT_RESUME_DIR" ]]' in text
    assert 'printf \'%s\\n\' "$RUN_DIR" > "$STATE_FILE"' in text


def test_answer_wrapper_hf_defaults_and_check_mode_are_safe() -> None:
    text = ANSWER_SCRIPT.read_text(encoding="utf-8")
    assert 'export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-0}"' not in text
    assert 'export HF_DATASETS_OFFLINE="${HF_DATASETS_OFFLINE:-0}"' not in text
    assert 'export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-0}"' not in text
    assert text.count("enable_eval_online_mode") >= 3
    check_block = text[text.index('if [[ "$CHECK_ONLY" == true ]]') :]
    check_block = check_block[: check_block.index("\nfi\n") + 4]
    assert "HF_HUB_OFFLINE=1" in check_block
    assert "HF_DATASETS_OFFLINE=1" in check_block
    assert "TRANSFORMERS_OFFLINE=1" in check_block
    assert "CONFIG_CHECK_OK" in check_block
    assert "resolve_cases" not in check_block


def test_online_mode_unsets_offline_values_loaded_from_environment() -> None:
    helper = ROOT / "scripts/lib/load_eval_env.sh"
    result = run_bash(
        f"source {helper!s}; "
        "export HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 "
        "TRANSFORMERS_OFFLINE=1; "
        "enable_eval_online_mode; "
        "env | grep -E '^(HF_HUB_OFFLINE|HF_DATASETS_OFFLINE|"
        "TRANSFORMERS_OFFLINE)=' || true"
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_online_mode_prevents_python_from_reloading_offline_dotenv_values() -> None:
    helper = ROOT / "scripts/lib/load_eval_env.sh"
    code = (
        "import os; "
        "from dotenv import load_dotenv; "
        "load_dotenv(); "
        "names=('HF_HUB_OFFLINE','HF_DATASETS_OFFLINE',"
        "'TRANSFORMERS_OFFLINE'); "
        "assert all(name not in os.environ for name in names)"
    )
    result = run_bash(
        f"source {helper!s}; "
        "load_eval_env; "
        "enable_eval_online_mode; "
        f"{sys.executable} -c {code!r}"
    )
    assert result.returncode == 0, result.stderr


def test_combined_real_run_child_receives_offline_variables_unset(
    tmp_path: Path,
) -> None:
    answer = tmp_path / "answer.sh"
    judge = tmp_path / "judge.sh"
    validator = tmp_path / "validator.py"
    captured = tmp_path / "child-env.txt"
    write_executable(
        answer,
        f"""#!/usr/bin/env bash
env | grep -E '^(HF_HUB_OFFLINE|HF_DATASETS_OFFLINE|TRANSFORMERS_OFFLINE)=' > {captured!s} || true
exit 7
""",
    )
    write_executable(judge, "#!/usr/bin/env bash\nexit 99\n")
    validator.write_text("raise SystemExit(99)\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(COMBINED_SCRIPT)],
        cwd=ROOT,
        env=combined_environment(tmp_path, answer, judge, validator),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 7
    assert captured.read_text(encoding="utf-8") == ""


def write_complete_answer_run(path: Path) -> None:
    (path / "meta").mkdir(parents=True)
    (path / "mab").mkdir()
    (path / "longmemeval").mkdir()
    (path / "meta/status.env").write_text(
        "EXIT_STATUS=0\nFINAL_MARKER=RUN_COMPLETED\n",
        encoding="utf-8",
    )
    for name, manifest in (
        ("mab", ROOT / "evals/manifests/mab_answer_heldout_v1.yaml"),
        (
            "longmemeval",
            ROOT / "evals/manifests/longmemeval_answer_heldout_v1.yaml",
        ),
    ):
        cases = json.loads(manifest.read_text(encoding="utf-8"))["cases"]
        rows = [
            {
                "case_id": case["case_id"],
                "status": "answer_completed",
                "generated_answer": "cached",
                "answer_model": "answer-model",
            }
            for case in cases
        ]
        (path / name / "results.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )


def test_answer_run_validator_accepts_complete_and_rejects_incomplete(
    tmp_path: Path,
) -> None:
    complete = tmp_path / "complete"
    write_complete_answer_run(complete)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_final_answer_run.py"),
            "--answer-run-dir",
            str(complete),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(result.stdout)
    assert value["mab_answer_count"] == 33
    assert value["longmemeval_answer_count"] == 19
    assert value["answer_model"] == "answer-model"

    lines = (complete / "mab/results.jsonl").read_text(encoding="utf-8").splitlines()
    (complete / "mab/results.jsonl").write_text(
        "\n".join(lines[:-1]) + "\n",
        encoding="utf-8",
    )
    failed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_final_answer_run.py"),
            "--answer-run-dir",
            str(complete),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert failed.returncode != 0
    assert "incomplete mab answers" in failed.stderr


def test_judge_requires_exact_answer_path_and_writes_separate_copy() -> None:
    text = JUDGE_SCRIPT.read_text(encoding="utf-8")
    assert "ANSWER_STATE_FILE" not in text
    assert 'missing required argument: --answer-run-dir' in text
    assert '--answer-run-dir "$ANSWER_RUN_DIR"' in text
    assert 'cp -R "$ANSWER_RUN_DIR/mab" "$RUN_DIR/mab"' in text
    assert 'cp -R "$ANSWER_RUN_DIR/longmemeval" "$RUN_DIR/longmemeval"' not in text
    assert '--judge-only-answers "$ANSWER_RUN_DIR/longmemeval/results.jsonl"' in text
    assert '--output-dir "$RUN_DIR/mab"' in text
    assert '--output-dir "$RUN_DIR/longmemeval"' in text
    assert "--resume" in text


def test_combined_launcher_is_sequential_and_stops_on_answer_failure() -> None:
    text = COMBINED_SCRIPT.read_text(encoding="utf-8")
    runtime = text[text.index('set +e\nbash "$ANSWER_SCRIPT"') :]
    answer_call = 'bash "$ANSWER_SCRIPT" --path-file "$ANSWER_PATH_FILE"'
    validate_call = 'uv run python "$ANSWER_VALIDATOR"'
    judge_call = 'bash "$JUDGE_SCRIPT"'
    assert runtime.index(answer_call) < runtime.index(validate_call)
    assert runtime.index(validate_call) < runtime.index(judge_call)
    assert text.startswith("#!/usr/bin/env bash\nset -euo pipefail")
    assert 'if [[ "$ANSWER_RUN_DIR" == "$JUDGE_RUN_DIR" ]]' in text
    assert "--background" in text
    assert 'nohup caffeinate -dimsu bash "$0" --run-dir "$COMBINED_DIR"' in text


def test_combined_records_answer_failure_and_never_invokes_judge(
    tmp_path: Path,
) -> None:
    answer = tmp_path / "answer.sh"
    judge = tmp_path / "judge.sh"
    validator = tmp_path / "validator.py"
    judge_marker = tmp_path / "judge-called"
    write_executable(answer, "#!/usr/bin/env bash\nexit 7\n")
    write_executable(
        judge,
        f"#!/usr/bin/env bash\ntouch {judge_marker!s}\nexit 0\n",
    )
    validator.write_text("raise SystemExit(0)\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(COMBINED_SCRIPT)],
        cwd=ROOT,
        env=combined_environment(tmp_path, answer, judge, validator),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 7
    assert not judge_marker.exists()
    status = combined_status(tmp_path)
    assert status["FAILED_PHASE"] == "answer"
    assert status["SUBPROCESS_EXIT_CODE"] == "7"
    assert status["FINAL_MARKER"] == "RUN_FAILED"


def test_zero_exit_with_missing_results_fails_cleanly_without_judge(
    tmp_path: Path,
) -> None:
    answer = tmp_path / "answer.sh"
    judge = tmp_path / "judge.sh"
    judge_marker = tmp_path / "judge-called"
    answer_run = tmp_path / "answer-run"
    write_executable(
        answer,
        f"""#!/usr/bin/env bash
set -euo pipefail
path_file=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --path-file) path_file="$2"; shift 2 ;;
    *) shift ;;
  esac
done
mkdir -p {answer_run!s}/meta
printf 'EXIT_STATUS=0\\nFINAL_MARKER=RUN_COMPLETED\\n' > {answer_run!s}/meta/status.env
printf '%s\\n' {answer_run!s} > "$path_file"
""",
    )
    write_executable(
        judge,
        f"#!/usr/bin/env bash\ntouch {judge_marker!s}\nexit 0\n",
    )

    result = subprocess.run(
        ["bash", str(COMBINED_SCRIPT)],
        cwd=ROOT,
        env=combined_environment(
            tmp_path,
            answer,
            judge,
            ROOT / "scripts/validate_final_answer_run.py",
        ),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    log = combined_log(tmp_path)
    assert "answer-run validation failed: missing required results file:" in log
    assert "Traceback" not in log
    assert not judge_marker.exists()
    status = combined_status(tmp_path)
    assert status["FAILED_PHASE"] == "answer"
    assert "missing" in status["FAILURE_REASON"]


def test_combined_waits_for_answer_and_hands_exact_path_to_judge(
    tmp_path: Path,
) -> None:
    answer = tmp_path / "answer.sh"
    judge = tmp_path / "judge.sh"
    validator = tmp_path / "validator.py"
    answer_run = tmp_path / "slow-answer-run"
    handed_path = tmp_path / "handed-answer-path"
    write_executable(
        answer,
        f"""#!/usr/bin/env bash
set -euo pipefail
path_file=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --path-file) path_file="$2"; shift 2 ;;
    *) shift ;;
  esac
done
sleep 0.2
mkdir -p {answer_run!s}/meta
printf 'EXIT_STATUS=0\\nFINAL_MARKER=RUN_COMPLETED\\n' > {answer_run!s}/meta/status.env
touch {answer_run!s}/answer-finished
printf '%s\\n' {answer_run!s} > "$path_file"
""",
    )
    validator.write_text(
        f"""from pathlib import Path
if not Path({str(answer_run / "answer-finished")!r}).is_file():
    raise SystemExit(9)
""",
        encoding="utf-8",
    )
    write_executable(
        judge,
        f"""#!/usr/bin/env bash
set -euo pipefail
answer_dir=""
path_file=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --answer-run-dir) answer_dir="$2"; shift 2 ;;
    --path-file) path_file="$2"; shift 2 ;;
    *) shift ;;
  esac
done
printf '%s\\n' "$answer_dir" > {handed_path!s}
judge_dir={str(tmp_path / "judge-run")!s}
mkdir -p "$judge_dir"
printf '%s\\n' "$judge_dir" > "$path_file"
""",
    )

    result = subprocess.run(
        ["bash", str(COMBINED_SCRIPT)],
        cwd=ROOT,
        env=combined_environment(tmp_path, answer, judge, validator),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert handed_path.read_text(encoding="utf-8").strip() == str(answer_run)
    status = combined_status(tmp_path)
    assert status["ANSWER_RUN_DIR"] == str(answer_run)
    assert status["FINAL_MARKER"] == "RUN_COMPLETED"


def test_validator_missing_results_has_no_traceback(tmp_path: Path) -> None:
    answer_run = tmp_path / "answer-run"
    (answer_run / "meta").mkdir(parents=True)
    (answer_run / "meta/status.env").write_text(
        "EXIT_STATUS=0\nFINAL_MARKER=RUN_COMPLETED\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_final_answer_run.py"),
            "--answer-run-dir",
            str(answer_run),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "missing required results file" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        (ANSWER_SCRIPT, "unknown argument: --not-a-real-option"),
        (JUDGE_SCRIPT, "unknown argument: --not-a-real-option"),
        (COMBINED_SCRIPT, "unknown argument: --not-a-real-option"),
    ],
)
def test_unknown_arguments_fail_clearly(
    script: Path,
    expected: str,
) -> None:
    result = subprocess.run(
        ["bash", str(script), "--not-a-real-option"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert expected in result.stderr
