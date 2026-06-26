from __future__ import annotations

from pathlib import Path

from evals.structured_memory.metrics import score_case, summarize_scores
from evals.structured_memory.run_structured_memory_eval import load_jsonl, run_cases


def test_structured_memory_metrics_score_write_retrieval_and_answer_use() -> None:
    case = {
        "case_id": "case-1",
        "expected_memory_substrings": ["concise answers"],
        "expected_answer_substrings": ["concise answers"],
        "should_write_memory": True,
        "should_retrieve_memory": True,
        "should_answer_with_memory": True,
    }

    score = score_case(
        case,
        stored_memory_text="User prefers concise answers.",
        retrieved_memory_text="User prefers concise answers.",
        answer="You prefer concise answers.",
    )

    assert score.memory_write_success is True
    assert score.memory_retrieval_hit is True
    assert score.answer_uses_memory is True
    assert score.failed_reasons == []


def test_structured_memory_metrics_score_abstain_case() -> None:
    case = {
        "case_id": "abstain",
        "false_memory_substrings": ["sqlite"],
        "should_write_memory": False,
        "should_retrieve_memory": False,
        "should_abstain": True,
    }

    score = score_case(
        case,
        stored_memory_text="",
        retrieved_memory_text="",
        answer="I do not have a stored database preference.",
    )

    assert score.memory_write_success is True
    assert score.memory_retrieval_hit is True
    assert score.answer_avoids_false_memory is True


def test_structured_memory_summary_rates_ignore_unavailable_answer_metrics() -> None:
    scores = [
        score_case(
            {
                "case_id": "write",
                "expected_memory_substrings": ["fact"],
                "should_write_memory": True,
                "should_retrieve_memory": False,
            },
            stored_memory_text="fact",
            retrieved_memory_text="",
            answer="",
        ),
        score_case(
            {
                "case_id": "abstain",
                "should_write_memory": False,
                "should_retrieve_memory": False,
                "should_abstain": True,
            },
            stored_memory_text="",
            retrieved_memory_text="",
            answer="No stored memory.",
        ),
    ]

    summary = summarize_scores(scores)

    assert summary["total_cases"] == 2
    assert summary["memory_write_success"] == 1.0
    assert summary["memory_retrieval_hit"] == 1.0
    assert summary["answer_uses_memory"] == 0.0
    assert summary["answer_avoids_false_memory"] == 1.0


def test_lifecycle_metrics_score_update_and_stale_memory() -> None:
    case = {
        "case_id": "update",
        "operation": "UPDATE",
        "expected_memory_substrings": ["concise practical answers"],
        "stale_memory_substrings": ["prefers long theoretical answers."],
        "expected_answer_substrings": ["concise practical answers"],
        "should_write_memory": True,
        "should_retrieve_memory": True,
        "should_answer_with_memory": True,
    }

    score = score_case(
        case,
        stored_memory_text="User prefers concise practical answers instead.",
        retrieved_memory_text="User prefers concise practical answers instead.",
        answer="You prefer concise practical answers.",
    )

    assert score.write_action_correct is True
    assert score.update_correct is True
    assert score.retrieval_hit is True
    assert score.answer_uses_correct_memory is True


def test_lifecycle_eval_runs_local_sample_dataset() -> None:
    cases = load_jsonl(Path("evals/structured_memory/datasets/lifecycle_sample.jsonl"))

    results = run_cases(cases)
    summary = summarize_scores([result.score for result in results])

    assert summary["total_cases"] == 5
    assert summary["write_action_correct"] == 1.0
    assert summary["noop_correct"] == 1.0
    assert summary["update_correct"] == 1.0
    assert summary["retrieval_hit"] == 1.0
    assert summary["answer_uses_correct_memory"] == 1.0
    assert summary["answer_avoids_false_memory"] == 1.0
    assert summary["failed_case_ids"] == []


def test_structured_memory_eval_runs_local_sample_dataset() -> None:
    cases = load_jsonl(Path("evals/structured_memory/datasets/cross_chat_sample.jsonl"))

    results = run_cases(cases)
    summary = summarize_scores([result.score for result in results])

    assert summary["total_cases"] == 3
    assert summary["memory_write_success"] == 1.0
    assert summary["memory_retrieval_hit"] == 1.0
    assert summary["answer_uses_memory"] == 1.0
    assert summary["answer_avoids_false_memory"] == 1.0
    assert summary["failed_case_ids"] == []
