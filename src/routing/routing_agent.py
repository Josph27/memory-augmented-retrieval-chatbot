from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from src.core.contracts import RoutePlan, SourcePlan
from src.routing.route_planner import RoutePlanner

ROUTING_MODES = {"rule", "llm", "hybrid"}
MIN_LLM_ROUTING_CONFIDENCE = 0.5


class RoutingModel(Protocol):
    """Minimal chat-model protocol used by optional LLM routing."""

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        """Return a chat completion as text."""
        ...


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
        min_confidence: float = MIN_LLM_ROUTING_CONFIDENCE,
    ) -> None:
        self.route_planner = route_planner or RoutePlanner()
        self.mode = normalized_routing_mode(mode)
        self.model = model
        self.min_confidence = min_confidence

    def route(self, query: str) -> RoutingDecision:
        """Return a structured routing decision for a user query."""
        if self.mode == "rule":
            return self._rule_decision(query=query, routing_mode="rule")
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
            enabled=source_enabled_from_llm(
                source.source,
                use_recent=use_recent,
                use_structured=use_structured,
                use_document=use_document,
            ),
            query=query.strip().lower(),
            reason=str(payload.get("reason") or "LLM routing policy selected sources."),
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
        metadata=decision.metadata,
    )
