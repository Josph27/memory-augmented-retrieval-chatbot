from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


MemorySourceType = Literal[
    "recent_messages",
    "structured_memory",
    "current_chat_chunks",
    "previous_chat_memory",
    "document_memory",
    "short_term",
    "long_term",
    "document",
    "raw_messages",
    "unknown",
]


@dataclass(frozen=True)
class SourcePlan:
    """A planned source to query for context."""

    source: MemorySourceType
    enabled: bool = True
    reason: str | None = None
    query: str | None = None
    limit: int | None = None
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoutePlan:
    """Routing decision for one user turn."""

    query: str
    sources: list[SourcePlan] = field(default_factory=list)
    intent: str | None = None
    confidence: float | None = None
    requires_retrieval: bool | None = None
    ranking_profile: str | None = None
    context_profile: str | None = None
    fallback_policy: str | None = None
    update_policy: str | None = None
    termination_policy: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryCandidate:
    """One candidate memory/context item before final prompt assembly."""

    source: MemorySourceType
    content: str
    score: float | None = None
    record_id: str | int | None = None
    chat_id: str | None = None
    source_message_ids: list[int] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextBudget:
    """Budget allocation for context construction."""

    max_tokens: int | None = None
    system_tokens: int | None = None
    memory_tokens: int | None = None
    recent_message_tokens: int | None = None
    retrieval_tokens: int | None = None
    reserved_response_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextPacket:
    """Context selected for a chat model call."""

    chat_id: str
    system_prompt: str | None = None
    structured_memory: str | None = None
    recent_message_ids: list[int] = field(default_factory=list)
    candidates: list[MemoryCandidate] = field(default_factory=list)
    budget: ContextBudget | None = None
    model_messages: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowTrace:
    """Trace record for one agent workflow run."""

    trace_id: str
    chat_id: str
    route_plan: RoutePlan | None = None
    retrieved_candidates: list[MemoryCandidate] = field(default_factory=list)
    context_packet: ContextPacket | None = None
    termination_reason: str | None = None
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentTurnResult:
    """Final result for one user turn through the agent pipeline."""

    answer: str
    chat_id: str
    trace_id: str
    termination_reason: str
    trace: WorkflowTrace
    assistant_message_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
