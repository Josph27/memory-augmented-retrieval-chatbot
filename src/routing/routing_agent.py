from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from src.core.contracts import MemorySourceType, RoutePlan, SourcePlan
from src.routing.route_planner import RoutePlanner
from src.routing.semantic_router import SemanticRouter

ROUTING_MODES = {
    "rule",
    "llm",
    "hybrid",
    "semantic",
    "hybrid_semantic",
    "semantic_full",
}
MIN_LLM_ROUTING_CONFIDENCE = 0.5
MIN_SEMANTIC_FULL_CONFIDENCE = 0.62
SEMANTIC_FULL_SOURCES = {
    "recent_messages",
    "structured_memory",
    "document_memory",
    "previous_chat_gist",
    "raw_message_span",
    "current_chat_span",
}


class RoutingModel(Protocol):
    """Minimal chat-model protocol used by optional LLM routing."""

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        """Return a chat completion as text."""
        ...


class SemanticRoutingBackend(Protocol):
    """Router contract for optional semantic backends."""

    def route(self, query: str, task_context: str | None = None) -> object:
        """Return a semantic route object."""
        ...

    def to_route_plan(self, semantic_plan: object) -> RoutePlan:
        """Adapt the semantic route object into the internal RoutePlan schema."""
        ...


@dataclass(frozen=True)
class SemanticFullExpansion:
    """Conservative source expansion produced by experimental semantic_full mode."""

    enabled_sources: frozenset[str] = field(default_factory=frozenset)
    intent: str | None = None
    context_profile: str | None = None
    confidence: float = 1.0
    reason: str = "No semantic expansion."


class SemanticFullBackend(Protocol):
    """Classifier contract for semantic_full expansion backends."""

    def classify(self, query: str) -> SemanticFullExpansion:
        """Return source expansions for the query."""
        ...


class KeywordSemanticFullBackend:
    """Small deterministic semantic expansion backend.

    This intentionally avoids model calls and heavy dependencies. It is an
    experimental opt-in layer over the deterministic RoutePlanner: it can add
    semantically implied sources, but it never removes the deterministic
    baseline sources.
    """

    document_patterns = (
        r"\b(?:uploaded|provided|attached)\b",
        r"\b(?:attachment|attachments)\b",
        r"\b(?:document|documents|file|files|pdf|report|paper)\b",
        r"\b(?:material|materials|source|sources) i (?:provided|uploaded|attached|gave)\b",
        r"\b(?:using|based on|from|in) (?:the )?(?:material|attachment|report)\b",
        r"\bwhat i (?:uploaded|provided|attached)\b",
        r"\bmain point of the report\b",
    )
    previous_chat_patterns = (
        r"\blast time\b",
        r"\bbefore\b",
        r"\bprevious(?:ly)?\b",
        r"\bprevious (?:chat|conversation|thread|discussion)\b",
        r"\bpast (?:chat|conversation|thread|discussion)\b",
        r"\bwhat did we discuss\b",
        r"\bwhat did i tell you\b",
        r"\bwhat we discussed\b",
        r"\bwhat i told you\b",
    )
    structured_memory_patterns = (
        r"\bwhat do you remember about my\b",
        r"\bmy preferences?\b",
        r"\bmy constraints?\b",
        r"\bconstraints did i ask you\b",
        r"\bkeep in mind\b",
        r"\bsaved memory\b",
        r"\bprofile information\b",
        r"\bremember about my preferences?\b",
    )
    current_chat_patterns = (
        r"\bearlier in this (?:chat|conversation|thread)\b",
        r"\bin this (?:chat|conversation|thread)\b",
        r"\bprevious turn\b",
        r"\babove\b",
        r"\bjust now\b",
    )
    summary_patterns = (r"\bsummar(?:ize|y)\b", r"\bmain point\b", r"\blimitations?\b")

    def classify(self, query: str) -> SemanticFullExpansion:
        normalized = normalize_for_semantic_full(query)
        enabled: set[str] = set()
        reasons: list[str] = []
        intent: str | None = None
        context_profile: str | None = None

        if matches_any(normalized, self.document_patterns):
            enabled.add("document_memory")
            reasons.append("document/material reference")
            intent = "semantic_document_question"
            if matches_any(normalized, self.summary_patterns):
                context_profile = "global_summary"

        if matches_any(normalized, self.previous_chat_patterns):
            enabled.update({"previous_chat_gist", "raw_message_span"})
            reasons.append("previous-chat recall reference")
            intent = intent or "semantic_previous_memory_question"

        if matches_any(normalized, self.structured_memory_patterns):
            enabled.add("structured_memory")
            reasons.append("durable user-memory reference")
            intent = intent or "semantic_structured_memory_question"

        if matches_any(normalized, self.current_chat_patterns):
            enabled.add("current_chat_span")
            reasons.append("current-chat recall reference")
            intent = intent or "semantic_current_chat_question"

        return SemanticFullExpansion(
            enabled_sources=frozenset(enabled),
            intent=intent,
            context_profile=context_profile,
            confidence=0.86 if enabled else 1.0,
            reason="; ".join(reasons) if reasons else "No semantic expansion.",
        )


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
    routing_mode: str = "rule"
    routing_fallback_reason: str | None = None
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
            "routing_mode": self.routing_mode,
            "routing_fallback_reason": self.routing_fallback_reason,
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
    """Responsibility wrapper around the route planner.

    Rule routing remains the default. Optional LLM and hybrid modes can use a
    chat model for structured routing, but any invalid/uncertain result falls
    back to the deterministic RoutePlanner path.
    """

    def __init__(
        self,
        route_planner: RoutePlanner | None = None,
        mode: str = "rule",
        model: RoutingModel | None = None,
        semantic_router: SemanticRoutingBackend | None = None,
        semantic_full_backend: SemanticFullBackend | None = None,
        min_confidence: float = MIN_LLM_ROUTING_CONFIDENCE,
    ) -> None:
        self.route_planner = route_planner or RoutePlanner()
        self.mode = normalized_routing_mode(mode)
        self.model = model
        self.semantic_router = semantic_router or SemanticRouter()
        self.semantic_full_backend = (
            semantic_full_backend or KeywordSemanticFullBackend()
        )
        self.min_confidence = min_confidence

    def route(self, query: str) -> RoutingDecision:
        """Return a structured routing decision for a user query."""
        if self.mode == "rule":
            return self._rule_decision(query=query, routing_mode="rule")
        if self.mode in {"semantic", "hybrid_semantic"}:
            return self._semantic_or_fallback_decision(query=query)
        if self.mode == "semantic_full":
            return self._semantic_full_or_fallback_decision(query=query)
        return self._llm_or_fallback_decision(query=query)

    def _rule_decision(
        self,
        query: str,
        routing_mode: str,
        fallback_reason: str | None = None,
    ) -> RoutingDecision:
        """Return the deterministic route planner decision."""
        try:
            route_plan = self.route_planner.plan(query)
        except Exception as error:
            return self._fallback_decision(
                query=query,
                error=error,
                routing_mode=routing_mode,
                fallback_reason=fallback_reason,
            )

        if not route_plan.sources:
            return self._fallback_decision(
                query=query,
                error=ValueError("route plan did not include any sources"),
                routing_mode=routing_mode,
                fallback_reason=fallback_reason,
            )

        decision = decision_from_route_plan(route_plan)
        return copy_decision(
            decision,
            routing_mode=routing_mode,
            fallback_mode=fallback_reason is not None,
            routing_fallback_reason=fallback_reason,
        )

    def _llm_or_fallback_decision(self, query: str) -> RoutingDecision:
        """Use LLM routing when valid, otherwise fall back to rule routing."""
        if self.model is None:
            return self._rule_decision(
                query=query,
                routing_mode=self.mode,
                fallback_reason="missing_model",
            )
        try:
            response = self.model.chat(
                llm_routing_messages(query=query),
                temperature=0,
            )
            payload = parse_routing_json(response)
            route_plan = route_plan_from_llm_payload(
                query=query,
                payload=payload,
                base_route_plan=self.route_planner.plan(query),
                mode=self.mode,
            )
            confidence = float(payload.get("confidence", 0.0))
            if confidence < self.min_confidence:
                return self._rule_decision(
                    query=query,
                    routing_mode=self.mode,
                    fallback_reason="low_confidence",
                )
            reason = str(payload.get("reason") or "LLM routing policy selected sources.")
            return RoutingDecision(
                route_plan=route_plan,
                use_recent_messages=source_is_enabled(route_plan, "recent_messages"),
                use_structured_memory=source_is_enabled(route_plan, "structured_memory"),
                use_document_memory=source_is_enabled(route_plan, "document_memory"),
                reason=reason,
                confidence=confidence,
                fallback_mode=False,
                routing_mode=self.mode,
                routing_fallback_reason=None,
                metadata={"llm_routing_used": True},
            )
        except Exception as error:
            return self._rule_decision(
                query=query,
                routing_mode=self.mode,
                fallback_reason=f"{type(error).__name__}: {error}",
            )

    def _semantic_full_or_fallback_decision(self, query: str) -> RoutingDecision:
        """Use semantic expansion over deterministic routing, failing closed."""
        try:
            base_route_plan = self.route_planner.plan(query)
            expansion = self.semantic_full_backend.classify(query)
            validate_semantic_full_expansion(expansion)
            if expansion.enabled_sources and (
                expansion.confidence < MIN_SEMANTIC_FULL_CONFIDENCE
            ):
                return self._rule_decision(
                    query=query,
                    routing_mode=self.mode,
                    fallback_reason="semantic_full_low_confidence",
                )
            route_plan, added_sources = expand_route_plan_semantically(
                base_route_plan,
                expansion,
            )
            validate_semantic_route_plan(route_plan)
            decision = decision_from_route_plan(route_plan)
            return copy_decision(
                decision,
                routing_mode=self.mode,
                fallback_mode=False,
                routing_fallback_reason=None,
                metadata={
                    **(decision.metadata or {}),
                    "semantic_full_used": True,
                    "semantic_full_confidence": expansion.confidence,
                    "semantic_full_added_sources": sorted(added_sources),
                    "semantic_full_reason": expansion.reason,
                    "semantic_full_fallback_reason": None,
                },
            )
        except Exception as error:
            return self._rule_decision(
                query=query,
                routing_mode=self.mode,
                fallback_reason=f"{type(error).__name__}: {error}",
            )

    def _semantic_or_fallback_decision(self, query: str) -> RoutingDecision:
        """Use the optional semantic backend when valid, otherwise rule routing."""
        try:
            semantic_plan = self.semantic_router.route(query)
            route_plan = self.semantic_router.to_route_plan(semantic_plan)
            validate_semantic_route_plan(route_plan)
            decision = decision_from_route_plan(route_plan)
            return copy_decision(
                decision,
                routing_mode=self.mode,
                fallback_mode=False,
                routing_fallback_reason=None,
                metadata={
                    **(decision.metadata or {}),
                    "semantic_routing_used": True,
                },
            )
        except Exception as error:
            return self._rule_decision(
                query=query,
                routing_mode=self.mode,
                fallback_reason=f"{type(error).__name__}: {error}",
            )

    def _fallback_decision(
        self,
        query: str,
        error: Exception,
        routing_mode: str,
        fallback_reason: str | None = None,
    ) -> RoutingDecision:
        """Return a conservative route when normal routing fails."""
        reason = fallback_reason or f"{type(error).__name__}: {error}"
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
            routing_mode=routing_mode,
            routing_fallback_reason=reason,
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
        routing_mode="rule",
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


def normalized_routing_mode(mode: str) -> str:
    """Return a supported routing mode, defaulting invalid values to rule."""
    normalized = (mode or "rule").strip().lower()
    return normalized if normalized in ROUTING_MODES else "rule"


def llm_routing_messages(query: str) -> list[dict[str, str]]:
    """Build a concise structured-output prompt for optional LLM routing."""
    return [
        {
            "role": "system",
            "content": (
                "You are a routing policy for a memory-augmented chatbot. "
                "Return only valid JSON. Decide which memory sources should be "
                "active for the user query. Keep current_chat_gist, "
                "previous_chat_gist, raw_message_span, current_chat_chunks, and "
                "previous_chat_memory disabled unless explicitly requested by "
                "the application; they are not enabled for normal routing yet."
            ),
        },
        {
            "role": "user",
            "content": (
                "Route this query:\n"
                f"{query}\n\n"
                "Return JSON with keys: use_recent_messages, "
                "use_structured_memory, use_document_memory, reason, confidence. "
                "confidence must be a number from 0 to 1."
            ),
        },
    ]


def parse_routing_json(text: str) -> dict[str, Any]:
    """Parse JSON from a model response, allowing simple fenced blocks."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("LLM routing response must be a JSON object")
    return parsed


def route_plan_from_llm_payload(
    query: str,
    payload: dict[str, Any],
    base_route_plan: RoutePlan,
    mode: str,
) -> RoutePlan:
    """Convert validated LLM routing JSON to a RoutePlan-compatible object."""
    required = ("use_recent_messages", "use_structured_memory", "use_document_memory")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"LLM routing response missing keys: {', '.join(missing)}")
    confidence = float(payload.get("confidence", 0.0))
    if not 0 <= confidence <= 1:
        raise ValueError("LLM routing confidence must be between 0 and 1")

    use_recent = bool(payload["use_recent_messages"])
    use_structured = bool(payload["use_structured_memory"])
    use_document = bool(payload["use_document_memory"])
    if mode == "hybrid":
        # Hybrid keeps the deterministic safety baseline for core chat memory,
        # while allowing the LLM to decide whether document memory is useful.
        use_recent = source_is_enabled(base_route_plan, "recent_messages")
        use_structured = source_is_enabled(base_route_plan, "structured_memory")

    sources = [
        copy_source_enabled(
            source,
            enabled=(
                source_enabled_from_llm(
                    source.source,
                    use_recent=use_recent,
                    use_structured=use_structured,
                    use_document=use_document,
                )
                if source.source
                in {"recent_messages", "structured_memory", "document_memory"}
                else source.enabled
            ),
            query=query.strip().lower(),
            reason=(
                str(payload.get("reason") or "LLM routing policy selected sources.")
                if source.source
                in {"recent_messages", "structured_memory", "document_memory"}
                else source.reason
            ),
        )
        for source in base_route_plan.sources
    ]
    return RoutePlan(
        query=query.strip().lower(),
        intent=base_route_plan.intent,
        confidence=confidence,
        requires_retrieval=use_document,
        sources=sources,
        ranking_profile=base_route_plan.ranking_profile,
        context_profile=(
            "document_question"
            if use_document
            else base_route_plan.context_profile or "general_chat"
        ),
        fallback_policy=base_route_plan.fallback_policy,
        update_policy=base_route_plan.update_policy,
        termination_policy=base_route_plan.termination_policy,
        metadata={
            **base_route_plan.metadata,
            "routing_mode": mode,
            "llm_routing_reason": str(payload.get("reason") or ""),
        },
    )


def expand_route_plan_semantically(
    base_route_plan: RoutePlan,
    expansion: SemanticFullExpansion,
) -> tuple[RoutePlan, set[str]]:
    """Return a RoutePlan with semantic_full sources added to the rule baseline."""
    enabled_expansions = set(expansion.enabled_sources)
    existing_sources = {source.source for source in base_route_plan.sources}
    added_sources = {
        source.source
        for source in base_route_plan.sources
        if source.source in enabled_expansions and not source.enabled
    }
    source_query = base_route_plan.metadata.get("retrieval_query") or base_route_plan.query
    sources = [
        expand_source_plan_semantically(
            source=source,
            should_enable=source.source in enabled_expansions,
            query=str(source_query),
            reason=expansion.reason,
            confidence=expansion.confidence,
        )
        for source in base_route_plan.sources
    ]
    for source_name in sorted(enabled_expansions - existing_sources):
        if source_name not in SEMANTIC_FULL_SOURCES:
            continue
        added_sources.add(source_name)
        sources.append(
            SourcePlan(
                source=cast(MemorySourceType, source_name),
                enabled=True,
                reason=f"Semantic full expansion enabled source: {expansion.reason}",
                query=str(source_query),
                filters={
                    "semantic_full_expansion": True,
                    "semantic_full_reason": expansion.reason,
                    "semantic_full_confidence": expansion.confidence,
                },
            )
        )

    return (
        RoutePlan(
            query=base_route_plan.query,
            intent=expansion.intent or base_route_plan.intent,
            confidence=max(
                base_route_plan.confidence or 0.0,
                expansion.confidence if enabled_expansions else 0.0,
            ),
            requires_retrieval=(
                base_route_plan.requires_retrieval
                or any(source not in {"recent_messages"} for source in enabled_expansions)
            ),
            sources=sources,
            ranking_profile=base_route_plan.ranking_profile,
            context_profile=expansion.context_profile or base_route_plan.context_profile,
            fallback_policy=base_route_plan.fallback_policy,
            update_policy=base_route_plan.update_policy,
            termination_policy=base_route_plan.termination_policy,
            metadata={
                **base_route_plan.metadata,
                "routing_mode": "semantic_full",
                "semantic_full_confidence": expansion.confidence,
                "semantic_full_added_sources": sorted(added_sources),
                "semantic_full_reason": expansion.reason,
            },
        ),
        added_sources,
    )


def expand_source_plan_semantically(
    source: SourcePlan,
    should_enable: bool,
    query: str,
    reason: str,
    confidence: float,
) -> SourcePlan:
    """Enable a source if semantic_full selected it, preserving rule selections."""
    if not should_enable:
        return source
    if source.enabled:
        return SourcePlan(
            source=source.source,
            enabled=True,
            reason=source.reason,
            query=source.query,
            limit=source.limit,
            filters={
                **source.filters,
                "semantic_full_matched": True,
                "semantic_full_reason": reason,
                "semantic_full_confidence": confidence,
            },
        )
    return SourcePlan(
        source=source.source,
        enabled=True,
        reason=f"Semantic full expansion enabled source: {reason}",
        query=query,
        limit=source.limit,
        filters={
            **source.filters,
            "semantic_full_expansion": True,
            "semantic_full_reason": reason,
            "semantic_full_confidence": confidence,
        },
    )


def validate_semantic_full_expansion(expansion: SemanticFullExpansion) -> None:
    """Fail closed when semantic_full emits unusable expansion data."""
    if not isinstance(expansion, SemanticFullExpansion):
        raise TypeError("semantic_full backend did not return a SemanticFullExpansion")
    if not 0 <= expansion.confidence <= 1:
        raise ValueError("semantic_full confidence must be between 0 and 1")
    invalid_sources = set(expansion.enabled_sources) - SEMANTIC_FULL_SOURCES
    if invalid_sources:
        raise ValueError(
            "semantic_full backend emitted unsupported sources: "
            + ", ".join(sorted(invalid_sources))
        )


def validate_semantic_route_plan(route_plan: RoutePlan) -> None:
    """Fail closed if a semantic backend does not emit the internal schema."""
    if not isinstance(route_plan, RoutePlan):
        raise TypeError("semantic backend did not return a RoutePlan")
    if not route_plan.sources:
        raise ValueError("semantic route plan did not include any sources")
    if not any(source.enabled for source in route_plan.sources):
        raise ValueError("semantic route plan did not enable any sources")
    for source in route_plan.sources:
        if not isinstance(source, SourcePlan):
            raise TypeError("semantic route plan contains a non-SourcePlan source")
        if source.enabled and not source.source:
            raise ValueError("semantic route plan enabled a source without a name")


def normalize_for_semantic_full(query: str) -> str:
    """Normalize a query for deterministic semantic_full matching."""
    return re.sub(r"\s+", " ", query.strip().lower())


def matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    """Return whether any regex pattern matches the normalized text."""
    return any(re.search(pattern, text) for pattern in patterns)


def source_enabled_from_llm(
    source: str,
    use_recent: bool,
    use_structured: bool,
    use_document: bool,
) -> bool:
    """Map LLM source booleans onto known source labels."""
    if source == "recent_messages":
        return use_recent
    if source == "structured_memory":
        return use_structured
    if source == "document_memory":
        return use_document
    return False


def copy_source_enabled(
    source: SourcePlan,
    enabled: bool,
    query: str,
    reason: str,
) -> SourcePlan:
    """Return a source plan with LLM-selected enabled state."""
    return SourcePlan(
        source=source.source,
        enabled=enabled,
        reason=reason if enabled else source.reason,
        query=query if enabled else None,
        limit=source.limit,
        filters=source.filters,
    )


def source_is_enabled(route_plan: RoutePlan, source: str) -> bool:
    """Return whether a source is enabled in a route plan."""
    return any(plan.source == source and plan.enabled for plan in route_plan.sources)


def copy_decision(
    decision: RoutingDecision,
    routing_mode: str,
    fallback_mode: bool,
    routing_fallback_reason: str | None,
    metadata: dict[str, Any] | None = None,
) -> RoutingDecision:
    """Return a decision with routing-mode metadata adjusted."""
    return RoutingDecision(
        route_plan=decision.route_plan,
        use_recent_messages=decision.use_recent_messages,
        use_structured_memory=decision.use_structured_memory,
        use_document_memory=decision.use_document_memory,
        reason=decision.reason,
        confidence=decision.confidence,
        fallback_mode=fallback_mode,
        routing_mode=routing_mode,
        routing_fallback_reason=routing_fallback_reason,
        metadata=metadata if metadata is not None else decision.metadata,
    )
