from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SUPPORTED_MEMORY_MODES = {
    "recent_only",
    "gist_only",
    "span_retrieval",
    "full",
    # Reserved compatibility modes from the first scaffold.
    "structured",
    "structured_vector",
}


@dataclass(frozen=True)
class HistoryMessage:
    """One normalized message from a benchmark session."""

    role: str
    content: str
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant"}:
            raise ValueError(f"Unsupported history role: {self.role!r}")
        if not self.content.strip():
            raise ValueError("History message content must not be empty.")


@dataclass(frozen=True)
class HistorySession:
    """One normalized conversation session."""

    session_id: str
    messages: tuple[HistoryMessage, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("Session id must not be empty.")
        if not self.messages:
            raise ValueError("A history session requires at least one message.")


@dataclass(frozen=True)
class LongMemEvalCase:
    """Normalized case consumed by the unofficial adapter runner."""

    case_id: str
    question: str
    gold_answer: str
    question_type: str | None
    sessions: tuple[HistorySession, ...]
    expected_evidence: tuple[str, ...] = ()
    expected_abstain: bool = False
    mock_answer: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("Case id must not be empty.")
        if not self.question.strip():
            raise ValueError("Question must not be empty.")
        if not self.expected_abstain and not self.gold_answer.strip():
            raise ValueError("A non-abstain case requires a gold answer.")
        if not self.sessions:
            raise ValueError("A benchmark case requires at least one history session.")
