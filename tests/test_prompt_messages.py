from __future__ import annotations

from src.context.prompt_messages import context_packet_to_model_messages
from src.core.contracts import ContextPacket


LATEST = {"role": "user", "content": "latest question"}


def packet(messages: list[dict[str, str]]) -> ContextPacket:
    return ContextPacket(chat_id="chat", model_messages=messages)


def valid_messages() -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "system"},
        {"role": "system", "content": "Structured Memory:\n- name: Alex"},
        {"role": "user", "content": "earlier"},
        {"role": "assistant", "content": "ack"},
        LATEST,
    ]


def test_context_packet_to_model_messages_accepts_valid_packet() -> None:
    result = context_packet_to_model_messages(packet(valid_messages()), LATEST)

    assert result.valid is True
    assert result.fallback_reason is None
    assert result.messages == valid_messages()


def test_context_packet_to_model_messages_rejects_missing_latest_user_message() -> None:
    result = context_packet_to_model_messages(
        packet(
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "earlier"},
            ]
        ),
        LATEST,
    )

    assert result.valid is False
    assert result.fallback_reason == "latest_user_message_missing"


def test_context_packet_to_model_messages_rejects_empty_content() -> None:
    result = context_packet_to_model_messages(
        packet(
            [
                {"role": "system", "content": "system"},
                {"role": "assistant", "content": ""},
                LATEST,
            ]
        ),
        LATEST,
    )

    assert result.valid is False
    assert result.fallback_reason == "empty_message_content"


def test_context_packet_to_model_messages_rejects_invalid_role() -> None:
    result = context_packet_to_model_messages(
        packet(
            [
                {"role": "system", "content": "system"},
                {"role": "tool", "content": "bad"},
                LATEST,
            ]
        ),
        LATEST,
    )

    assert result.valid is False
    assert result.fallback_reason == "invalid_message_role"


def test_context_packet_to_model_messages_rejects_duplicate_latest_user_message() -> None:
    result = context_packet_to_model_messages(
        packet(
            [
                {"role": "system", "content": "system"},
                LATEST,
                LATEST,
            ]
        ),
        LATEST,
    )

    assert result.valid is False
    assert result.fallback_reason == "latest_user_message_duplicated"


def test_context_packet_to_model_messages_rejects_severe_comparison_warning() -> None:
    result = context_packet_to_model_messages(
        packet(valid_messages()),
        LATEST,
        context_comparison={"warnings": ["missing_latest_user_message"]},
    )

    assert result.valid is False
    assert result.fallback_reason == "context_comparison_missing_latest_user_message"
