from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.multi_source_retrieval.run_multi_source_retrieval_eval import (
    DEFAULT_DATASET,
    load_jsonl,
    report_payload,
    run_case,
    run_cases,
    summarize_results,
    write_report,
)


def test_load_jsonl_reads_sample_dataset() -> None:
    cases = load_jsonl(DEFAULT_DATASET)

    assert len(cases) >= 6
    assert {case["case_id"] for case in cases} >= {
        "document_query",
        "structured_memory_semantic",
        "raw_span_provenance_query",
        "unknown_or_abstain_query",
    }


def test_source_selection_and_retrieval_case_passes() -> None:
    case = {
        "case_id": "document",
        "query": "What does the uploaded report say?",
        "enabled_sources": ["recent_messages", "structured_memory", "document_memory"],
        "expected_sources": ["document_memory"],
        "forbidden_sources": ["previous_chat_gist"],
        "expected_candidate_contains": ["uploaded report supports retrieval"],
        "expected_min_hits": 1,
        "candidate_fixtures": [
            {
                "source": "document_memory",
                "content": "The uploaded report supports retrieval from Chroma.",
                "record_id": "doc-1",
            }
        ],
    }

    result = run_case(case, top_k=3)

    assert result.source_selection_correct is True
    assert result.retrieval_hit is True
    assert result.forbidden_source_violation is False
    assert result.failed_reasons == []
    assert result.trace["routing"]["active_sources"] == [
        "recent_messages",
        "structured_memory",
        "document_memory",
    ]
    assert result.trace["retrieved_candidates"][0]["source"] == "document_memory"


def test_abstain_case_requires_no_retrieved_candidates() -> None:
    case = {
        "case_id": "abstain",
        "query": "What private token did I store?",
        "enabled_sources": ["recent_messages", "structured_memory"],
        "expected_sources": [],
        "forbidden_sources": ["document_memory", "previous_chat_gist"],
        "expected_candidate_contains": [],
        "expected_min_hits": 0,
        "candidate_fixtures": [],
    }

    result = run_case(case, top_k=3)

    assert result.retrieval_hit is True
    assert result.abstain_correct is True
    assert result.failed_reasons == []


def test_forbidden_source_violation_is_reported() -> None:
    case = {
        "case_id": "bad-source",
        "query": "What did the old chat say?",
        "enabled_sources": ["previous_chat_gist"],
        "expected_sources": ["previous_chat_gist"],
        "forbidden_sources": ["previous_chat_gist"],
        "expected_candidate_contains": ["old chat"],
        "expected_min_hits": 1,
        "candidate_fixtures": [
            {
                "source": "previous_chat_gist",
                "content": "old chat discussed memory",
                "record_id": 1,
            }
        ],
    }

    result = run_case(case, top_k=3)

    assert result.forbidden_source_violation is True
    assert "forbidden_source_retrieved" in result.failed_reasons


def test_summary_and_trace_export_schema(tmp_path: Path) -> None:
    cases = load_jsonl(DEFAULT_DATASET, limit=2)
    results = run_cases(cases, top_k=5)
    summary = summarize_results(results)
    payload = report_payload(results, top_k=5)
    output = tmp_path / "multi_source_report.json"

    write_report(output, payload)
    parsed = json.loads(output.read_text(encoding="utf-8"))

    assert summary["total_cases"] == 2
    assert summary["source_selection_accuracy"] == 1.0
    assert parsed["eval_name"] == "multi_source_retrieval"
    assert parsed["mode"] == "mock"
    assert parsed["top_k"] == 5
    assert parsed["cases"][0]["trace"]["routing"]["source_plans"]
    assert "retrieved_candidates" in parsed["cases"][0]["trace"]


def test_evaluation_jsonl_loaders_preserve_input_and_error_contract(tmp_path: Path) -> None:
    from evals.structured_memory.run_structured_memory_eval import load_jsonl as structured_load

    path = tmp_path / "cases.jsonl"
    path.write_text('\n {"case_id": "a"}\n42\n null\n', encoding="utf-8")
    for loader in (load_jsonl, structured_load):
        assert loader(path) == [{"case_id": "a"}, 42, None]
        assert loader(path, limit=1) == [{"case_id": "a"}]
        assert loader(path, limit=0) == [{"case_id": "a"}]
        assert loader(path, limit=-1) == [{"case_id": "a"}]
        with pytest.raises(FileNotFoundError):
            loader(tmp_path / "missing.jsonl")
    path.write_text('{"invalid": }\n', encoding="utf-8")
    for loader in (load_jsonl, structured_load):
        with pytest.raises(json.JSONDecodeError):
            loader(path)

    # Both direct CLI entry points must resolve the shared helper after path setup.
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    for script in (
        "evals/structured_memory/run_structured_memory_eval.py",
        "evals/multi_source_retrieval/run_multi_source_retrieval_eval.py",
    ):
        result = subprocess.run(
            [sys.executable, str(root / script), "--help"],
            cwd=tmp_path, capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, result.stderr
        assert "--dataset" in result.stdout
