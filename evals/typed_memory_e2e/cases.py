from __future__ import annotations

from evals.typed_memory_e2e.schemas import (
    BenchmarkMessage,
    BenchmarkSession,
    TypedMemoryCase,
)


def msg(role: str, content: str) -> BenchmarkMessage:
    return BenchmarkMessage(role=role, content=content)


def current_quote_case(index: int) -> TypedMemoryCase:
    topic = f"router-marker-{index}"
    target = f"My exact {topic} phrase is preserve boundary {index}."
    fillers = tuple(
        msg("assistant" if item % 2 else "user", f"Neutral later turn {item}.")
        for item in range(12 + index)
    )
    return TypedMemoryCase(
        name=f"same_chat_exact_quote_{index + 1}",
        description="Exact current-chat wording survives recent-window variation.",
        category="same_chat_exact_quote",
        sessions=(
            BenchmarkSession(
                chat_name="active",
                messages=(msg("user", target), msg("assistant", "Recorded."), *fillers),
            ),
        ),
        query=f"What exact phrase did I use about {topic}?",
        expected_sources=("current_chat_span",),
        forbidden_sources=("document_memory",),
        required_text_in_context=(target,),
        requires_raw_span=True,
    )


def previous_quote_case(index: int) -> TypedMemoryCase:
    topic = f"archive-marker-{index}"
    target = f"My exact {topic} phrase is retain provenance {index}."
    fillers = tuple(
        msg(
            "user" if item % 2 == 0 else "assistant",
            f"{topic} background turn {item}.",
        )
        for item in range(4 + index * 2)
    )
    midpoint = len(fillers) // 2
    messages = (*fillers[:midpoint], msg("user", target), *fillers[midpoint:])
    return TypedMemoryCase(
        name=f"previous_chat_exact_quote_{index + 1}",
        description="Ended-chat gist expands to exact transcript evidence.",
        category="previous_chat_exact_quote",
        sessions=(
            BenchmarkSession("ended", messages=messages, end_chat=True),
            BenchmarkSession("current"),
        ),
        query=f"What exact phrase did I use in the previous chat about {topic}?",
        expected_sources=("previous_chat_gist", "raw_message_span"),
        forbidden_sources=("document_memory",),
        required_text_in_context=(target,),
        requires_raw_span=True,
    )


def gist_orientation_case(index: int) -> TypedMemoryCase:
    topic = f"orientation-{index}"
    target = f"We discussed {topic} deployment planning."
    return TypedMemoryCase(
        name=f"gist_orientation_{index + 1}",
        description="Previous-chat gist supplies lossy orientation.",
        category="gist_orientation",
        sessions=(
            BenchmarkSession(
                "ended",
                messages=(msg("user", target), msg("assistant", "Plan recorded.")),
                end_chat=True,
            ),
            BenchmarkSession("current"),
        ),
        query=f"What did we discuss last time about {topic}?",
        expected_sources=("previous_chat_gist",),
        required_text_in_context=(topic,),
    )


def gist_only_failure_case(index: int) -> TypedMemoryCase:
    topic = f"gist-only-{index}"
    return TypedMemoryCase(
        name=f"gist_only_exact_quote_fails_{index + 1}",
        description="Orientation without transcript provenance fails closed.",
        category="gist_only_exact_quote_fails",
        sessions=(BenchmarkSession("current"),),
        query=f"Quote exactly what I said in the previous chat about {topic}.",
        expected_sources=("previous_chat_gist",),
        forbidden_sources=("raw_message_span", "current_chat_span"),
        requires_raw_span=True,
        expected_insufficient_evidence=True,
        fixture={"gist_only_text": f"The {topic} topic was discussed."},
    )


def structured_case(index: int) -> TypedMemoryCase:
    key = f"architecture-{index}"
    value = f"User prefers {key} with deterministic boundaries."
    exact_quote = index == 5
    return TypedMemoryCase(
        name=f"structured_memory_recall_{index + 1}",
        description="SQLite structured memory remains typed and retrievable.",
        category="structured_memory_recall",
        sessions=(
            BenchmarkSession(
                "source",
                messages=(msg("user", value), msg("assistant", "Stored.")),
            ),
            BenchmarkSession("current"),
        ),
        query=(
            f"What exact phrase did I use about {key}?"
            if exact_quote
            else f"What do I prefer for {key}?"
        ),
        expected_sources=(
            ("structured_memory",) if not exact_quote else ()
        ),
        forbidden_sources=(
            ("structured_memory",) if exact_quote else ("document_memory",)
        ),
        required_text_in_context=(() if exact_quote else (value,)),
        requires_raw_span=exact_quote,
        requires_structured_memory=not exact_quote,
        expected_insufficient_evidence=exact_quote,
        expected_provenance=not exact_quote,
        fixture={"structured_memory": value, "structured_key": key},
    )


def recent_case(index: int) -> TypedMemoryCase:
    target = f"Recent continuity marker {index}."
    messages = (
        msg("user", f"Older context {index}."),
        msg("assistant", "Acknowledged."),
        msg("user", target),
        msg("assistant", f"Latest response {index}."),
    )
    return TypedMemoryCase(
        name=f"recent_message_suffix_{index + 1}",
        description="Recent-message context is chronological and query-safe.",
        category="recent_message_suffix_and_context_budget",
        sessions=(BenchmarkSession("active", messages=messages),),
        query="How are you?",
        expected_sources=("recent_messages",),
        forbidden_sources=("raw_message_span", "document_memory"),
        required_text_in_context=(target,),
        fixture={"expected_query_count": 1},
    )


def anchor_case(index: int) -> TypedMemoryCase:
    topic = f"anchor-{index}"
    target = f"The exact {topic} phrase is immutable evidence {index}."
    long_text = f"{'padding ' * (120 + index * 20)}{target}{' tail' * 120}"
    return TypedMemoryCase(
        name=f"raw_span_anchor_truncation_{index + 1}",
        description="Tight raw-span formatting preserves the matched anchor.",
        category="raw_span_anchor_truncation",
        sessions=(
            BenchmarkSession(
                "active",
                messages=(msg("user", long_text), msg("assistant", "Recorded.")),
            ),
        ),
        query=f"What exact phrase did I use about {topic}?",
        expected_sources=("current_chat_span",),
        required_text_in_context=(target,),
        requires_raw_span=True,
        fixture={"current_span_max_chars": 320 + index * 20},
    )


def provenance_case(index: int) -> TypedMemoryCase:
    topic = f"provenance-{index}"
    target = f"My exact {topic} statement is trace every source id."
    return TypedMemoryCase(
        name=f"provenance_preservation_{index + 1}",
        description="Expanded previous-chat evidence retains parent provenance.",
        category="provenance_preservation",
        sessions=(
            BenchmarkSession(
                "ended",
                messages=(msg("user", target), msg("assistant", "Recorded.")),
                end_chat=True,
            ),
            BenchmarkSession("current"),
        ),
        query=f"Quote exactly my previous chat statement about {topic}.",
        expected_sources=("raw_message_span",),
        required_text_in_context=(target,),
        requires_raw_span=True,
    )


def casual_case(index: int) -> TypedMemoryCase:
    return TypedMemoryCase(
        name=f"casual_chat_minimal_memory_{index + 1}",
        description="Casual chat avoids expensive memory sources.",
        category="casual_chat_minimal_memory",
        sessions=(
            BenchmarkSession(
                "active",
                messages=(msg("assistant", f"Friendly greeting {index}."),),
            ),
        ),
        query=("How are you?", "Hello there.", "Nice to meet you.")[index],
        expected_sources=("recent_messages",),
        forbidden_sources=(
            "raw_message_span",
            "current_chat_span",
            "previous_chat_gist",
            "document_memory",
        ),
    )


def all_cases() -> list[TypedMemoryCase]:
    cases = [
        *(current_quote_case(index) for index in range(6)),
        *(previous_quote_case(index) for index in range(8)),
        *(gist_orientation_case(index) for index in range(4)),
        *(gist_only_failure_case(index) for index in range(4)),
        *(structured_case(index) for index in range(6)),
        *(recent_case(index) for index in range(4)),
        *(anchor_case(index) for index in range(4)),
        *(provenance_case(index) for index in range(4)),
        *(casual_case(index) for index in range(3)),
    ]
    assert len(cases) == 43
    return cases
