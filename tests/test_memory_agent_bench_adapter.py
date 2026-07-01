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
from evals.memory_agent_bench.raw_replay import (
    EVAL_RAW_REPLAY_SOURCE,
    EvalRawReplayChunkRetriever,
)
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


class DeterministicEmbeddingBackend:
    model_name = "test-deterministic-embedding"

    def embed_query(self, text: str) -> list[float]:
        if "city" in text.lower():
            return [1.0, 0.0]
        return [0.0, 1.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0] if "relocated to berlin" in text.lower() else [0.0, 1.0]
            for text in texts
        ]


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


def test_eval_raw_replay_retrieval_finds_old_chunk_with_provenance() -> None:
    replayed = [
        {
            "session_id": "session-1",
            "chunk_index": 0,
            "user_message_id": 11,
            "chat_id": "old-chat",
            "content": "The distinctive deployment codename is cobalt lantern.",
        },
        {
            "session_id": "session-1",
            "chunk_index": 1,
            "user_message_id": 13,
            "chat_id": "old-chat",
            "content": "Unrelated later conversation.",
        },
    ]
    retriever = EvalRawReplayChunkRetriever(replayed, top_k=1)

    candidates = retriever.retrieve(
        "question-chat",
        SourcePlan(
            source=EVAL_RAW_REPLAY_SOURCE,  # type: ignore[arg-type]
            query="What is the distinctive deployment codename?",
            limit=1,
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].source == EVAL_RAW_REPLAY_SOURCE
    assert "cobalt lantern" in candidates[0].content
    assert candidates[0].source_message_ids == [11]
    assert candidates[0].chat_id == "old-chat"
    assert candidates[0].metadata["chunk_index"] == 0
    assert candidates[0].metadata["eval_only"] is True


def test_raw_replay_diagnostic_is_disabled_by_default() -> None:
    report = run_benchmark(load_examples(FIXTURE, limit=1), answer_mode="mock")
    row = report["results"][0]

    assert report["raw_replay_enabled"] is False
    assert row["raw_replay_diagnostics"]["raw_replay_enabled"] is False
    assert row["raw_replay_diagnostics"]["raw_replay_candidate_count"] == 0
    assert EVAL_RAW_REPLAY_SOURCE not in row["sources"]


def test_raw_replay_retrieval_uses_query_not_gold() -> None:
    replayed = [
        {
            "session_id": "session-1",
            "chunk_index": 0,
            "user_message_id": 1,
            "content": "GOLD_ONLY_TOKEN with unrelated material.",
        },
        {
            "session_id": "session-1",
            "chunk_index": 1,
            "user_message_id": 3,
            "content": "Router evidence uses a cobalt deployment codename.",
        },
    ]
    retriever = EvalRawReplayChunkRetriever(replayed, top_k=1)

    candidate = retriever.retrieve(
        "question-chat",
        SourcePlan(
            source=EVAL_RAW_REPLAY_SOURCE,  # type: ignore[arg-type]
            query="What cobalt deployment evidence did the router use?",
        ),
    )[0]

    assert candidate.source_message_ids == [3]
    assert "GOLD_ONLY_TOKEN" not in candidate.content


def test_raw_replay_candidates_are_bounded() -> None:
    replayed = [
        {
            "session_id": "session-1",
            "chunk_index": index,
            "user_message_id": index * 2 + 1,
            "content": f"{'padding ' * 100} marker-{index} {'detail ' * 100}",
        }
        for index in range(5)
    ]
    retriever = EvalRawReplayChunkRetriever(
        replayed,
        top_k=2,
        max_chars=160,
    )

    candidates = retriever.retrieve(
        "question-chat",
        SourcePlan(
            source=EVAL_RAW_REPLAY_SOURCE,  # type: ignore[arg-type]
            query="padding detail marker",
            limit=2,
        ),
    )

    assert len(candidates) == 2
    assert all(len(candidate.content) <= 160 for candidate in candidates)
    assert all(candidate.metadata["truncated"] is True for candidate in candidates)


def test_enabled_raw_replay_reaches_context_packet() -> None:
    report = run_benchmark(
        load_examples(FIXTURE, limit=1),
        answer_mode="mock",
        raw_replay_enabled=True,
        raw_replay_top_k=2,
        raw_replay_max_chars=400,
    )
    row = report["results"][0]
    diagnostics = row["raw_replay_diagnostics"]

    assert report["raw_replay_enabled"] is True
    assert diagnostics["raw_replay_enabled"] is True
    assert diagnostics["raw_replay_candidate_count"] >= 1
    assert diagnostics["raw_replay_reached_context"] is True
    assert diagnostics["raw_replay_gold_literal_found"] is True
    assert diagnostics["raw_replay_gold_message_found"] is True
    assert diagnostics["raw_replay_gold_literal_reached_context"] is True
    assert diagnostics["raw_replay_gold_message_reached_context"] is True
    assert EVAL_RAW_REPLAY_SOURCE in row["sources"]
    assert len(diagnostics["raw_replay_top_ids"]) <= 10


def test_raw_replay_embedding_mode_is_opt_in() -> None:
    retriever = EvalRawReplayChunkRetriever(
        [
            {
                "session_id": "session-1",
                "chunk_index": 0,
                "user_message_id": 1,
                "content": "Alex relocated to Berlin last spring.",
            },
            {
                "session_id": "session-1",
                "chunk_index": 1,
                "user_message_id": 3,
                "content": "Unrelated city planning notes.",
            },
        ],
        top_k=1,
    )

    candidate = retriever.retrieve(
        "question-chat",
        SourcePlan(
            source=EVAL_RAW_REPLAY_SOURCE,  # type: ignore[arg-type]
            query="What city did Alex move to?",
            limit=1,
        ),
    )[0]

    assert candidate.source_message_ids == [3]
    assert candidate.metadata["retrieval_mode"] == "eval_raw_replay_lexical"


def test_raw_replay_embedding_mode_finds_low_overlap_semantic_chunk() -> None:
    retriever = EvalRawReplayChunkRetriever(
        [
            {
                "session_id": "session-1",
                "chunk_index": 0,
                "user_message_id": 1,
                "content": "Alex relocated to Berlin last spring.",
            },
            {
                "session_id": "session-1",
                "chunk_index": 1,
                "user_message_id": 3,
                "content": "Unrelated city planning notes.",
            },
        ],
        top_k=1,
        retrieval_mode="embedding",
        embedding_backend=DeterministicEmbeddingBackend(),
    )

    candidate = retriever.retrieve(
        "question-chat",
        SourcePlan(
            source=EVAL_RAW_REPLAY_SOURCE,  # type: ignore[arg-type]
            query="What city did Alex move to?",
            limit=1,
        ),
    )[0]

    assert candidate.source_message_ids == [1]
    assert "Berlin" in candidate.content
    assert candidate.metadata["retrieval_mode"] == "eval_raw_replay_embedding"


def test_raw_replay_hybrid_fuses_lexical_and_embedding_ranks() -> None:
    retriever = EvalRawReplayChunkRetriever(
        [
            {
                "session_id": "session-1",
                "chunk_index": 0,
                "user_message_id": 1,
                "content": "Alex relocated to Berlin last spring.",
            },
            {
                "session_id": "session-1",
                "chunk_index": 1,
                "user_message_id": 3,
                "content": "City city city planning notes.",
            },
            {
                "session_id": "session-1",
                "chunk_index": 2,
                "user_message_id": 5,
                "content": "Completely unrelated text.",
            },
        ],
        top_k=2,
        retrieval_mode="hybrid",
        embedding_backend=DeterministicEmbeddingBackend(),
        candidate_pool_size=2,
    )

    candidates = retriever.retrieve(
        "question-chat",
        SourcePlan(
            source=EVAL_RAW_REPLAY_SOURCE,  # type: ignore[arg-type]
            query="What city did Alex move to?",
            limit=2,
        ),
    )

    assert {candidate.source_message_ids[0] for candidate in candidates} == {1, 3}
    assert all(
        candidate.metadata["retrieval_mode"] == "eval_raw_replay_hybrid"
        for candidate in candidates
    )


def test_raw_replay_pool_and_rank_diagnostics_are_bounded_and_post_hoc() -> None:
    replayed = [
        {
            "session_id": "session-1",
            "chunk_index": index,
            "user_message_id": index * 2 + 1,
            "content": (
                "Alex relocated to Berlin last spring."
                if index == 4
                else f"Unrelated city note {index}."
            ),
        }
        for index in range(8)
    ]
    retriever = EvalRawReplayChunkRetriever(
        replayed,
        top_k=2,
        retrieval_mode="embedding",
        embedding_backend=DeterministicEmbeddingBackend(),
        candidate_pool_size=3,
    )

    candidates = retriever.retrieve(
        "question-chat",
        SourcePlan(
            source=EVAL_RAW_REPLAY_SOURCE,  # type: ignore[arg-type]
            query="What city did Alex move to?",
            limit=8,
        ),
    )
    diagnostics = retriever.gold_rank_diagnostics({9})

    assert len(candidates) == 2
    assert diagnostics["raw_replay_candidate_pool_size"] == 3
    assert diagnostics["gold_rank_embedding"] == 1
    assert diagnostics["gold_in_candidate_pool"] is True
