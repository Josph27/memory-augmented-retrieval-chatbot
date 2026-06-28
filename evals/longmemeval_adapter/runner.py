from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol, cast

from src.agents.chat_agent import ChatAgent
from src.agents.context_builder_agent import ContextBuilderAgent
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.short_term_memory_agent import ShortTermMemoryAgent
from src.config import AppConfig
from src.core.contracts import (
    MemoryCandidate,
    RoutePlan,
    SourcePlan,
)
from src.database import Database
from src.memory.short_term import ShortTermMemory
from src.memory.structured_state import MemoryUpdateResult
from src.model_wrapper import ModelWrapper
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.retrieval.recent_messages_retriever import RecentMessagesRetriever
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.routing_agent import RoutingAgent

from evals.longmemeval_adapter.schema import LongMemEvalCase
from evals.longmemeval_adapter.scoring import score_case, summarize_scores


SYSTEM_PROMPT = (
    "Answer the question using only the supplied conversation memory. "
    "If the memory does not support an answer, say I don't know."
)


class ModelLike(Protocol):
    """Minimal answer-model protocol used by the coordinator."""

    model_name: str

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        """Return one answer."""
        ...


class AdapterModeUnavailable(RuntimeError):
    """Raised when a requested pilot mode is not safely implemented."""


class FixedAnswerModel:
    """Deterministic model used by fixture/mock runs."""

    model_name = "longmemeval-adapter-mock"

    def __init__(self, answer: str) -> None:
        self.answer = answer

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del messages, temperature
        return self.answer


class NoopMemoryUpdater:
    """Prevent benchmark questions from mutating prepared fixture state."""

    def update(self, existing_memory, messages):  # type: ignore[no-untyped-def]
        del messages
        return MemoryUpdateResult(
            memory_state=existing_memory,
            accepted=False,
            rejection_reason="longmemeval_adapter_noop",
        )


class FixedRoutePlanner:
    """Return the benchmark-controlled source plan."""

    def __init__(self, route_plan: RoutePlan) -> None:
        self.route_plan = route_plan

    def plan(self, query: str) -> RoutePlan:
        return RoutePlan(
            query=query,
            sources=self.route_plan.sources,
            intent=self.route_plan.intent,
            confidence=self.route_plan.confidence,
            requires_retrieval=self.route_plan.requires_retrieval,
            ranking_profile=self.route_plan.ranking_profile,
            context_profile=self.route_plan.context_profile,
            fallback_policy=self.route_plan.fallback_policy,
            update_policy=self.route_plan.update_policy,
            termination_policy=self.route_plan.termination_policy,
            metadata=dict(self.route_plan.metadata),
        )


def run_adapter(
    cases: list[LongMemEvalCase],
    memory_mode: str,
    answer_mode: str,
    model: ModelLike | None = None,
) -> dict[str, Any]:
    """Run pilot cases in isolated databases and return a JSON-ready report."""
    if memory_mode in {"structured", "structured_vector"}:
        raise AdapterModeUnavailable(
            f"{memory_mode!r} preparation is reserved by the scaffold but not yet "
            "implemented without model-derived memory extraction. Use recent_only "
            "or full."
        )
    if memory_mode not in {"recent_only", "full"}:
        raise ValueError(f"Unsupported memory mode: {memory_mode}")
    if answer_mode not in {"mock", "model"}:
        raise ValueError(f"Unsupported answer mode: {answer_mode}")
    if answer_mode == "model" and model is None:
        model = configured_model()

    results = [
        run_case(
            case,
            memory_mode=memory_mode,
            answer_mode=answer_mode,
            model=model,
        )
        for case in cases
    ]
    return {
        "eval_name": "longmemeval_pilot_adapter",
        "benchmark_name": "LongMemEval",
        "scoring": "unofficial_normalized_exact_contains",
        "mode": answer_mode,
        "memory_mode": memory_mode,
        "summary": summarize_scores(results),
        "cases": results,
    }


def run_case(
    case: LongMemEvalCase,
    memory_mode: str,
    answer_mode: str,
    model: ModelLike | None,
) -> dict[str, Any]:
    """Run one case through the real coordinator with controlled source exposure."""
    with tempfile.TemporaryDirectory(prefix="longmemeval_adapter_") as temp_dir:
        database = Database(Path(temp_dir) / "case.db")
        current_chat_id = f"{case.case_id}-current"
        database.create_chat(current_chat_id, title="LongMemEval pilot question")
        if memory_mode == "recent_only":
            seed_recent_history(database, current_chat_id, case)
        else:
            seed_previous_session_gists(database, case)

        answer_model = model
        if answer_mode == "mock":
            fallback = "I don't know." if case.expected_abstain else case.gold_answer
            answer_model = FixedAnswerModel(case.mock_answer or fallback)
        if answer_model is None:
            raise AdapterModeUnavailable("Model mode requires configured model access.")

        retrievers = {
            "recent_messages": RecentMessagesRetriever(database, default_limit=8),
            "previous_chat_gist": PreviousChatGistRetriever(database),
        }
        route_plan = route_for_mode(case, memory_mode)
        routing_agent = RoutingAgent(
            route_planner=FixedRoutePlanner(route_plan),  # type: ignore[arg-type]
            mode="rule",
        )
        short_term = ShortTermMemory(
            database=database,
            model=cast(Any, answer_model),
            raw_message_limit=8,
            memory_update_batch_size=1000,
            structured_memory_updater=NoopMemoryUpdater(),
        )
        coordinator = CoordinatorAgent(
            database=database,
            memory_agent=ShortTermMemoryAgent(short_term),
            context_builder=ContextBuilderAgent(short_term),
            chat_agent=ChatAgent(cast(Any, answer_model)),
            system_prompt=SYSTEM_PROMPT,
            retriever_dispatcher=RetrieverDispatcher(
                database=database,
                retrievers=retrievers,
            ),
            routing_agent=routing_agent,
            memory_reranker=MemoryReranker(mode="deterministic"),
        )
        started = perf_counter()
        turn = coordinator.run_turn(current_chat_id, case.question)
        latency_ms = round((perf_counter() - started) * 1000, 2)
        retrieved = turn.trace.retrieved_candidates
        score = score_case(
            case,
            answer=turn.answer,
            retrieved_contents=[candidate.content for candidate in retrieved],
        )
        return {
            "case_id": case.case_id,
            "question_type": case.question_type,
            "question": case.question,
            "answer": turn.answer,
            **asdict(score),
            "latency_ms": latency_ms,
            "retrieved_sources": sorted({candidate.source for candidate in retrieved}),
            "retrieved_candidates": [
                candidate_summary(candidate) for candidate in retrieved
            ],
            "context_packet_sources": [
                candidate.source
                for candidate in (
                    turn.trace.context_packet.candidates
                    if turn.trace.context_packet
                    else []
                )
            ],
            "trace": trace_summary(turn.trace),
        }


def seed_recent_history(
    database: Database,
    chat_id: str,
    case: LongMemEvalCase,
) -> None:
    """Insert all history into one chat; runtime retrieval still exposes only recent rows."""
    for session in case.sessions:
        for message in session.messages:
            database.save_message(chat_id, message.role, message.content)


def seed_previous_session_gists(database: Database, case: LongMemEvalCase) -> None:
    """Persist prior sessions and deterministic, non-gold gist representations."""
    for index, session in enumerate(case.sessions):
        chat_id = f"{case.case_id}-history-{index + 1}"
        database.create_chat(chat_id, title=f"Benchmark history {session.session_id}")
        message_ids = [
            database.save_message(chat_id, message.role, message.content)
            for message in session.messages
        ]
        gist_text = "\n".join(
            f"{message.role}: {message.content}" for message in session.messages
        )
        database.insert_chat_gist(
            chat_id=chat_id,
            source_type="previous_chat_gist",
            gist_text=gist_text,
            topics=[],
            start_message_id=message_ids[0],
            end_message_id=message_ids[-1],
            metadata={
                "benchmark": "LongMemEval",
                "session_id": session.session_id,
                "adapter_representation": "deterministic_session_transcript",
            },
        )


def route_for_mode(case: LongMemEvalCase, memory_mode: str) -> RoutePlan:
    """Build an explicit benchmark route without changing production routing."""
    sources = [
        SourcePlan(
            source="recent_messages",
            enabled=True,
            reason="LongMemEval recent baseline.",
            query=case.question,
            limit=8,
        ),
        SourcePlan(
            source="previous_chat_gist",
            enabled=memory_mode == "full",
            reason="LongMemEval full-memory episodic source.",
            query=case.question if memory_mode == "full" else None,
            limit=8,
        ),
    ]
    return RoutePlan(
        query=case.question,
        sources=sources,
        intent="longmemeval_pilot",
        confidence=1.0,
        requires_retrieval=True,
        ranking_profile="longmemeval_pilot",
        context_profile=(
            "mixed_memory_document" if memory_mode == "full" else "general_chat"
        ),
        fallback_policy="adapter_controlled_route",
        update_policy="disabled_for_adapter",
        termination_policy="response_generated_and_messages_saved",
        metadata={"memory_mode": memory_mode, "unofficial_adapter": True},
    )


def candidate_summary(candidate: MemoryCandidate) -> dict[str, Any]:
    """Serialize a compact candidate trace without exposing entire datasets."""
    return {
        "source": candidate.source,
        "record_id": candidate.record_id,
        "chat_id": candidate.chat_id,
        "score": candidate.score,
        "snippet": candidate.content[:500],
        "source_message_ids": list(candidate.source_message_ids),
        "metadata": json_safe(candidate.metadata),
    }


def trace_summary(trace: Any) -> dict[str, Any]:
    """Serialize the adapter-relevant WorkflowTrace fields."""
    route_plan = trace.route_plan
    packet = trace.context_packet
    return {
        "trace_id": trace.trace_id,
        "active_sources": [
            source.source
            for source in (route_plan.sources if route_plan else [])
            if source.enabled
        ],
        "routing": json_safe(trace.metadata.get("routing_decision")),
        "reranker": json_safe(trace.metadata.get("reranker")),
        "context_manager": json_safe(trace.metadata.get("context_manager")),
        "context_sections": list(
            packet.metadata.get("section_order", []) if packet else []
        ),
        "prompt_source": trace.metadata.get("prompt_source"),
        "fallback_reason": trace.metadata.get("fallback_reason"),
        "errors": list(trace.errors),
    }


def configured_model() -> ModelLike:
    """Build the existing model wrapper only for explicit model mode."""
    config = AppConfig.from_env()
    if not config.openai_api_key or not config.model_name:
        raise AdapterModeUnavailable(
            "Model mode requires OPENAI_API_KEY and MODEL_NAME. "
            "OPENAI_BASE_URL is also required for a custom compatible endpoint."
        )
    return cast(ModelLike, ModelWrapper(config))


def json_safe(value: Any) -> Any:
    """Return JSON-compatible trace data."""
    return json.loads(json.dumps(value, default=str))


def write_report(path: Path, report: dict[str, Any]) -> None:
    """Write one pilot report outside the committed fixture tree."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
