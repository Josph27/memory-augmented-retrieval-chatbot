from __future__ import annotations

import json
from pathlib import Path

from evals.generated_answer.run_generated_answer_eval import (
    DEFAULT_DATASET,
    load_jsonl,
    load_replay_answers,
    report_payload,
    run_case,
    run_cases,
    score_case,
    summarize_results,
    write_report,
)


class FakeAnswerGenerator:
    """Deterministic answer generator for model-mode dispatch tests."""

    model_name = "fake-eval-model"

    def generate(self, question: str, contexts: list[str]) -> str:
        del question, contexts
        return "The answer is SQLite."


def test_generated_answer_dataset_loads_adapter_ready_cases() -> None:
    cases = load_jsonl(DEFAULT_DATASET)

    assert len(cases) == 8
    assert {case["task_type"] for case in cases} >= {
        "document_qa",
        "structured_memory_semantic",
        "episodic_gist",
        "raw_span_provenance",
        "memory_update_conflict",
        "abstain",
    }
    assert all("benchmark_name" in case for case in cases)


def test_mock_eval_passes_controlled_dataset() -> None:
    results = run_cases(load_jsonl(DEFAULT_DATASET), mode="mock")
    summary = summarize_results(results)

    assert summary["total_cases"] == 8
    assert summary["answer_contains_expected"] == 1.0
    assert summary["forbidden_claim_violations"] == 0
    assert summary["abstain_accuracy"] == 1.0
    assert summary["expected_source_used"] == 1.0
    assert summary["retrieved_context_used"] == 1.0
    assert summary["overall_case_pass_rate"] == 1.0
    assert summary["failed_case_ids"] == []


def test_abstain_case_requires_unknown_answer() -> None:
    case = next(
        case
        for case in load_jsonl(DEFAULT_DATASET)
        if case["case_id"] == "abstain_no_relevant_memory"
    )

    result = run_case(case, mode="mock")

    assert result.abstain_correct is True
    assert result.expected_source_used is True
    assert result.retrieved_context_used is True
    assert result.overall_case_pass is True


def test_forbidden_claim_is_reported() -> None:
    case = {
        "case_id": "forbidden",
        "task_type": "document_qa",
        "query": "Which backend?",
        "expected_sources": ["document_memory"],
        "expected_answer_contains": ["Chroma"],
        "forbidden_answer_contains": ["FAISS"],
        "should_abstain": False,
    }
    contexts = [
        {
            "source": "document_memory",
            "content": "Chroma is the preferred backend.",
            "metadata": {},
        }
    ]

    result = score_case(
        case,
        answer="Chroma is preferred, but FAISS is required.",
        contexts=contexts,
        mode="replay",
    )

    assert result.forbidden_claim_violations == ["FAISS"]
    assert "forbidden_claim_present" in result.failed_reasons
    assert result.overall_case_pass is False


def test_model_mode_uses_injected_fake_generator() -> None:
    case = {
        "case_id": "fake-model",
        "task_type": "document_qa",
        "query": "Which database?",
        "setup_fixture": {
            "retrieved_contexts": [
                {"source": "document_memory", "content": "The answer is SQLite."}
            ]
        },
        "expected_sources": ["document_memory"],
        "expected_answer_contains": ["SQLite"],
        "forbidden_answer_contains": [],
        "should_abstain": False,
    }

    result = run_case(
        case,
        mode="model",
        answer_generator=FakeAnswerGenerator(),
    )

    assert result.answer == "The answer is SQLite."
    assert result.overall_case_pass is True


def test_replay_answers_and_report_export(tmp_path: Path) -> None:
    answers_path = tmp_path / "answers.jsonl"
    answers_path.write_text(
        json.dumps({"case_id": "replay-case", "answer": "Use SQLite."}) + "\n",
        encoding="utf-8",
    )
    replay_answers = load_replay_answers(answers_path)
    case = {
        "case_id": "replay-case",
        "task_type": "structured_memory_exact",
        "query": "Which database?",
        "setup_fixture": {
            "retrieved_contexts": [
                {"source": "structured_memory", "content": "Use SQLite."}
            ]
        },
        "expected_sources": ["structured_memory"],
        "expected_answer_contains": ["SQLite"],
        "forbidden_answer_contains": [],
        "should_abstain": False,
    }
    result = run_case(case, mode="replay", replay_answers=replay_answers)
    payload = report_payload([result], mode="replay")
    report_path = tmp_path / "report.json"

    write_report(report_path, payload)
    parsed = json.loads(report_path.read_text(encoding="utf-8"))

    assert parsed["eval_name"] == "generated_answer_memory_rag"
    assert parsed["mode"] == "replay"
    assert parsed["summary"]["overall_case_pass_rate"] == 1.0
    assert parsed["cases"][0]["trace"]["retrieved_contexts"][0]["source"] == (
        "structured_memory"
    )
