from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class QuerySignals:
    """Boolean signals detected from a user query."""

    asks_about_current_chat: bool = False
    asks_about_previous_memory: bool = False
    asks_about_documents: bool = False
    asks_about_decision: bool = False
    asks_about_task: bool = False
    asks_for_exact_quote: bool = False
    asks_for_global_summary: bool = False
    asks_general_question: bool = False


@dataclass(frozen=True)
class QueryAnalysis:
    """Small structured analysis used by the route planner."""

    normalized_query: str
    intent: str
    signals: QuerySignals
    confidence: float
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class QueryAnalyzerPolicy:
    """Centralized lexical policy for the current lightweight analyzer."""

    current_chat_terms: tuple[str, ...] = (
        "this chat",
        "this conversation",
        "we discussed",
        "what did i say",
        "what have we",
        "earlier",
        "above",
    )
    previous_memory_terms: tuple[str, ...] = (
        "previous chat",
        "past chat",
        "other chat",
        "last time",
        "remember from before",
    )
    document_terms: tuple[str, ...] = (
        "document",
        "pdf",
        "file",
        "upload",
        "paper",
        "docs",
        "text",
        "source",
        "according to",
        "paragraph",
        "article",
    )
    decision_terms: tuple[str, ...] = (
        "decide",
        "decided",
        "decision",
        "choose",
        "chosen",
        "which database",
        "which model",
    )
    task_terms: tuple[str, ...] = (
        "task",
        "todo",
        "next step",
        "open item",
        "what should i do next",
    )
    exact_quote_terms: tuple[str, ...] = (
        "quote exactly",
        "exact phrase",
        "exact words",
        "exact wording",
        "what wording",
        "how did i phrase",
        "verbatim",
    )
    global_summary_terms: tuple[str, ...] = (
        "summarize the book",
        "summarize this book",
        "summarize what i told you earlier",
        "summary of the previous conversation",
        "summarize the previous conversation",
        "summarize our previous conversation",
    )


class QueryAnalyzer:
    """Rule-light query analyzer for route planning.

    The analyzer is intentionally deterministic for now. Its output is used only
    for tracing and future routing, not for answer generation.
    """

    def __init__(self, policy: QueryAnalyzerPolicy | None = None) -> None:
        self.policy = policy or QueryAnalyzerPolicy()

    def analyze(self, query: str) -> QueryAnalysis:
        """Analyze a user query into normalized text, intent, signals, and confidence."""
        normalized = normalize_query(query)
        inline_summary = bool(
            re.match(r"^(?:summarize|summary of) this text\s*:", normalized)
        )
        signals = QuerySignals(
            asks_about_current_chat=contains_any(normalized, self.policy.current_chat_terms),
            asks_about_previous_memory=contains_any(
                normalized,
                self.policy.previous_memory_terms,
            ),
            asks_about_documents=(
                contains_any(normalized, self.policy.document_terms)
                and not inline_summary
            ),
            asks_about_decision=contains_any(normalized, self.policy.decision_terms),
            asks_about_task=contains_any(normalized, self.policy.task_terms),
            asks_for_exact_quote=contains_any(
                normalized,
                self.policy.exact_quote_terms,
            ),
            asks_for_global_summary=contains_any(
                normalized,
                self.policy.global_summary_terms,
            ),
        )
        asks_general = not any(
            (
                signals.asks_about_current_chat,
                signals.asks_about_previous_memory,
                signals.asks_about_documents,
                signals.asks_about_decision,
                signals.asks_about_task,
                signals.asks_for_exact_quote,
                signals.asks_for_global_summary,
            )
        )
        signals = QuerySignals(
            asks_about_current_chat=signals.asks_about_current_chat,
            asks_about_previous_memory=signals.asks_about_previous_memory,
            asks_about_documents=signals.asks_about_documents,
            asks_about_decision=signals.asks_about_decision,
            asks_about_task=signals.asks_about_task,
            asks_for_exact_quote=signals.asks_for_exact_quote,
            asks_for_global_summary=signals.asks_for_global_summary,
            asks_general_question=asks_general,
        )
        intent = detect_intent(signals)
        return QueryAnalysis(
            normalized_query=normalized,
            intent=intent,
            signals=signals,
            confidence=confidence_for(signals),
        )


def normalize_query(query: str) -> str:
    """Normalize whitespace and case for lightweight signal detection."""
    return re.sub(r"\s+", " ", query.strip().lower())


def contains_any(query: str, terms: tuple[str, ...]) -> bool:
    """Return whether any configured term appears in the query."""
    return any(term in query for term in terms)


def detect_intent(signals: QuerySignals) -> str:
    """Map signals to a single coarse intent."""
    if signals.asks_for_global_summary:
        return "previous_memory_question"
    if signals.asks_about_documents:
        return "document_question"
    if signals.asks_about_previous_memory:
        return "previous_memory_question"
    if signals.asks_about_decision:
        return "decision_question"
    if signals.asks_about_task:
        return "task_question"
    if signals.asks_about_current_chat:
        return "current_chat_question"
    return "general_question"


def confidence_for(signals: QuerySignals) -> float:
    """Assign a simple confidence score based on how specific the signals are."""
    signal_count = sum(
        (
            signals.asks_about_current_chat,
            signals.asks_about_previous_memory,
            signals.asks_about_documents,
            signals.asks_about_decision,
            signals.asks_about_task,
        )
    )
    if signal_count >= 2:
        return 0.8
    if signal_count == 1:
        return 0.7
    return 0.55
