from __future__ import annotations

import os
import re

from src.core.contracts import RoutePlan, SourcePlan
from src.routing.semantic_contracts import (
    EvidenceContract,
    IntentScore,
    MemoryScope,
    RetrievalQuery,
    SemanticRoutePlan,
)
from src.routing.retrieval_query import simplify_retrieval_query


EXACT_QUOTE = "EXACT_QUOTE"
SAME_CHAT_RECALL = "SAME_CHAT_RECALL"
PREVIOUS_CHAT_RECALL = "PREVIOUS_CHAT_RECALL"
STRUCTURED_PREFERENCE_RECALL = "STRUCTURED_PREFERENCE_RECALL"
DOCUMENT_QA = "DOCUMENT_QA"
PROJECT_STATE_SUMMARY = "PROJECT_STATE_SUMMARY"
CASUAL_CHAT = "CASUAL_CHAT"
MEMORY_QA = "MEMORY_QA"

RETRIEVAL_NONE = "none"
RETRIEVAL_POSSIBLE = "possible"
RETRIEVAL_REQUIRED = "required"

CURRENT_CHAT = "CURRENT_CHAT"
PREVIOUS_CHATS = "PREVIOUS_CHATS"
ANY_CHAT = "ANY_CHAT"
DOCUMENTS = "DOCUMENTS"
GLOBAL_STRUCTURED_MEMORY = "GLOBAL_STRUCTURED_MEMORY"
NONE = "NONE"

SCOPE_CURRENT_CHAT: MemoryScope = "current_chat"
SCOPE_PREVIOUS_CHAT: MemoryScope = "previous_chat"
SCOPE_DURABLE: MemoryScope = "durable"
SCOPE_DOCUMENT: MemoryScope = "document"
SCOPE_UNKNOWN: MemoryScope = "unknown"

SEMANTIC_SOURCE_CANDIDATE_LIMIT = 8

ALL_SOURCES = (
    "recent_messages",
    "structured_memory",
    "document_memory",
    "current_chat_gist",
    "current_chat_span",
    "previous_chat_gist",
    "raw_message_span",
)

EXACT_QUOTE_PATTERNS = (
    r"\bquote(?:\s+me)?\b",
    r"\bexact(?:\s+phrase|\s+words?|\s+wording)?\b",
    r"\bverbatim\b",
    r"\bhow did i phrase\b",
    r"\bwhat wording did i use\b",
    r"\bwhat were my .*words\b",
)
CURRENT_CHAT_PATTERNS = (
    r"\bearlier in this chat\b",
    r"\bthis chat\b",
    r"\bthis conversation\b",
    r"\babove\b",
    r"\bjust now\b",
)
PREVIOUS_CHAT_PATTERNS = (
    r"\blast time\b",
    r"\bprevious chat\b",
    r"\bprevious conversation\b",
    r"\bpast chat\b",
    r"\bearlier chat\b",
)
ANY_CHAT_PATTERNS = (
    r"\bwe discussed before\b",
    r"\bwhat did i say about\b",
    r"\bmy earlier message\b",
)
DOCUMENT_PATTERNS = (
    r"\baccording to (?:the )?(?:uploaded )?(?:document|file|report|paper)\b",
    r"\buploaded (?:document|file|report|paper)\b",
    r"\b(?:document|report|paper|pdf) says?\b",
    r"\b(?:this|that) (?:document|report|file)\b",
    r"\bthe file i uploaded\b",
    r"\bsummarize it\b",
    r"(?:这个报告|这个文档|刚才的文件|上传的文件|里面写了什么|根据它来说|总结一下它)",
)
SUMMARY_REQUEST_PATTERNS = (
    r"\bsummar(?:ize|y)\b",
    r"\btl;dr\b",
)
SUMMARY_REFERENTIAL_PATTERNS = (
    *DOCUMENT_PATTERNS,
    r"\bbook\b",
    r"\bstory\b",
    r"\bnovel\b",
    r"\bprevious conversation\b",
    r"\bearlier conversation\b",
    r"\bwhat i told you earlier\b",
    r"\bwhat we discussed earlier\b",
)
PREFERENCE_PATTERNS = (
    r"\bwhat do i prefer\b",
    r"\bmy preference\b",
    r"\bdo i prefer\b",
    r"\bremember my preference\b",
)
PROJECT_STATE_PATTERNS = (
    r"\bwhere are we\b",
    r"\bproject state\b",
    r"\bcurrent status\b",
    r"\bnext steps?\b",
    r"\bopen tasks?\b",
)
SAME_CHAT_RECALL_PATTERNS = (
    r"\bwhat did i say earlier\b",
    r"\bwhat did we discuss earlier\b",
    r"\bearlier in (?:this )?(?:chat|conversation)\b",
)
PREVIOUS_RECALL_PATTERNS = (
    r"\bwhat did we discuss last time\b",
    r"\bwhat did we discuss before\b",
    r"\bremember from before\b",
    r"\bsummary of the previous conversation\b",
    r"\bsummar(?:ize|y) (?:the )?previous conversation\b",
)
NON_RETRIEVAL_PATTERNS = (
    r"^(?:hi|hello|hey|thanks|thank you|good morning|good evening)[!. ]*$",
    r"^how are you[?.! ]*$",
    r"\b(?:write|rewrite|draft|compose|brainstorm|invent|create)\b",
)
MEMORY_QA_CUES = (
    r"\b(?:my|our|we|i)\b",
    r"\bproject\b",
    r"\b(?:choose|chose|decide|decided|use|used|prefer|preferred)\b",
)
QUESTION_PATTERNS = (
    r"^(?:who|what|when|where|which|why|how|is|are|was|were|do|does|did|can)\b",
)


class SemanticRouter:
    """Deterministic, default-off semantic routing baseline."""

    def route(
        self,
        query: str,
        task_context: str | None = None,
    ) -> SemanticRoutePlan:
        """Return typed intent, evidence, source, and retrieval-query contracts."""
        normalized = normalize_query(query)
        language = detect_language(query)
        intent, confidence, reason = classify_intent(normalized)
        retrieval_need = retrieval_need_for(
            normalized,
            intent=intent,
            task_context=task_context,
        )
        if intent == CASUAL_CHAT and retrieval_need == RETRIEVAL_REQUIRED:
            intent = MEMORY_QA
            confidence = 0.82
            reason = "factual memory QA requires bounded persistent retrieval"
        temporal_scope = detect_temporal_scope(normalized, intent)
        required_scopes = required_scopes_for(
            normalized,
            intent=intent,
            temporal_scope=temporal_scope,
        )
        primary_scope = primary_scope_for(intent, temporal_scope)
        sources = sources_for(
            intent,
            temporal_scope,
            required_scopes=required_scopes,
        )
        contract = evidence_contract_for(intent)
        profile = context_profile_for(intent, normalized)
        return SemanticRoutePlan(
            original_query=query,
            normalized_query=normalized,
            language=language,
            intents=(
                IntentScore(
                    intent=intent,
                    confidence=confidence,
                    reason=reason,
                ),
            ),
            temporal_scope=temporal_scope,
            enabled_sources=sources,
            evidence_contract=contract,
            retrieval_queries=retrieval_queries_for(
                original_query=query,
                normalized_query=normalized,
                intent=intent,
                enabled_sources=sources,
                context_profile=profile,
            ),
            confidence=confidence,
            retrieval_need=retrieval_need,
            memory_scope=memory_scope_for(intent, temporal_scope),
            primary_scope=primary_scope,
            required_scopes=required_scopes,
            task_context=task_context,
        )

    def to_route_plan(self, semantic_plan: SemanticRoutePlan) -> RoutePlan:
        """Adapt typed semantic routing to the existing dispatcher contract."""
        enabled = set(semantic_plan.enabled_sources)
        profile = context_profile_for(
            semantic_plan.intents[0].intent,
            semantic_plan.normalized_query,
        )
        retrieval_query = generated_retrieval_query(semantic_plan)
        rewrite_applied = retrieval_query != semantic_plan.original_query
        rewrite_reason = next(
            (
                item.purpose
                for item in semantic_plan.retrieval_queries
                if item.is_generated and item.text == retrieval_query
            ),
            "original_query",
        )
        source_plans = [
            SourcePlan(
                source=source,  # type: ignore[arg-type]
                enabled=source in enabled,
                reason=source_reason(source, semantic_plan),
                query=(
                    retrieval_query
                    if source in enabled and source != "recent_messages"
                    else semantic_plan.original_query
                    if source in enabled
                    else None
                ),
                limit=source_candidate_limit(source) if source in enabled else None,
                filters={
                    "semantic_router_version": semantic_plan.router_version,
                    "context_profile": profile,
                    "original_query": semantic_plan.original_query,
                    "retrieval_query": retrieval_query,
                    "query_rewrite_applied": rewrite_applied,
                    "query_rewrite_reason": rewrite_reason,
                    "retrieval_query_purposes": [
                        item.purpose
                        for item in semantic_plan.retrieval_queries
                        if source in item.allowed_sources
                    ],
                },
            )
            for source in ALL_SOURCES
        ]
        primary_intent = semantic_plan.intents[0].intent
        return RoutePlan(
            query=semantic_plan.original_query,
            intent=primary_intent,
            confidence=semantic_plan.confidence,
            requires_retrieval=primary_intent != CASUAL_CHAT,
            sources=source_plans,
            ranking_profile="semantic_v2",
            context_profile=profile,
            fallback_policy="abstain_when_evidence_contract_is_unsatisfied",
            update_policy="read_only_langgraph_spike",
            termination_policy="mock_answer_or_insufficient_evidence",
            metadata={
                "router_version": semantic_plan.router_version,
                "language": semantic_plan.language,
                "temporal_scope": semantic_plan.temporal_scope,
                "retrieval_need": semantic_plan.retrieval_need,
                "memory_scope": semantic_plan.memory_scope,
                "primary_scope": semantic_plan.primary_scope,
                "required_scopes": sorted(semantic_plan.required_scopes),
                "task_context": semantic_plan.task_context,
                "original_query": semantic_plan.original_query,
                "retrieval_query": retrieval_query,
                "query_rewrite_applied": rewrite_applied,
                "query_rewrite_reason": rewrite_reason,
            },
        )


def normalize_query(query: str) -> str:
    """Normalize case and whitespace without changing the original query."""
    return re.sub(r"\s+", " ", query.strip().lower())


def detect_language(query: str) -> str:
    """Return a conservative English-or-unknown language label."""
    if re.search(r"[a-zA-Z]", query):
        return "en"
    return "unknown"


def classify_intent(normalized_query: str) -> tuple[str, float, str]:
    """Classify a query using deterministic English semantic examples."""
    rules = (
        (EXACT_QUOTE, EXACT_QUOTE_PATTERNS, 0.95, "quote/provenance wording"),
        (DOCUMENT_QA, DOCUMENT_PATTERNS, 0.92, "document-grounded wording"),
        (
            STRUCTURED_PREFERENCE_RECALL,
            PREFERENCE_PATTERNS,
            0.9,
            "durable preference wording",
        ),
        (
            PROJECT_STATE_SUMMARY,
            PROJECT_STATE_PATTERNS,
            0.86,
            "project-state wording",
        ),
        (
            PREVIOUS_CHAT_RECALL,
            PREVIOUS_RECALL_PATTERNS,
            0.88,
            "previous-chat wording",
        ),
        (
            SAME_CHAT_RECALL,
            SAME_CHAT_RECALL_PATTERNS,
            0.88,
            "same-chat wording",
        ),
    )
    for intent, patterns, confidence, reason in rules:
        if matches_any(normalized_query, patterns):
            return intent, confidence, reason
    return CASUAL_CHAT, 0.7, "no memory or document intent matched"


def detect_temporal_scope(normalized_query: str, intent: str) -> str:
    """Detect rough source scope independently from semantic intent."""
    if intent == DOCUMENT_QA:
        return DOCUMENTS
    if intent == STRUCTURED_PREFERENCE_RECALL:
        return GLOBAL_STRUCTURED_MEMORY
    if matches_any(normalized_query, CURRENT_CHAT_PATTERNS):
        return CURRENT_CHAT
    if matches_any(normalized_query, PREVIOUS_CHAT_PATTERNS):
        return PREVIOUS_CHATS
    if matches_any(normalized_query, ANY_CHAT_PATTERNS) or intent == EXACT_QUOTE:
        return ANY_CHAT
    if intent == SAME_CHAT_RECALL:
        return CURRENT_CHAT
    if intent == PREVIOUS_CHAT_RECALL:
        return PREVIOUS_CHATS
    if intent == MEMORY_QA:
        return ANY_CHAT
    return NONE


def required_scopes_for(
    normalized_query: str,
    *,
    intent: str,
    temporal_scope: str,
) -> frozenset[MemoryScope]:
    """Collect independently required memory scopes for one primary intent."""
    scopes: set[MemoryScope] = set()
    if intent == DOCUMENT_QA or matches_any(normalized_query, DOCUMENT_PATTERNS):
        scopes.add(SCOPE_DOCUMENT)
    if intent == SAME_CHAT_RECALL or matches_any(
        normalized_query, CURRENT_CHAT_PATTERNS
    ):
        scopes.add(SCOPE_CURRENT_CHAT)
    if intent == PREVIOUS_CHAT_RECALL or matches_any(
        normalized_query, PREVIOUS_CHAT_PATTERNS
    ):
        scopes.add(SCOPE_PREVIOUS_CHAT)
    if intent == STRUCTURED_PREFERENCE_RECALL:
        scopes.add(SCOPE_DURABLE)
    if intent == PROJECT_STATE_SUMMARY:
        scopes.update((SCOPE_DURABLE, SCOPE_PREVIOUS_CHAT))
    if intent == MEMORY_QA:
        scopes.add(SCOPE_UNKNOWN)
    if intent == EXACT_QUOTE and not scopes:
        if temporal_scope == CURRENT_CHAT:
            scopes.add(SCOPE_CURRENT_CHAT)
        elif temporal_scope == PREVIOUS_CHATS:
            scopes.add(SCOPE_PREVIOUS_CHAT)
        else:
            scopes.update((SCOPE_CURRENT_CHAT, SCOPE_PREVIOUS_CHAT))
    return frozenset(scopes)


def primary_scope_for(intent: str, temporal_scope: str) -> MemoryScope | None:
    """Return the primary scope while retaining independent required scopes."""
    scope = memory_scope_for(intent, temporal_scope)
    if scope == "none":
        return None
    return scope  # type: ignore[return-value]


def sources_for(
    intent: str,
    temporal_scope: str = NONE,
    *,
    required_scopes: frozenset[MemoryScope] | None = None,
) -> tuple[str, ...]:
    """Map semantic intent to typed memory sources."""
    scopes = required_scopes
    if scopes is None:
        scopes = required_scopes_for(
            "",
            intent=intent,
            temporal_scope=temporal_scope,
        )
    enabled = {"recent_messages"}
    source_by_scope = {
        SCOPE_DOCUMENT: {"document_memory"},
        SCOPE_CURRENT_CHAT: {"current_chat_span"},
        SCOPE_PREVIOUS_CHAT: {"previous_chat_gist", "raw_message_span"},
        SCOPE_DURABLE: {"structured_memory"},
        SCOPE_UNKNOWN: {
            "structured_memory",
            "previous_chat_gist",
            "raw_message_span",
        },
    }
    for scope in scopes:
        enabled.update(source_by_scope[scope])
    if intent == EXACT_QUOTE and SCOPE_PREVIOUS_CHAT in scopes:
        enabled.add("raw_message_span")
    return tuple(source for source in ALL_SOURCES if source in enabled)


def retrieval_need_for(
    normalized_query: str,
    *,
    intent: str,
    task_context: str | None,
) -> str:
    """Separate retrieval necessity from source scope and intent wording."""
    if intent != CASUAL_CHAT:
        return RETRIEVAL_REQUIRED
    if matches_any(normalized_query, SUMMARY_REQUEST_PATTERNS) and matches_any(
        normalized_query,
        SUMMARY_REFERENTIAL_PATTERNS,
    ):
        return RETRIEVAL_REQUIRED
    if matches_any(normalized_query, NON_RETRIEVAL_PATTERNS):
        return RETRIEVAL_NONE
    if task_context == "memory_qa":
        return RETRIEVAL_REQUIRED
    if (
        matches_any(normalized_query, QUESTION_PATTERNS)
        and matches_any(normalized_query, MEMORY_QA_CUES)
    ):
        return RETRIEVAL_REQUIRED
    if matches_any(normalized_query, QUESTION_PATTERNS):
        return RETRIEVAL_POSSIBLE
    return RETRIEVAL_NONE


def memory_scope_for(intent: str, temporal_scope: str) -> str:
    """Map temporal/source understanding to the small public scope contract."""
    if temporal_scope == CURRENT_CHAT:
        return "current_chat"
    if temporal_scope == PREVIOUS_CHATS:
        return "previous_chat"
    if intent == STRUCTURED_PREFERENCE_RECALL:
        return "durable"
    if intent == DOCUMENT_QA:
        return "document"
    if intent == MEMORY_QA or temporal_scope == ANY_CHAT:
        return "unknown"
    return "none"


def evidence_contract_for(intent: str) -> EvidenceContract:
    """Return the evidence requirements associated with an intent."""
    if intent == EXACT_QUOTE:
        return EvidenceContract(
            requires_raw_span=True,
            must_not_answer_from_gist_only=True,
        )
    if intent == DOCUMENT_QA:
        return EvidenceContract(requires_document_citation=True)
    if intent == STRUCTURED_PREFERENCE_RECALL:
        return EvidenceContract(requires_structured_memory=True)
    return EvidenceContract()


def retrieval_queries_for(
    *,
    original_query: str,
    normalized_query: str,
    intent: str,
    enabled_sources: tuple[str, ...],
    context_profile: str,
) -> tuple[RetrievalQuery, ...]:
    """Build bounded hints while preserving the original query exactly."""
    queries = [
        RetrievalQuery(
            text=original_query,
            purpose="original_user_query",
            allowed_sources=enabled_sources,
            is_generated=False,
        )
    ]
    rewrite = simplify_retrieval_query(
        original_query,
        context_profile=context_profile,
        enabled=query_simplification_enabled(),
    )
    if rewrite.applied:
        queries.append(
            RetrievalQuery(
                text=rewrite.retrieval_query,
                purpose=rewrite.reason,
                allowed_sources=tuple(
                    source for source in enabled_sources if source != "recent_messages"
                ),
                is_generated=True,
            )
        )
    if intent == EXACT_QUOTE:
        queries.append(
            RetrievalQuery(
                text=normalized_query,
                purpose="quote_orientation_search",
                allowed_sources=("previous_chat_gist",),
                is_generated=True,
            )
        )
    return tuple(queries)


def matches_any(query: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, query, flags=re.IGNORECASE) for pattern in patterns)


def context_profile_for(intent: str, normalized_query: str = "") -> str:
    if matches_any(normalized_query, SUMMARY_REQUEST_PATTERNS) and matches_any(
        normalized_query,
        SUMMARY_REFERENTIAL_PATTERNS,
    ):
        return "global_summary"
    if intent == DOCUMENT_QA:
        return "document_question"
    if intent == CASUAL_CHAT:
        return "general_chat"
    return "memory_recall"


def generated_retrieval_query(semantic_plan: SemanticRoutePlan) -> str:
    generated = next(
        (
            item.text
            for item in semantic_plan.retrieval_queries
            if item.is_generated and item.purpose != "quote_orientation_search"
        ),
        None,
    )
    return generated or semantic_plan.original_query


def source_candidate_limit(source: str) -> int:
    env_name = {
        "previous_chat_gist": "GIST_RETRIEVAL_CANDIDATES",
        "raw_message_span": "DIRECT_RAW_RETRIEVAL_CANDIDATES",
    }.get(source)
    if env_name is None:
        return SEMANTIC_SOURCE_CANDIDATE_LIMIT
    try:
        return max(1, int(os.getenv(env_name, "8" if source == "previous_chat_gist" else "12")))
    except ValueError:
        return 8 if source == "previous_chat_gist" else 12


def query_simplification_enabled() -> bool:
    return os.getenv(
        "ENABLE_RETRIEVAL_QUERY_SIMPLIFICATION",
        "1",
    ).strip().lower() in {"1", "true", "yes", "on"}


def source_reason(source: str, semantic_plan: SemanticRoutePlan) -> str:
    status = "enabled" if source in semantic_plan.enabled_sources else "disabled"
    return (
        f"Semantic Router v2 {status} {source} for "
        f"{semantic_plan.intents[0].intent}."
    )
