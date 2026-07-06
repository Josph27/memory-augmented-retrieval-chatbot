from __future__ import annotations

from src.context.context_comparator import ContextComparator
from src.core.contracts import ContextPacket


LATEST = {"role": "user", "content": "What is my name?"}


def packet(messages: list[dict[str, str]]) -> ContextPacket:
    return ContextPacket(
        chat_id="chat",
        model_messages=messages,
    )


def old_messages() -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "system"},
        {
            "role": "system",
            "content": "Current structured memory:\n{\"user_facts\": [\"Name is Alex\"]}",
        },
        {"role": "user", "content": "Earlier user message"},
        {"role": "assistant", "content": "Earlier assistant response"},
        LATEST,
    ]


def test_context_comparator_detects_missing_latest_user_query() -> None:
    comparison = ContextComparator().compare(
        old_model_messages=old_messages(),
        new_context_packet=packet(
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "Earlier user message"},
            ]
        ),
        latest_user_message=LATEST,
    )

    assert "missing_latest_user_message" in comparison.warnings
    assert comparison.old_prompt.has_latest_user_message is True
    assert comparison.new_context_packet.has_latest_user_message is False


def test_context_comparator_detects_missing_recent_messages() -> None:
    comparison = ContextComparator().compare(
        old_model_messages=old_messages(),
        new_context_packet=packet(
            [
                {"role": "system", "content": "system"},
                {
                    "role": "system",
                    "content": "Structured Memory:\n- [name] Name is Alex",
                },
                LATEST,
            ]
        ),
        latest_user_message=LATEST,
    )

    assert "missing_recent_messages" in comparison.warnings
    assert comparison.old_prompt.has_recent_messages is True
    assert comparison.new_context_packet.has_recent_messages is False


def test_context_comparator_detects_missing_structured_memory() -> None:
    comparison = ContextComparator().compare(
        old_model_messages=old_messages(),
        new_context_packet=packet(
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "Earlier user message"},
                LATEST,
            ]
        ),
        latest_user_message=LATEST,
    )

    assert "missing_structured_memory" in comparison.warnings
    assert comparison.old_prompt.has_structured_memory is True
    assert comparison.new_context_packet.has_structured_memory is False


def test_context_comparator_detects_large_token_count_difference() -> None:
    comparison = ContextComparator().compare(
        old_model_messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "short"},
            LATEST,
        ],
        new_context_packet=packet(
            [
                {"role": "system", "content": "system"},
                {
                    "role": "system",
                    "content": "Structured Memory:\n" + ("memory detail " * 120),
                },
                {"role": "user", "content": "short"},
                LATEST,
            ]
        ),
        latest_user_message=LATEST,
    )

    assert "large_token_count_difference" in comparison.warnings
    assert comparison.token_difference > 0
    assert comparison.token_difference_ratio >= 0.5
