from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TokenEstimator(Protocol):
    """Replaceable token estimator interface.

    Implementations may be approximate or backed by a model-specific tokenizer.
    The chat pipeline only depends on this protocol so a real tokenizer can be
    plugged in without changing context construction.
    """

    model_name: str | None
    backend: str

    def estimate_text(self, text: str) -> int:
        """Estimate tokens for plain text."""
        ...

    def estimate_messages(self, messages: list[dict[str, str]]) -> int:
        """Estimate tokens for chat messages."""
        ...


@dataclass(frozen=True)
class TokenEstimatorInfo:
    """Debug metadata describing the tokenizer backend in use."""

    backend: str
    model_name: str | None
    approximate: bool


class ApproximateTokenEstimator:
    """Small tokenizer-free estimator.

    This intentionally overestimates a little and can later be replaced with a
    model-specific tokenizer behind the same interface.
    """

    backend = "approximate_chars"

    def __init__(
        self,
        chars_per_token: float = 4.0,
        per_message_overhead: int = 4,
        model_name: str | None = None,
    ) -> None:
        self.chars_per_token = chars_per_token
        self.per_message_overhead = per_message_overhead
        self.model_name = model_name

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

    def info(self) -> TokenEstimatorInfo:
        """Return compact debug metadata about this estimator."""
        return TokenEstimatorInfo(
            backend=self.backend,
            model_name=self.model_name,
            approximate=True,
        )


def build_token_estimator(model_name: str | None = None) -> TokenEstimator:
    """Build the best available token estimator.

    No real tokenizer dependency is currently declared by the project, so this
    returns the approximate fallback. The factory is the extension point for a
    future model-specific tokenizer.
    """
    return ApproximateTokenEstimator(model_name=model_name)
