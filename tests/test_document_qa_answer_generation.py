from __future__ import annotations

from evals.document_qa.answer_generation import (
    answer_is_unknown,
    build_grounded_qa_messages,
    format_contexts,
)


def test_grounded_qa_prompt_requires_context_only_answer() -> None:
    messages = build_grounded_qa_messages(
        question="What database is used?",
        contexts=["The project uses SQLite."],
    )

    assert messages[0]["role"] == "system"
    assert "using only the provided contexts" in messages[0]["content"]
    assert "I don't know" in messages[0]["content"]
    assert "The project uses SQLite." in messages[1]["content"]
    assert "What database is used?" in messages[1]["content"]


def test_format_contexts_numbers_contexts() -> None:
    assert format_contexts(["First.", "Second."]) == "[1] First.\n\n[2] Second."


def test_format_contexts_handles_empty_contexts() -> None:
    assert format_contexts([]) == "No contexts were retrieved."


def test_answer_is_unknown_detects_declines() -> None:
    assert answer_is_unknown("I don't know.")
    assert answer_is_unknown("I do not know based on the context.")
    assert not answer_is_unknown("SQLite")
