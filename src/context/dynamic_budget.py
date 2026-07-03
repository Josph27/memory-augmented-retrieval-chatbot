from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from src.core.contracts import RoutePlan


LONG_DOCUMENT_TASK_CONTEXTS = frozenset(
    {"document_synthesis", "long_document_summary"}
)


@dataclass(frozen=True)
class MemoryBudgetPolicy:
    """Small route-aware working-memory policy, independent of model hard limits."""

    base_memory_budget: int = 4096
    chat_memory_cap: int = 8192
    document_memory_cap: int = 16_384
    multi_scope_memory_cap: int = 16_384
    long_document_memory_cap: int = 32_768
    required_evidence_headroom_ratio: float = 0.25


@dataclass(frozen=True)
class DynamicBudgetPlan:
    base_memory_budget: int
    route_specific_cap: int
    route_cap_reason: str
    required_evidence_floor: int
    required_headroom: int
    required_target: int
    available_memory_budget: int
    working_memory_budget: int
    budget_expanded_for_required_evidence: bool
    required_evidence_exceeds_available: bool

    def to_metadata(self) -> dict[str, object]:
        return {
            "base_memory_budget": self.base_memory_budget,
            "route_specific_cap": self.route_specific_cap,
            "route_cap_reason": self.route_cap_reason,
            "required_evidence_floor": self.required_evidence_floor,
            "required_headroom": self.required_headroom,
            "required_target": self.required_target,
            "available_memory_budget": self.available_memory_budget,
            "working_memory_budget": self.working_memory_budget,
            "budget_expanded_for_required_evidence": (
                self.budget_expanded_for_required_evidence
            ),
            "required_evidence_exceeds_available": (
                self.required_evidence_exceeds_available
            ),
        }


class DynamicWorkingMemoryBudgetPlanner:
    """Resolve one deterministic route cap and required-evidence-aware target."""

    def __init__(self, policy: MemoryBudgetPolicy | None = None) -> None:
        self.policy = policy or MemoryBudgetPolicy()

    def plan(
        self,
        *,
        route_plan: RoutePlan,
        available_memory_budget: int,
        required_evidence_floor: int,
    ) -> DynamicBudgetPlan:
        route_cap, reason = route_specific_cap(route_plan, self.policy)
        required_headroom = ceil(
            required_evidence_floor
            * max(0.0, self.policy.required_evidence_headroom_ratio)
        )
        required_target = required_evidence_floor + required_headroom
        normal_target = max(self.policy.base_memory_budget, required_target)
        working = min(
            max(0, available_memory_budget),
            max(0, route_cap),
            max(0, normal_target),
        )
        expanded = False
        if (
            required_evidence_floor > route_cap
            and required_evidence_floor <= available_memory_budget
        ):
            working = min(
                available_memory_budget,
                max(required_evidence_floor, required_target),
            )
            expanded = working > route_cap
        return DynamicBudgetPlan(
            base_memory_budget=self.policy.base_memory_budget,
            route_specific_cap=route_cap,
            route_cap_reason=reason,
            required_evidence_floor=required_evidence_floor,
            required_headroom=required_headroom,
            required_target=required_target,
            available_memory_budget=max(0, available_memory_budget),
            working_memory_budget=max(0, working),
            budget_expanded_for_required_evidence=expanded,
            required_evidence_exceeds_available=(
                required_evidence_floor > available_memory_budget
            ),
        )


def route_specific_cap(
    route_plan: RoutePlan,
    policy: MemoryBudgetPolicy,
) -> tuple[int, str]:
    """Use existing typed route/task fields only; do not classify query text here."""
    metadata = route_plan.metadata
    task_context = str(metadata.get("task_context") or "")
    required_scopes = {
        str(scope)
        for scope in metadata.get("required_scopes", [])
        if isinstance(scope, str)
    }
    if task_context in LONG_DOCUMENT_TASK_CONTEXTS:
        return policy.long_document_memory_cap, "explicit_long_document_task"
    if len(required_scopes) > 1:
        return policy.multi_scope_memory_cap, "multiple_required_scopes"
    if required_scopes == {"document"} or route_plan.intent in {
        "DOCUMENT_QA",
        "document_question",
    }:
        return policy.document_memory_cap, "single_document_scope"
    if required_scopes & {"current_chat", "previous_chat"} or route_plan.intent in {
        "SAME_CHAT_RECALL",
        "PREVIOUS_CHAT_RECALL",
        "current_chat_question",
        "previous_memory_question",
    }:
        return policy.chat_memory_cap, "chat_recall_scope"
    if required_scopes == {"durable"} or route_plan.intent in {
        "STRUCTURED_PREFERENCE_RECALL",
        "decision_question",
    }:
        return policy.base_memory_budget, "simple_durable_recall"
    return policy.base_memory_budget, "base_recent_or_general"
