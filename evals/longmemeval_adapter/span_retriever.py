from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from src.core.contracts import MemoryCandidate, SourcePlan
from src.database import Database, StoredMessage

from evals.longmemeval_adapter.schema import LongMemEvalCase


DEFAULT_SPAN_MAX_MESSAGES = 4
DEFAULT_SPAN_MAX_CHARS = 1600
DEFAULT_SPAN_OVERLAP_MESSAGES = 1

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "assistant",
    "did",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "the",
    "to",
    "user",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "system",
}


@dataclass(frozen=True)
class MessageSpan:
    """One bounded benchmark-history window with stable message provenance."""

    case_id: str
    session_id: str
    chat_id: str
    start_message_id: int
    end_message_id: int
    message_count: int
    content: str
    span_index: int


class LongMemEvalMessageSpanRetriever:
    """Eval-only lexical retrieval over bounded role-labelled message spans."""

    def __init__(self, spans: list[MessageSpan]) -> None:
        self.spans = spans
        self.document_frequency = document_frequency(spans)

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        """Rank spans lexically and return standard raw-message candidates."""
        del chat_id
        query = source_plan.query or ""
        ranked = sorted(
            (
                (lexical_span_score(query, span, self.document_frequency, len(self.spans)), span)
                for span in self.spans
            ),
            key=lambda item: (-item[0], item[1].session_id, item[1].span_index),
        )
        limit = source_plan.limit or 8
        return [
            span_to_candidate(span, score)
            for score, span in ranked
            if score > 0.0
        ][:limit]


def seed_message_spans(
    database: Database,
    case: LongMemEvalCase,
    max_messages: int = DEFAULT_SPAN_MAX_MESSAGES,
    max_chars: int = DEFAULT_SPAN_MAX_CHARS,
    overlap_messages: int = DEFAULT_SPAN_OVERLAP_MESSAGES,
) -> list[MessageSpan]:
    """Persist benchmark sessions and split them into compact windows."""
    spans: list[MessageSpan] = []
    for session_index, session in enumerate(case.sessions):
        chat_id = f"{case.case_id}-history-{session_index + 1}"
        replay_timestamp = str(session.metadata.get("date") or "").strip() or None
        database.create_chat(
            chat_id,
            title=f"Benchmark history {session.session_id}",
            created_at=replay_timestamp,
        )
        stored_messages = database.messages_for_chat(chat_id)
        if not stored_messages:
            for message in session.messages:
                database.save_message(
                    chat_id,
                    message.role,
                    message.content,
                    created_at=message.created_at or replay_timestamp,
                )
            stored_messages = database.messages_for_chat(chat_id)
        spans.extend(
            split_session_messages(
                case_id=case.case_id,
                session_id=session.session_id,
                chat_id=chat_id,
                messages=stored_messages,
                max_messages=max_messages,
                max_chars=max_chars,
                overlap_messages=overlap_messages,
            )
        )
    return spans


def split_session_messages(
    case_id: str,
    session_id: str,
    chat_id: str,
    messages: list[StoredMessage],
    max_messages: int = DEFAULT_SPAN_MAX_MESSAGES,
    max_chars: int = DEFAULT_SPAN_MAX_CHARS,
    overlap_messages: int = DEFAULT_SPAN_OVERLAP_MESSAGES,
) -> list[MessageSpan]:
    """Split messages into overlapping windows bounded by message and character count."""
    if not messages:
        return []
    max_messages = max(1, max_messages)
    max_chars = max(200, max_chars)
    overlap_messages = max(0, min(overlap_messages, max_messages - 1))
    spans: list[MessageSpan] = []
    start = 0
    while start < len(messages):
        if len(format_messages([messages[start]])) > max_chars:
            spans.extend(
                split_oversized_message(
                    case_id=case_id,
                    session_id=session_id,
                    chat_id=chat_id,
                    message=messages[start],
                    max_chars=max_chars,
                    first_span_index=len(spans),
                )
            )
            start += 1
            continue
        window: list[StoredMessage] = []
        for message in messages[start:]:
            proposed = [*window, message]
            proposed_text = format_messages(proposed)
            if window and (
                len(proposed) > max_messages or len(proposed_text) > max_chars
            ):
                break
            window = proposed
            if len(window) >= max_messages or len(proposed_text) >= max_chars:
                break
        if not window:
            window = [messages[start]]
        content = truncate_role_message(window[0], max_chars)
        if len(window) > 1:
            content = format_messages(window)
        spans.append(
            MessageSpan(
                case_id=case_id,
                session_id=session_id,
                chat_id=chat_id,
                start_message_id=window[0].id,
                end_message_id=window[-1].id,
                message_count=len(window),
                content=content[:max_chars],
                span_index=len(spans),
            )
        )
        consumed = len(window)
        start += max(1, consumed - overlap_messages)
    return spans


def span_to_candidate(span: MessageSpan, score: float) -> MemoryCandidate:
    """Normalize one benchmark span as a project MemoryCandidate."""
    return MemoryCandidate(
        source="raw_message_span",
        content=f"[session={span.session_id}]\n{span.content}",
        score=score,
        record_id=f"{span.case_id}:{span.session_id}:{span.span_index}",
        chat_id=span.chat_id,
        source_message_ids=[span.start_message_id, span.end_message_id],
        metadata={
            "benchmark": "LongMemEval",
            "benchmark_case_id": span.case_id,
            "session_id": span.session_id,
            "start_message_id": span.start_message_id,
            "end_message_id": span.end_message_id,
            "message_count": span.message_count,
            "span_index": span.span_index,
            "retrieval_backend": "longmemeval_lexical_message_span",
            "retrieval_mode": "lexical_span",
            "status": "active",
        },
    )


def lexical_span_score(
    query: str,
    span: MessageSpan,
    frequencies: Counter[str],
    span_count: int,
) -> float:
    """Return a compact TF-IDF-like lexical relevance score."""
    query_terms = set(tokenize(query))
    if not query_terms:
        return 0.0
    span_terms = Counter(tokenize(span.content))
    score = 0.0
    for term in query_terms:
        frequency = span_terms.get(term, 0)
        if frequency <= 0:
            continue
        inverse_document_frequency = math.log(
            1.0 + (span_count + 1) / (frequencies.get(term, 0) + 1)
        )
        score += (1.0 + math.log(frequency)) * inverse_document_frequency
    return score / max(1, len(query_terms))


def document_frequency(spans: Iterable[MessageSpan]) -> Counter[str]:
    """Count spans containing each lexical term."""
    frequencies: Counter[str] = Counter()
    for span in spans:
        frequencies.update(set(tokenize(span.content)))
    return frequencies


def tokenize(text: str) -> list[str]:
    """Tokenize meaningful alphanumeric terms for deterministic retrieval."""
    return [
        token
        for token in re.findall(r"\w+", text.casefold(), flags=re.UNICODE)
        if len(token) > 1 and token not in STOP_WORDS
    ]


def format_messages(messages: list[StoredMessage]) -> str:
    """Preserve role labels in a compact message window."""
    return "\n".join(f"{message.role}: {message.content}" for message in messages)


def truncate_role_message(message: StoredMessage, max_chars: int) -> str:
    """Bound a single oversized message while preserving its role."""
    prefix = f"{message.role}: "
    available = max(1, max_chars - len(prefix))
    return prefix + message.content[:available]


def split_oversized_message(
    case_id: str,
    session_id: str,
    chat_id: str,
    message: StoredMessage,
    max_chars: int,
    first_span_index: int,
    overlap_chars: int = 150,
) -> list[MessageSpan]:
    """Split one oversized message so evidence beyond its prefix remains retrievable."""
    prefix = f"{message.role}: "
    payload_limit = max(1, max_chars - len(prefix))
    overlap_chars = max(0, min(overlap_chars, payload_limit - 1))
    step = max(1, payload_limit - overlap_chars)
    spans = []
    for offset in range(0, len(message.content), step):
        chunk = message.content[offset : offset + payload_limit]
        spans.append(
            MessageSpan(
                case_id=case_id,
                session_id=session_id,
                chat_id=chat_id,
                start_message_id=message.id,
                end_message_id=message.id,
                message_count=1,
                content=prefix + chunk,
                span_index=first_span_index + len(spans),
            )
        )
        if offset + payload_limit >= len(message.content):
            break
    return spans
