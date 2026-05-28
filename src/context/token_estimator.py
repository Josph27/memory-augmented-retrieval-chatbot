from __future__ import annotations

from typing import Protocol


class TokenEstimator(Protocol):
    """Replaceable token estimator interface."""

    def estimate_text(self, text: str) -> int:
        """Estimate tokens for plain text."""
        ...

    def estimate_messages(self, messages: list[dict[str, str]]) -> int:
        """Estimate tokens for chat messages."""
        ...


class ApproximateTokenEstimator:
    """Small tokenizer-free estimator.

    This intentionally overestimates a little and can later be replaced with a
    model-specific tokenizer behind the same interface.
    """

    def __init__(self, chars_per_token: float = 4.0, per_message_overhead: int = 4) -> None:
        self.chars_per_token = chars_per_token
        self.per_message_overhead = per_message_overhead

    def estimate_text(self, text: str) -> int:
        """Estimate tokens from character length."""
        if not text:
            return 0
        return max(1, int(len(text) / self.chars_per_token) + 1)

    def estimate_messages(self, messages: list[dict[str, str]]) -> int:
        """Estimate chat message tokens including small per-message overhead."""
        total = 0
        for message in messages:
            total += self.per_message_overhead
            total += self.estimate_text(str(message.get("role", "")))
            total += self.estimate_text(str(message.get("content", "")))
        return total
