from __future__ import annotations

from src.context.context_builder import ContextBuilder
from src.core.contracts import ContextBudget, MemoryCandidate, RoutePlan, SourcePlan


def candidate(
    source: str,
    content: str,
    score: float,
    record_id: str,
    role: str | None = None,
    source_message_id: int | None = None,
) -> MemoryCandidate:
    metadata = {}
    if role is not None:
        metadata["role"] = role
    if source == "structured_memory":
        metadata["category"] = "user_facts"
        metadata["key"] = "name"
    return MemoryCandidate(
        source=source,
        content=content,
        score=score,
        record_id=record_id,
        chat_id="chat",
        source_message_ids=(
            [source_message_id]
            if source == "recent_messages" and source_message_id is not None
            else []
        ),
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
    assert packet.metadata["estimated_prompt_tokens"] > 0
    assert packet.metadata["token_estimator"] == "approximate"
    accounting = packet.metadata["token_accounting"]
    assert accounting["system_tokens"] > 0
    assert accounting["structured_memory_tokens"] > 0
    assert accounting["recent_message_tokens"] > 0
    assert accounting["latest_user_message_tokens"] > 0
    assert accounting["answer_reserve"] == 0
    assert accounting["safety_margin"] == 0
    assert accounting["token_estimator"]["approximate"] is True


def test_context_builder_orders_structured_before_recent_and_latest_last() -> None:
    builder = ContextBuilder()
    budget = ContextBudget(
        source_token_budgets={
            "structured_memory": 100,
            "recent_messages": 100,
        }
    )
    ranked = [
        candidate(
            "recent_messages",
            "recent user",
            0.9,
            "r1",
            role="user",
            source_message_id=10,
        ),
        candidate("structured_memory", "Name is Alex", 0.8, "m1"),
        candidate(
            "recent_messages",
            "recent assistant",
            0.7,
            "r2",
            role="assistant",
            source_message_id=11,
        ),
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
    assert contents[1].startswith("Current structured memory:")
    assert contents[-3:] == ["recent user", "recent assistant", "latest question"]
    assert packet.recent_message_ids == [10, 11]
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
        candidate(
            "recent_messages",
            "recent",
            0.9,
            "r1",
            role="user",
            source_message_id=10,
        ),
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
    assert contents[1].startswith("Current structured memory:")
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


def test_context_builder_orders_recent_messages_chronologically_not_by_rank() -> None:
    builder = ContextBuilder()
    budget = ContextBudget(source_token_budgets={"recent_messages": 100})
    ranked = [
        candidate(
            "recent_messages",
            "assistant second",
            0.95,
            "r2",
            role="assistant",
            source_message_id=12,
        ),
        candidate(
            "recent_messages",
            "user first",
            0.2,
            "r1",
            role="user",
            source_message_id=11,
        ),
        candidate(
            "recent_messages",
            "latest question",
            0.99,
            "r3",
            role="user",
            source_message_id=13,
        ),
    ]

    packet = builder.build(
        system_prompt="system",
        latest_user_message={"role": "user", "content": "latest question"},
        ranked_candidates=ranked,
        context_budget=budget,
        route_plan=RoutePlan(query="q", sources=[]),
    )

    contents = [message["content"] for message in packet.model_messages]
    assert contents == ["system", "user first", "assistant second", "latest question"]
    assert packet.recent_message_ids == [11, 12]


def test_context_builder_excludes_latest_user_message_from_recent_candidates() -> None:
    builder = ContextBuilder()
    budget = ContextBudget(
        source_token_budgets={
            "structured_memory": 100,
            "recent_messages": 100,
        }
    )
    ranked = [
        candidate("structured_memory", "Name is Alex", 0.8, "m1"),
        candidate(
            "recent_messages",
            "hi my name is Alex",
            0.5,
            "r1",
            role="user",
            source_message_id=1,
        ),
        candidate(
            "recent_messages",
            "can you remember my name",
            0.99,
            "r2",
            role="user",
            source_message_id=2,
        ),
    ]

    packet = builder.build(
        system_prompt="system",
        latest_user_message={"role": "user", "content": "can you remember my name"},
        ranked_candidates=ranked,
        context_budget=budget,
        route_plan=RoutePlan(query="q", sources=[]),
    )

    contents = [message["content"] for message in packet.model_messages]
    assert contents.count("can you remember my name") == 1
    assert contents[-1] == "can you remember my name"
    assert contents[1].startswith("Current structured memory:")
    assert packet.recent_message_ids == [1]
    assert any(
        item["record_id"] == "r2"
        and item["reason"] == "latest_user_message_excluded"
        for item in packet.metadata["dropped_candidates"]
    )


def test_context_builder_detects_overflow_and_drops_low_ranked_non_recent() -> None:
    builder = ContextBuilder()
    budget = ContextBudget(
        max_tokens=85,
        reserved_response_tokens=5,
        source_token_budgets={
            "structured_memory": 200,
            "recent_messages": 200,
        },
        metadata={"safety_margin_tokens": 5},
    )
    low_value_memory = (
        "This lower ranked memory is intentionally verbose so it should be "
        "dropped first when the packet needs to fit the context window."
    )
    ranked = [
        candidate("structured_memory", "User name is Alex.", 0.9, "m-high"),
        candidate("structured_memory", low_value_memory, 0.1, "m-low"),
        candidate(
            "recent_messages",
            "hi my name is Alex",
            0.2,
            "r1",
            role="user",
            source_message_id=1,
        ),
    ]

    packet = builder.build(
        system_prompt="system prompt",
        latest_user_message={"role": "user", "content": "can you remember my name?"},
        ranked_candidates=ranked,
        context_budget=budget,
        route_plan=RoutePlan(query="q", sources=[]),
    )

    contents = [message["content"] for message in packet.model_messages]
    assert contents[-1] == "can you remember my name?"
    assert contents.count("can you remember my name?") == 1
    assert "hi my name is Alex" in contents
    assert packet.recent_message_ids == [1]
    assert "m-low" in packet.metadata["dropped_candidate_ids"]
    assert any(
        item["record_id"] == "m-low" and item["reason"] == "context_overflow"
        for item in packet.metadata["dropped_candidates"]
    )
    assert not any(
        item["source"] == "recent_messages" and item["reason"] == "context_overflow"
        for item in packet.metadata["dropped_candidates"]
    )
    assert packet.metadata["token_accounting"]["context_limit"] == 85


def test_context_builder_records_overflow_when_recent_and_latest_still_exceed_limit() -> None:
    builder = ContextBuilder()
    budget = ContextBudget(
        max_tokens=10,
        reserved_response_tokens=5,
        source_token_budgets={"recent_messages": 200},
        metadata={"safety_margin_tokens": 5},
    )
    ranked = [
        candidate(
            "recent_messages",
            "this recent message is kept even though the budget is tiny",
            0.2,
            "r1",
            role="user",
            source_message_id=1,
        ),
    ]

    packet = builder.build(
        system_prompt="system prompt",
        latest_user_message={"role": "user", "content": "latest must stay final"},
        ranked_candidates=ranked,
        context_budget=budget,
        route_plan=RoutePlan(query="q", sources=[]),
    )

    contents = [message["content"] for message in packet.model_messages]
    assert contents[-1] == "latest must stay final"
    assert contents.count("latest must stay final") == 1
    assert packet.metadata["overflow_detected"] is True
    assert packet.metadata["overflow_tokens"] > 0
    assert packet.metadata["estimated_prompt_tokens"] == packet.metadata[
        "token_accounting"
    ]["total_prompt_tokens"]
