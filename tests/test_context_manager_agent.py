from __future__ import annotations

from src.agents.context_manager_agent import ContextManagerAgent
from src.context.context_budget_allocator import ContextBudgetAllocator
from src.context.context_builder import ContextBuilder
from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan


def candidate(
    source: str,
    content: str,
    record_id: str,
    score: float = 0.8,
) -> MemoryCandidate:
    """Create a small test memory candidate."""
    return MemoryCandidate(
        source=source,
        content=content,
        score=score,
        record_id=record_id,
        chat_id="chat",
        metadata={"role": "user"} if source == "recent_messages" else {},
    )


def test_context_manager_agent_matches_direct_allocator_and_builder_output() -> None:
    route_plan = RoutePlan(
        query="q",
        context_profile="document_question",
        sources=[
            SourcePlan(source="recent_messages", enabled=True),
            SourcePlan(source="structured_memory", enabled=True),
            SourcePlan(source="document_memory", enabled=True),
        ],
    )
    ranked = [
        candidate("document_memory", "Document fact.", "doc-1"),
        candidate("recent_messages", "Recent message.", "recent-1"),
    ]
    latest_user_message = {"role": "user", "content": "latest question"}
    allocator = ContextBudgetAllocator()
    builder = ContextBuilder()

    direct_budget = allocator.allocate(
        route_plan=route_plan,
        ranked_candidates=ranked,
        system_prompt="system",
    )
    direct_packet = builder.build(
        system_prompt="system",
        latest_user_message=latest_user_message,
        ranked_candidates=ranked,
        context_budget=direct_budget,
        route_plan=route_plan,
    )

    result = ContextManagerAgent(
        budget_allocator=allocator,
        context_builder=builder,
    ).build_context_packet(
        system_prompt="system",
        latest_user_message=latest_user_message,
        ranked_candidates=ranked,
        route_plan=route_plan,
    )

    assert result.context_budget == direct_budget
    assert result.context_packet.model_messages == direct_packet.model_messages
    assert result.context_packet.candidates == direct_packet.candidates


def test_context_manager_agent_records_trace_metadata() -> None:
    route_plan = RoutePlan(
        query="q",
        context_profile="document_question",
        sources=[
            SourcePlan(source="recent_messages", enabled=True),
            SourcePlan(source="document_memory", enabled=True),
        ],
    )
    ranked = [
        candidate("document_memory", "Document fact.", "doc-1"),
        candidate("recent_messages", "Recent message.", "recent-1"),
    ]

    result = ContextManagerAgent().build_context_packet(
        system_prompt="system",
        latest_user_message={"role": "user", "content": "latest question"},
        ranked_candidates=ranked,
        route_plan=route_plan,
    )
    metadata = result.metadata

    assert metadata["context_manager_used"] is True
    assert metadata["source_budgets"]["document_memory"] > 0
    assert metadata["included_candidate_counts_by_source"]["document_memory"] == 1
    assert metadata["included_candidate_counts_by_source"]["recent_messages"] == 1
    assert metadata["dropped_candidate_counts_by_source"] == {}
    assert metadata["final_prompt_sections"] == [
        "system",
        "structured_memory",
        "retrieved_memory",
        "recent_messages",
        "latest_user_message",
    ]
