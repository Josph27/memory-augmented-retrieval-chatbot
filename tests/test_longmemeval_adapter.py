from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.longmemeval_adapter.loader import (
    load_longmemeval_cases,
    normalize_record,
)
from evals.longmemeval_adapter.runner import run_adapter, write_report
from evals.longmemeval_adapter.scoring import score_case


FIXTURE = (
    Path(__file__).parents[1]
    / "evals"
    / "longmemeval_adapter"
    / "fixtures"
    / "tiny_longmemeval_sample.jsonl"
)


def test_fixture_loads_and_normalizes_common_fields() -> None:
    cases = load_longmemeval_cases(FIXTURE)

    assert len(cases) == 2
    assert cases[0].case_id == "tiny-preference"
    assert cases[0].question_type == "single-session-user"
    assert cases[0].sessions[0].messages[0].role == "user"
    assert cases[0].gold_answer == "solarized dark"


def test_schema_rejects_missing_history() -> None:
    with pytest.raises(ValueError, match="sessions/history"):
        normalize_record(
            {
                "case_id": "missing-history",
                "question": "What should be remembered?",
                "gold_answer": "a preference",
            }
        )


def test_limit_is_applied() -> None:
    cases = load_longmemeval_cases(FIXTURE, limit=1)

    assert [case.case_id for case in cases] == ["tiny-preference"]


def test_scoring_contains_exact_and_abstain() -> None:
    cases = load_longmemeval_cases(FIXTURE)

    preference = score_case(
        cases[0],
        answer="The answer is solarized dark.",
        retrieved_contents=["User prefers solarized dark."],
    )
    abstain = score_case(
        cases[1],
        answer="I don't know.",
        retrieved_contents=[],
    )

    assert preference.answer_contains_gold is True
    assert preference.answer_exact_gold is False
    assert preference.retrieval_hit is True
    assert preference.passed is True
    assert abstain.abstain_correct is True
    assert abstain.passed is True


def test_mock_runner_produces_report_without_live_model() -> None:
    report = run_adapter(
        load_longmemeval_cases(FIXTURE),
        memory_mode="full",
        answer_mode="mock",
    )

    assert report["eval_name"] == "longmemeval_pilot_adapter"
    assert report["memory_mode"] == "full"
    assert report["mode"] == "mock"
    assert report["summary"]["total_cases"] == 2
    assert report["summary"]["contains_gold_rate"] == 0.5
    assert report["summary"]["abstain_accuracy"] == 1.0
    assert report["summary"]["retrieval_hit_rate"] == 1.0
    assert report["cases"][0]["trace"]["active_sources"] == [
        "recent_messages",
        "previous_chat_gist",
    ]


def test_recent_only_report_and_json_export(tmp_path: Path) -> None:
    report = run_adapter(
        load_longmemeval_cases(FIXTURE, limit=1),
        memory_mode="recent_only",
        answer_mode="mock",
    )
    output = tmp_path / "report.json"
    write_report(output, report)
    saved = json.loads(output.read_text(encoding="utf-8"))

    assert saved["memory_mode"] == "recent_only"
    assert saved["summary"]["total_cases"] == 1
    assert "previous_chat_gist" not in saved["cases"][0]["retrieved_sources"]
