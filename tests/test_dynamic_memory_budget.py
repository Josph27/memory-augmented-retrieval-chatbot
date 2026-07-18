from __future__ import annotations

import pytest

from src.agents.context_manager_agent import ContextManagerAgent
from src.context.context_budget_allocator import ContextBudgetAllocator
from src.context.context_builder import ContextBuilder
from src.context.dynamic_budget import (
    DynamicWorkingMemoryBudgetPlanner,
    MemoryBudgetPolicy,
)
from src.context.evidence_selector import (
    EvidenceConstrainedContextSelector,
    SelectorPolicy,
)
from src.context.model_profile import ResolvedContextWindow
from src.context.token_estimator import ApproximateTokenEstimator
from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan


class WordCounter(ApproximateTokenEstimator):
    backend = "word_test"

    def count_text(self, text: str) -> int:
        return len(text.split()) if text else 0

    def estimate_text(self, text: str) -> int:
        return self.count_text(text)

    def count_messages(
        self,
        messages,
        *,
        add_generation_prompt: bool,
    ) -> int:
        return (
            sum(self.count_text(message.get("content", "")) for message in messages)
            + len(messages)
            + (1 if add_generation_prompt else 0)
        )

    def estimate_messages(self, messages) -> int:
        return self.count_messages(messages, add_generation_prompt=False)


def route(
    enabled: tuple[str, ...],
    *,
    scopes: tuple[str, ...] = (),
    intent: str = "test",
    task_context: str | None = None,
    requires_raw: bool = False,
    context_profile: str | None = None,
) -> RoutePlan:
    return RoutePlan(
        query="question",
        intent=intent,
        context_profile=context_profile,
        sources=[
            SourcePlan(source=source, enabled=source in enabled)
            for source in (
                "recent_messages",
                "structured_memory",
                "document_memory",
                "current_chat_span",
                "previous_chat_gist",
                "raw_message_span",
            )
        ],
        metadata={
            "required_scopes": list(scopes),
            "requires_raw_span": requires_raw,
            "task_context": task_context,
        },
    )


def candidate(
    source: str,
    words: int,
    record_id: str,
    *,
    score: float,
    message_ids: list[int] | None = None,
) -> MemoryCandidate:
    return MemoryCandidate(
        source=source,
        content=" ".join(
            [f"{source}-{record_id}"] + [f"w{index}" for index in range(max(0, words - 1))]
        ),
        score=score,
        record_id=record_id,
        chat_id="chat",
        source_message_ids=message_ids or [],
        metadata={"role": "user"} if source == "recent_messages" else {},
    )


@pytest.mark.parametrize(
    ("route_plan", "expected_cap", "expected_reason"),
    [
        (
            route(("recent_messages",)),
            4096,
            "base_recent_or_general",
        ),
        (
            route(
                ("structured_memory",),
                scopes=("durable",),
                intent="STRUCTURED_PREFERENCE_RECALL",
            ),
            4096,
            "simple_durable_recall",
        ),
        (
            route(("current_chat_span",), scopes=("current_chat",)),
            8192,
            "chat_recall_scope",
        ),
        (
            route(("previous_chat_gist",), scopes=("previous_chat",)),
            8192,
            "chat_recall_scope",
        ),
        (
            route(("document_memory",), scopes=("document",)),
            49_152,
            "single_document_scope",
        ),
        (
            route(
                ("document_memory", "current_chat_span"),
                scopes=("document", "current_chat"),
            ),
            16_384,
            "multiple_required_scopes",
        ),
    ],
)
def test_route_specific_caps(
    route_plan: RoutePlan,
    expected_cap: int,
    expected_reason: str,
) -> None:
    plan = DynamicWorkingMemoryBudgetPlanner().plan(
        route_plan=route_plan,
        available_memory_budget=100_000,
        required_evidence_floor=0,
    )

    assert plan.route_specific_cap == expected_cap
    assert plan.route_cap_reason == expected_reason
    assert plan.working_memory_budget == 4096


def test_required_floor_smaller_than_base_does_not_shrink_base() -> None:
    plan = DynamicWorkingMemoryBudgetPlanner().plan(
        route_plan=route(("document_memory",), scopes=("document",)),
        available_memory_budget=100_000,
        required_evidence_floor=1000,
    )

    assert plan.required_target == 1250
    assert plan.working_memory_budget == 4096


def test_memory_recall_profile_uses_moderate_requested_budget() -> None:
    plan = DynamicWorkingMemoryBudgetPlanner().plan(
        route_plan=route(
            ("structured_memory", "raw_message_span"),
            context_profile="memory_recall",
        ),
        available_memory_budget=100_000,
        required_evidence_floor=0,
    )

    assert plan.requested_memory_budget == 8192
    assert plan.working_memory_budget == 8192


def test_global_summary_profile_uses_large_budget_with_explicit_reserve() -> None:
    plan = DynamicWorkingMemoryBudgetPlanner().plan(
        route_plan=route(
            ("previous_chat_gist", "raw_message_span"),
            context_profile="global_summary",
        ),
        available_memory_budget=100_000,
        required_evidence_floor=0,
    )

    assert plan.route_specific_cap == 131_072
    assert plan.requested_memory_budget == 65_536
    assert plan.budget_reserve_tokens == 4096
    assert plan.working_memory_budget == 65_536


def test_global_summary_budget_never_consumes_reserved_hard_headroom() -> None:
    plan = DynamicWorkingMemoryBudgetPlanner(
        MemoryBudgetPolicy(
            global_summary_budget_tokens=65_536,
            global_summary_max_budget_tokens=131_072,
            global_summary_reserved_tokens=4096,
        )
    ).plan(
        route_plan=route(
            ("raw_message_span",),
            context_profile="global_summary",
        ),
        available_memory_budget=20_000,
        required_evidence_floor=0,
    )

    assert plan.working_memory_budget == 15_904
    assert plan.working_memory_budget + plan.budget_reserve_tokens == 20_000


def test_required_floor_larger_than_base_expands_working_budget() -> None:
    plan = DynamicWorkingMemoryBudgetPlanner().plan(
        route_plan=route(("current_chat_span",), scopes=("current_chat",)),
        available_memory_budget=100_000,
        required_evidence_floor=6000,
    )

    assert plan.required_target == 7500
    assert plan.working_memory_budget == 7500
    assert plan.budget_expanded_for_required_evidence is False


def test_required_floor_can_exceed_route_cap_but_not_available_budget() -> None:
    planner = DynamicWorkingMemoryBudgetPlanner()
    expanded = planner.plan(
        route_plan=route(("current_chat_span",), scopes=("current_chat",)),
        available_memory_budget=20_000,
        required_evidence_floor=9000,
    )
    oversized = planner.plan(
        route_plan=route(("current_chat_span",), scopes=("current_chat",)),
        available_memory_budget=8000,
        required_evidence_floor=9000,
    )

    assert expanded.working_memory_budget == 11_250
    assert expanded.budget_expanded_for_required_evidence is True
    assert oversized.working_memory_budget == 8000
    assert oversized.required_evidence_exceeds_available is True


def test_optional_selection_stops_below_configured_utility() -> None:
    selector = EvidenceConstrainedContextSelector(SelectorPolicy(minimum_optional_utility=0.5))
    useful = candidate("document_memory", 10, "useful", score=0.8)
    weak = candidate("document_memory", 10, "weak", score=0.1)

    result = selector.select(
        candidates=[useful, weak],
        route_plan=route(("document_memory",)),
        token_budget=1000,
        token_counter=WordCounter(),
    )

    assert [item.record_id for item in result.selected_candidates] == ["useful"]
    assert result.optional_selection_stopped_by == "below_minimum_utility"
    assert result.token_usage == 10


def test_manager_reports_missing_and_oversized_required_evidence() -> None:
    counter = WordCounter()
    policy = MemoryBudgetPolicy(
        base_memory_budget=20,
        chat_memory_cap=30,
        document_memory_cap=30,
        multi_scope_memory_cap=30,
        long_document_memory_cap=60,
    )
    manager = ContextManagerAgent(
        budget_allocator=ContextBudgetAllocator(token_estimator=counter),
        context_builder=ContextBuilder(token_estimator=counter),
        budget_planner=DynamicWorkingMemoryBudgetPlanner(policy),
        context_window=ResolvedContextWindow(
            model_id="test",
            native_context_window=60,
            sliding_window=None,
            endpoint_context_window=60,
            endpoint_limit_verified=True,
            application_context_cap=60,
            effective_context_window=60,
            limit_source="endpoint_metadata",
        ),
        output_reserve=10,
    )
    missing = manager.build_context_packet(
        system_prompt="system",
        latest_user_message={"role": "user", "content": "question"},
        ranked_candidates=[],
        route_plan=route(("document_memory",), scopes=("document",)),
    )
    oversized = manager.build_context_packet(
        system_prompt="system",
        latest_user_message={"role": "user", "content": "question"},
        ranked_candidates=[candidate("document_memory", 100, "oversized", score=0.9)],
        route_plan=route(("document_memory",), scopes=("document",)),
    )

    assert missing.context_packet.metadata["evidence_contract_satisfied"] is False
    assert "document" in missing.context_packet.metadata["missing_requirements"]
    assert oversized.context_budget.metadata["required_evidence_exceeds_available"] is True
    assert oversized.context_packet.metadata["evidence_contract_satisfied"] is False
    assert (
        oversized.context_packet.metadata["final_prompt_tokens"]
        <= (oversized.context_packet.metadata["hard_input_budget"])
    )


def test_explicit_document_synthesis_can_use_more_than_base_budget() -> None:
    counter = WordCounter()
    manager = ContextManagerAgent(
        budget_allocator=ContextBudgetAllocator(token_estimator=counter),
        context_builder=ContextBuilder(token_estimator=counter),
        context_window=ResolvedContextWindow(
            model_id="test",
            native_context_window=50_000,
            sliding_window=None,
            endpoint_context_window=50_000,
            endpoint_limit_verified=True,
            application_context_cap=50_000,
            effective_context_window=50_000,
            limit_source="endpoint_metadata",
        ),
        output_reserve=512,
    )
    documents = [
        candidate("document_memory", 1100, f"doc-{index}", score=0.9 - index * 0.01)
        for index in range(5)
    ]

    result = manager.build_context_packet(
        system_prompt="system",
        latest_user_message={"role": "user", "content": "synthesize"},
        ranked_candidates=documents,
        route_plan=route(
            ("document_memory",),
            scopes=("document",),
            task_context="document_synthesis",
        ),
    )

    assert result.context_budget.metadata["route_specific_cap"] == 32_768
    assert result.context_budget.metadata["required_evidence_floor"] > 4096
    assert result.context_packet.metadata["working_memory_budget"] > 4096
    assert len(result.context_packet.candidates) == 5


def test_context_profiles_reach_final_packet_without_hidden_4096_cap() -> None:
    counter = WordCounter()
    manager = ContextManagerAgent(
        budget_allocator=ContextBudgetAllocator(token_estimator=counter),
        context_builder=ContextBuilder(token_estimator=counter),
        budget_planner=DynamicWorkingMemoryBudgetPlanner(
            MemoryBudgetPolicy(
                memory_recall_budget_tokens=8192,
                global_summary_budget_tokens=65_536,
                global_summary_max_budget_tokens=131_072,
                global_summary_reserved_tokens=4096,
            )
        ),
        context_window=ResolvedContextWindow(
            model_id="test",
            native_context_window=243_282,
            sliding_window=None,
            endpoint_context_window=243_282,
            endpoint_limit_verified=True,
            application_context_cap=243_282,
            effective_context_window=243_282,
            limit_source="endpoint_metadata",
        ),
        output_reserve=512,
    )
    history = [
        candidate(
            "raw_message_span",
            1500,
            f"history-{index}",
            score=0.9 - index * 0.01,
            message_ids=[index + 1],
        )
        for index in range(6)
    ]

    recall = manager.build_context_packet(
        system_prompt="system",
        latest_user_message={"role": "user", "content": "question"},
        ranked_candidates=history,
        route_plan=route(
            ("raw_message_span",),
            context_profile="memory_recall",
        ),
    )
    summary = manager.build_context_packet(
        system_prompt="system",
        latest_user_message={"role": "user", "content": "summarize history"},
        ranked_candidates=history,
        route_plan=route(
            ("raw_message_span",),
            context_profile="global_summary",
        ),
    )

    assert recall.context_packet.metadata["working_memory_budget"] == 8192
    assert recall.context_packet.metadata["selected_memory_tokens"] == 7500
    assert summary.context_packet.metadata["working_memory_budget"] == 65_536
    assert summary.context_packet.metadata["selected_memory_tokens"] == 9000
    assert summary.context_packet.metadata["selected_memory_tokens"] > 4096
    assert (
        summary.context_packet.metadata["final_prompt_tokens"]
        < (summary.context_packet.metadata["hard_input_budget"])
    )
