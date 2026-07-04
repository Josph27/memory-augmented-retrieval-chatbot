from __future__ import annotations

from dataclasses import dataclass
import os
import re

from src.core.contracts import MemoryCandidate, SourcePlan
from src.database import Database, StoredMessage

DEFAULT_RAW_SPAN_MAX_CHARS = 4000
TRUNCATION_MARKER = "\n[raw message span truncated]"
EARLIER_OMISSION_MARKER = "[... earlier messages omitted ...]"
INTERVENING_OMISSION_MARKER = "[... intervening messages omitted ...]"
LATER_OMISSION_MARKER = "[... later messages omitted ...]"
ANCHOR_START_OMISSION_MARKER = "[raw message span truncated before anchor]"
ANCHOR_END_OMISSION_MARKER = "[raw message span truncated after anchor]"
QUERY_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
LOCAL_QUERY_WINDOW_CHARS = 320
DIRECT_RAW_DEFAULT_LIMIT = 12
DIRECT_RAW_WINDOW_MESSAGES = 2
DIRECT_RAW_MAX_MESSAGES_PER_SPAN = 12
RAW_RETRIEVAL_STOPWORDS = {
    "a",
    "all",
    "and",
    "answer",
    "based",
    "by",
    "complete",
    "content",
    "did",
    "does",
    "global",
    "information",
    "in",
    "is",
    "of",
    "on",
    "summary",
    "the",
    "to",
    "was",
    "were",
    "what",
    "which",
    "who",
}


@dataclass(frozen=True)
class DirectMessageHit:
    chat_id: str
    message_index: int
    message_id: int
    score: float


class RawMessageSpanRetriever:
    """Retrieve source-of-truth raw messages for an explicit message-id span."""

    def __init__(
        self,
        database: Database,
        max_chars: int | None = None,
        direct_limit: int | None = None,
        enable_direct: bool = True,
    ) -> None:
        self.database = database
        self.max_chars = (
            raw_span_max_chars_from_env() if max_chars is None else max_chars
        )
        self.direct_limit = max(
            1,
            direct_limit if direct_limit is not None else direct_raw_limit_from_env(),
        )
        self.enable_direct = enable_direct

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        """Return a raw message span candidate when span filters are provided."""
        span = self._span_from_plan(chat_id=chat_id, source_plan=source_plan)
        if span is None:
            if not self.enable_direct:
                return []
            return self._retrieve_direct(chat_id=chat_id, source_plan=source_plan)

        span_chat_id, start_message_id, end_message_id, gist_id = span
        allowed_chat_ids = allowed_chat_ids_filter(source_plan.filters)
        if (
            allowed_chat_ids is not None
            and span_chat_id not in allowed_chat_ids
        ):
            return []
        messages = self.database.messages_for_chat_span(
            chat_id=span_chat_id,
            start_message_id=start_message_id,
            end_message_id=end_message_id,
        )
        if not messages:
            return []

        anchor_ids = anchor_message_ids_for_plan(
            messages=messages,
            source_plan=source_plan,
        )
        content = format_raw_span_with_anchor(
            messages,
            anchor_message_ids=anchor_ids,
            max_chars=self.max_chars,
            query=source_plan.query,
        )
        truncated = content != format_messages(messages)
        return [
            MemoryCandidate(
                source="raw_message_span",
                content=content,
                score=1.0,
                record_id=gist_id or f"{span_chat_id}:{start_message_id}-{end_message_id}",
                chat_id=span_chat_id,
                source_message_ids=[message.id for message in messages],
                metadata={
                    "source_chat_id": span_chat_id,
                    "start_message_id": start_message_id,
                    "end_message_id": end_message_id,
                    "message_count": len(messages),
                    "gist_id": gist_id,
                    "anchor_message_ids": sorted(anchor_ids),
                    "truncated": truncated,
                    "retrieval_mode": "raw_span_lookup",
                    "retrieval_path": "explicit_span",
                    "retrieval_paths": ["explicit_span"],
                    "status": "active",
                },
            )
        ]

    def _retrieve_direct(
        self,
        *,
        chat_id: str,
        source_plan: SourcePlan,
    ) -> list[MemoryCandidate]:
        limit = max(1, source_plan.limit or self.direct_limit)
        allowed_chat_ids = allowed_chat_ids_filter(source_plan.filters)
        if source_plan.filters.get("context_profile") == "global_summary":
            return self._global_summary_spans(
                active_chat_id=chat_id,
                allowed_chat_ids=allowed_chat_ids,
            )
        query = source_plan.query or ""
        query_terms = retrieval_terms(query)
        if not query_terms:
            return []
        chats = chronological_inactive_chats(
            self.database,
            active_chat_id=chat_id,
            allowed_chat_ids=allowed_chat_ids,
        )
        messages_by_chat = {
            str(chat["id"]): self.database.messages_for_chat(str(chat["id"]))
            for chat in chats
        }
        hits: list[DirectMessageHit] = []
        for chat in chats:
            source_chat_id = str(chat["id"])
            for index, message in enumerate(messages_by_chat[source_chat_id]):
                terms = retrieval_terms(message.content)
                overlap = query_terms & terms
                if not overlap:
                    continue
                local_overlap = max_local_query_overlap(
                    message.content,
                    query_terms,
                    window_chars=LOCAL_QUERY_WINDOW_CHARS,
                )
                _, local_span_width = local_query_match_quality(
                    message.content,
                    query_terms,
                    window_chars=LOCAL_QUERY_WINDOW_CHARS,
                )
                density_bonus = (
                    0.04
                    * max(
                        0.0,
                        1.0
                        - local_span_width / LOCAL_QUERY_WINDOW_CHARS,
                    )
                    if local_overlap > 1
                    else 0.0
                )
                uncommon = sum(
                    term.isdigit() or len(term) >= 7
                    for term in overlap
                )
                score = min(
                    1.0,
                    (
                        0.7 * local_overlap
                        + 0.3 * len(overlap)
                    )
                    / max(1, len(query_terms))
                    + density_bonus
                    + min(0.2, uncommon * 0.04),
                )
                hits.append(
                    DirectMessageHit(
                        chat_id=source_chat_id,
                        message_index=index,
                        message_id=message.id,
                        score=score,
                    )
                )
        hits.sort(key=lambda item: (-item.score, -item.message_id, item.chat_id))
        selected_hits = hits[:limit]
        ranges_by_chat: dict[str, list[tuple[int, int]]] = {}
        for hit in selected_hits:
            messages = messages_by_chat[hit.chat_id]
            ranges_by_chat.setdefault(hit.chat_id, []).append(
                (
                    max(0, hit.message_index - DIRECT_RAW_WINDOW_MESSAGES),
                    min(
                        len(messages) - 1,
                        hit.message_index + DIRECT_RAW_WINDOW_MESSAGES,
                    ),
                )
            )
        candidates: list[MemoryCandidate] = []
        for source_chat_id, ranges in ranges_by_chat.items():
            messages = messages_by_chat[source_chat_id]
            for start, end in merge_index_ranges(ranges):
                span_messages = messages[start : end + 1]
                matched_ids = [
                    hit.message_id
                    for hit in selected_hits
                    if hit.chat_id == source_chat_id
                    and start <= hit.message_index <= end
                ]
                score = max(
                    hit.score
                    for hit in selected_hits
                    if hit.chat_id == source_chat_id
                    and start <= hit.message_index <= end
                )
                candidates.append(
                    direct_raw_candidate(
                        span_messages,
                        query=query,
                        max_chars=self.max_chars,
                        matched_ids=matched_ids,
                        score=score,
                        timeline_index=start,
                        timeline_count=len(messages),
                    )
                )
        return sorted(
            candidates,
            key=lambda candidate: (
                -(candidate.score or 0.0),
                -int(candidate.metadata.get("end_message_id", 0)),
                str(candidate.chat_id),
            ),
        )[:limit]

    def _global_summary_spans(
        self,
        *,
        active_chat_id: str,
        allowed_chat_ids: set[str] | None = None,
    ) -> list[MemoryCandidate]:
        chunks: list[tuple[list[StoredMessage], int]] = []
        timeline_index = 0
        for chat in chronological_inactive_chats(
            self.database,
            active_chat_id=active_chat_id,
            allowed_chat_ids=allowed_chat_ids,
        ):
            messages = self.database.messages_for_chat(str(chat["id"]))
            for span_messages in chronological_message_chunks(
                messages,
                max_chars=self.max_chars,
                max_messages=DIRECT_RAW_MAX_MESSAGES_PER_SPAN,
            ):
                chunks.append((span_messages, timeline_index))
                timeline_index += len(span_messages)
        total_chunks = len(chunks)
        candidates = [
            direct_raw_candidate(
                chunks[index][0],
                query=None,
                max_chars=self.max_chars,
                matched_ids=[],
                score=0.65,
                timeline_index=chunks[index][1],
                timeline_count=timeline_index,
                coverage_chunk_index=index,
                coverage_chunk_count=total_chunks,
            )
            for index in range(total_chunks)
        ]
        return candidates

    def _span_from_plan(
        self,
        chat_id: str,
        source_plan: SourcePlan,
    ) -> tuple[str, int, int, int | None] | None:
        """Read span filters or resolve them from a gist id."""
        filters = source_plan.filters
        gist_id = int_filter(filters, "gist_id")
        if gist_id is not None:
            gist = self.database.chat_gist(gist_id)
            if (
                gist is not None
                and gist.start_message_id is not None
                and gist.end_message_id is not None
            ):
                return (
                    gist.chat_id,
                    gist.start_message_id,
                    gist.end_message_id,
                    gist.id,
                )

        start_message_id = int_filter(
            filters,
            "start_message_id",
            "message_start_id",
            "start_id",
        )
        end_message_id = int_filter(
            filters,
            "end_message_id",
            "message_end_id",
            "end_id",
        )
        span_chat_id = filters.get("chat_id", chat_id)
        if (
            isinstance(span_chat_id, str)
            and start_message_id is not None
            and end_message_id is not None
        ):
            return (span_chat_id, start_message_id, end_message_id, None)
        return None


def source_plan_for_gist_candidate(candidate: MemoryCandidate) -> SourcePlan | None:
    """Build an explicit raw-span source plan from a gist candidate."""
    if candidate.source not in {"current_chat_gist", "previous_chat_gist"}:
        return None

    gist_id = candidate.record_id if isinstance(candidate.record_id, int) else None
    if gist_id is not None:
        return SourcePlan(
            source="raw_message_span",
            enabled=True,
            reason="Fetch raw messages linked from gist candidate.",
            filters={"gist_id": gist_id},
        )

    start_message_id = int_filter(candidate.metadata, "start_message_id")
    end_message_id = int_filter(candidate.metadata, "end_message_id")
    if (
        candidate.chat_id is not None
        and start_message_id is not None
        and end_message_id is not None
    ):
        return SourcePlan(
            source="raw_message_span",
            enabled=True,
            reason="Fetch raw messages linked from gist candidate metadata.",
            filters={
                "chat_id": candidate.chat_id,
                "start_message_id": start_message_id,
                "end_message_id": end_message_id,
            },
        )

    return None


def format_messages(
    messages: list[StoredMessage],
    max_chars: int | None = None,
) -> str:
    """Format raw messages compactly for span drill-down context."""
    text = "\n".join(f"{message.role}: {message.content}" for message in messages)
    return truncate_text(text, max_chars=max_chars)


def format_raw_span_with_anchor(
    messages: list[StoredMessage],
    *,
    anchor_message_ids: set[int],
    max_chars: int,
    query: str | None = None,
) -> str:
    """Format a bounded raw span while retaining selected evidence messages."""
    if not messages:
        return ""
    full_text = format_messages(messages)
    if max_chars <= 0 or len(full_text) <= max_chars:
        return full_text

    anchor_indexes = [
        index
        for index, message in enumerate(messages)
        if message.id in anchor_message_ids
    ]
    if not anchor_indexes:
        anchor_indexes = [best_query_message_index(messages, query)]

    selected = set(anchor_indexes)
    anchor_only = render_selected_messages(messages, selected)
    if len(anchor_only) > max_chars:
        primary_index = best_anchor_index(messages, anchor_indexes, query)
        return truncate_anchor_message(
            messages[primary_index],
            query=query,
            max_chars=max_chars,
            has_earlier=primary_index > 0,
            has_later=primary_index < len(messages) - 1,
        )

    neighbor_indexes = sorted(
        (index for index in range(len(messages)) if index not in selected),
        key=lambda index: (
            min(abs(index - anchor_index) for anchor_index in anchor_indexes),
            index,
        ),
    )
    for index in neighbor_indexes:
        proposed = selected | {index}
        rendered = render_selected_messages(messages, proposed)
        if len(rendered) <= max_chars:
            selected = proposed
    return render_selected_messages(messages, selected)


def render_selected_messages(
    messages: list[StoredMessage],
    selected_indexes: set[int],
) -> str:
    """Render selected messages chronologically with explicit omission markers."""
    selected = sorted(selected_indexes)
    lines: list[str] = []
    if selected[0] > 0:
        lines.append(EARLIER_OMISSION_MARKER)
    previous: int | None = None
    for index in selected:
        if previous is not None and index > previous + 1:
            lines.append(INTERVENING_OMISSION_MARKER)
        message = messages[index]
        lines.append(f"{message.role}: {message.content}")
        previous = index
    if selected[-1] < len(messages) - 1:
        lines.append(LATER_OMISSION_MARKER)
    return "\n".join(lines)


def truncate_anchor_message(
    message: StoredMessage,
    *,
    query: str | None,
    max_chars: int,
    has_earlier: bool,
    has_later: bool,
) -> str:
    """Keep a query-relevant window when one anchor alone exceeds the cap."""
    prefix = f"{message.role}: "
    leading_markers = [EARLIER_OMISSION_MARKER] if has_earlier else []
    trailing_markers = [LATER_OMISSION_MARKER] if has_later else []
    anchor_markers = [
        ANCHOR_START_OMISSION_MARKER,
        ANCHOR_END_OMISSION_MARKER,
    ]
    fixed_lines = [*leading_markers, *anchor_markers, *trailing_markers]
    fixed_chars = sum(len(line) for line in fixed_lines) + len(fixed_lines)
    available = max(1, max_chars - len(prefix) - fixed_chars)
    center = query_match_center(
        message.content,
        query,
        window_chars=available,
    )
    start = max(0, center - available // 2)
    start = min(start, max(0, len(message.content) - available))
    excerpt = message.content[start : start + available]
    lines = [
        *leading_markers,
        ANCHOR_START_OMISSION_MARKER,
        f"{prefix}{excerpt}",
        ANCHOR_END_OMISSION_MARKER,
        *trailing_markers,
    ]
    rendered = "\n".join(lines)
    return rendered[:max_chars]


def anchor_message_ids_for_plan(
    *,
    messages: list[StoredMessage],
    source_plan: SourcePlan,
) -> set[int]:
    """Resolve explicit anchor IDs, then fall back to the best query match."""
    explicit = int_set_filter(source_plan.filters, "anchor_message_ids")
    available_ids = {message.id for message in messages}
    explicit &= available_ids
    if explicit:
        return explicit
    if source_plan.query:
        return {messages[best_query_message_index(messages, source_plan.query)].id}
    return available_ids


def best_query_message_index(
    messages: list[StoredMessage],
    query: str | None,
) -> int:
    """Return the strongest deterministic lexical message anchor."""
    query_terms = retrieval_terms(query or "")
    return max(
        range(len(messages)),
        key=lambda index: (
            *local_query_match_sort_key(
                messages[index].content,
                query_terms,
                window_chars=LOCAL_QUERY_WINDOW_CHARS,
            ),
            len(query_terms & query_tokens(messages[index].content)),
            messages[index].role == "user",
            messages[index].id,
        ),
    )


def best_anchor_index(
    messages: list[StoredMessage],
    anchor_indexes: list[int],
    query: str | None,
) -> int:
    """Choose one primary anchor only when all anchors cannot fit together."""
    query_terms = retrieval_terms(query or "")
    return max(
        anchor_indexes,
        key=lambda index: (
            *local_query_match_sort_key(
                messages[index].content,
                query_terms,
                window_chars=LOCAL_QUERY_WINDOW_CHARS,
            ),
            len(query_terms & query_tokens(messages[index].content)),
            messages[index].role == "user",
            messages[index].id,
        ),
    )


def query_match_center(
    content: str,
    query: str | None,
    *,
    window_chars: int | None = None,
) -> int:
    """Locate the densest query-term cluster for an overlong anchor window."""
    lowered = content.lower()
    terms = retrieval_terms(query or "")
    positions = [
        (match.start(), match.end(), term)
        for term in terms
        for match in re.finditer(rf"\b{re.escape(term)}\b", lowered)
    ]
    if not positions:
        return len(content) // 2
    effective_window = max(1, window_chars or LOCAL_QUERY_WINDOW_CHARS)
    scoring_window = min(effective_window, LOCAL_QUERY_WINDOW_CHARS)

    def quality(item: tuple[int, int, str]) -> tuple[int, int, int, int]:
        start, end, term = item
        center = start + (end - start) // 2
        window_start = max(0, center - scoring_window // 2)
        window_end = min(len(content), window_start + scoring_window)
        window_terms = query_tokens(lowered[window_start:window_end])
        return (
            len(terms & window_terms),
            len(term),
            -window_start,
            -start,
        )

    start, end, _ = max(positions, key=quality)
    return start + (end - start) // 2


def max_local_query_overlap(
    content: str,
    query_terms: set[str],
    *,
    window_chars: int,
) -> int:
    """Return the largest distinct query-term overlap in one local window."""
    return local_query_match_quality(
        content,
        query_terms,
        window_chars=window_chars,
    )[0]


def local_query_match_sort_key(
    content: str,
    query_terms: set[str],
    *,
    window_chars: int,
) -> tuple[int, int]:
    overlap, span_width = local_query_match_quality(
        content,
        query_terms,
        window_chars=window_chars,
    )
    return overlap, -span_width


def local_query_match_quality(
    content: str,
    query_terms: set[str],
    *,
    window_chars: int,
) -> tuple[int, int]:
    """Return maximum distinct overlap and its tightest occurrence span."""
    if not query_terms or not content:
        return 0, window_chars
    lowered = content.lower()
    occurrences = [
        (match.start(), term)
        for term in query_terms
        for match in re.finditer(rf"\b{re.escape(term)}\b", lowered)
    ]
    if not occurrences:
        return 0, window_chars
    best = (0, window_chars)
    for position, _ in occurrences:
        start = max(0, position - window_chars // 2)
        window_occurrences = [
            (term_position, term)
            for term_position, term in occurrences
            if start <= term_position < start + window_chars
        ]
        distinct = {term for _, term in window_occurrences}
        span_width = (
            max(term_position for term_position, _ in window_occurrences)
            - min(term_position for term_position, _ in window_occurrences)
            if len(distinct) > 1
            else window_chars
        )
        if (len(distinct), -span_width) > (best[0], -best[1]):
            best = (len(distinct), span_width)
    return best


def query_tokens(value: str) -> set[str]:
    """Return stable lexical terms for selecting a raw-message anchor."""
    return set(QUERY_TOKEN_PATTERN.findall(value.lower()))


def truncate_text(text: str, max_chars: int | None = None) -> str:
    """Return text capped to max_chars with an explicit truncation marker."""
    if max_chars is None or max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= len(TRUNCATION_MARKER):
        return TRUNCATION_MARKER[:max_chars]
    return text[: max_chars - len(TRUNCATION_MARKER)].rstrip() + TRUNCATION_MARKER


def direct_raw_candidate(
    messages: list[StoredMessage],
    *,
    query: str | None,
    max_chars: int,
    matched_ids: list[int],
    score: float,
    timeline_index: int,
    timeline_count: int,
    coverage_chunk_index: int | None = None,
    coverage_chunk_count: int | None = None,
) -> MemoryCandidate:
    ids = [message.id for message in messages]
    anchors = set(matched_ids or ids)
    content = format_raw_span_with_anchor(
        messages,
        anchor_message_ids=anchors,
        max_chars=max_chars,
        query=query,
    )
    return MemoryCandidate(
        source="raw_message_span",
        content=content,
        score=score,
        record_id=f"direct-raw:{messages[0].chat_id}:{ids[0]}-{ids[-1]}",
        chat_id=messages[0].chat_id,
        source_message_ids=ids,
        metadata={
            "source_chat_id": messages[0].chat_id,
            "start_message_id": ids[0],
            "end_message_id": ids[-1],
            "matched_message_ids": matched_ids,
            "anchor_message_ids": sorted(anchors),
            "message_count": len(messages),
            "truncated": content != format_messages(messages),
            "span_kind": "previous_chat_direct_raw",
            "retrieval_reason": (
                "chronological_global_summary_coverage"
                if coverage_chunk_index is not None
                else "deterministic_lexical_match"
            ),
            "retrieval_mode": "sqlite_previous_chat_direct_raw",
            "lexical_retrieval_score": score,
            "similarity_score": score,
            "retrieval_path": "direct_raw",
            "retrieval_paths": ["direct_raw"],
            "timeline_index": timeline_index,
            "timeline_message_count": timeline_count,
            "coverage_chunk_index": coverage_chunk_index,
            "coverage_chunk_count": coverage_chunk_count,
            "status": "active",
        },
    )


def chronological_inactive_chats(
    database: Database,
    *,
    active_chat_id: str,
    allowed_chat_ids: set[str] | None = None,
) -> list[dict]:
    return sorted(
        (
            chat
            for chat in database.list_inactive_chats()
            if str(chat["id"]) != active_chat_id
            and (
                allowed_chat_ids is None
                or str(chat["id"]) in allowed_chat_ids
            )
        ),
        key=lambda chat: (
            str(chat.get("created_at") or ""),
            str(chat["id"]),
        ),
    )


def chronological_message_chunks(
    messages: list[StoredMessage],
    *,
    max_chars: int,
    max_messages: int,
) -> list[list[StoredMessage]]:
    chunks: list[list[StoredMessage]] = []
    current: list[StoredMessage] = []
    for message in messages:
        proposed = [*current, message]
        if current and (
            len(proposed) > max_messages
            or len(format_messages(proposed)) > max_chars
        ):
            chunks.append(current)
            current = [message]
        else:
            current = proposed
    if current:
        chunks.append(current)
    return chunks


def merge_index_ranges(
    ranges: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if not merged or start > merged[-1][1] + 1:
            merged.append((start, end))
            continue
        previous_start, previous_end = merged[-1]
        merged[-1] = (previous_start, max(previous_end, end))
    return merged


def retrieval_terms(value: str) -> set[str]:
    return {
        term
        for term in query_tokens(value)
        if term not in RAW_RETRIEVAL_STOPWORDS and len(term) > 1
    }


def raw_span_max_chars_from_env() -> int:
    """Read the raw message span context cap from the environment."""
    raw_value = os.getenv("RAW_MESSAGE_SPAN_MAX_CHARS", "").strip()
    if not raw_value:
        return DEFAULT_RAW_SPAN_MAX_CHARS
    try:
        value = int(raw_value)
    except ValueError:
        return DEFAULT_RAW_SPAN_MAX_CHARS
    return value if value > 0 else DEFAULT_RAW_SPAN_MAX_CHARS


def direct_raw_limit_from_env() -> int:
    try:
        return max(
            1,
            int(
                os.getenv(
                    "DIRECT_RAW_RETRIEVAL_CANDIDATES",
                    str(DIRECT_RAW_DEFAULT_LIMIT),
                )
            ),
        )
    except ValueError:
        return DIRECT_RAW_DEFAULT_LIMIT


def int_filter(filters: dict[str, object], *names: str) -> int | None:
    """Read an integer filter while rejecting bool values."""
    for name in names:
        value = filters.get(name)
        if type(value) is int:
            return value
    return None


def int_set_filter(filters: dict[str, object], name: str) -> set[int]:
    """Read integer IDs from a source-plan filter."""
    value = filters.get(name, [])
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {item for item in value if type(item) is int}


def allowed_chat_ids_filter(
    filters: dict[str, object],
) -> set[str] | None:
    """Return an explicit chat scope, or None when no scope was supplied."""
    if "allowed_chat_ids" not in filters:
        return None
    value = filters.get("allowed_chat_ids")
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {
        str(item)
        for item in value
        if isinstance(item, (str, int)) and not isinstance(item, bool)
    }
