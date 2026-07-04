from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_mab_post_fix_targeted.sh"
MANIFEST = ROOT / "evals" / "manifests" / "mab_context_pipeline_targeted_v1.json"


def check_environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(
        {
            "OPENAI_API_KEY": "test-answer-key",
            "OPENAI_BASE_URL": "https://example.invalid/v1",
            "ANSWER_MODEL": "test-answer-model",
            "JUDGE_API_KEY": "test-judge-key",
            "JUDGE_MODEL": "test-judge-model",
        }
    )
    return environment


@pytest.mark.parametrize(
    "arguments",
    (
        ("--check", "--manifest", str(MANIFEST)),
        ("--manifest", str(MANIFEST), "--check"),
    ),
)
def test_targeted_wrapper_accepts_manifest_in_either_order(
    arguments: tuple[str, ...],
) -> None:
    completed = subprocess.run(
        ["bash", str(SCRIPT), *arguments],
        cwd=ROOT,
        env=check_environment(),
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    assert "CONFIG_CHECK_OK" in completed.stdout
    assert f"TARGET_MANIFEST_PATH: {MANIFEST}" in completed.stdout
    assert "test-answer-key" not in completed.stdout + completed.stderr
    assert "test-judge-key" not in completed.stdout + completed.stderr


def test_targeted_wrapper_rejects_unknown_arguments() -> None:
    completed = subprocess.run(
        ["bash", str(SCRIPT), "--unsupported"],
        cwd=ROOT,
        env=check_environment(),
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 2
    assert "unknown argument: --unsupported" in completed.stderr
