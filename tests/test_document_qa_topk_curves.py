from __future__ import annotations

from evals.document_qa.compare_retrieval_modes import ModeComparisonResult
from evals.document_qa.compare_topk_curves import (
    TopKCurveResult,
    backend_for_mode,
    evaluate_topk_curves,
    normalized_top_k_values,
    result_to_dict,
    topk_result_from_comparison,
    topk_row,
)


def make_comparison(mode: str) -> ModeComparisonResult:
    """Build one deterministic comparison row."""
    return ModeComparisonResult(
        mode=mode,
        total_cases=3,
        answer_anchor_match_rate=1.0,
        expected_answer_match_rate=1.0,
        context_evidence_hit_rate=0.5,
        context_answer_anchor_hit_rate=0.75,
        context_expected_answer_hit_rate=0.8,
        answer_mode="oracle",
        model_name=None,
        answer_unknown_rate=0.0,
        skipped=False,
        failed_case_ids=["case-2"],
        unknown_case_ids=[],
    )


def test_normalized_top_k_values_keeps_positive_unique_values() -> None:
    assert normalized_top_k_values([1, 3, 3, 0, -1, 5]) == [1, 3, 5]


def test_topk_result_from_comparison_copies_retrieval_metrics() -> None:
    result = topk_result_from_comparison(
        comparison=make_comparison("vector_retrieval"),
        top_k=5,
        backend="sqlite_vec",
    )

    assert result.mode == "vector_retrieval"
    assert result.backend == "sqlite_vec"
    assert result.k == 5
    assert result.cases == 3
    assert result.context_evidence_hit_rate == 0.5
    assert result.context_answer_anchor_hit_rate == 0.75
    assert result.context_expected_answer_hit_rate == 0.8
    assert result.failed_case_ids == ["case-2"]


def test_backend_for_mode_only_labels_vector_modes() -> None:
    assert backend_for_mode("keyword_retrieval", "sqlite_vec") == "-"
    assert backend_for_mode("vector_retrieval", "sqlite_vec") == "sqlite_vec"
    assert backend_for_mode("hybrid_retrieval", "sqlite_vec") == "sqlite_vec"


def test_topk_row_and_json_output_are_stable() -> None:
    result = TopKCurveResult(
        mode="keyword_retrieval",
        backend="-",
        k=3,
        cases=4,
        context_evidence_hit_rate=0.25,
        context_answer_anchor_hit_rate=0.5,
        context_expected_answer_hit_rate=0.75,
        skipped=False,
        failed_case_ids=["case-1"],
    )

    assert topk_row(result) == [
        "keyword_retrieval",
        "-",
        "3",
        "4",
        "0.25",
        "0.50",
        "0.75",
        "no",
        "",
    ]
    assert result_to_dict(result)["context_expected_answer_hit_rate"] == 0.75


def test_evaluate_topk_curves_aggregates_modes_and_k_values(monkeypatch) -> None:
    calls = []

    def fake_evaluate_mode(**kwargs):
        calls.append(kwargs)
        return make_comparison(kwargs["mode"])

    monkeypatch.setattr(
        "evals.document_qa.compare_topk_curves.evaluate_mode",
        fake_evaluate_mode,
    )

    results = evaluate_topk_curves(
        modes=["keyword_retrieval", "vector_retrieval"],
        cases=[{"case_id": "case-1"}],
        top_k_values=[1, 3],
        retrieval_scope="corpus",
        vector_backend="sqlite_json",
    )

    assert len(results) == 4
    assert [result.k for result in results] == [1, 3, 1, 3]
    assert calls[0]["top_k"] == 1
    assert calls[1]["top_k"] == 3
    assert calls[2]["mode"] == "vector_retrieval"
    assert calls[2]["vector_backend"] == "sqlite_json"
