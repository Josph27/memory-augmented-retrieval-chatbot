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
    build_eval_resources,
    evaluate_case,
)


def make_result(
    case_id: str,
    answer_anchor_match: bool = True,
    expected_answer_match: bool = True,
    context_evidence_hit: bool = True,
    context_answer_anchor_hit: bool = True,
    context_expected_answer_hit: bool = True,
) -> EvalResult:
    """Build a deterministic document QA eval result."""
    return EvalResult(
        case_id=case_id,
        answer_anchor_match=answer_anchor_match,
        expected_answer_match=expected_answer_match,
        context_evidence_hit=context_evidence_hit,
        context_answer_anchor_hit=context_answer_anchor_hit,
        context_expected_answer_hit=context_expected_answer_hit,
        ragas_row={},
    )


def test_aggregate_mode_results_computes_rates_and_failed_cases() -> None:
    result = aggregate_mode_results(
        mode="keyword_retrieval",
        results=[
            make_result("case-1"),
            make_result("case-2", context_evidence_hit=False),
        ],
    )

    assert result.mode == "keyword_retrieval"
    assert result.total_cases == 2
    assert result.answer_anchor_match_rate == 1.0
    assert result.expected_answer_match_rate == 1.0
    assert result.context_evidence_hit_rate == 0.5
    assert result.context_answer_anchor_hit_rate == 1.0
    assert result.context_expected_answer_hit_rate == 1.0
    assert result.failed_case_ids == ["case-2"]
    assert not result.skipped


def test_comparison_row_marks_skipped_mode_with_reason() -> None:
    result = ModeComparisonResult(
        mode="vector_retrieval",
        total_cases=3,
        answer_anchor_match_rate=0.0,
        expected_answer_match_rate=0.0,
        context_evidence_hit_rate=0.0,
        context_answer_anchor_hit_rate=0.0,
        context_expected_answer_hit_rate=0.0,
        skipped=True,
        failed_case_ids=[],
        unavailable_reason="sentence-transformers is unavailable",
    )

    row = comparison_row(result)

    assert row[0] == "vector_retrieval"
    assert row[7] == "yes"
    assert "sentence-transformers" in row[9]


def test_format_row_uses_fixed_width_columns() -> None:
    row = format_row(["mode", "1"], [8, 5])

    assert row == "mode     | 1    "


def test_result_to_dict_is_json_ready() -> None:
    result = ModeComparisonResult(
        mode="hybrid_retrieval",
        total_cases=1,
        answer_anchor_match_rate=1.0,
        expected_answer_match_rate=1.0,
        context_evidence_hit_rate=1.0,
        context_answer_anchor_hit_rate=1.0,
        context_expected_answer_hit_rate=1.0,
        skipped=False,
        failed_case_ids=[],
    )

    payload = result_to_dict(result)

    assert payload["mode"] == "hybrid_retrieval"
    assert payload["context_evidence_hit_rate"] == 1.0
    assert payload["context_expected_answer_hit_rate"] == 1.0
    assert payload["failed_case_ids"] == []


def test_corpus_scope_retrieves_relevant_document_with_distractors() -> None:
    cases = [
        {
            "case_id": "relevant",
            "source": "test",
            "document_id": "doc-relevant",
            "document_text": "The Luminara protocol stores the sapphire deployment key.",
            "question": "Which protocol stores the sapphire deployment key?",
            "expected_answer": "Luminara",
            "supporting_evidence": "The Luminara protocol stores the sapphire deployment key.",
            "answer_anchor": "Luminara",
            "category": "synthetic",
        },
        {
            "case_id": "distractor-1",
            "source": "test",
            "document_id": "doc-distractor-1",
            "document_text": "The Harbor checklist describes routine office access.",
            "question": "What does the Harbor checklist describe?",
            "expected_answer": "routine office access",
            "supporting_evidence": "The Harbor checklist describes routine office access.",
            "answer_anchor": "routine office access",
            "category": "synthetic",
        },
        {
            "case_id": "distractor-2",
            "source": "test",
            "document_id": "doc-distractor-2",
            "document_text": "The Atlas note discusses cafeteria maintenance.",
            "question": "What does the Atlas note discuss?",
            "expected_answer": "cafeteria maintenance",
            "supporting_evidence": "The Atlas note discusses cafeteria maintenance.",
            "answer_anchor": "cafeteria maintenance",
            "category": "synthetic",
        },
    ]
    resources = build_eval_resources(
        context_mode="keyword_retrieval",
        retrieval_scope="corpus",
        cases=cases,
    )

    result = evaluate_case(
        cases[0],
        context_mode="keyword_retrieval",
        top_k=1,
        resources=resources,
        retrieval_scope="corpus",
    )

    assert result.context_answer_anchor_hit
    assert result.context_expected_answer_hit
    assert result.context_evidence_hit
