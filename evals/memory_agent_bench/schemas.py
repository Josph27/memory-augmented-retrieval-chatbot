from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MABenchSession:
    """One incrementally replayed benchmark session."""

    session_id: str
    chunks: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("MemoryAgentBench session_id must not be empty.")
        if not self.chunks or any(not chunk.strip() for chunk in self.chunks):
            raise ValueError("MemoryAgentBench sessions require non-empty chunks.")


@dataclass(frozen=True)
class MABenchExample:
    """Normalized MemoryAgentBench-style example."""

    example_id: str
    competency: str
    sessions: tuple[MABenchSession, ...]
    questions: tuple[str, ...]
    answers: tuple[tuple[str, ...], ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.example_id.strip():
            raise ValueError("MemoryAgentBench example_id must not be empty.")
        if not self.competency.strip():
            raise ValueError("MemoryAgentBench competency must not be empty.")
        if not self.sessions:
            raise ValueError("MemoryAgentBench examples require at least one session.")
        if not self.questions or any(not question.strip() for question in self.questions):
            raise ValueError("MemoryAgentBench examples require non-empty questions.")
        if len(self.questions) != len(self.answers):
            raise ValueError("MemoryAgentBench questions and answers must align.")
        if any(not answers for answers in self.answers):
            raise ValueError("Each MemoryAgentBench question requires a gold answer.")
