from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.contracts import RoutePlan, SourcePlan
from src.routing.route_planner import RoutePlanner


@dataclass(frozen=True)
class RoutingDecision:
    """Agent-shaped routing output for one user query."""

    route_plan: RoutePlan
    use_recent_messages: bool
    use_structured_memory: bool
    use_document_memory: bool
    reason: str
    confidence: float
    fallback_mode: bool = False
    metadata: dict[str, Any] | None = None

    def to_trace_dict(self) -> dict[str, Any]:
        """Return a stable trace representation for WorkflowTrace metadata."""
        return {
            "use_recent_messages": self.use_recent_messages,
            "use_structured_memory": self.use_structured_memory,
            "use_document_memory": self.use_document_memory,
            "reason": self.reason,
            "confidence": self.confidence,
            "fallback_mode": self.fallback_mode,
            "active_sources": [
                source.source for source in self.route_plan.sources if source.enabled
            ],
            "disabled_sources": [
                source.source for source in self.route_plan.sources if not source.enabled
            ],
            "intent": self.route_plan.intent,
            "context_profile": self.route_plan.context_profile,
            **(self.metadata or {}),
        }


class RoutingAgent:
    """Responsibility wrapper around the deterministic route planner.

    This class makes routing an explicit agent role without changing the
    current rule/keyword routing behavior. It delegates to RoutePlanner and
    adds a human-readable decision record for traces.
    """

    def __init__(self, route_planner: RoutePlanner | None = None) -> None:
        self.route_planner = route_planner or RoutePlanner()

    def route(self, query: str) -> RoutingDecision:
        """Return a structured routing decision for a user query."""
        try:
            route_plan = self.route_planner.plan(query)
        except Exception as error:
            return self._fallback_decision(query=query, error=error)

        if not route_plan.sources:
            return self._fallback_decision(
                query=query,
                error=ValueError("route plan did not include any sources"),
            )

        return decision_from_route_plan(route_plan)

    def _fallback_decision(self, query: str, error: Exception) -> RoutingDecision:
        """Return a conservative route when normal routing fails."""
        route_plan = RoutePlan(
            query=query.strip().lower(),
            intent="fallback_question",
            confidence=0.0,
            requires_retrieval=False,
            sources=[
                SourcePlan(
                    source="recent_messages",
                    enabled=True,
                    reason="Routing fallback keeps recent messages enabled.",
                    query=query.strip().lower(),
                ),
                SourcePlan(
                    source="structured_memory",
                    enabled=True,
                    reason="Routing fallback keeps structured memory enabled.",
                    query=query.strip().lower(),
                ),
                SourcePlan(
                    source="document_memory",
                    enabled=False,
                    reason="Routing fallback does not enable document memory automatically.",
                ),
            ],
            ranking_profile="none_current_order",
            context_profile="general_chat",
            fallback_policy="routing_agent_safe_default",
            metadata={"routing_error": f"{type(error).__name__}: {error}"},
        )
        return RoutingDecision(
            route_plan=route_plan,
            use_recent_messages=True,
            use_structured_memory=True,
            use_document_memory=False,
            reason=f"Routing fallback used after {type(error).__name__}.",
            confidence=0.0,
            fallback_mode=True,
            metadata={"routing_error": f"{type(error).__name__}: {error}"},
        )


def decision_from_route_plan(route_plan: RoutePlan) -> RoutingDecision:
    """Build an agent-shaped decision from an existing RoutePlan."""
    enabled_sources = {source.source for source in route_plan.sources if source.enabled}
    reason = routing_reason(route_plan, enabled_sources)
    return RoutingDecision(
        route_plan=route_plan,
        use_recent_messages="recent_messages" in enabled_sources,
        use_structured_memory="structured_memory" in enabled_sources,
        use_document_memory="document_memory" in enabled_sources,
        reason=reason,
        confidence=route_plan.confidence if route_plan.confidence is not None else 0.0,
        fallback_mode=False,
    )


def routing_reason(route_plan: RoutePlan, enabled_sources: set[str]) -> str:
    """Return a concise human-readable reason for the route decision."""
    if "document_memory" in enabled_sources:
        return "Document-like query detected; recent, structured, and document memory enabled."
    if route_plan.intent in {
        "current_chat_question",
        "previous_memory_question",
        "decision_question",
        "task_question",
    }:
        return "Memory-oriented query detected; recent and structured memory enabled."
    return "General query; recent and structured memory enabled by default."
