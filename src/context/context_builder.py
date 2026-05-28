from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.context.token_estimator import ApproximateTokenEstimator, TokenEstimator
from src.core.contracts import ContextBudget, ContextPacket, MemoryCandidate, RoutePlan


CONTEXT_SOURCE_ORDER = (
    "structured_memory",
    "current_chat_chunks",
    "previous_chat_memory",
    "document_memory",
    "recent_messages",
)


@dataclass(frozen=True)
class SelectedContext:
    """Selected and dropped candidates for one source."""

    selected: list[MemoryCandidate]
    dropped: list[dict[str, Any]]
    used_tokens: int


class ContextBuilder:
    """Build a trace-only context packet from ranked candidates and budgets."""

    def __init__(self, token_estimator: TokenEstimator | None = None) -> None:
        self.token_estimator = token_estimator or ApproximateTokenEstimator()

    def build(
        self,
        system_prompt: str,
        latest_user_message: dict[str, str],
        ranked_candidates: list[MemoryCandidate],
        context_budget: ContextBudget,
        route_plan: RoutePlan,
    ) -> ContextPacket:
        """Build a budget-aware ContextPacket without affecting the model call."""
        grouped = group_candidates_by_source(ranked_candidates)
        selected_by_source: dict[str, SelectedContext] = {}
        selected_candidates: list[MemoryCandidate] = []
        dropped_candidates: list[dict[str, Any]] = []

        for source in CONTEXT_SOURCE_ORDER:
            selected = self.select_for_source(
                source=source,
                candidates=grouped.get(source, []),
                budget=context_budget.source_token_budgets.get(source, 0),
            )
            selected_by_source[source] = selected
            selected_candidates.extend(selected.selected)
            dropped_candidates.extend(selected.dropped)

        model_messages = self.build_trace_messages(
            system_prompt=system_prompt,
            selected_by_source=selected_by_source,
            latest_user_message=latest_user_message,
        )
        estimated_tokens = self.token_estimator.estimate_messages(model_messages)
        return ContextPacket(
            chat_id=first_chat_id(ranked_candidates),
            system_prompt=system_prompt,
            structured_memory=format_source_section(
                "structured_memory",
                selected_by_source["structured_memory"].selected,
            ),
            recent_message_ids=[
                source_id
                for candidate in selected_by_source["recent_messages"].selected
                for source_id in candidate.source_message_ids
            ],
            candidates=selected_candidates,
            budget=context_budget,
            model_messages=model_messages,
            metadata={
                "trace_only": True,
                "route_intent": route_plan.intent,
                "context_profile": context_budget.metadata.get("context_profile"),
                "estimated_token_usage": estimated_tokens,
                "source_token_usage": {
                    source: selected.used_tokens
                    for source, selected in selected_by_source.items()
                },
                "dropped_candidates": dropped_candidates,
                "section_order": [
                    "system",
                    "structured_memory",
                    "retrieved_memory",
                    "recent_messages",
                    "latest_user_message",
                ],
            },
        )

    def select_for_source(
        self,
        source: str,
        candidates: list[MemoryCandidate],
        budget: int,
    ) -> SelectedContext:
        """Select highest-ranked candidates that fit in one source budget."""
        selected: list[MemoryCandidate] = []
        dropped: list[dict[str, Any]] = []
        used_tokens = 0
        for candidate in candidates:
            candidate_tokens = self.token_estimator.estimate_text(candidate.content)
            if candidate_tokens + used_tokens <= budget:
                selected.append(candidate)
                used_tokens += candidate_tokens
                continue

            dropped.append(
                {
                    "record_id": candidate.record_id,
                    "source": candidate.source,
                    "reason": "source_budget_exceeded",
                    "estimated_tokens": candidate_tokens,
                    "source_budget": budget,
                }
            )
        return SelectedContext(selected=selected, dropped=dropped, used_tokens=used_tokens)

    def build_trace_messages(
        self,
        system_prompt: str,
        selected_by_source: dict[str, SelectedContext],
        latest_user_message: dict[str, str],
    ) -> list[dict[str, str]]:
        """Create trace-only model-shaped messages in the target ordering."""
        messages = [{"role": "system", "content": system_prompt}]
        structured_memory = format_source_section(
            "structured_memory",
            selected_by_source["structured_memory"].selected,
        )
        if structured_memory:
            messages.append({"role": "system", "content": structured_memory})

        retrieved_memory = "\n\n".join(
            section
            for section in (
                format_source_section(
                    "current_chat_chunks",
                    selected_by_source["current_chat_chunks"].selected,
                ),
                format_source_section(
                    "previous_chat_memory",
                    selected_by_source["previous_chat_memory"].selected,
                ),
                format_source_section(
                    "document_memory",
                    selected_by_source["document_memory"].selected,
                ),
            )
            if section
        )
        if retrieved_memory:
            messages.append({"role": "system", "content": retrieved_memory})

        recent_messages = selected_by_source["recent_messages"].selected
        messages.extend(format_recent_message(candidate) for candidate in recent_messages)
        messages.append(latest_user_message)
        return messages


def group_candidates_by_source(
    candidates: list[MemoryCandidate],
) -> dict[str, list[MemoryCandidate]]:
    """Group ranked candidates by source while preserving rank order."""
    grouped: dict[str, list[MemoryCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.source, []).append(candidate)
    return grouped


def format_source_section(source: str, candidates: list[MemoryCandidate]) -> str:
    """Format non-recent candidates into a section."""
    if not candidates:
        return ""

    title = source.replace("_", " ").title()
    lines = [f"{title}:"]
    for candidate in candidates:
        label = candidate.record_id if candidate.record_id is not None else "candidate"
        lines.append(f"- [{label}] {candidate.content}")
    return "\n".join(lines)


def format_recent_message(candidate: MemoryCandidate) -> dict[str, str]:
    """Convert a recent-message candidate back to a chat-shaped message."""
    role = str(candidate.metadata.get("role", "user"))
    return {"role": role, "content": candidate.content}


def first_chat_id(candidates: list[MemoryCandidate]) -> str:
    """Return the first available chat id for the packet."""
    for candidate in candidates:
        if candidate.chat_id:
            return candidate.chat_id
    return ""
