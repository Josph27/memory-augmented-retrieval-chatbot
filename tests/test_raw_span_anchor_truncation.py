from __future__ import annotations

from pathlib import Path

from src.agents.context_manager_agent import ContextManagerAgent
from src.context.context_budget_allocator import (
    ContextBudgetAllocator,
    ContextBudgetPolicy,
)
from src.context.context_builder import ContextBuilder
from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan
from src.database import Database
from src.orchestration.langgraph_memory_pipeline import evidence_failure_reason
from src.retrieval.current_chat_span_retriever import CurrentChatSpanRetriever
from src.retrieval.gist_raw_span_expander import GistRawSpanExpander
from src.retrieval.raw_message_span_retriever import (
    EARLIER_OMISSION_MARKER,
    LATER_OMISSION_MARKER,
    format_raw_span_with_anchor,
)
from src.routing.semantic_contracts import EvidenceContract


def test_gist_expansion_preserves_middle_anchor_under_small_limit(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("old-chat")
    ids = [
        database.save_message(
            "old-chat",
            "user" if index % 2 == 0 else "assistant",
            (
                "The answer token is ANCHOR_ZIRCON_42."
                if index == 4
                else f"Surrounding transcript message {index} with padding."
            ),
        )
        for index in range(9)
    ]
    gist = MemoryCandidate(
        source="previous_chat_gist",
        content="The old chat discussed a zircon answer token.",
        record_id="gist-anchor",
        chat_id="old-chat",
        source_message_ids=ids,
        metadata={
            "start_message_id": ids[0],
            "end_message_id": ids[-1],
        },
    )

    expanded = GistRawSpanExpander(
        database,
        max_messages=9,
        max_chars=180,
    ).expand([gist], "What was the ANCHOR_ZIRCON_42 answer token?")

    assert len(expanded) == 1
    raw = expanded[0]
    assert "The answer token is ANCHOR_ZIRCON_42." in raw.content
    assert EARLIER_OMISSION_MARKER in raw.content
    assert LATER_OMISSION_MARKER in raw.content
    assert raw.source_message_ids == ids
    assert raw.metadata["anchor_message_ids"] == [ids[4]]
    assert raw.metadata["truncated"] is True
    assert len(raw.content) <= 180


def test_current_chat_span_preserves_matched_anchor_under_small_limit(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    ids = [
        database.save_message(
            "chat",
            "user" if index % 2 == 0 else "assistant",
            (
                "The deployment marker is CURRENT_SPAN_COBALT."
                if index == 3
                else f"Long surrounding message {index} {'padding ' * 8}"
            ),
        )
        for index in range(7)
    ]

    candidates = CurrentChatSpanRetriever(
        database,
        window_messages=3,
        max_chars=190,
    ).retrieve(
        "chat",
        SourcePlan(
            source="current_chat_span",
            query="What was the CURRENT_SPAN_COBALT deployment marker?",
            filters={"max_spans": 1},
        ),
    )

    assert len(candidates) == 1
    span = candidates[0]
    assert "The deployment marker is CURRENT_SPAN_COBALT." in span.content
    assert ids[3] in span.source_message_ids
    assert ids[3] in span.metadata["anchor_message_ids"]
    assert span.metadata["truncated"] is True


def test_context_packet_keeps_anchor_with_tight_budget(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    target_id = database.save_message(
        "chat",
        "user",
        "The exact budget phrase is KEEP_ANCHOR_EVIDENCE.",
    )
    for index in range(4):
        database.save_message(
            "chat",
            "assistant",
            f"Verbose neighboring context {index} {'detail ' * 20}",
        )
    query = "What exact budget phrase used KEEP_ANCHOR_EVIDENCE?"
    source_plan = SourcePlan(
        source="current_chat_span",
        enabled=True,
        query=query,
        filters={"window_messages": 4, "max_spans": 1, "max_chars": 180},
    )
    route_plan = RoutePlan(
        query=query,
        intent="EXACT_QUOTE",
        sources=[source_plan],
        ranking_profile="semantic_v2",
        context_profile="memory_recall",
    )
    candidates = CurrentChatSpanRetriever(database).retrieve("chat", source_plan)
    manager = ContextManagerAgent(
        budget_allocator=ContextBudgetAllocator(
            policy=ContextBudgetPolicy(
                default_model_context_limit=420,
                default_answer_reserve=80,
            )
        ),
        context_builder=ContextBuilder(),
    )

    packet = manager.build_context_packet(
        system_prompt="Use exact raw evidence.",
        latest_user_message={"role": "user", "content": query},
        ranked_candidates=candidates,
        route_plan=route_plan,
    ).context_packet

    raw = next(
        candidate
        for candidate in packet.candidates
        if candidate.source == "current_chat_span"
    )
    assert "The exact budget phrase is KEEP_ANCHOR_EVIDENCE." in raw.content
    assert target_id in raw.source_message_ids
    assert packet.budget is not None
    assert packet.budget.max_tokens == 420
    assert (
        evidence_failure_reason(
            EvidenceContract(requires_raw_span=True),
            {candidate.source for candidate in packet.candidates},
        )
        is None
    )


def test_overlong_anchor_keeps_query_relevant_window(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    message_id = database.save_message(
        "chat",
        "user",
        f"{'prefix ' * 80}DISTINCTIVE_MIDDLE_TOKEN{' suffix' * 80}",
    )
    message = database.messages_for_chat("chat")[0]

    content = format_raw_span_with_anchor(
        [message],
        anchor_message_ids={message_id},
        max_chars=180,
        query="What was the DISTINCTIVE_MIDDLE_TOKEN?",
    )

    assert "DISTINCTIVE_MIDDLE_TOKEN" in content
    assert "raw message span truncated" in content
    assert len(content) <= 180


def test_non_raw_candidate_content_is_unchanged() -> None:
    candidate = MemoryCandidate(
        source="structured_memory",
        content="Keep structured memory formatting unchanged.",
        record_id="memory-1",
    )

    assert candidate.content == "Keep structured memory formatting unchanged."
