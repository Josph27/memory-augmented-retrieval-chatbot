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
from evals.longmemeval_adapter.span_retriever import (
    LongMemEvalMessageSpanRetriever,
    seed_message_spans,
)
from src.core.contracts import SourcePlan
from src.database import Database


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


def test_loader_preserves_parallel_official_session_ids() -> None:
    case = normalize_record(
        {
            "question_id": "official-shape",
            "question": "What was discussed?",
            "answer": "testing",
            "haystack_session_ids": ["session-real-id"],
            "haystack_dates": ["2026-01-01"],
            "haystack_sessions": [
                [{"role": "user", "content": "We discussed testing."}]
            ],
            "answer_session_ids": ["session-real-id"],
        }
    )

    assert case.sessions[0].session_id == "session-real-id"
    assert case.sessions[0].metadata["date"] == "2026-01-01"
    assert case.metadata["answer_session_ids"] == ["session-real-id"]


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
        "previous_chat_gist",
        "raw_message_span",
    ]
    assert "raw_message_span" in report["cases"][0]["retrieved_sources"]
    assert report["cases"][0]["context_included"] is True
    assert report["summary"]["context_inclusion_rate"] == 1.0
    assert report["summary"]["average_context_candidates_included"] > 0
    assert report["summary"]["cases_with_empty_context"] == []
    assert report["summary"]["retrieved_source_counts"]["raw_message_span"] >= 1
    assert report["summary"]["reranker_mode"] == "deterministic"
    assert report["summary"]["cross_encoder_used_count"] == 0
    assert report["summary"]["average_retrieved_candidates"] > 0
    assert report["summary"]["answer_i_dont_know_rate"] == 0.5


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


def test_session_history_is_split_into_provenance_spans(tmp_path: Path) -> None:
    case = load_longmemeval_cases(FIXTURE, limit=1)[0]
    database = Database(tmp_path / "spans.db")

    spans = seed_message_spans(
        database,
        case,
        max_messages=1,
        max_chars=300,
        overlap_messages=0,
    )

    assert len(spans) == 2
    assert spans[0].session_id == "session-1"
    assert spans[0].start_message_id == spans[0].end_message_id
    assert spans[0].message_count == 1
    assert spans[0].case_id == "tiny-preference"


def test_span_retrieval_finds_fixture_fact(tmp_path: Path) -> None:
    case = load_longmemeval_cases(FIXTURE, limit=1)[0]
    database = Database(tmp_path / "retrieve.db")
    spans = seed_message_spans(database, case, max_messages=1)

    candidates = LongMemEvalMessageSpanRetriever(spans).retrieve(
        chat_id="current",
        source_plan=SourcePlan(
            source="raw_message_span",
            query="Which solarized editor theme does the user prefer?",
            limit=2,
        ),
    )

    assert candidates
    assert candidates[0].source == "raw_message_span"
    assert "solarized dark" in candidates[0].content
    assert candidates[0].metadata["session_id"] == "session-1"
    assert candidates[0].metadata["start_message_id"]
    assert candidates[0].metadata["end_message_id"]


def test_span_retrieval_mode_uses_raw_message_candidates() -> None:
    report = run_adapter(
        load_longmemeval_cases(FIXTURE, limit=1),
        memory_mode="span_retrieval",
        answer_mode="mock",
    )

    case = report["cases"][0]
    assert case["retrieved_sources"] == ["raw_message_span"]
    assert case["context_packet_sources"] == ["raw_message_span"]
    assert case["query_echo_excluded"] is True
