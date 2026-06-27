from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.context.context_budget_allocator import ContextBudgetAllocator
from src.context.context_builder import ContextBuilder
from src.core.contracts import ContextBudget, ContextPacket, MemoryCandidate, RoutePlan


@dataclass(frozen=True)
class ContextManagerResult:
    """Context orchestration result produced by ContextManagerAgent."""

    context_budget: ContextBudget
    context_packet: ContextPacket
    metadata: dict[str, Any]


class ContextManagerAgent:
    """Responsibility wrapper for deterministic context budgeting and packet building."""

    def __init__(
        self,
        budget_allocator: ContextBudgetAllocator | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self.budget_allocator = budget_allocator or ContextBudgetAllocator()
        self.context_builder = context_builder or ContextBuilder()

    def build_context_packet(
        self,
        *,
        system_prompt: str,
        latest_user_message: dict[str, str],
        ranked_candidates: list[MemoryCandidate],
        route_plan: RoutePlan,
    ) -> ContextManagerResult:
        """Allocate budget and build a ContextPacket without changing prompt behavior."""
        context_budget = self.budget_allocator.allocate(
            route_plan=route_plan,
            ranked_candidates=ranked_candidates,
            system_prompt=system_prompt,
        )
        context_packet = self.context_builder.build(
            system_prompt=system_prompt,
            latest_user_message=latest_user_message,
            ranked_candidates=ranked_candidates,
            context_budget=context_budget,
            route_plan=route_plan,
        )
        return ContextManagerResult(
            context_budget=context_budget,
            context_packet=context_packet,
            metadata=context_manager_metadata(context_budget, context_packet),
        )


def context_manager_metadata(
    context_budget: ContextBudget,
    context_packet: ContextPacket,
) -> dict[str, Any]:
    """Return trace metadata for context-manager decisions."""
    dropped = context_packet.metadata.get("dropped_candidates", [])
    if not isinstance(dropped, list):
        dropped = []
    return {
        "context_manager_used": True,
        "source_budgets": dict(context_budget.source_token_budgets),
        "included_candidate_counts_by_source": candidate_counts_by_source(
            context_packet.candidates
        ),
        "dropped_candidate_counts_by_source": dropped_counts_by_source(dropped),
        "final_prompt_sections": list(context_packet.metadata.get("section_order", [])),
    }


def candidate_counts_by_source(
    candidates: list[MemoryCandidate],
) -> dict[str, int]:
    """Count selected candidates by source."""
    counts: dict[str, int] = {}
    for candidate in candidates:
        counts[candidate.source] = counts.get(candidate.source, 0) + 1
    return counts


def dropped_counts_by_source(dropped_candidates: list[object]) -> dict[str, int]:
    """Count dropped candidates by source from ContextPacket metadata."""
    counts: dict[str, int] = {}
    for item in dropped_candidates:
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        if not isinstance(source, str):
            continue
        counts[source] = counts.get(source, 0) + 1
    return counts
