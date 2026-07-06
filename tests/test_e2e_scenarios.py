from __future__ import annotations

import json
from pathlib import Path

from evals.e2e_scenarios.run_e2e_scenarios import (
    DEFAULT_DATASET,
    FakeAnswerModel,
    load_jsonl,
    report_payload,
    run_case,
    run_cases,
    summarize_results,
    write_report,
)


def test_e2e_scenario_dataset_loads_controlled_cases() -> None:
    cases = load_jsonl(DEFAULT_DATASET)

    assert len(cases) == 7
    assert {case["case_id"] for case in cases} >= {
        "document_question",
        "semantic_memory_paraphrase",
        "previous_chat_gist",
        "raw_span_provenance",
        "hybrid_reranker_ordering",
    }


def test_mock_e2e_document_scenario_runs_real_coordinator() -> None:
    case = next(
        case
        for case in load_jsonl(DEFAULT_DATASET)
        if case["case_id"] == "document_question"
    )

    result = run_case(case, mode="mock")

    assert result.scenario_pass is True
    assert result.expected_source_present is True
    assert result.expected_context_included is True
    assert result.reranker_top_source_correct is True
    assert result.answer_contains_expected is True
    assert result.trace["active_sources"] == [
        "recent_messages",
        "structured_memory",
        "document_memory",
    ]
    assert result.trace["workflow_metadata"]["routing_decision"]
    assert result.trace["workflow_metadata"]["reranker"]
    assert result.trace["workflow_metadata"]["context_manager"]


def test_e2e_abstain_scenario_avoids_forbidden_claims() -> None:
    case = next(
        case
        for case in load_jsonl(DEFAULT_DATASET)
        if case["case_id"] == "abstain_with_distractor"
    )

    result = run_case(case, mode="mock")

    assert result.abstain_correct is True
    assert result.forbidden_claim_violations == []
    assert result.scenario_pass is True


def test_model_mode_accepts_injected_fake_model_without_network() -> None:
    case = next(
        case
        for case in load_jsonl(DEFAULT_DATASET)
        if case["case_id"] == "structured_preference"
    )
    model = FakeAnswerModel("You prefer concise, practical engineering explanations.")

    result = run_case(case, mode="model", model=model)

    assert result.scenario_pass is True
    assert model.calls
    assert model.calls[0][-1]["content"] == case["query"]


def test_e2e_report_export_schema(tmp_path: Path) -> None:
    cases = load_jsonl(DEFAULT_DATASET, limit=2)
    results = run_cases(cases, mode="mock")
    payload = report_payload(results, mode="mock")
    output = tmp_path / "e2e-report.json"

    write_report(output, payload)
    parsed = json.loads(output.read_text(encoding="utf-8"))

    assert parsed["eval_name"] == "end_to_end_memory_rag_scenarios"
    assert parsed["summary"]["scenario_pass_rate"] == 1.0
    assert parsed["scenarios"][0]["trace"]["retrieved_candidates"]
    assert parsed["scenarios"][0]["trace"]["reranked_candidates"]
    assert parsed["scenarios"][0]["trace"]["context_packet"]["sections"]
    assert "workflow_metadata" in parsed["scenarios"][0]["trace"]


def test_all_mock_e2e_scenarios_pass() -> None:
    results = run_cases(load_jsonl(DEFAULT_DATASET), mode="mock")
    summary = summarize_results(results)

    assert summary["total_scenarios"] == 7
    assert summary["expected_source_present"] == 1.0
    assert summary["expected_context_included"] == 1.0
    assert summary["reranker_top_source_correct"] == 1.0
    assert summary["answer_contains_expected"] == 1.0
    assert summary["forbidden_claim_violations"] == 0
    assert summary["abstain_correctness"] == 1.0
    assert summary["scenario_pass_rate"] == 1.0
    assert summary["failed_scenario_ids"] == []
