from __future__ import annotations

import tempfile
from dataclasses import asdict
from pathlib import Path
import shutil
from typing import Any, Protocol, cast

from src.actions.chat_end import ChatEndAction
from src.agents.chat_agent import ChatAgent
from src.agents.context_manager_agent import ContextManagerAgent
from src.agents.context_builder_agent import ContextBuilderAgent
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.short_term_memory_agent import ShortTermMemoryAgent
from src.core.contracts import AgentTurnResult, RoutePlan, SourcePlan
from src.database import Database
from src.memory.short_term import ShortTermMemory, StructuredMemoryUpdater
from src.memory.structured_state import MemoryUpdateResult
from src.orchestration.demo_orchestration import NATIVE
from src.retrieval.current_chat_span_retriever import CurrentChatSpanRetriever
from src.retrieval.cross_encoder_reranker import CrossEncoderBackend
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.retrieval.raw_message_span_retriever import RawMessageSpanRetriever
from src.retrieval.recent_messages_retriever import RecentMessagesRetriever
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.retrieval.structured_memory_retriever import StructuredMemoryRetriever
from src.routing.routing_agent import RoutingAgent

from evals.memory_agent_bench.metrics import normalize_text, score_answer
from evals.memory_agent_bench.raw_replay import (
    EVAL_RAW_REPLAY_SOURCE,
    EvalRawReplayChunkRetriever,
    EvalRawReplayContextManager,
    ReplayEmbeddingBackend,
    raw_replay_diagnostics,
)
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
    replayed_chunks: list[dict[str, Any]]

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

    def __init__(
        self,
        *,
        raw_replay_enabled: bool = False,
        raw_replay_top_k: int = 8,
    ) -> None:
        self.raw_replay_enabled = raw_replay_enabled
        self.raw_replay_top_k = max(1, raw_replay_top_k)

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
        if self.raw_replay_enabled:
            sources.append(
                SourcePlan(
                    source=EVAL_RAW_REPLAY_SOURCE,  # type: ignore[arg-type]
                    enabled=True,
                    query=query,
                    limit=self.raw_replay_top_k,
                    reason="MemoryAgentBench eval-only raw replay diagnostic.",
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

    def __init__(
        self,
        model: ChatModel,
        mock_answer: bool,
        *,
        raw_replay_enabled: bool = False,
        raw_replay_top_k: int = 8,
        raw_replay_max_chars: int = 4000,
        raw_replay_retrieval_mode: str = "lexical",
        raw_replay_embedding_backend: ReplayEmbeddingBackend | None = None,
        raw_replay_candidate_pool_size: int = 50,
        reranker_mode: str = "deterministic",
        cross_encoder_backend: CrossEncoderBackend | None = None,
        cross_encoder_top_k: int = 10,
        cross_encoder_weight: float = 0.65,
        orchestration_mode: str = NATIVE,
        deterministic_memory_updates: bool = False,
        context_manager_agent: ContextManagerAgent | None = None,
        structured_memory_updater: StructuredMemoryUpdater | None = None,
        raw_message_limit: int = 8,
        memory_update_batch_size: int = 2,
        recent_messages_max_count: int | None = None,
        memory_update_trigger_tokens: int = 1000,
        memory_update_max_input_tokens: int = 4000,
        memory_update_max_messages: int | None = None,
        memory_recent_protection_tokens: int = 1500,
        memory_replay_trigger_tokens: int = 4000,
        memory_replay_max_input_tokens: int = 8000,
        memory_replay_max_messages: int = 128,
        database_path: Path | None = None,
    ) -> None:
        self._temp_dir = None
        if database_path is None:
            self._temp_dir = tempfile.TemporaryDirectory(prefix="memory_agent_bench_")
            database_path = Path(self._temp_dir.name) / "benchmark.db"
        self.database = Database(database_path)
        self.model = model
        self.mock_answer = mock_answer
        self.raw_replay_enabled = raw_replay_enabled
        self.raw_replay_top_k = max(1, raw_replay_top_k)
        self.raw_replay_max_chars = max(1, raw_replay_max_chars)
        self.raw_replay_retrieval_mode = raw_replay_retrieval_mode
        self.raw_replay_embedding_backend = raw_replay_embedding_backend
        self.raw_replay_candidate_pool_size = max(
            self.raw_replay_top_k,
            raw_replay_candidate_pool_size,
        )
        self.reranker_mode = reranker_mode
        self.cross_encoder_backend = cross_encoder_backend
        self.cross_encoder_top_k = max(1, cross_encoder_top_k)
        self.cross_encoder_weight = cross_encoder_weight
        self.orchestration_mode = orchestration_mode
        self.context_manager_agent = context_manager_agent
        self.raw_message_limit = raw_message_limit
        self.memory_update_batch_size = memory_update_batch_size
        self.recent_messages_max_count = (
            recent_messages_max_count
            if recent_messages_max_count is not None
            else raw_message_limit
        )
        self.memory_update_trigger_tokens = memory_update_trigger_tokens
        self.memory_update_max_input_tokens = memory_update_max_input_tokens
        self.memory_update_max_messages = (
            memory_update_max_messages
            if memory_update_max_messages is not None
            else memory_update_batch_size
        )
        self.memory_recent_protection_tokens = memory_recent_protection_tokens
        self.memory_replay_trigger_tokens = memory_replay_trigger_tokens
        self.memory_replay_max_input_tokens = memory_replay_max_input_tokens
        self.memory_replay_max_messages = memory_replay_max_messages
        self._raw_replay_retriever: EvalRawReplayChunkRetriever | None = None
        self._structured_memory_updater = structured_memory_updater
        if self._structured_memory_updater is None and (
            mock_answer or deterministic_memory_updates
        ):
            self._structured_memory_updater = RecordingNoopUpdater()
        self.memory = ShortTermMemory(
            database=self.database,
            model=cast(Any, model),
            raw_message_limit=self.raw_message_limit,
            memory_update_batch_size=self.memory_update_batch_size,
            structured_memory_updater=self._structured_memory_updater,
            recent_messages_max_count=self.recent_messages_max_count,
            memory_update_trigger_tokens=self.memory_update_trigger_tokens,
            memory_update_max_input_tokens=self.memory_update_max_input_tokens,
            memory_update_max_messages=self.memory_update_max_messages,
            memory_recent_protection_tokens=self.memory_recent_protection_tokens,
            memory_replay_trigger_tokens=self.memory_replay_trigger_tokens,
            memory_replay_max_input_tokens=self.memory_replay_max_input_tokens,
            memory_replay_max_messages=self.memory_replay_max_messages,
        )
        self.current_chat_id: str | None = None
        self.memory_update_calls = 0
        self.chat_end_calls = 0
        self.question_count = 0
        self.replayed_chunks: list[dict[str, Any]] = []

    @property
    def structured_update_backend_calls(self) -> int | None:
        """Expose deterministic backend calls in mock mode."""
        updater = self._structured_memory_updater
        return updater.calls if isinstance(updater, RecordingNoopUpdater) else None

    def replay_session(
        self,
        example_id: str,
        session_id: str,
        chunks: tuple[str, ...],
    ) -> None:
        chat_id = f"{example_id}-{session_id}"
        self.database.create_chat(chat_id, title=f"MemoryAgentBench {session_id}")
        self.current_chat_id = chat_id
        for chunk_index, chunk in enumerate(chunks):
            user_message_id = self.database.save_message(chat_id, "user", chunk)
            self.database.save_message(chat_id, "assistant", "Acknowledged.")
            self.replayed_chunks.append(
                {
                    "session_id": session_id,
                    "chunk_index": chunk_index,
                    "user_message_id": user_message_id,
                    "chat_id": chat_id,
                    "content": chunk,
                }
            )
        replay_result = self.memory.process_replay_batches(chat_id)
        self.memory_update_calls += replay_result.batch_count

    def prepare_history(self, example: MABenchExample) -> None:
        for session in example.sessions:
            self.replay_session(
                example.example_id,
                session.session_id,
                session.chunks,
            )
            self.end_current_session()

    def copy_database_to(self, target_path: Path) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.database.path, target_path)

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
        route_planner = FixedBenchmarkRoutePlanner(
            raw_replay_enabled=self.raw_replay_enabled,
            raw_replay_top_k=self.raw_replay_top_k,
        )
        retrievers = {
            "recent_messages": QueryEchoExcludingRecentRetriever(
                self.database,
                default_limit=self.recent_messages_max_count,
            ),
            "structured_memory": StructuredMemoryRetriever(self.database),
            "previous_chat_gist": PreviousChatGistRetriever(self.database),
            "raw_message_span": RawMessageSpanRetriever(self.database),
            "current_chat_span": CurrentChatSpanRetriever(self.database),
        }
        if self.raw_replay_enabled:
            self._raw_replay_retriever = EvalRawReplayChunkRetriever(
                self.replayed_chunks,
                top_k=self.raw_replay_top_k,
                max_chars=self.raw_replay_max_chars,
                retrieval_mode=self.raw_replay_retrieval_mode,
                embedding_backend=self.raw_replay_embedding_backend,
                candidate_pool_size=self.raw_replay_candidate_pool_size,
            )
            retrievers[EVAL_RAW_REPLAY_SOURCE] = self._raw_replay_retriever
        coordinator = CoordinatorAgent(
            database=self.database,
            memory_agent=ShortTermMemoryAgent(self.memory),
            context_builder=ContextBuilderAgent(self.memory),
            chat_agent=ChatAgent(cast(Any, self.model)),
            system_prompt=SYSTEM_PROMPT,
            routing_agent=RoutingAgent(
                route_planner=route_planner,  # type: ignore[arg-type]
                mode="rule",
            ),
            retriever_dispatcher=RetrieverDispatcher(
                self.database,
                retrievers=retrievers,  # type: ignore[arg-type]
            ),
            memory_reranker=MemoryReranker(
                mode=self.reranker_mode,
                cross_encoder_backend=self.cross_encoder_backend,
                cross_encoder_top_k=self.cross_encoder_top_k,
                cross_encoder_weight=self.cross_encoder_weight,
            ),
            context_manager_agent=(
                EvalRawReplayContextManager()
                if self.raw_replay_enabled
                else self.context_manager_agent
            ),
        )
        return coordinator.run_turn(
            question_chat_id,
            question,
            orchestration_mode=self.orchestration_mode,
            task_context="memory_qa",
        )

    def raw_replay_rank_diagnostics(
        self,
        gold_message_ids: set[int],
    ) -> dict[str, Any]:
        """Expose post-hoc ranks without feeding benchmark gold to retrieval."""
        if self._raw_replay_retriever is None:
            return {}
        return self._raw_replay_retriever.gold_rank_diagnostics(gold_message_ids)

    def close(self) -> None:
        if self._temp_dir is not None:
            self._temp_dir.cleanup()


def run_example(
    example: MABenchExample,
    *,
    mock_answer: bool,
    model: ChatModel | None = None,
    finalize_sessions: bool = True,
    skip_replay: bool = False,
    harness: BenchmarkHarness | None = None,
    raw_replay_enabled: bool = False,
    raw_replay_top_k: int = 8,
    raw_replay_max_chars: int = 4000,
    raw_replay_retrieval_mode: str = "lexical",
    raw_replay_embedding_backend: ReplayEmbeddingBackend | None = None,
    raw_replay_candidate_pool_size: int = 50,
    reranker_mode: str = "deterministic",
    cross_encoder_backend: CrossEncoderBackend | None = None,
    cross_encoder_top_k: int = 10,
    cross_encoder_weight: float = 0.65,
    orchestration_mode: str = NATIVE,
) -> list[dict[str, Any]]:
    """Replay one example incrementally, then evaluate its questions."""
    selected_model = model or MockAnswerModel()
    selected_harness = harness or ProductionLikeHarness(
        selected_model,
        mock_answer=mock_answer,
        raw_replay_enabled=raw_replay_enabled,
        raw_replay_top_k=raw_replay_top_k,
        raw_replay_max_chars=raw_replay_max_chars,
        raw_replay_retrieval_mode=raw_replay_retrieval_mode,
        raw_replay_embedding_backend=raw_replay_embedding_backend,
        raw_replay_candidate_pool_size=raw_replay_candidate_pool_size,
        reranker_mode=reranker_mode,
        cross_encoder_backend=cross_encoder_backend,
        cross_encoder_top_k=cross_encoder_top_k,
        cross_encoder_weight=cross_encoder_weight,
        orchestration_mode=orchestration_mode,
    )
    try:
        if not skip_replay:
            for session in example.sessions:
                selected_harness.replay_session(
                    example.example_id,
                    session.session_id,
                    session.chunks,
                )
                if finalize_sessions:
                    selected_harness.end_current_session()

        rows = []
        for question_index, (question, gold_answers) in enumerate(
            zip(
                example.questions,
                example.answers,
                strict=True,
            )
        ):
            turn = selected_harness.ask(question, gold_answers)
            packet = turn.trace.context_packet
            candidates = packet.candidates if packet is not None else []
            evidence = "\n".join(candidate.content for candidate in candidates)
            metrics = score_answer(turn.answer, gold_answers, evidence)
            candidate_sources = {candidate.source for candidate in candidates}
            diagnostics = evidence_diagnostics(
                gold_answers=gold_answers,
                replayed_chunks=getattr(selected_harness, "replayed_chunks", []),
                retrieved=turn.trace.retrieved_candidates,
                ranked=turn.trace.ranked_candidates,
                context_candidates=candidates,
                dropped_candidates=(
                    packet.metadata.get("dropped_candidates", [])
                    if packet is not None
                    else []
                ),
            )
            raw_diagnostics = raw_replay_diagnostics(
                enabled=raw_replay_enabled,
                gold_answers=gold_answers,
                retrieved_candidates=turn.trace.retrieved_candidates,
                context_candidates=candidates,
                gold_message_ids=set(diagnostics["gold_message_ids"]),
                rank_diagnostics=(
                    selected_harness.raw_replay_rank_diagnostics(
                        set(diagnostics["gold_message_ids"])
                    )
                    if hasattr(selected_harness, "raw_replay_rank_diagnostics")
                    else None
                ),
            )
            gist_gold_found = bool(
                candidate_ids_containing_gold(
                    [
                        candidate
                        for candidate in turn.trace.retrieved_candidates
                        if candidate.source == "previous_chat_gist"
                    ],
                    diagnostics["normalized_gold_answers"],
                )
            )
            rows.append(
                {
                    "example_id": example.example_id,
                    "competency": example.competency,
                    "source_dataset": example.metadata.get("source"),
                    "row_index": example.metadata.get("adapter_row_index"),
                    "question_index": question_index,
                    "session_count": len(example.sessions),
                    "replayed_chunk_count": sum(
                        len(session.chunks) for session in example.sessions
                    ),
                    "question": question,
                    "gold_answers": list(gold_answers),
                    "prediction": turn.answer,
                    "mock_answer": mock_answer,
                    "generated_answer_grounding_tested": not mock_answer,
                    "execution_classification": (
                        selected_harness.execution_classification
                    ),
                    "orchestration_mode": orchestration_mode,
                    "answer_metric": asdict(metrics),
                    "evidence_metric": {
                        "gold_in_context": metrics.evidence_contains_answer,
                    },
                    "sources": sorted(candidate_sources),
                    "selected_evidence_ids": [
                        candidate_identity(candidate) for candidate in candidates
                    ],
                    "source_coverage": {
                        source: source in candidate_sources
                        for source in (
                            "recent_messages",
                            "structured_memory",
                            "previous_chat_gist",
                            "raw_message_span",
                            "document_memory",
                            "current_chat_span",
                            EVAL_RAW_REPLAY_SOURCE,
                        )
                    },
                    "context_packet_summary": evidence[:1000],
                    "context_char_size": len(evidence),
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
                    "ranked_candidates": [
                        candidate_summary(candidate)
                        for candidate in turn.trace.ranked_candidates
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
                    "evidence_diagnostics": diagnostics,
                    "raw_replay_diagnostics": {
                        **raw_diagnostics,
                        "previous_chat_gist_found_gold": gist_gold_found,
                        "eval_raw_replay_chunk_found_gold": raw_diagnostics[
                            "raw_replay_gold_literal_found"
                        ],
                    },
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


def candidate_identity(candidate: Any) -> str:
    """Return a compact stable identity without serializing evidence text."""
    record_id = candidate.record_id
    if record_id is None:
        record_id = candidate.metadata.get("candidate_id") or "unidentified"
    return f"{candidate.source}:{record_id}"


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
        "orchestration": turn.trace.metadata.get("orchestration"),
    }


def evidence_diagnostics(
    *,
    gold_answers: tuple[str, ...],
    replayed_chunks: list[dict[str, Any]],
    retrieved: list[Any],
    ranked: list[Any],
    context_candidates: list[Any],
    dropped_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Locate bounded gold evidence across replay and candidate pipeline stages."""
    normalized_gold = [normalize_text(answer) for answer in gold_answers]
    locations = []
    for replayed in replayed_chunks:
        normalized_content = normalize_text(str(replayed.get("content", "")))
        matched = [
            answer
            for answer, normalized in zip(gold_answers, normalized_gold, strict=True)
            if normalized and normalized in normalized_content
        ]
        if not matched:
            continue
        locations.append(
            {
                "session_id": replayed.get("session_id"),
                "chunk_index": replayed.get("chunk_index"),
                "user_message_id": replayed.get("user_message_id"),
                "matched_gold_answers": matched,
                "snippet": bounded_match_snippet(
                    str(replayed.get("content", "")),
                    matched[0],
                ),
            }
        )

    gold_message_ids = {
        int(location["user_message_id"])
        for location in locations
        if isinstance(location.get("user_message_id"), int)
    }
    retrieved_text_ids = candidate_ids_containing_gold(retrieved, normalized_gold)
    ranked_text_ids = candidate_ids_containing_gold(ranked, normalized_gold)
    context_text_ids = candidate_ids_containing_gold(
        context_candidates,
        normalized_gold,
    )
    raw_provenance_ids = [
        candidate_id(candidate)
        for candidate in retrieved
        if candidate.source == "raw_message_span"
        and gold_message_ids.intersection(candidate.source_message_ids)
    ]
    if not locations:
        failure_stage = "dataset_or_metric_gold_not_in_replay"
    elif context_text_ids:
        failure_stage = "none_literal_gold_reached_context"
    elif retrieved_text_ids and not context_text_ids:
        failure_stage = "context_budget_or_context_selection"
    elif raw_provenance_ids:
        failure_stage = "raw_span_formatting_or_char_truncation"
    else:
        failure_stage = "gist_retrieval_or_raw_window_selection"

    return {
        "normalized_gold_answers": normalized_gold,
        "gold_in_replay": bool(locations),
        "gold_replay_locations": locations[:20],
        "gold_replay_location_count": len(locations),
        "gold_message_ids": sorted(gold_message_ids),
        "retrieved_candidate_ids_with_gold_text": retrieved_text_ids,
        "ranked_candidate_ids_with_gold_text": ranked_text_ids,
        "context_candidate_ids_with_gold_text": context_text_ids,
        "raw_span_ids_covering_gold_message": raw_provenance_ids,
        "dropped_candidates": dropped_candidates[:20],
        "failure_stage": failure_stage,
    }


def candidate_ids_containing_gold(
    candidates: list[Any],
    normalized_gold: list[str],
) -> list[str]:
    """Return stable IDs for candidates containing a normalized gold string."""
    return [
        candidate_id(candidate)
        for candidate in candidates
        if any(
            gold and gold in normalize_text(candidate.content)
            for gold in normalized_gold
        )
    ]


def candidate_id(candidate: Any) -> str:
    """Return a report-safe candidate identity."""
    return f"{candidate.source}:{candidate.record_id}"


def bounded_match_snippet(content: str, answer: str, radius: int = 120) -> str:
    """Return a bounded original-text snippet around a literal gold match."""
    index = content.lower().find(answer.lower())
    if index < 0:
        return content[: radius * 2]
    start = max(0, index - radius)
    end = min(len(content), index + len(answer) + radius)
    return content[start:end]
