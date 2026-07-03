from __future__ import annotations

import pytest

from src.agents.context_manager_agent import ContextManagerAgent
from src.context.context_budget_allocator import ContextBudgetAllocator
from src.context.context_builder import ContextBuilder
from src.context.dynamic_budget import (
    DynamicWorkingMemoryBudgetPlanner,
    MemoryBudgetPolicy,
)
from src.context.evidence_selector import EvidenceConstrainedContextSelector
from src.context.model_profile import ResolvedContextWindow
from src.context.token_estimator import ApproximateTokenEstimator
from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan
from src.database import Database
from src.orchestration.demo_orchestration import run_read_only_langgraph_orchestration
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher


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
        content = sum(self.count_text(message.get("content", "")) for message in messages)
        return content + len(messages) + (1 if add_generation_prompt else 0)

    def estimate_messages(self, messages) -> int:
        return self.count_messages(messages, add_generation_prompt=False)


def route(
    enabled: tuple[str, ...],
    *,
    scopes: tuple[str, ...] = (),
    requires_raw: bool = False,
) -> RoutePlan:
    return RoutePlan(
        query="relevant evidence",
        intent="EXACT_QUOTE" if requires_raw else "test",
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
        },
    )


def candidate(
    source: str,
    words: int,
    record_id: str | int,
    *,
    score: float,
    message_ids: list[int] | None = None,
    parent_gist_id: int | None = None,
    role: str | None = None,
    content: str | None = None,
) -> MemoryCandidate:
    metadata = {}
    if parent_gist_id is not None:
        metadata.update(
            {
                "parent_gist_id": parent_gist_id,
                "derived_from_source": "previous_chat_gist",
            }
        )
    if role is not None:
        metadata["role"] = role
    return MemoryCandidate(
        source=source,
        content=content
        or " ".join(
            [f"{source}-{record_id}"]
            + [f"w{index}" for index in range(max(0, words - 1))]
        ),
        score=score,
        record_id=record_id,
        chat_id="chat",
        source_message_ids=message_ids or [],
        metadata=metadata,
    )


def selected_ids(result) -> set[str | int]:
    return {item.record_id for item in result.selected_candidates}


@pytest.mark.parametrize("case", ["q5", "q11", "q17", "q19"])
def test_rank_one_raw_regressions_fit_global_budget(case: str) -> None:
    rank_one = candidate(
        "raw_message_span",
        100,
        case,
        score=0.9,
        message_ids=list(range(1, 13)),
    )
    shorter = candidate(
        "raw_message_span",
        20,
        f"{case}-short",
        score=0.6,
        message_ids=list(range(30, 34)),
    )

    result = EvidenceConstrainedContextSelector().select(
        candidates=[rank_one, shorter],
        route_plan=route(("raw_message_span",), requires_raw=True),
        token_budget=100,
        token_counter=WordCounter(),
    )

    assert case in selected_ids(result)
    assert f"{case}-short" not in selected_ids(result)
    assert result.selection_reasons[result.trace_id_by_object[id(rank_one)]] == (
        "required_raw_evidence"
    )
    assert result.token_usage == 100


def test_required_document_and_current_chat_are_both_admitted() -> None:
    document = candidate("document_memory", 20, "doc", score=0.9)
    current = candidate(
        "current_chat_span",
        20,
        "current",
        score=0.85,
        message_ids=[1, 2],
    )

    result = EvidenceConstrainedContextSelector().select(
        candidates=[document, current],
        route_plan=route(
            ("document_memory", "current_chat_span"),
            scopes=("document", "current_chat"),
        ),
        token_budget=40,
        token_counter=WordCounter(),
    )

    assert selected_ids(result) == {"doc", "current"}
    assert result.evidence_contract_satisfied is True


def test_required_document_and_previous_chat_are_both_admitted() -> None:
    document = candidate("document_memory", 20, "doc", score=0.9)
    gist = candidate("previous_chat_gist", 10, 7, score=0.7)
    raw = candidate(
        "raw_message_span",
        20,
        "raw",
        score=0.85,
        message_ids=[3, 4],
        parent_gist_id=7,
    )

    result = EvidenceConstrainedContextSelector().select(
        candidates=[document, raw, gist],
        route_plan=route(
            ("document_memory", "previous_chat_gist"),
            scopes=("document", "previous_chat"),
        ),
        token_budget=40,
        token_counter=WordCounter(),
    )

    assert selected_ids(result) == {"doc", "raw"}
    assert "previous_chat" in result.required_evidence_selected


def test_selected_raw_child_folds_parent_gist() -> None:
    gist = candidate("previous_chat_gist", 10, 7, score=0.8)
    raw = candidate(
        "raw_message_span",
        20,
        "raw",
        score=0.9,
        message_ids=[1, 2],
        parent_gist_id=7,
    )

    result = EvidenceConstrainedContextSelector().select(
        candidates=[raw, gist],
        route_plan=route(("previous_chat_gist",)),
        token_budget=50,
        token_counter=WordCounter(),
    )

    assert selected_ids(result) == {"raw"}
    assert any(
        item["reason"] == "folded_into_raw_child"
        for item in result.duplicate_decisions
    )


def test_parent_gist_remains_when_raw_child_does_not_fit() -> None:
    raw = candidate(
        "raw_message_span",
        60,
        "raw",
        score=0.9,
        message_ids=[1, 2],
        parent_gist_id=7,
    )
    gist = candidate("previous_chat_gist", 10, 7, score=0.8)

    result = EvidenceConstrainedContextSelector().select(
        candidates=[raw, gist],
        route_plan=route(("previous_chat_gist",)),
        token_budget=20,
        token_counter=WordCounter(),
    )

    assert selected_ids(result) == {7}


def test_identical_candidates_are_deduplicated() -> None:
    first = candidate(
        "document_memory",
        2,
        "first",
        score=0.9,
        content="same text",
    )
    second = candidate(
        "structured_memory",
        2,
        "second",
        score=0.8,
        content="same   text",
    )

    result = EvidenceConstrainedContextSelector().select(
        candidates=[first, second],
        route_plan=route(("document_memory", "structured_memory")),
        token_budget=20,
        token_counter=WordCounter(),
    )

    assert selected_ids(result) == {"first"}
    assert any(item["reason"] == "exact_duplicate" for item in result.duplicate_decisions)


def test_highly_overlapping_spans_only_consume_budget_once() -> None:
    first = candidate(
        "raw_message_span",
        10,
        "first",
        score=0.9,
        message_ids=[1, 2, 3, 4],
    )
    second = candidate(
        "raw_message_span",
        10,
        "second",
        score=0.8,
        message_ids=[2, 3, 4, 5],
    )

    result = EvidenceConstrainedContextSelector().select(
        candidates=[first, second],
        route_plan=route(("raw_message_span",)),
        token_budget=30,
        token_counter=WordCounter(),
    )

    assert selected_ids(result) == {"first"}
    assert result.token_usage == 10
    assert any(item["reason"] == "overlapping_span" for item in result.duplicate_decisions)


def test_optional_candidates_share_global_pool_and_disabled_sources_are_excluded() -> None:
    document = candidate("document_memory", 10, "doc", score=0.9)
    memory = candidate("structured_memory", 10, "memory", score=0.85)
    disabled = candidate("current_chat_span", 1, "disabled", score=1.0)

    result = EvidenceConstrainedContextSelector().select(
        candidates=[disabled, document, memory],
        route_plan=route(("document_memory", "structured_memory")),
        token_budget=20,
        token_counter=WordCounter(),
    )

    assert selected_ids(result) == {"doc", "memory"}


def test_recent_messages_preserve_newest_contiguous_suffix() -> None:
    recent = [
        candidate(
            "recent_messages",
            4,
            index,
            score=0.5,
            message_ids=[index],
            role="user" if index % 2 else "assistant",
        )
        for index in (1, 2, 3)
    ]

    result = EvidenceConstrainedContextSelector().select(
        candidates=recent,
        route_plan=route(("recent_messages",)),
        token_budget=8,
        token_counter=WordCounter(),
    )

    assert [item.record_id for item in result.selected_candidates] == [2, 3]
    assert all(
        result.selection_reasons[result.trace_id_by_object[id(item)]]
        == "protected_recent_suffix"
        for item in result.selected_candidates
    )


def test_missing_required_evidence_is_reported() -> None:
    result = EvidenceConstrainedContextSelector().select(
        candidates=[],
        route_plan=route(("document_memory",), scopes=("document",)),
        token_budget=100,
        token_counter=WordCounter(),
    )

    assert result.evidence_contract_satisfied is False
    assert result.missing_requirements == ["document"]


def test_context_manager_respects_working_and_hard_budgets() -> None:
    counter = WordCounter()
    manager = ContextManagerAgent(
        budget_allocator=ContextBudgetAllocator(token_estimator=counter),
        context_builder=ContextBuilder(token_estimator=counter),
        context_window=ResolvedContextWindow(
            model_id="test",
            native_context_window=100,
            sliding_window=None,
            endpoint_context_window=100,
            endpoint_limit_verified=True,
            application_context_cap=100,
            effective_context_window=100,
            limit_source="endpoint_metadata",
        ),
        output_reserve=10,
        budget_planner=DynamicWorkingMemoryBudgetPlanner(
            MemoryBudgetPolicy(
                base_memory_budget=20,
                chat_memory_cap=20,
                document_memory_cap=20,
                multi_scope_memory_cap=20,
                long_document_memory_cap=20,
            )
        ),
    )
    candidates = [
        candidate("document_memory", 10, "one", score=0.9),
        candidate("document_memory", 10, "two", score=0.8),
        candidate("document_memory", 10, "three", score=0.7),
    ]

    result = manager.build_context_packet(
        system_prompt="system instruction",
        latest_user_message={"role": "user", "content": "question"},
        ranked_candidates=candidates,
        route_plan=route(("document_memory",)),
    )

    selection = result.context_packet.metadata["evidence_selection"]
    assert selection["token_usage"] <= 20
    assert result.context_packet.metadata["final_prompt_tokens"] <= (
        result.context_packet.metadata["hard_input_budget"]
    )


class SpySelector(EvidenceConstrainedContextSelector):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def select(self, **kwargs):
        self.calls += 1
        return super().select(**kwargs)


class SpyBudgetPlanner(DynamicWorkingMemoryBudgetPlanner):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def plan(self, **kwargs):
        self.calls += 1
        return super().plan(**kwargs)


def test_native_and_langgraph_use_same_budget_policy_selector_and_read_only_graph(
    tmp_path,
) -> None:
    selector = SpySelector()
    budget_planner = SpyBudgetPlanner()
    counter = WordCounter()
    manager = ContextManagerAgent(
        budget_allocator=ContextBudgetAllocator(token_estimator=counter),
        context_builder=ContextBuilder(token_estimator=counter),
        selector=selector,
        budget_planner=budget_planner,
    )
    manager.build_context_packet(
        **{
        "system_prompt": "system",
        "latest_user_message": {"role": "user", "content": "question"},
        "ranked_candidates": [
            candidate("document_memory", 5, "doc", score=0.9)
        ],
        "route_plan": route(("document_memory",)),
        }
    )
    database = Database(tmp_path / "selector.db")
    database.create_chat("chat")
    database.save_message("chat", "assistant", "Hello.")
    before = database.messages_for_chat("chat")
    run_read_only_langgraph_orchestration(
        chat_id="chat",
        query="How are you?",
        dispatcher=RetrieverDispatcher(database),
        reranker=MemoryReranker(),
        context_manager=manager,
        system_prompt="system",
    )

    assert selector.calls == 4
    assert budget_planner.calls == 2
    assert database.messages_for_chat("chat") == before
