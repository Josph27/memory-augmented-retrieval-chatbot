from __future__ import annotations

from evals.document_qa.compare_retrieval_modes import (
    ModeComparisonResult,
    aggregate_mode_results,
    comparison_row,
    format_row,
    result_to_dict,
)
from evals.document_qa.run_document_qa_eval import (
    EvalResult,
    EvalResources,
    evaluate_case,
)


def make_result(
    case_id: str,
    answer_anchor_match: bool = True,
    expected_answer_match: bool = True,
    context_evidence_hit: bool = True,
    context_answer_anchor_hit: bool = True,
    context_expected_answer_hit: bool = True,
    answer: str = "answer",
    answer_mode: str = "oracle",
    answer_unknown: bool = False,
) -> EvalResult:
    """Build a deterministic document QA eval result."""
    return EvalResult(
        case_id=case_id,
        answer_anchor_match=answer_anchor_match,
        expected_answer_match=expected_answer_match,
        context_evidence_hit=context_evidence_hit,
        context_answer_anchor_hit=context_answer_anchor_hit,
        context_expected_answer_hit=context_expected_answer_hit,
        answer=answer,
        answer_mode=answer_mode,
        model_name=None,
        answer_unknown=answer_unknown,
        ragas_row={},
    )


def test_aggregate_mode_results_computes_rates_and_failed_cases() -> None:
    result = aggregate_mode_results(
        mode="langchain_chroma",
        results=[
            make_result("case-1"),
            make_result("case-2", context_evidence_hit=False),
        ],
    )

    assert result.mode == "langchain_chroma"
    assert result.total_cases == 2
    assert result.answer_anchor_match_rate == 1.0
    assert result.expected_answer_match_rate == 1.0
    assert result.context_evidence_hit_rate == 0.5
    assert result.context_answer_anchor_hit_rate == 1.0
    assert result.context_expected_answer_hit_rate == 1.0
    assert result.answer_mode == "oracle"
    assert result.answer_unknown_rate == 0.0
    assert result.failed_case_ids == ["case-2"]
    assert not result.skipped


def test_comparison_row_marks_skipped_mode_with_reason() -> None:
    result = ModeComparisonResult(
        mode="langchain_chroma",
        total_cases=3,
        answer_anchor_match_rate=0.0,
        expected_answer_match_rate=0.0,
        context_evidence_hit_rate=0.0,
        context_answer_anchor_hit_rate=0.0,
        context_expected_answer_hit_rate=0.0,
        answer_mode="model",
        model_name="test-model",
        answer_unknown_rate=0.0,
        skipped=True,
        failed_case_ids=[],
        unknown_case_ids=[],
        unavailable_reason="LangChain-Chroma is unavailable",
    )

    row = comparison_row(result)

    assert row[0] == "langchain_chroma"
    assert row[1] == "model"
    assert row[9] == "yes"
    assert "LangChain-Chroma" in row[11]


def test_format_row_uses_fixed_width_columns() -> None:
    row = format_row(["mode", "1"], [8, 5])

    assert row == "mode     | 1    "


def test_result_to_dict_is_json_ready() -> None:
    result = ModeComparisonResult(
        mode="langchain_chroma",
        total_cases=1,
        answer_anchor_match_rate=1.0,
        expected_answer_match_rate=1.0,
        context_evidence_hit_rate=1.0,
        context_answer_anchor_hit_rate=1.0,
        context_expected_answer_hit_rate=1.0,
        answer_mode="oracle",
        model_name=None,
        answer_unknown_rate=0.0,
        skipped=False,
        failed_case_ids=[],
        unknown_case_ids=[],
    )

    payload = result_to_dict(result)

    assert payload["mode"] == "langchain_chroma"
    assert payload["answer_mode"] == "oracle"
    assert payload["context_evidence_hit_rate"] == 1.0
    assert payload["context_expected_answer_hit_rate"] == 1.0
    assert payload["failed_case_ids"] == []


class FakeAnswerGenerator:
    @property
    def model_name(self) -> str:
        return "fake-answer-model"

    def generate(self, question: str, contexts: list[str]) -> str:
        del question, contexts
        return "Luminara"


def test_model_answer_mode_uses_answer_generator() -> None:
    case = {
        "case_id": "answer-case",
        "source": "test",
        "document_id": "doc-answer",
        "document_text": "The Luminara protocol stores the key.",
        "question": "Which protocol stores the key?",
        "expected_answer": "Luminara",
        "supporting_evidence": "The Luminara protocol stores the key.",
        "answer_anchor": "Luminara",
        "category": "synthetic",
    }
    resources = EvalResources(
        answer_generator=FakeAnswerGenerator(),
        answer_mode="model",
        model_name="fake-answer-model",
    )

    result = evaluate_case(
        case,
        context_mode="document_text",
        resources=resources,
        answer_mode="model",
    )

    assert result.answer == "Luminara"
    assert result.answer_mode == "model"
    assert result.model_name == "fake-answer-model"
    assert result.answer_anchor_match
    assert result.expected_answer_match
