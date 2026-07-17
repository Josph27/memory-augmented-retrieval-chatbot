from __future__ import annotations

import os
from dataclasses import dataclass

from src.core.contracts import RoutePlan, SourcePlan
from src.routing.query_analyzer import QueryAnalysis, QueryAnalyzer
from src.routing.retrieval_query import simplify_retrieval_query


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
            source="current_chat_gist",
            enabled=False,
            reason="Current-chat gist retrieval is not implemented yet.",
        ),
        SourceRoutingPolicy(
            source="current_chat_span",
            enabled=False,
            reason="Current-chat span retrieval is enabled only for same-chat recall.",
        ),
        SourceRoutingPolicy(
            source="previous_chat_gist",
            enabled=False,
            reason="Previous-chat gist retrieval is enabled only for previous-chat recall.",
        ),
        SourceRoutingPolicy(
            source="raw_message_span",
            enabled=False,
            reason="Raw-message span drill-down is not enabled by default.",
        ),
        SourceRoutingPolicy(
            source="current_chat_chunks",
            enabled=False,
            reason="Legacy alias; prefer current_chat_gist for new memory code.",
        ),
        SourceRoutingPolicy(
            source="previous_chat_memory",
            enabled=False,
            reason="Legacy alias; prefer previous_chat_gist for new memory code.",
        ),
        SourceRoutingPolicy(
            source="document_memory",
            enabled=False,
            reason="Document memory is enabled only for document-like questions.",
            limit=None,
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
        context_profile = (
            "global_summary"
            if analysis.signals.asks_for_global_summary
            else self.policy.intent_context_profiles.get(
                analysis.intent,
                "general_chat",
            )
        )
        rewrite = simplify_retrieval_query(
            analysis.normalized_query,
            context_profile=context_profile,
            enabled=retrieval_query_simplification_enabled(),
        )
        sources = [
            SourcePlan(
                source=source_policy.source,
                enabled=source_enabled(source_policy, analysis),
                reason=source_reason(source_policy, analysis),
                query=(
                    rewrite.retrieval_query if source_enabled(source_policy, analysis) else None
                ),
                limit=source_policy.limit,
                filters={
                    "context_profile": context_profile,
                    "original_query": analysis.normalized_query,
                    "retrieval_query": rewrite.retrieval_query,
                    "query_rewrite_applied": rewrite.applied,
                    "query_rewrite_reason": rewrite.reason,
                },
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
            context_profile=context_profile,
            fallback_policy=self.policy.fallback_policy,
            update_policy=self.policy.update_policy,
            termination_policy=self.policy.termination_policy,
            metadata={
                "signals": signals_to_csv(analysis),
                "requires_raw_span": analysis.signals.asks_for_exact_quote,
                "original_query": analysis.normalized_query,
                "retrieval_query": rewrite.retrieval_query,
                "query_rewrite_applied": rewrite.applied,
                "query_rewrite_reason": rewrite.reason,
            },
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
            ("asks_for_exact_quote", analysis.signals.asks_for_exact_quote),
            ("asks_for_global_summary", analysis.signals.asks_for_global_summary),
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
    if source_policy.source == "current_chat_span":
        return (
            analysis.signals.asks_about_current_chat
            and not analysis.signals.asks_about_previous_memory
        )
    if source_policy.source == "previous_chat_gist":
        return previous_chat_gist_retrieval_enabled() and (
            analysis.signals.asks_about_previous_memory or analysis.signals.asks_for_global_summary
        )
    if source_policy.source == "raw_message_span":
        return previous_chat_gist_retrieval_enabled() and (
            analysis.signals.asks_about_previous_memory or analysis.signals.asks_for_global_summary
        )
    return source_policy.enabled


def source_reason(
    source_policy: SourceRoutingPolicy,
    analysis: QueryAnalysis,
) -> str:
    """Return a per-query reason for a source plan."""
    if source_policy.source == "document_memory" and analysis.signals.asks_about_documents:
        return "Document-like query detected; enabling LangChain-Chroma document retrieval."
    if (
        source_policy.source == "current_chat_span"
        and analysis.signals.asks_about_current_chat
        and not analysis.signals.asks_about_previous_memory
    ):
        return "Same-chat recall detected; enabling exact current-chat span retrieval."
    if (
        source_policy.source == "previous_chat_gist"
        and previous_chat_gist_retrieval_enabled()
        and (
            analysis.signals.asks_about_previous_memory or analysis.signals.asks_for_global_summary
        )
    ):
        return "Previous-chat memory query detected; enabling previous-chat gist retrieval."
    if (
        source_policy.source == "raw_message_span"
        and previous_chat_gist_retrieval_enabled()
        and (
            analysis.signals.asks_about_previous_memory or analysis.signals.asks_for_global_summary
        )
    ):
        return "Previous-chat recall enables direct raw-span evidence."
    return source_policy.reason


def previous_chat_gist_retrieval_enabled() -> bool:
    """Return whether previous-chat gist retrieval is enabled for route planning."""
    value = os.getenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED")
    if value is None:
        return True
    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def retrieval_query_simplification_enabled() -> bool:
    value = os.getenv("ENABLE_RETRIEVAL_QUERY_SIMPLIFICATION")
    if value is None:
        return True
    return value.strip().lower() in {"1", "true", "yes", "on"}
