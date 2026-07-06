from __future__ import annotations

from dataclasses import dataclass

from src.core.contracts import ContextPacket


VALID_MESSAGE_ROLES = {"system", "user", "assistant"}
SEVERE_COMPARISON_WARNINGS = {"missing_latest_user_message"}


@dataclass(frozen=True)
class PromptAssemblyResult:
    """Validated model messages derived from a ContextPacket."""

    messages: list[dict[str, str]]
    valid: bool
    fallback_reason: str | None = None


def context_packet_to_model_messages(
    packet: ContextPacket | None,
    latest_user_message: dict[str, str],
    context_comparison: dict[str, object] | None = None,
) -> PromptAssemblyResult:
    """Return validated chat messages from a ContextPacket."""
    if packet is None:
        return PromptAssemblyResult([], False, "context_packet_missing")

    messages = [dict(message) for message in packet.model_messages]
    fallback_reason = validate_model_messages(
        messages=messages,
        latest_user_message=latest_user_message,
    )
    if fallback_reason is not None:
        return PromptAssemblyResult(messages, False, fallback_reason)

    severe_warning = severe_context_comparison_warning(context_comparison)
    if severe_warning is not None:
        return PromptAssemblyResult(messages, False, severe_warning)

    return PromptAssemblyResult(messages, True)


def validate_model_messages(
    messages: list[dict[str, str]],
    latest_user_message: dict[str, str],
) -> str | None:
    """Validate OpenAI-compatible model messages for a final prompt call."""
    if not messages:
        return "no_valid_messages"

    first = messages[0]
    if first.get("role") != "system" or not first.get("content", "").strip():
        return "system_prompt_missing"

    latest_count = 0
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role not in VALID_MESSAGE_ROLES:
            return "invalid_message_role"
        if not isinstance(content, str) or not content.strip():
            return "empty_message_content"
        if (
            role == latest_user_message.get("role")
            and content == latest_user_message.get("content")
        ):
            latest_count += 1

    if latest_count == 0:
        return "latest_user_message_missing"
    if latest_count > 1:
        return "latest_user_message_duplicated"

    last = messages[-1]
    if (
        last.get("role") != latest_user_message.get("role")
        or last.get("content") != latest_user_message.get("content")
    ):
        return "latest_user_message_not_final"

    return None


def severe_context_comparison_warning(
    context_comparison: dict[str, object] | None,
) -> str | None:
    """Return fallback reason for comparison warnings that block prompt switch."""
    if not context_comparison:
        return None

    warnings = context_comparison.get("warnings", [])
    if not isinstance(warnings, list):
        return None

    warning_names = {warning for warning in warnings if isinstance(warning, str)}
    if warning_names & SEVERE_COMPARISON_WARNINGS:
        return "context_comparison_missing_latest_user_message"
    return None
