from __future__ import annotations

from dataclasses import dataclass

from src.core.contracts import RoutePlan, SourcePlan
from src.routing.query_analyzer import QueryAnalysis, QueryAnalyzer


@dataclass(frozen=True)
class SourceRoutingPolicy:
    """Static routing policy for one memory source."""

    source: str
    enabled: bool
    reason: str
    limit: int | None = None


@dataclass(frozen=True)
class RoutePlannerPolicy:
    """Centralized route defaults for the current architecture."""

    active_sources: tuple[SourceRoutingPolicy, ...] = (
        SourceRoutingPolicy(
            source="recent_messages",
            enabled=True,
            reason="Current runtime always includes recent raw messages.",
        ),
        SourceRoutingPolicy(
            source="structured_memory",
            enabled=True,
            reason="Current runtime includes structured current-chat memory when present.",
        ),
    )
    future_sources: tuple[SourceRoutingPolicy, ...] = (
        SourceRoutingPolicy(
            source="current_chat_chunks",
            enabled=False,
            reason="Gist/chunk retrieval is not implemented yet.",
        ),
        SourceRoutingPolicy(
            source="previous_chat_memory",
            enabled=False,
            reason="Long-term memory across chats is not implemented yet.",
        ),
        SourceRoutingPolicy(
            source="document_memory",
            enabled=False,
            reason="Document memory and retrieval are not implemented yet.",
        ),
    )
    ranking_profile: str = "none_current_order"
    context_profile: str = "structured_memory_plus_recent_messages"
    fallback_policy: str = "answer_from_available_context_or_state_missing_information"
    update_policy: str = "update_structured_memory_after_response_when_threshold_reached"
    termination_policy: str = "response_generated_and_messages_saved"


class RoutePlanner:
    """Create production-shaped route plans without changing retrieval behavior."""

    def __init__(
        self,
        analyzer: QueryAnalyzer | None = None,
        policy: RoutePlannerPolicy | None = None,
    ) -> None:
        self.analyzer = analyzer or QueryAnalyzer()
        self.policy = policy or RoutePlannerPolicy()

    def plan(self, query: str) -> RoutePlan:
        """Analyze a query and return the current route plan."""
        analysis = self.analyzer.analyze(query)
        return self.plan_from_analysis(analysis)

    def plan_from_analysis(self, analysis: QueryAnalysis) -> RoutePlan:
        """Build a RoutePlan from precomputed query analysis."""
        sources = [
            SourcePlan(
                source=source_policy.source,
                enabled=source_policy.enabled,
                reason=source_policy.reason,
                query=analysis.normalized_query if source_policy.enabled else None,
                limit=source_policy.limit,
            )
            for source_policy in (*self.policy.active_sources, *self.policy.future_sources)
        ]
        return RoutePlan(
            query=analysis.normalized_query,
            intent=analysis.intent,
            confidence=analysis.confidence,
            requires_retrieval=False,
            sources=sources,
            ranking_profile=self.policy.ranking_profile,
            context_profile=self.policy.context_profile,
            fallback_policy=self.policy.fallback_policy,
            update_policy=self.policy.update_policy,
            termination_policy=self.policy.termination_policy,
            metadata={"signals": signals_to_csv(analysis)},
        )


def signals_to_csv(analysis: QueryAnalysis) -> str:
    """Serialize active signal names for compact trace metadata."""
    active = [
        name
        for name, enabled in (
            ("asks_about_current_chat", analysis.signals.asks_about_current_chat),
            ("asks_about_previous_memory", analysis.signals.asks_about_previous_memory),
            ("asks_about_documents", analysis.signals.asks_about_documents),
            ("asks_about_decision", analysis.signals.asks_about_decision),
            ("asks_about_task", analysis.signals.asks_about_task),
            ("asks_general_question", analysis.signals.asks_general_question),
        )
        if enabled
    ]
    return ",".join(active)
