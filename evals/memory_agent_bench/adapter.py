from __future__ import annotations

import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol, cast

from src.actions.chat_end import ChatEndAction
from src.agents.chat_agent import ChatAgent
from src.agents.context_builder_agent import ContextBuilderAgent
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.short_term_memory_agent import ShortTermMemoryAgent
from src.core.contracts import AgentTurnResult, RoutePlan, SourcePlan
from src.database import Database
from src.memory.short_term import ShortTermMemory
from src.memory.structured_state import MemoryUpdateResult
from src.retrieval.current_chat_span_retriever import CurrentChatSpanRetriever
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.retrieval.raw_message_span_retriever import RawMessageSpanRetriever
from src.retrieval.recent_messages_retriever import RecentMessagesRetriever
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.retrieval.structured_memory_retriever import StructuredMemoryRetriever
from src.routing.routing_agent import RoutingAgent

from evals.memory_agent_bench.metrics import score_answer
from evals.memory_agent_bench.schemas import MABenchExample


SYSTEM_PROMPT = (
    "Answer using only supplied memory evidence. If evidence is insufficient, "
    "say I don't know."
)


class ChatModel(Protocol):
    """Minimal model contract shared by mock and configured model modes."""

    model_name: str

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        """Return one chat completion."""
        ...


class BenchmarkHarness(Protocol):
    """Lifecycle operations required by the benchmark adapter."""

    execution_classification: str
    memory_update_calls: int
    chat_end_calls: int
    structured_update_backend_calls: int | None

    def replay_session(self, example_id: str, session_id: str, chunks: tuple[str, ...]) -> None:
        """Replay one session incrementally and update memory."""
        ...

    def end_current_session(self) -> None:
        """Finalize the current session through chat lifecycle handling."""
        ...

    def ask(self, question: str, gold_answers: tuple[str, ...]) -> AgentTurnResult:
        """Ask one benchmark question through the coordinator."""
        ...

    def close(self) -> None:
        """Release temporary resources."""
        ...


class MockAnswerModel:
    """Deterministic answer model; it does not establish answer grounding."""

    model_name = "memory-agent-bench-mock-answer"

    def __init__(self) -> None:
        self.answer = "I don't know."

    def set_answer(self, answer: str) -> None:
        self.answer = answer

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del messages, temperature
        return self.answer


class RecordingNoopUpdater:
    """Offline structured-memory backend that records real update-path calls."""

    def __init__(self) -> None:
        self.calls = 0

    def update(self, existing_memory, messages):  # type: ignore[no-untyped-def]
        self.calls += 1
        return MemoryUpdateResult(
            memory_state=existing_memory,
            accepted=False,
            rejection_reason="langmem_no_valid_memories",
        )


class FixedBenchmarkRoutePlanner:
    """Expose relevant typed sources without altering production route defaults."""

    def plan(self, query: str) -> RoutePlan:
        sources = [
            SourcePlan(
                source=source,
                enabled=True,
                query=query,
                limit=8,
                reason="MemoryAgentBench production-like source exposure.",
            )
            for source in (
                "recent_messages",
                "structured_memory",
                "previous_chat_gist",
                "raw_message_span",
                "current_chat_span",
            )
        ]
        sources.append(
            SourcePlan(
                source="document_memory",
                enabled=False,
                reason="MemoryAgentBench history is not document memory.",
            )
        )
        return RoutePlan(
            query=query,
            intent="memory_agent_bench_question",
            confidence=1.0,
            requires_retrieval=True,
            sources=sources,
            ranking_profile="memory_agent_bench",
            context_profile="mixed_memory_document",
            metadata={"fixture_assisted_route": True},
        )


class QueryEchoExcludingRecentRetriever(RecentMessagesRetriever):
    """Do not count the separately supplied benchmark question as memory."""

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[Any]:
        query = (source_plan.query or "").strip()
        return [
            candidate
            for candidate in super().retrieve(chat_id, source_plan)
            if not (
                candidate.metadata.get("role") == "user"
                and candidate.content.strip() == query
            )
        ]


class ProductionLikeHarness:
    """Isolated SQLite lifecycle harness using production memory components."""

    execution_classification = "production-like with fixture-assisted routing"

    def __init__(self, model: ChatModel, mock_answer: bool) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(prefix="memory_agent_bench_")
        self.database = Database(Path(self._temp_dir.name) / "benchmark.db")
        self.model = model
        self.mock_answer = mock_answer
        self._noop_updater = RecordingNoopUpdater() if mock_answer else None
        self.memory = ShortTermMemory(
            database=self.database,
            model=cast(Any, model),
            raw_message_limit=8,
            memory_update_batch_size=2,
            structured_memory_updater=self._noop_updater,
        )
        self.current_chat_id: str | None = None
        self.memory_update_calls = 0
        self.chat_end_calls = 0
        self.question_count = 0

    @property
    def structured_update_backend_calls(self) -> int | None:
        """Expose deterministic backend calls in mock mode."""
        return self._noop_updater.calls if self._noop_updater is not None else None

    def replay_session(
        self,
        example_id: str,
        session_id: str,
        chunks: tuple[str, ...],
    ) -> None:
        chat_id = f"{example_id}-{session_id}"
        self.database.create_chat(chat_id, title=f"MemoryAgentBench {session_id}")
        self.current_chat_id = chat_id
        for chunk in chunks:
            self.database.save_message(chat_id, "user", chunk)
            self.database.save_message(chat_id, "assistant", "Acknowledged.")
            self.memory_update_calls += 1
            self.memory.update_memory_if_needed(chat_id)

    def end_current_session(self) -> None:
        if self.current_chat_id is None:
            return
        ChatEndAction(self.database, self.memory).execute(self.current_chat_id)
        self.chat_end_calls += 1
        self.current_chat_id = None

    def ask(self, question: str, gold_answers: tuple[str, ...]) -> AgentTurnResult:
        self.question_count += 1
        question_chat_id = f"benchmark-question-{self.question_count}"
        self.database.create_chat(question_chat_id, title="MemoryAgentBench question")
        if self.mock_answer and isinstance(self.model, MockAnswerModel):
            self.model.set_answer(gold_answers[0])
        coordinator = CoordinatorAgent(
            database=self.database,
            memory_agent=ShortTermMemoryAgent(self.memory),
            context_builder=ContextBuilderAgent(self.memory),
            chat_agent=ChatAgent(cast(Any, self.model)),
            system_prompt=SYSTEM_PROMPT,
            routing_agent=RoutingAgent(
                route_planner=FixedBenchmarkRoutePlanner(),  # type: ignore[arg-type]
                mode="rule",
            ),
            retriever_dispatcher=RetrieverDispatcher(
                self.database,
                retrievers={
                    "recent_messages": QueryEchoExcludingRecentRetriever(
                        self.database,
                        default_limit=8,
                    ),
                    "structured_memory": StructuredMemoryRetriever(self.database),
                    "previous_chat_gist": PreviousChatGistRetriever(self.database),
                    "raw_message_span": RawMessageSpanRetriever(self.database),
                    "current_chat_span": CurrentChatSpanRetriever(self.database),
                },
            ),
            memory_reranker=MemoryReranker(mode="deterministic"),
        )
        return coordinator.run_turn(question_chat_id, question)

    def close(self) -> None:
        self._temp_dir.cleanup()


def run_example(
    example: MABenchExample,
    *,
    mock_answer: bool,
    model: ChatModel | None = None,
    finalize_sessions: bool = True,
    harness: BenchmarkHarness | None = None,
) -> list[dict[str, Any]]:
    """Replay one example incrementally, then evaluate its questions."""
    selected_model = model or MockAnswerModel()
    selected_harness = harness or ProductionLikeHarness(
        selected_model,
        mock_answer=mock_answer,
    )
    try:
        for session in example.sessions:
            selected_harness.replay_session(
                example.example_id,
                session.session_id,
                session.chunks,
            )
            if finalize_sessions:
                selected_harness.end_current_session()

        rows = []
        for question, gold_answers in zip(
            example.questions,
            example.answers,
            strict=True,
        ):
            turn = selected_harness.ask(question, gold_answers)
            packet = turn.trace.context_packet
            candidates = packet.candidates if packet is not None else []
            evidence = "\n".join(candidate.content for candidate in candidates)
            metrics = score_answer(turn.answer, gold_answers, evidence)
            candidate_sources = {candidate.source for candidate in candidates}
            rows.append(
                {
                    "example_id": example.example_id,
                    "competency": example.competency,
                    "question": question,
                    "gold_answers": list(gold_answers),
                    "prediction": turn.answer,
                    "mock_answer": mock_answer,
                    "generated_answer_grounding_tested": not mock_answer,
                    "execution_classification": (
                        selected_harness.execution_classification
                    ),
                    "answer_metric": asdict(metrics),
                    "evidence_metric": {
                        "gold_in_context": metrics.evidence_contains_answer,
                    },
                    "sources": sorted(candidate_sources),
                    "source_coverage": {
                        source: source in candidate_sources
                        for source in (
                            "recent_messages",
                            "structured_memory",
                            "previous_chat_gist",
                            "raw_message_span",
                            "document_memory",
                            "current_chat_span",
                        )
                    },
                    "context_packet_summary": evidence[:1000],
                    "provenance_present": any(
                        candidate_has_provenance(candidate) for candidate in candidates
                    ),
                    "stale_or_deactivated_memory_present": any(
                        str(candidate.metadata.get("status", "active")).lower()
                        in {"inactive", "deleted", "superseded"}
                        for candidate in candidates
                    ),
                    "route_plan": route_plan_summary(turn),
                    "retrieved_candidates": [
                        candidate_summary(candidate)
                        for candidate in turn.trace.retrieved_candidates
                    ],
                    "post_expansion_candidates": [
                        candidate_summary(candidate)
                        for candidate in turn.trace.retrieved_candidates
                        if candidate.metadata.get("expanded_from_gist")
                        or candidate.metadata.get("parent_gist_id")
                    ],
                    "memory_update_calls": selected_harness.memory_update_calls,
                    "structured_update_backend_calls": (
                        selected_harness.structured_update_backend_calls
                    ),
                    "chat_end_calls": selected_harness.chat_end_calls,
                    "workflow_trace": workflow_trace_summary(turn),
                    "notes": (
                        ["Mock answer mode: generated-answer grounding was not tested."]
                        if mock_answer
                        else []
                    ),
                }
            )
        return rows
    finally:
        selected_harness.close()


def candidate_has_provenance(candidate: Any) -> bool:
    """Return whether a candidate carries traceable source identity."""
    return bool(
        candidate.record_id
        or candidate.source_message_ids
        or candidate.metadata.get("source_message_ids")
        or candidate.metadata.get("start_message_id")
    )


def candidate_summary(candidate: Any) -> dict[str, Any]:
    """Return compact JSON-safe candidate evidence."""
    return {
        "source": candidate.source,
        "record_id": candidate.record_id,
        "content": candidate.content[:500],
        "source_message_ids": list(candidate.source_message_ids),
        "metadata": dict(candidate.metadata),
    }


def route_plan_summary(turn: AgentTurnResult) -> dict[str, Any]:
    """Return the route fields needed for benchmark diagnostics."""
    route = turn.trace.route_plan
    if route is None:
        return {}
    return {
        "intent": route.intent,
        "context_profile": route.context_profile,
        "active_sources": [
            source.source for source in route.sources if source.enabled
        ],
        "metadata": dict(route.metadata),
    }


def workflow_trace_summary(turn: AgentTurnResult) -> dict[str, Any]:
    """Export compact observability fields without serializing internal objects."""
    return {
        "trace_id": turn.trace.trace_id,
        "errors": list(turn.trace.errors),
        "retrieved_sources": [
            candidate.source for candidate in turn.trace.retrieved_candidates
        ],
        "ranked_sources": [
            candidate.source for candidate in turn.trace.ranked_candidates
        ],
        "context_sources": (
            [candidate.source for candidate in turn.trace.context_packet.candidates]
            if turn.trace.context_packet is not None
            else []
        ),
        "timings_ms": dict(turn.trace.metadata.get("timings_ms", {})),
        "prompt_source": turn.trace.metadata.get("prompt_source"),
        "routing_decision": turn.trace.metadata.get("routing_decision"),
        "reranker": turn.trace.metadata.get("reranker"),
        "context_manager": turn.trace.metadata.get("context_manager"),
    }
