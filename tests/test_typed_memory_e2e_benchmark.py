from __future__ import annotations

import json
from dataclasses import replace

from evals.typed_memory_e2e.cases import all_cases
from evals.typed_memory_e2e.run_typed_memory_e2e import select_cases
from evals.typed_memory_e2e.runner import run_benchmark, run_case, write_jsonl


def test_runner_executes_one_case() -> None:
    result = run_case(all_cases()[0])

    assert result.passed is True
    assert result.raw_span_present is True
    assert result.provenance_present is True


def test_missing_required_text_fails_case() -> None:
    case = replace(
        all_cases()[0],
        name="missing-required-text",
        required_text_in_context=("TEXT THAT DOES NOT EXIST",),
    )

    result = run_case(case)

    assert result.passed is False
    assert "required_text_missing" in result.failure_reasons


def test_missing_raw_span_fails_exact_quote_case() -> None:
    case = next(
        case
        for case in all_cases()
        if case.category == "gist_only_exact_quote_fails"
    )

    result = run_case(
        replace(case, expected_insufficient_evidence=False)
    )

    assert result.passed is False
    assert "required_raw_span_missing" in result.failure_reasons


def test_provenance_validation_works() -> None:
    case = next(
        case for case in all_cases() if case.category == "provenance_preservation"
    )

    result = run_case(case)

    assert result.passed is True
    assert result.provenance_present is True
    assert "raw_message_span" in result.sources_observed


def test_aggregate_summary_and_case_filters() -> None:
    selected = select_cases(
        all_cases(),
        names=set(),
        categories={"casual_chat_minimal_memory"},
    )
    report = run_benchmark(selected[:2])

    assert len(selected) == 3
    assert report["num_cases"] == 2
    assert report["num_passed"] == 2
    assert report["pass_rate_by_category"] == {
        "casual_chat_minimal_memory": 1.0
    }
    named = select_cases(
        all_cases(),
        names={selected[0].name},
        categories=set(),
    )
    assert [case.name for case in named] == [selected[0].name]


def test_jsonl_output_is_bounded(tmp_path) -> None:
    report = run_benchmark([all_cases()[0]])
    output = tmp_path / "typed-memory.jsonl"

    write_jsonl(output, report)

    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert max(map(len, lines)) < 5000
    assert "padding padding padding" not in lines[1]
    assert json.loads(lines[0])["summary"]["num_cases"] == 1


def test_benchmark_has_at_least_thirty_cases() -> None:
    cases = all_cases()

    assert len(cases) == 43
    assert len({case.name for case in cases}) == len(cases)
