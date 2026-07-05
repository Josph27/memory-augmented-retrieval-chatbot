from __future__ import annotations

import json
from pathlib import Path
import inspect

import pytest

import evals.longmemeval_answer_eval as longmemeval_eval
from evals.longmemeval_answer_eval import (
    RunOptions,
    load_manifest,
    replay_history_sessions_production_like,
    resolve_cases,
    run_evaluation,
    run_judge_only,
    timestamp_preservation_status,
)
from evals.longmemeval_adapter.schema import HistoryMessage, HistorySession, LongMemEvalCase
from evals.mab_answer_eval.schemas import EvaluationModels
from src.actions.chat_end import ChatEndAction
from src.config import AppConfig
from src.database import Database
from src.memory.short_term import ShortTermMemory
from src.memory.structured_state import MemoryUpdateResult


class FakeAnswerModel:
    model_name = "offline-test-model"

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, temperature=None):  # type: ignore[no-untyped-def]
        del messages, temperature
        self.calls += 1
        return "solarized dark"


class AcceptedMemoryUpdater:
    def __init__(self) -> None:
        self.calls = 0

    def update(self, existing_memory, messages):  # type: ignore[no-untyped-def]
        del existing_memory
        self.calls += 1
        user_ids = [message.id for message in messages if message.role == "user"]
        return MemoryUpdateResult(
            memory_state={
                "memories": [
                    {
                        "id": "preference:theme",
                        "category": "preferences",
                        "key": "theme",
                        "value": "solarized dark",
                        "source_message_ids": user_ids,
                        "confidence": 0.9,
                        "status": "active",
                    }
                ]
            },
            accepted=True,
        )


class FakeJudgeClient:
    model_name = "judge-a"

    def __init__(self) -> None:
        self.calls = 0

    def judge(self, messages):  # type: ignore[no-untyped-def]
        del messages
        self.calls += 1
        return json.dumps(
            {
                "correct": True,
                "complete": True,
                "brief_reason": "Matches the reference.",
            }
        )


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "evals"
    / "longmemeval_adapter"
    / "fixtures"
    / "tiny_longmemeval_sample.jsonl"
)


def write_manifest(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "name": "longmemeval-offline",
                "version": 1,
                "seed": 7,
                "execution_mode": "graph",
                "dataset_path": str(FIXTURE),
                "cases": [
                    {
                        "case_id": "tiny-preference",
                        "question_type": "single-session-user",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def frozen_answer_row(manifest_path: Path) -> dict:
    manifest = load_manifest(manifest_path)
    return {
        "evaluation_level": "answer",
        "evaluation_version": "lifecycle_v2",
        "run_id": "frozen-answer-run",
        "manifest_name": manifest.name,
        "manifest_hash": manifest.manifest_hash,
        "case_id": "tiny-preference",
        "dataset": "longmemeval",
        "execution_mode": "graph",
        "question_type": "single-session-user",
        "answer_model": "answer-a",
        "judge_model": "__answer_only__",
        "judge_endpoint": None,
        "question": "Which theme do I prefer?",
        "reference_answer": ["solarized dark"],
        "generated_answer": "solarized dark",
        "answer_cache_key": "answer-key",
        "selected_evidence_hash": "evidence-hash",
        "result_identity": "result-identity",
        "generation_parameters": {"temperature": 0},
        "context_diagnostics": {
            "selected_memory_tokens": 10,
            "final_prompt_tokens": 20,
        },
        "latency_ms": {"generation": 4.0, "judge": 0.0, "total": 5.0},
        "official_metric": {"name": "pilot", "score": 1.0, "passed": True},
        "status": "answer_completed",
        "error": None,
    }


def test_manifest_resolves_fixture_case(tmp_path: Path) -> None:
    manifest = load_manifest(write_manifest(tmp_path / "manifest.yaml"))
    resolved = resolve_cases(manifest)

    assert manifest.dataset_path == FIXTURE
    assert manifest.execution_mode == "graph"
    assert [case.spec.case_id for case in resolved] == ["tiny-preference"]


def test_dry_run_validates_without_writing(tmp_path: Path) -> None:
    manifest = load_manifest(write_manifest(tmp_path / "manifest.yaml"))
    output_dir = tmp_path / "artifacts"

    report = run_evaluation(
        manifest,
        models=EvaluationModels(
            "answer-a",
            "judge-a",
            judge_endpoint="https://judge.example",
        ),
        config=AppConfig.from_env(),
        options=RunOptions(output_dir=output_dir, execution_mode="graph", dry_run=True),
    )

    assert report["cases"] == 1
    assert report["estimated_generation_calls"] == 1
    assert report["estimated_judge_calls"] == 1
    assert not output_dir.exists()


def test_judge_only_uses_frozen_answers_without_replay_or_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = write_manifest(tmp_path / "manifest.yaml")
    manifest = load_manifest(manifest_path)
    source_path = tmp_path / "frozen-results.jsonl"
    source_path.write_text(
        json.dumps(frozen_answer_row(manifest_path)) + "\n",
        encoding="utf-8",
    )
    source_before = source_path.read_bytes()
    output_dir = tmp_path / "judge"
    judge = FakeJudgeClient()

    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        raise AssertionError("answer generation or replay was called")

    monkeypatch.setattr(longmemeval_eval, "resolve_cases", forbidden)
    monkeypatch.setattr(
        longmemeval_eval,
        "replay_history_sessions_production_like",
        forbidden,
    )
    monkeypatch.setattr(longmemeval_eval.LongMemEvalAnswerExecutor, "execute", forbidden)

    report = run_judge_only(
        manifest,
        source_results_path=source_path,
        models=EvaluationModels(
            "answer-a",
            "judge-a",
            judge_endpoint="https://judge.example",
        ),
        options=RunOptions(
            output_dir=output_dir,
            execution_mode="graph",
            resume=True,
        ),
        judge_client=judge,
    )

    assert source_path.read_bytes() == source_before
    assert judge.calls == 1
    assert report["generation_calls_this_invocation"] == 0
    assert report["judge_calls_this_invocation"] == 1
    completed = json.loads(
        (output_dir / "results.jsonl").read_text(encoding="utf-8").strip()
    )
    assert completed["status"] == "completed"
    assert completed["generated_answer"] == "solarized dark"
    assert completed["answer_cache_key"] == "answer-key"
    assert completed["selected_evidence_hash"] == "evidence-hash"
    assert completed["context_diagnostics"] == {
        "selected_memory_tokens": 10,
        "final_prompt_tokens": 20,
    }


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda rows: [], "missing LongMemEval answer rows"),
        (lambda rows: [*rows, dict(rows[0])], "duplicate LongMemEval answer row"),
        (
            lambda rows: [{**rows[0], "case_id": "not-frozen"}],
            "non-frozen LongMemEval answer row",
        ),
        (
            lambda rows: [{**rows[0], "status": "completed"}],
            "is not frozen answer_completed",
        ),
    ],
)
def test_judge_only_rejects_invalid_frozen_answer_sets(
    tmp_path: Path,
    mutation,  # type: ignore[no-untyped-def]
    expected: str,
) -> None:
    manifest_path = write_manifest(tmp_path / "manifest.yaml")
    manifest = load_manifest(manifest_path)
    source_path = tmp_path / "frozen-results.jsonl"
    rows = mutation([frozen_answer_row(manifest_path)])
    source_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=expected):
        run_judge_only(
            manifest,
            source_results_path=source_path,
            models=EvaluationModels(
                "answer-a",
                "judge-a",
                judge_endpoint="https://judge.example",
            ),
            options=RunOptions(
                output_dir=tmp_path / "judge",
                execution_mode="graph",
                dry_run=True,
            ),
        )


def test_longmemeval_history_replay_finalizes_each_session_and_preserves_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = LongMemEvalCase(
        case_id="two-session",
        question="Which theme do I prefer?",
        gold_answer="solarized dark",
        question_type="multi-session",
        sessions=(
            HistorySession(
                session_id="session-a",
                messages=(
                    HistoryMessage("user", "I prefer solarized dark.", created_at="2023-02-15T01:00:00Z"),
                    HistoryMessage("assistant", "Noted.", created_at="2023-02-15T01:01:00Z"),
                ),
                metadata={"date": "2023-02-15T01:00:00Z"},
            ),
            HistorySession(
                session_id="session-b",
                messages=(
                    HistoryMessage("user", "Also, keep the font large.", created_at="2023-02-16T01:00:00Z"),
                    HistoryMessage("assistant", "Recorded.", created_at="2023-02-16T01:01:00Z"),
                ),
                metadata={"date": "2023-02-16T01:00:00Z"},
            ),
        ),
    )
    database = Database(tmp_path / "case.db")
    updater = AcceptedMemoryUpdater()
    memory = ShortTermMemory(
        database=database,
        model=FakeAnswerModel(),
        raw_message_limit=8,
        memory_update_batch_size=2,
        structured_memory_updater=updater,
        memory_replay_trigger_tokens=1,
        memory_replay_max_input_tokens=64,
        memory_replay_max_messages=16,
    )
    original_execute = ChatEndAction.execute
    end_calls: list[str] = []
    gist_callers: list[str] = []
    original_insert = database.insert_chat_gist

    def record_execute(self, chat_id: str):  # type: ignore[no-untyped-def]
        end_calls.append(chat_id)
        return original_execute(self, chat_id)

    def record_insert(*args, **kwargs):  # type: ignore[no-untyped-def]
        gist_callers.append(Path(inspect.stack()[1].filename).name)
        return original_insert(*args, **kwargs)

    monkeypatch.setattr(ChatEndAction, "execute", record_execute)
    monkeypatch.setattr(database, "insert_chat_gist", record_insert)

    spans = replay_history_sessions_production_like(
        database=database,
        memory=memory,
        case=case,
    )
    database.create_chat("two-session-question", title="LongMemEval question")

    active_chat_ids = {row["id"] for row in database.list_active_chats()}
    inactive_chat_ids = {row["id"] for row in database.list_inactive_chats()}
    first_chat_messages = database.messages_for_chat("two-session-history-1")
    second_chat_messages = database.messages_for_chat("two-session-history-2")

    assert len(spans) >= 2
    assert updater.calls >= 2
    assert end_calls == ["two-session-history-1", "two-session-history-2"]
    assert inactive_chat_ids == {"two-session-history-1", "two-session-history-2"}
    assert active_chat_ids == {"two-session-question"}
    assert [message.role for message in first_chat_messages] == ["user", "assistant"]
    assert [message.role for message in second_chat_messages] == ["user", "assistant"]
    assert all(message.summarized for message in first_chat_messages + second_chat_messages)
    assert all(message.gist_processed for message in first_chat_messages + second_chat_messages)
    assert database.chat_memory_state("two-session-history-1") is not None
    assert database.chat_memory_state("two-session-history-2") is not None
    assert len(database.chat_gists_by_source_type("previous_chat_gist")) == 2
    assert set(gist_callers) == {"previous_chat_gist.py"}


def test_empty_message_skipping_preserves_session_boundaries(tmp_path: Path) -> None:
    dataset = tmp_path / "empty-boundaries.jsonl"
    dataset.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "case_id": "empty-boundaries",
                        "question_type": "multi-session",
                        "question": "What theme do I prefer?",
                        "gold_answer": "solarized dark",
                        "sessions": [
                            {
                                "session_id": "a",
                                "messages": [
                                    {"role": "user", "content": "I prefer solarized dark."},
                                    {"role": "assistant", "content": ""},
                                    {"role": "assistant", "content": "Noted."},
                                ],
                            },
                            {
                                "session_id": "b",
                                "messages": [
                                    {"role": "user", "content": ""},
                                    {"role": "user", "content": "Use a large font."},
                                    {"role": "assistant", "content": "Recorded."},
                                ],
                            },
                        ],
                    }
                )
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        json.dumps(
            {
                "name": "empty-boundaries",
                "version": 1,
                "seed": 7,
                "execution_mode": "graph",
                "dataset_path": str(dataset),
                "cases": [{"case_id": "empty-boundaries", "question_type": "multi-session"}],
            }
        ),
        encoding="utf-8",
    )
    manifest = load_manifest(manifest_path)
    resolved = resolve_cases(manifest)
    case = resolved[0].case
    database = Database(tmp_path / "empty-boundaries.db")
    updater = AcceptedMemoryUpdater()
    memory = ShortTermMemory(
        database=database,
        model=FakeAnswerModel(),
        raw_message_limit=8,
        memory_update_batch_size=2,
        structured_memory_updater=updater,
        memory_replay_trigger_tokens=1,
        memory_replay_max_input_tokens=64,
        memory_replay_max_messages=16,
    )

    replay_history_sessions_production_like(
        database=database,
        memory=memory,
        case=case,
    )

    assert len(case.sessions) == 2
    assert {row["id"] for row in database.list_inactive_chats()} == {
        "empty-boundaries-history-1",
        "empty-boundaries-history-2",
    }
    assert [message.content for message in database.messages_for_chat("empty-boundaries-history-1")] == [
        "I prefer solarized dark.",
        "Noted.",
    ]


def test_longmemeval_replay_batches_offline_updates_once_per_session(
    tmp_path: Path,
) -> None:
    case = LongMemEvalCase(
        case_id="batched",
        question="What theme do I prefer?",
        gold_answer="solarized dark",
        question_type="multi-session",
        sessions=(
            HistorySession(
                session_id="session-a",
                messages=(
                    HistoryMessage("user", "I prefer solarized dark.", created_at="2023-02-15T01:00:00Z"),
                    HistoryMessage("assistant", "Noted.", created_at="2023-02-15T01:01:00Z"),
                    HistoryMessage("assistant", "Saved.", created_at="2023-02-15T01:02:00Z"),
                ),
                metadata={"date": "2023-02-15T01:00:00Z"},
            ),
            HistorySession(
                session_id="session-b",
                messages=(
                    HistoryMessage("user", "Use a large font.", created_at="2023-02-16T01:00:00Z"),
                    HistoryMessage("assistant", "Recorded.", created_at="2023-02-16T01:01:00Z"),
                    HistoryMessage("assistant", "Anything else?", created_at="2023-02-16T01:02:00Z"),
                ),
                metadata={"date": "2023-02-16T01:00:00Z"},
            ),
        ),
    )
    database = Database(tmp_path / "batched.db")
    updater = AcceptedMemoryUpdater()
    memory = ShortTermMemory(
        database=database,
        model=FakeAnswerModel(),
        raw_message_limit=8,
        memory_update_batch_size=2,
        structured_memory_updater=updater,
        memory_replay_trigger_tokens=1,
        memory_replay_max_input_tokens=64,
        memory_replay_max_messages=16,
    )

    replay_history_sessions_production_like(
        database=database,
        memory=memory,
        case=case,
    )

    assert updater.calls == 2
    assert [message.content for message in database.messages_for_chat("batched-history-2")] == [
        "Use a large font.",
        "Recorded.",
        "Anything else?",
    ]


def test_timestamp_status_prefers_message_then_session_timestamps() -> None:
    message_case = LongMemEvalCase(
        case_id="message-ts",
        question="Q",
        gold_answer="A",
        question_type="multi-session",
        sessions=(
            HistorySession(
                session_id="s1",
                messages=(HistoryMessage("user", "x", created_at="2023-01-01T00:00:00Z"),),
            ),
        ),
    )
    session_case = LongMemEvalCase(
        case_id="session-ts",
        question="Q",
        gold_answer="A",
        question_type="multi-session",
        sessions=(
            HistorySession(
                session_id="s1",
                messages=(HistoryMessage("user", "x"),),
                metadata={"date": "2023-01-01T00:00:00Z"},
            ),
        ),
    )

    assert timestamp_preservation_status(message_case) == "message_timestamp_preserved_when_present"
    assert timestamp_preservation_status(session_case) == (
        "session_timestamp_preserved_when_message_timestamp_absent"
    )
