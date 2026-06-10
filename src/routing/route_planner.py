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
            reason="Document memory is enabled only for document-like questions.",
            limit=4,
        ),
    )
    ranking_profile: str = "none_current_order"
    fallback_policy: str = "answer_from_available_context_or_state_missing_information"
    update_policy: str = "update_structured_memory_after_response_when_threshold_reached"
    termination_policy: str = "response_generated_and_messages_saved"
    intent_context_profiles: dict[str, str] = None

    def __post_init__(self) -> None:
        if self.intent_context_profiles is None:
            object.__setattr__(
                self,
                "intent_context_profiles",
                {
                    "general_question": "general_chat",
                    "current_chat_question": "memory_recall",
                    "previous_memory_question": "memory_recall",
                    "decision_question": "memory_recall",
                    "task_question": "memory_recall",
                    "document_question": "document_question",
                },
            )


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
                enabled=source_enabled(source_policy, analysis),
                reason=source_reason(source_policy, analysis),
                query=(
                    analysis.normalized_query
                    if source_enabled(source_policy, analysis)
                    else None
                ),
                limit=source_policy.limit,
            )
            for source_policy in (*self.policy.active_sources, *self.policy.future_sources)
        ]
        return RoutePlan(
            query=analysis.normalized_query,
            intent=analysis.intent,
            confidence=analysis.confidence,
            requires_retrieval=analysis.signals.asks_about_documents,
            sources=sources,
            ranking_profile=self.policy.ranking_profile,
            context_profile=self.policy.intent_context_profiles.get(
                analysis.intent,
                "general_chat",
            ),
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


def source_enabled(
    source_policy: SourceRoutingPolicy,
    analysis: QueryAnalysis,
) -> bool:
    """Return whether a source should be enabled for this query."""
    if source_policy.source == "document_memory":
        return analysis.signals.asks_about_documents
    return source_policy.enabled


def source_reason(
    source_policy: SourceRoutingPolicy,
    analysis: QueryAnalysis,
) -> str:
    """Return a per-query reason for a source plan."""
    if source_policy.source == "document_memory" and analysis.signals.asks_about_documents:
        return "Document-like query detected; enabling LangChain-Chroma document retrieval."
    return source_policy.reason
