from __future__ import annotations

import re

from src.core.contracts import RoutePlan, SourcePlan
from src.routing.semantic_contracts import (
    EvidenceContract,
    IntentScore,
    RetrievalQuery,
    SemanticRoutePlan,
)


EXACT_QUOTE = "EXACT_QUOTE"
SAME_CHAT_RECALL = "SAME_CHAT_RECALL"
PREVIOUS_CHAT_RECALL = "PREVIOUS_CHAT_RECALL"
STRUCTURED_PREFERENCE_RECALL = "STRUCTURED_PREFERENCE_RECALL"
DOCUMENT_QA = "DOCUMENT_QA"
PROJECT_STATE_SUMMARY = "PROJECT_STATE_SUMMARY"
CASUAL_CHAT = "CASUAL_CHAT"

CURRENT_CHAT = "CURRENT_CHAT"
PREVIOUS_CHATS = "PREVIOUS_CHATS"
ANY_CHAT = "ANY_CHAT"
DOCUMENTS = "DOCUMENTS"
GLOBAL_STRUCTURED_MEMORY = "GLOBAL_STRUCTURED_MEMORY"
NONE = "NONE"

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
    r"原话",
    r"具体怎么说",
    r"什么措辞",
    r"用了什么措辞",
    r"逐字引用",
    r"怎么说的",
)
CURRENT_CHAT_PATTERNS = (
    r"\bearlier in this chat\b",
    r"\bthis chat\b",
    r"\bthis conversation\b",
    r"\babove\b",
    r"\bjust now\b",
    r"刚才",
    r"这个\s*chat",
    r"这次聊天",
)
PREVIOUS_CHAT_PATTERNS = (
    r"\blast time\b",
    r"\bprevious chat\b",
    r"\bpast chat\b",
    r"\bearlier chat\b",
    r"上次",
    r"之前的聊天",
)
ANY_CHAT_PATTERNS = (
    r"\bwe discussed before\b",
    r"\bwhat did i say about\b",
    r"\bmy earlier message\b",
    r"我们之前说过",
    r"我之前关于",
)
DOCUMENT_PATTERNS = (
    r"\baccording to (?:the )?(?:uploaded )?(?:document|file|report|paper)\b",
    r"\buploaded (?:document|file|report|paper)\b",
    r"\b(?:document|report|paper|pdf) says?\b",
    r"根据(?:上传的)?(?:文档|文件|报告)",
)
PREFERENCE_PATTERNS = (
    r"\bwhat do i prefer\b",
    r"\bmy preference\b",
    r"\bdo i prefer\b",
    r"\bremember my preference\b",
    r"我的偏好",
    r"我更喜欢",
)
PROJECT_STATE_PATTERNS = (
    r"\bwhere are we\b",
    r"\bproject state\b",
    r"\bcurrent status\b",
    r"\bnext steps?\b",
    r"\bopen tasks?\b",
    r"项目进展",
    r"当前状态",
    r"下一步",
)
SAME_CHAT_RECALL_PATTERNS = (
    r"\bwhat did i say earlier\b",
    r"\bwhat did we discuss earlier\b",
    r"\bearlier in (?:this )?(?:chat|conversation)\b",
    r"刚才说",
    r"这次聊天.*说",
)
PREVIOUS_RECALL_PATTERNS = (
    r"\bwhat did we discuss last time\b",
    r"\bwhat did we discuss before\b",
    r"\bremember from before\b",
    r"上次.*(?:说|讨论)",
    r"之前的聊天",
)


class SemanticRouter:
    """Deterministic, default-off semantic routing baseline."""

    def route(self, query: str) -> SemanticRoutePlan:
        """Return typed intent, evidence, source, and retrieval-query contracts."""
        normalized = normalize_query(query)
        language = detect_language(query)
        intent, confidence, reason = classify_intent(normalized)
        temporal_scope = detect_temporal_scope(normalized, intent)
        sources = sources_for(intent)
        contract = evidence_contract_for(intent)
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
            ),
            confidence=confidence,
        )

    def to_route_plan(self, semantic_plan: SemanticRoutePlan) -> RoutePlan:
        """Adapt typed semantic routing to the existing dispatcher contract."""
        enabled = set(semantic_plan.enabled_sources)
        source_plans = [
            SourcePlan(
                source=source,  # type: ignore[arg-type]
                enabled=source in enabled,
                reason=source_reason(source, semantic_plan),
                query=semantic_plan.original_query if source in enabled else None,
                limit=4 if source in enabled else None,
                filters={
                    "semantic_router_version": semantic_plan.router_version,
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
            context_profile=context_profile_for(primary_intent),
            fallback_policy="abstain_when_evidence_contract_is_unsatisfied",
            update_policy="read_only_langgraph_spike",
            termination_policy="mock_answer_or_insufficient_evidence",
            metadata={
                "router_version": semantic_plan.router_version,
                "language": semantic_plan.language,
                "temporal_scope": semantic_plan.temporal_scope,
            },
        )


def normalize_query(query: str) -> str:
    """Normalize case and whitespace without changing the original query."""
    return re.sub(r"\s+", " ", query.strip().lower())


def detect_language(query: str) -> str:
    """Return a conservative en/zh/unknown language label."""
    if re.search(r"[\u3400-\u9fff]", query):
        return "zh"
    if re.search(r"[a-zA-Z]", query):
        return "en"
    return "unknown"


def classify_intent(normalized_query: str) -> tuple[str, float, str]:
    """Classify a query using deterministic multilingual semantic examples."""
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
    return NONE


def sources_for(intent: str) -> tuple[str, ...]:
    """Map semantic intent to typed memory sources."""
    mappings = {
        EXACT_QUOTE: (
            "recent_messages",
            "current_chat_span",
            "previous_chat_gist",
            "raw_message_span",
        ),
        SAME_CHAT_RECALL: ("recent_messages", "current_chat_span"),
        PREVIOUS_CHAT_RECALL: (
            "recent_messages",
            "previous_chat_gist",
            "raw_message_span",
        ),
        STRUCTURED_PREFERENCE_RECALL: (
            "recent_messages",
            "structured_memory",
            "previous_chat_gist",
        ),
        DOCUMENT_QA: ("recent_messages", "document_memory"),
        PROJECT_STATE_SUMMARY: (
            "recent_messages",
            "structured_memory",
            "previous_chat_gist",
        ),
        CASUAL_CHAT: ("recent_messages",),
    }
    return mappings[intent]


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


def context_profile_for(intent: str) -> str:
    if intent == DOCUMENT_QA:
        return "document_question"
    if intent == CASUAL_CHAT:
        return "general_chat"
    return "memory_recall"


def source_reason(source: str, semantic_plan: SemanticRoutePlan) -> str:
    status = "enabled" if source in semantic_plan.enabled_sources else "disabled"
    return (
        f"Semantic Router v2 {status} {source} for "
        f"{semantic_plan.intents[0].intent}."
    )
