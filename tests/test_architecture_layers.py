from __future__ import annotations

import json
from pathlib import Path

from src.chat_service import ChatService
from src.context.context_budget_allocator import ContextBudgetAllocator
from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan
from src.database import Database
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.route_planner import RoutePlanner


class FakeModel:
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del messages, temperature
        return "fake response"


class SpyRetriever:
    def __init__(self, source: str) -> None:
        self.source = source
        self.calls = 0

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        self.calls += 1
        return [
            MemoryCandidate(
                source=source_plan.source,
                content=f"{self.source}:{chat_id}",
                chat_id=chat_id,
            )
        ]


def test_route_planner_profiles_and_sources() -> None:
    planner = RoutePlanner()

    general = planner.plan("How do Python dictionaries work?")
    assert general.intent == "general_question"
    assert general.context_profile == "general_chat"

    memory = planner.plan("Which database did we decide to use?")
    assert memory.intent == "decision_question"
    assert memory.context_profile == "memory_recall"

    document = planner.plan("Can you inspect the uploaded PDF document?")
    assert document.intent == "document_question"
    assert document.context_profile == "document_question"

    enabled = {source.source for source in document.sources if source.enabled}
    disabled = {source.source for source in document.sources if not source.enabled}
    assert enabled == {"recent_messages", "structured_memory"}
    assert {"current_chat_chunks", "previous_chat_memory", "document_memory"} <= disabled


def test_retriever_dispatcher_calls_only_enabled_retrievers() -> None:
    recent = SpyRetriever("recent")
    structured = SpyRetriever("structured")
    document = SpyRetriever("document")
    dispatcher = RetrieverDispatcher(
        database=None,  # type: ignore[arg-type]
        retrievers={
            "recent_messages": recent,
            "structured_memory": structured,
            "document_memory": document,
        },
    )
    route_plan = RoutePlan(
        query="q",
        sources=[
            SourcePlan(source="recent_messages", enabled=True),
            SourcePlan(source="structured_memory", enabled=True),
            SourcePlan(source="document_memory", enabled=False),
        ],
    )

    candidates = dispatcher.retrieve("chat-1", route_plan)

    assert recent.calls == 1
    assert structured.calls == 1
    assert document.calls == 0
    assert all(isinstance(candidate, MemoryCandidate) for candidate in candidates)
    assert {candidate.source for candidate in candidates} == {
        "recent_messages",
        "structured_memory",
    }


def test_retrievers_return_useful_metadata(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    chat_id = "chat"
    db.create_chat(chat_id)
    first_id = db.save_message(chat_id, "user", "My name is Alex.")
    db.save_message(chat_id, "assistant", "ack")
    db.upsert_chat_memory_state(
        chat_id,
        json.dumps(
            {
                "memories": [
                    {
                        "id": "user_facts:name",
                        "category": "user_facts",
                        "key": "name",
                        "value": "Alex",
                        "source_message_ids": [first_id],
                        "confidence": 0.95,
                        "status": "active",
                    }
                ]
            }
        ),
    )
    route_plan = RoutePlanner().plan("What is my name?")
    candidates = RetrieverDispatcher(db, raw_message_limit=8).retrieve(chat_id, route_plan)

    recent = [candidate for candidate in candidates if candidate.source == "recent_messages"]
    structured = [candidate for candidate in candidates if candidate.source == "structured_memory"]

    assert recent
    assert recent[0].metadata["role"] == "user"
    assert recent[0].metadata["order"] == 0
    assert structured
    assert structured[0].metadata["category"] == "user_facts"
    assert structured[0].metadata["confidence"] == 0.95
    assert structured[0].source_message_ids == [first_id]


def test_memory_reranker_scores_sorts_and_does_not_mutate() -> None:
    original_metadata = {"confidence": 0.9, "status": "active"}
    candidates = [
        MemoryCandidate(
            source="structured_memory",
            content="SQLite",
            metadata=original_metadata,
        ),
        MemoryCandidate(
            source="structured_memory",
            content="SQLite",
            metadata={"confidence": 0.9, "status": "active"},
        ),
        MemoryCandidate(
            source="structured_memory",
            content="Old SQLite",
            metadata={"confidence": 0.9, "status": "deleted"},
        ),
    ]

    ranked = MemoryReranker().rank(candidates, ranking_profile="test_profile")

    assert "score_breakdown" not in original_metadata
    assert ranked[0].score is not None
    assert ranked == sorted(ranked, key=lambda candidate: candidate.score or 0.0, reverse=True)
    assert ranked[0].metadata["ranking_profile"] == "test_profile"
    assert "score_breakdown" in ranked[0].metadata

    duplicate = [candidate for candidate in ranked if candidate.content == "SQLite"][1]
    deleted = next(candidate for candidate in ranked if candidate.metadata["status"] == "deleted")
    assert duplicate.metadata["score_breakdown"]["features"]["redundancy_penalty"] > 0
    assert deleted.metadata["score_breakdown"]["features"]["status_penalty"] > 0
    assert deleted.score < ranked[0].score


def test_context_budget_allocator_profiles_and_disabled_sources() -> None:
    allocator = ContextBudgetAllocator()
    planner = RoutePlanner()

    general_budget = allocator.allocate(
        route_plan=planner.plan("Explain SQLite."),
        ranked_candidates=[],
        model_context_limit=1000,
        answer_reserve=120,
        system_prompt_tokens=50,
    )
    assert general_budget.metadata["context_profile"] == "general_chat"
    assert general_budget.reserved_response_tokens == 120
    assert general_budget.metadata["safety_margin_tokens"] > 0
    assert general_budget.source_token_budgets["recent_messages"] >= 0
    assert general_budget.source_token_budgets["structured_memory"] >= 0
    assert general_budget.source_token_budgets.get("document_memory", 0) == 0

    memory_budget = allocator.allocate(
        route_plan=planner.plan("What did we decide earlier?"),
        ranked_candidates=[],
        model_context_limit=1000,
        answer_reserve=100,
        system_prompt_tokens=50,
    )
    assert memory_budget.metadata["context_profile"] == "memory_recall"

    document_budget = allocator.allocate(
        route_plan=planner.plan("Read this document."),
        ranked_candidates=[],
        model_context_limit=1000,
        answer_reserve=100,
        system_prompt_tokens=50,
    )
    assert document_budget.metadata["context_profile"] == "document_question"
    assert document_budget.source_token_budgets.get("document_memory", 0) == 0

    mixed_route = RoutePlan(
        query="mixed",
        context_profile="mixed_memory_document",
        sources=[
            SourcePlan(source="recent_messages", enabled=True),
            SourcePlan(source="structured_memory", enabled=True),
            SourcePlan(source="document_memory", enabled=True),
            SourcePlan(source="previous_chat_memory", enabled=False),
        ],
    )
    mixed_budget = allocator.allocate(
        route_plan=mixed_route,
        ranked_candidates=[],
        model_context_limit=1000,
        answer_reserve=100,
        system_prompt_tokens=50,
    )
    assert mixed_budget.metadata["context_profile"] == "mixed_memory_document"
    assert mixed_budget.source_token_budgets["document_memory"] > 0
    assert mixed_budget.source_token_budgets.get("previous_chat_memory", 0) == 0


def test_coordinator_trace_contains_all_trace_only_layers(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    service = ChatService(
        database=db,
        model=FakeModel(),
        raw_message_limit=8,
        memory_update_batch_size=6,
    )
    chat_id = service.start_chat()

    result = service.handle_user_turn(chat_id, "Which database did we decide to use?")

    assert result.answer == "fake response"
    assert result.trace.trace_id
    assert result.trace.route_plan is not None
    assert result.trace.retrieved_candidates
    assert result.trace.ranked_candidates
    assert result.trace.context_budget is not None
    assert result.trace.termination_reason == "response_generated_and_messages_saved"
    assert result.trace.context_packet is not None
    assert result.trace.context_packet.metadata["trace_only"] is True
    assert result.trace.context_packet.budget == result.trace.context_budget
    assert result.trace.context_packet.model_messages[-1] == {
        "role": "user",
        "content": "Which database did we decide to use?",
    }
