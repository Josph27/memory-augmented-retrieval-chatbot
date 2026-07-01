from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.memory_agent_bench.adapter import run_example
from evals.memory_agent_bench.loader import (
    load_examples,
    load_huggingface_examples,
    normalize_record,
    split_context,
)
from evals.memory_agent_bench.metrics import score_answer
from evals.memory_agent_bench.runner import run_benchmark, write_jsonl_report
from src.core.contracts import (
    AgentTurnResult,
    ContextPacket,
    MemoryCandidate,
    RoutePlan,
    SourcePlan,
    WorkflowTrace,
)


FIXTURE = (
    Path(__file__).parents[1]
    / "evals"
    / "memory_agent_bench"
    / "fixtures"
    / "tiny_sample.jsonl"
)


class RecordingHarness:
    execution_classification = "production-like test harness"

    def __init__(self) -> None:
        self.replayed: list[tuple[str, str, str]] = []
        self.memory_update_calls = 0
        self.structured_update_backend_calls: int | None = 0
        self.chat_end_calls = 0
        self.closed = False
        self.replayed_chunks: list[dict[str, object]] = []

    def replay_session(
        self,
        example_id: str,
        session_id: str,
        chunks: tuple[str, ...],
    ) -> None:
        for chunk_index, chunk in enumerate(chunks):
            self.replayed.append((example_id, session_id, chunk))
            self.replayed_chunks.append(
                {
                    "session_id": session_id,
                    "chunk_index": chunk_index,
                    "user_message_id": chunk_index + 1,
                    "content": chunk,
                }
            )
            self.memory_update_calls += 1
            assert self.structured_update_backend_calls is not None
            self.structured_update_backend_calls += 1

    def end_current_session(self) -> None:
        self.chat_end_calls += 1

    def ask(self, question: str, gold_answers: tuple[str, ...]) -> AgentTurnResult:
        candidate = MemoryCandidate(
            source="previous_chat_gist",
            content=f"user: The answer is {gold_answers[0]}.",
            record_id="gist-1",
            source_message_ids=[11],
            metadata={"start_message_id": 11, "end_message_id": 11},
        )
        route = RoutePlan(
            query=question,
            sources=[SourcePlan(source="previous_chat_gist", enabled=True)],
        )
        packet = ContextPacket(
            chat_id="question",
            candidates=[candidate],
            model_messages=[{"role": "user", "content": question}],
        )
        trace = WorkflowTrace(
            trace_id="trace",
            chat_id="question",
            route_plan=route,
            retrieved_candidates=[candidate],
            ranked_candidates=[candidate],
            context_packet=packet,
        )
        return AgentTurnResult(
            answer=gold_answers[0],
            chat_id="question",
            trace_id="trace",
            termination_reason="test",
            trace=trace,
        )

    def close(self) -> None:
        self.closed = True


def test_fixture_parses_normalized_example() -> None:
    examples = load_examples(FIXTURE)

    assert len(examples) == 2
    assert examples[0].competency == "Accurate_Retrieval"
    assert examples[0].sessions[0].chunks[0].startswith("My deployment")
    assert examples[0].questions == ("What is my deployment codename?",)
    assert examples[0].answers == (("cobalt lantern",),)


def test_official_context_shape_is_chunked_and_question_limited() -> None:
    example = normalize_record(
        {
            "context": "First fact.\n\n" + ("Second fact is long. " * 20),
            "questions": ["Question one?", "Question two?"],
            "answers": [["answer one"], ["answer two"]],
            "metadata": {
                "source": "factconsolidation_mh_6k",
                "qa_pair_ids": ["q1", "q2"],
            },
        },
        competency="Conflict_Resolution",
        example_index=0,
        question_limit=1,
        context_chunk_chars=120,
    )

    assert example.example_id == "factconsolidation_mh_6k-row-1"
    assert example.competency == "Conflict_Resolution"
    assert example.questions == ("Question one?",)
    assert example.answers == (("answer one",),)
    assert len(example.sessions[0].chunks) > 1
    assert all(len(chunk) <= 120 for chunk in example.sessions[0].chunks)
    assert example.metadata["adapter_context_chunk_count"] > 1


def test_context_split_rejects_unreasonably_small_bound() -> None:
    with pytest.raises(ValueError, match="at least 100"):
        split_context("content", max_chars=50)


def test_incremental_replay_calls_memory_update_and_session_lifecycle() -> None:
    example = load_examples(FIXTURE, limit=1)[0]
    harness = RecordingHarness()

    rows = run_example(example, mock_answer=True, harness=harness)

    assert [item[2] for item in harness.replayed] == list(
        example.sessions[0].chunks
    )
    assert harness.memory_update_calls == len(example.sessions[0].chunks)
    assert harness.chat_end_calls == 1
    assert rows[0]["memory_update_calls"] == len(example.sessions[0].chunks)
    assert harness.closed is True


def test_multi_session_calls_chat_end_between_sessions() -> None:
    example = load_examples(FIXTURE)[1]
    harness = RecordingHarness()

    run_example(example, mock_answer=True, harness=harness)

    assert harness.chat_end_calls == 2
    assert {item[1] for item in harness.replayed} == {"session-1", "session-2"}


def test_context_evidence_and_provenance_are_reported() -> None:
    example = load_examples(FIXTURE, limit=1)[0]
    row = run_example(
        example,
        mock_answer=True,
        harness=RecordingHarness(),
    )[0]

    assert row["evidence_metric"]["gold_in_context"] is True
    assert row["sources"] == ["previous_chat_gist"]
    assert row["provenance_present"] is True
    assert row["retrieved_candidates"][0]["source_message_ids"] == [11]
    assert row["evidence_diagnostics"]["gold_in_replay"] is True
    assert row["evidence_diagnostics"]["failure_stage"] == (
        "none_literal_gold_reached_context"
    )


def test_mock_answer_mode_is_labeled_honestly() -> None:
    report = run_benchmark(load_examples(FIXTURE, limit=1), answer_mode="mock")

    row = report["results"][0]
    assert row["mock_answer"] is True
    assert row["generated_answer_grounding_tested"] is False
    assert report["summary"]["generated_answer_grounding_tested"] is False
    assert "not tested" in row["notes"][0]
    assert row["memory_update_calls"] == 2
    assert row["structured_update_backend_calls"] >= 1


def test_simple_answer_metrics() -> None:
    metrics = score_answer(
        "The code is Cobalt-Lantern.",
        ("cobalt lantern",),
        "user: My deployment codename is cobalt lantern.",
    )

    assert metrics.exact_match is False
    assert metrics.substring_match is False
    assert metrics.normalized_substring_match is True
    assert metrics.evidence_contains_answer is True


def test_jsonl_report_contains_summary_and_results(tmp_path: Path) -> None:
    report = run_benchmark(load_examples(FIXTURE, limit=1), answer_mode="mock")
    output = tmp_path / "report.jsonl"

    write_jsonl_report(output, report)
    rows = [
        json.loads(line)
        for line in output.read_text(encoding="utf-8").splitlines()
    ]

    assert "report_summary" in rows[0]
    assert rows[1]["example_id"] == "accurate-retrieval-1"


def test_huggingface_support_is_lazy_and_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "datasets", None)

    with pytest.raises(RuntimeError, match="optional 'datasets' package"):
        load_huggingface_examples("org/not-downloaded")
