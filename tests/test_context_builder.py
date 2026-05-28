from __future__ import annotations

from src.context.context_builder import ContextBuilder
from src.core.contracts import ContextBudget, MemoryCandidate, RoutePlan, SourcePlan


def candidate(
    source: str,
    content: str,
    score: float,
    record_id: str,
    role: str | None = None,
) -> MemoryCandidate:
    metadata = {}
    if role is not None:
        metadata["role"] = role
    return MemoryCandidate(
        source=source,
        content=content,
        score=score,
        record_id=record_id,
        chat_id="chat",
        source_message_ids=[int(score * 100)] if source == "recent_messages" else [],
        metadata=metadata,
    )


def test_context_builder_respects_budgets_and_records_drops() -> None:
    builder = ContextBuilder()
    budget = ContextBudget(
        source_token_budgets={
            "structured_memory": 20,
            "recent_messages": 8,
            "document_memory": 0,
        }
    )
    ranked = [
        candidate("structured_memory", "User prefers concise answers.", 0.9, "m1"),
        candidate(
            "structured_memory",
            "This structured memory is intentionally much too long for the tiny budget.",
            0.8,
            "m2",
        ),
        candidate("recent_messages", "short recent", 0.7, "r1", role="user"),
        candidate(
            "recent_messages",
            "this recent message is too long for the remaining tiny source budget",
            0.6,
            "r2",
            role="assistant",
        ),
    ]

    packet = builder.build(
        system_prompt="system",
        latest_user_message={"role": "user", "content": "latest"},
        ranked_candidates=ranked,
        context_budget=budget,
        route_plan=RoutePlan(query="q", sources=[]),
    )

    selected_ids = {context.record_id for context in packet.candidates}
    dropped = packet.metadata["dropped_candidates"]
    assert "m1" in selected_ids
    assert "m2" not in selected_ids
    assert any(item["record_id"] == "m2" for item in dropped)
    assert all(item["reason"] == "source_budget_exceeded" for item in dropped)
    assert packet.metadata["estimated_token_usage"] > 0


def test_context_builder_orders_structured_before_recent_and_latest_last() -> None:
    builder = ContextBuilder()
    budget = ContextBudget(
        source_token_budgets={
            "structured_memory": 100,
            "recent_messages": 100,
        }
    )
    ranked = [
        candidate("recent_messages", "recent user", 0.9, "r1", role="user"),
        candidate("structured_memory", "Name is Alex", 0.8, "m1"),
        candidate("recent_messages", "recent assistant", 0.7, "r2", role="assistant"),
    ]

    packet = builder.build(
        system_prompt="system",
        latest_user_message={"role": "user", "content": "latest question"},
        ranked_candidates=ranked,
        context_budget=budget,
        route_plan=RoutePlan(query="q", sources=[]),
    )

    contents = [message["content"] for message in packet.model_messages]
    assert contents[0] == "system"
    assert contents[1].startswith("Structured Memory:")
    assert contents[-3:] == ["recent user", "recent assistant", "latest question"]
    assert packet.recent_message_ids == [90, 70]
    assert packet.structured_memory is not None


def test_context_builder_formats_retrieved_sections_between_structured_and_recent() -> None:
    builder = ContextBuilder()
    budget = ContextBudget(
        source_token_budgets={
            "structured_memory": 100,
            "document_memory": 100,
            "recent_messages": 100,
        }
    )
    ranked = [
        candidate("recent_messages", "recent", 0.9, "r1", role="user"),
        candidate("document_memory", "document fact", 0.8, "d1"),
        candidate("structured_memory", "memory fact", 0.7, "m1"),
    ]

    packet = builder.build(
        system_prompt="system",
        latest_user_message={"role": "user", "content": "latest"},
        ranked_candidates=ranked,
        context_budget=budget,
        route_plan=RoutePlan(
            query="q",
            context_profile="document_question",
            sources=[SourcePlan(source="document_memory", enabled=True)],
        ),
    )

    contents = [message["content"] for message in packet.model_messages]
    assert contents[1].startswith("Structured Memory:")
    assert contents[2].startswith("Document Memory:")
    assert contents[-2:] == ["recent", "latest"]
    assert packet.metadata["context_profile"] is None
    assert packet.metadata["section_order"] == [
        "system",
        "structured_memory",
        "retrieved_memory",
        "recent_messages",
        "latest_user_message",
    ]
