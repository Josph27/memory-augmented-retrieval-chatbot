from __future__ import annotations

from pathlib import Path

from evals.document_qa.langchain_baseline import (
    LangChainBaselineResult,
    aggregate_results,
    load_baseline_cases,
    print_summary,
    skipped_summary,
    split_unique_documents,
    summary_to_dict,
)


def test_load_baseline_cases_supports_limit(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        "\n".join(
            [
                '{"case_id":"case-1","document_text":"A","question":"Q1",'
                '"expected_answer":"A","answer_anchor":"A","supporting_evidence":"A"}',
                '{"case_id":"case-2","document_text":"B","question":"Q2",'
                '"expected_answer":"B","answer_anchor":"B","supporting_evidence":"B"}',
            ]
        ),
        encoding="utf-8",
    )

    cases = load_baseline_cases(dataset, limit=1)

    assert len(cases) == 1
    assert cases[0]["case_id"] == "case-1"


class FakeChunk:
    def __init__(self, page_content: str, metadata: dict) -> None:
        self.page_content = page_content
        self.metadata = metadata


class FakeSplitter:
    def create_documents(self, texts: list[str], metadatas: list[dict]) -> list[FakeChunk]:
        return [FakeChunk(page_content=texts[0], metadata=metadatas[0])]


def test_split_unique_documents_deduplicates_identical_texts() -> None:
    cases = [
        {
            "case_id": "case-1",
            "document_id": "doc-1",
            "source": "test",
            "document_text": "Repeated document text.",
        },
        {
            "case_id": "case-2",
            "document_id": "doc-2",
            "source": "test",
            "document_text": "Repeated document text.",
        },
    ]

    texts, metadatas = split_unique_documents(cases, FakeSplitter())

    assert texts == ["Repeated document text."]
    assert metadatas[0]["document_id"] == "doc-1"
    assert metadatas[0]["chunk_index"] == 0


def test_aggregate_results_computes_rates_and_failed_cases() -> None:
    summary = aggregate_results(
        results=[
            LangChainBaselineResult(
                case_id="case-1",
                context_evidence_hit=True,
                context_answer_anchor_hit=True,
                context_expected_answer_hit=True,
                contexts=["A"],
            ),
            LangChainBaselineResult(
                case_id="case-2",
                context_evidence_hit=False,
                context_answer_anchor_hit=True,
                context_expected_answer_hit=True,
                contexts=["B"],
            ),
        ],
        top_k=3,
        vectorstore="faiss",
        backend_used="fake",
    )

    assert summary.cases == 2
    assert summary.top_k == 3
    assert summary.ctx_evidence == 0.5
    assert summary.ctx_anchor == 1.0
    assert summary.ctx_expected == 1.0
    assert summary.failed_case_ids == ["case-2"]


def test_skipped_summary_and_json_output_are_stable(capsys) -> None:
    summary = skipped_summary(
        cases=4,
        top_k=1,
        vectorstore="chroma",
        reason="optional dependency missing",
    )

    print_summary(summary)
    payload = summary_to_dict(summary)
    captured = capsys.readouterr()

    assert "skipped: yes" in captured.out
    assert "optional dependency missing" in captured.out
    assert payload["skipped"] is True
    assert payload["skipped_reason"] == "optional dependency missing"
    assert payload["vectorstore"] == "chroma"
