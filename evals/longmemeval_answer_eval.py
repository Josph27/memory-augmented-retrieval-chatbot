from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

from src.actions.chat_end import ChatEndAction
from evals.longmemeval_adapter.loader import load_longmemeval_cases
from evals.longmemeval_adapter.runner import (
    PriorRecentMessagesRetriever,
    build_reranker,
    route_for_mode,
)
from evals.longmemeval_adapter.schema import LongMemEvalCase
from evals.longmemeval_adapter.scoring import score_case
from evals.longmemeval_adapter.span_retriever import (
    LongMemEvalMessageSpanRetriever,
    split_session_messages,
)
from evals.mab_answer_eval.artifacts import (
    RESULTS_FILE,
    append_jsonl,
    latest_results,
    read_jsonl,
    write_compact_artifacts,
    write_judge_comparison,
)
from evals.mab_answer_eval.judge import (
    JUDGE_PROMPT_VERSION,
    JudgeClient,
    OpenAIJudgeClient,
    evaluate_with_judge,
    judge_parameters,
)
from evals.mab_answer_eval.runner import (
    ANSWER_PARAMETERS,
    artifact_paths,
    stable_hash,
)
from evals.mab_answer_eval.schemas import EvaluationModels, JudgeResult, OfficialMetricResult
from openai import OpenAI, OpenAIError
from src.agents.chat_agent import ChatAgent
from src.agents.context_builder_agent import ContextBuilderAgent
from src.agents.context_manager_agent import ContextManagerAgent
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.short_term_memory_agent import ShortTermMemoryAgent
from src.config import AppConfig
from src.context.dynamic_budget import MemoryBudgetPolicy
from src.database import Database
from src.memory.short_term import ShortTermMemory
from src.memory.structured_state import MemoryUpdateResult
from src.model_wrapper import ModelWrapper
from src.orchestration.demo_orchestration import LANGGRAPH_DEMO, NATIVE
from src.retrieval.current_chat_span_retriever import CurrentChatSpanRetriever
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.retrieval.structured_memory_retriever import StructuredMemoryRetriever
from src.routing.routing_agent import RoutingAgent


SYSTEM_PROMPT = (
    "Answer the question using only the supplied conversation memory. "
    "If the memory does not support an answer, say I don't know."
)
OFFICIAL_METRIC_NAME = "longmemeval_adapter_pilot"
EVALUATION_VERSION = "lifecycle_v2"
ANSWER_CACHE_VERSION = f"longmemeval-answer-{EVALUATION_VERSION}"


@dataclass(frozen=True)
class LongMemManifestCase:
    case_id: str
    question_type: str


@dataclass(frozen=True)
class LongMemManifest:
    name: str
    version: int
    seed: int
    execution_mode: str
    dataset_path: Path
    cases: tuple[LongMemManifestCase, ...]
    manifest_hash: str


@dataclass(frozen=True)
class ResolvedLongMemCase:
    spec: LongMemManifestCase
    case: LongMemEvalCase


@dataclass(frozen=True)
class AnswerExecution:
    generated_answer: str
    context_diagnostics: dict[str, Any]
    selected_evidence_for_judge: str
    latency_ms: dict[str, float]
    official_metric: OfficialMetricResult
    raw_metadata: dict[str, Any]


@dataclass(frozen=True)
class RunOptions:
    output_dir: Path
    execution_mode: str
    resume: bool = False
    max_cases: int | None = None
    fail_fast: bool = False
    dry_run: bool = False


class NoopMemoryUpdater:
    def update(self, existing_memory, messages):  # type: ignore[no-untyped-def]
        del messages
        return MemoryUpdateResult(
            memory_state=existing_memory,
            accepted=False,
            rejection_reason="longmemeval_answer_eval_noop",
        )


class EvaluationAnswerModel:
    def __init__(self, model: ModelWrapper) -> None:
        self._model = model
        self.model_name = model.model_name

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del temperature
        return self._model.chat(messages, temperature=ANSWER_PARAMETERS["temperature"])


class FixedRoutePlanner:
    def __init__(self, case: LongMemEvalCase) -> None:
        self._route_plan = route_for_mode(case, "full")

    def plan(self, query: str):  # type: ignore[no-untyped-def]
        del query
        return self._route_plan


class LongMemEvalAnswerExecutor:
    def __init__(
        self,
        *,
        model: EvaluationAnswerModel,
        config: AppConfig,
        execution_mode: str,
        routing_mode: str | None = None,
    ) -> None:
        self.model = model
        self.config = config
        self.execution_mode = execution_mode
        self.routing_mode = routing_mode or config.routing_mode

    def execute(self, resolved_case: ResolvedLongMemCase) -> AnswerExecution:
        case = resolved_case.case
        with TemporaryDirectory(prefix="longmemeval_answer_eval_") as temp_dir:
            database = Database(Path(temp_dir) / "case.db")
            short_term = ShortTermMemory(
                database=database,
                model=self.model,
                raw_message_limit=self.config.raw_message_limit,
                memory_update_batch_size=self.config.memory_update_batch_size,
                recent_messages_max_count=self.config.recent_messages_max_count,
                memory_update_trigger_tokens=self.config.memory_update_trigger_tokens,
                memory_update_max_input_tokens=self.config.memory_update_max_input_tokens,
                memory_update_max_messages=self.config.memory_update_max_messages,
                memory_recent_protection_tokens=self.config.memory_recent_protection_tokens,
                memory_replay_trigger_tokens=self.config.memory_replay_trigger_tokens,
                memory_replay_max_input_tokens=self.config.memory_replay_max_input_tokens,
                memory_replay_max_messages=self.config.memory_replay_max_messages,
            )
            spans = replay_history_sessions_production_like(
                database=database,
                memory=short_term,
                case=case,
            )
            question_chat_id = f"{case.case_id}-question"
            database.create_chat(question_chat_id, title="LongMemEval question")
            context_manager = ContextManagerAgent.for_model(
                self.model.model_name,
                endpoint_context_window=self.config.endpoint_context_window,
                application_context_cap=self.config.application_context_cap,
                endpoint_limit_source=self.config.endpoint_context_limit_source,
                memory_budget_policy=MemoryBudgetPolicy(
                    base_memory_budget=self.config.base_memory_budget,
                    memory_recall_budget_tokens=(
                        self.config.memory_recall_budget_tokens
                    ),
                    chat_memory_cap=self.config.chat_memory_cap,
                    document_memory_cap=self.config.document_memory_cap,
                    multi_scope_memory_cap=self.config.multi_scope_memory_cap,
                    long_document_memory_cap=self.config.long_document_memory_cap,
                    global_summary_budget_tokens=(
                        self.config.global_summary_budget_tokens
                    ),
                    global_summary_max_budget_tokens=(
                        self.config.global_summary_max_budget_tokens
                    ),
                    global_summary_reserved_tokens=(
                        self.config.global_summary_reserved_tokens
                    ),
                    required_evidence_headroom_ratio=(
                        self.config.required_evidence_headroom_ratio
                    ),
                ),
                minimum_optional_candidate_utility=(
                    self.config.minimum_optional_candidate_utility
                ),
                raw_span_overlap_threshold=self.config.raw_span_overlap_threshold,
            )
            coordinator = CoordinatorAgent(
                database=database,
                memory_agent=ShortTermMemoryAgent(short_term),
                context_builder=ContextBuilderAgent(short_term),
                chat_agent=ChatAgent(self.model),
                system_prompt=SYSTEM_PROMPT,
                routing_agent=RoutingAgent(
                    route_planner=FixedRoutePlanner(case),  # type: ignore[arg-type]
                    mode=self.routing_mode,
                ),
                retriever_dispatcher=RetrieverDispatcher(
                    database=database,
                    retrievers={
                        "recent_messages": PriorRecentMessagesRetriever(
                            database,
                            default_limit=self.config.recent_messages_max_count,
                        ),
                        "structured_memory": StructuredMemoryRetriever(database),
                        "previous_chat_gist": PreviousChatGistRetriever(database),
                        "raw_message_span": LongMemEvalMessageSpanRetriever(spans),
                        "current_chat_span": CurrentChatSpanRetriever(database),
                    },
                ),
                memory_reranker=build_reranker("deterministic", model=None),
                context_manager_agent=context_manager,
            )
            started = time.perf_counter()
            turn = coordinator.run_turn(
                question_chat_id,
                case.question,
                orchestration_mode=(
                    LANGGRAPH_DEMO if self.execution_mode == "graph" else NATIVE
                ),
                task_context="memory_qa",
            )
            total_latency = (time.perf_counter() - started) * 1000
            trace = turn.trace
            workflow = trace.metadata
            packet = trace.context_packet
            context_manager_metadata = workflow.get("context_manager") or {}
            token_accounting = (
                (context_manager_metadata.get("token_accounting") or {})
                if isinstance(context_manager_metadata, dict)
                else {}
            )
            evidence_selection = (
                (context_manager_metadata.get("evidence_selection") or {})
                if isinstance(context_manager_metadata, dict)
                else {}
            )
            gold_session_ids = {
                str(value) for value in (case.metadata.get("answer_session_ids") or [])
            }
            retrieved = list(trace.retrieved_candidates)
            ranked = list(trace.ranked_candidates)
            selected = list(packet.candidates if packet is not None else [])
            retrieved_session_ids = [
                str(candidate.metadata.get("session_id"))
                for candidate in retrieved
                if candidate.metadata.get("session_id") is not None
            ]
            official_score = score_case(
                case,
                answer=turn.answer,
                retrieved_contents=[candidate.content for candidate in retrieved],
                retrieved_session_ids=retrieved_session_ids,
            )
            route_plan = trace.route_plan
            enabled_sources = [
                source.source for source in (route_plan.sources if route_plan else []) if source.enabled
            ]
            required_scopes = list(
                ((route_plan.metadata if route_plan else {}) or {}).get(
                    "required_scopes",
                    [],
                )
            )
            return AnswerExecution(
                generated_answer=turn.answer,
                context_diagnostics={
                    "gold_candidate_present": has_gold_session(retrieved, gold_session_ids),
                    "gold_context_present": has_gold_session(selected, gold_session_ids),
                    "selected_source_types": sorted({candidate.source for candidate in selected}),
                    "selected_evidence_ids": [
                        f"{candidate.source}:{candidate.record_id}" for candidate in selected
                    ],
                    "evidence_contract_satisfied": bool(
                        evidence_selection.get("evidence_contract_satisfied", True)
                    ),
                    "selected_memory_tokens": int(
                        evidence_selection.get("token_usage", 0) or 0
                    ),
                        "final_prompt_tokens": int(
                            token_accounting.get("final_prompt_tokens", 0) or 0
                        ),
                    "enabled_sources": enabled_sources,
                    "routing_mode_used": (
                        (route_plan.metadata if route_plan else {}) or {}
                    ).get("routing_mode")
                    or self.routing_mode,
                    "required_scopes": required_scopes,
                    "gold_candidate_rank": gold_session_rank(ranked, gold_session_ids),
                    "gold_context_drop_reason": first_session_drop_reason(
                        gold_session_ids,
                        evidence_selection.get("dropped_candidates", []),
                    ),
                    "working_memory_budget": int(
                        context_manager_metadata.get("working_memory_budget", 0) or 0
                    ),
                    "hard_input_budget": int(
                        context_manager_metadata.get("hard_input_budget", 0) or 0
                    ),
                    "prompt_source": workflow.get("prompt_source"),
                    "fallback_reason": workflow.get("fallback_reason"),
                    "route_intent": route_plan.intent if route_plan else None,
                    "route_context_profile": (
                        route_plan.context_profile if route_plan else None
                    ),
                    "expected_answer_session_ids": sorted(gold_session_ids),
                },
                selected_evidence_for_judge="\n".join(
                    candidate.content for candidate in selected
                )[:4000],
                latency_ms={
                    "total": round(total_latency, 3),
                    "generation": float(
                        (workflow.get("timings_ms") or {}).get("main_model_call", 0.0)
                        or 0.0
                    ),
                },
                official_metric=OfficialMetricResult(
                    OFFICIAL_METRIC_NAME,
                    float(bool(official_score.passed)),
                    bool(official_score.passed),
                ),
                raw_metadata={
                    "evaluation_version": EVALUATION_VERSION,
                    "memory_ingestion_semantics": "production",
                    "memory_scheduling_profile": "offline_replay",
                    "token_batching_enabled": True,
                    "direct_derived_memory_injection": False,
                    "timestamp_preservation_status": timestamp_preservation_status(case),
                    "prompt_source": workflow.get("prompt_source"),
                    "fallback_reason": workflow.get("fallback_reason"),
                    "tokenizer_mode": token_accounting.get("tokenizer_mode"),
                    "orchestration": workflow.get("orchestration"),
                    "routing_mode_used": (
                        (route_plan.metadata if route_plan else {}) or {}
                    ).get("routing_mode")
                    or self.routing_mode,
                },
            )


def has_gold_session(candidates: list[Any], gold_session_ids: set[str]) -> bool:
    if not gold_session_ids:
        return False
    return any(str(candidate.metadata.get("session_id")) in gold_session_ids for candidate in candidates)


def gold_session_rank(candidates: list[Any], gold_session_ids: set[str]) -> int | None:
    if not gold_session_ids:
        return None
    for index, candidate in enumerate(candidates, start=1):
        if str(candidate.metadata.get("session_id")) in gold_session_ids:
            return index
    return None


def replay_history_sessions_production_like(
    *,
    database: Database,
    memory: ShortTermMemory,
    case: LongMemEvalCase,
) -> list[Any]:
    spans: list[Any] = []
    for index, session in enumerate(case.sessions):
        chat_id = f"{case.case_id}-history-{index + 1}"
        replay_timestamp = replay_chat_timestamp(session)
        database.create_chat(
            chat_id,
            title=f"Benchmark history {session.session_id}",
            created_at=replay_timestamp,
        )
        for message in session.messages:
            database.save_message(
                chat_id,
                message.role,
                message.content,
                created_at=message.created_at or replay_timestamp,
            )
        memory.process_replay_batches(chat_id)
        ChatEndAction(database, memory).execute(chat_id)
        spans.extend(
            seed_message_spans_for_existing_chat(
                database=database,
                case=case,
                session_index=index,
            )
        )
    return spans


def seed_message_spans_for_existing_chat(
    *,
    database: Database,
    case: LongMemEvalCase,
    session_index: int,
) -> list[Any]:
    session = case.sessions[session_index]
    chat_id = f"{case.case_id}-history-{session_index + 1}"
    stored_messages = database.messages_for_chat(chat_id)
    return split_session_messages(
        case_id=case.case_id,
        session_id=session.session_id,
        chat_id=chat_id,
        messages=stored_messages,
    )


def replay_chat_timestamp(session: Any) -> str | None:
    value = session.metadata.get("date") if hasattr(session, "metadata") else None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def timestamp_preservation_status(case: LongMemEvalCase) -> str:
    has_message_timestamp = any(
        message.created_at
        for session in case.sessions
        for message in session.messages
    )
    has_session_timestamp = any(
        str(session.metadata.get("date") or "").strip()
        for session in case.sessions
    )
    if has_message_timestamp:
        return "message_timestamp_preserved_when_present"
    if has_session_timestamp:
        return "session_timestamp_preserved_when_message_timestamp_absent"
    return "no_benchmark_timestamp_available"


def first_session_drop_reason(
    gold_session_ids: set[str],
    dropped_candidates: list[dict[str, Any]],
) -> str | None:
    if not gold_session_ids:
        return None
    for candidate in dropped_candidates:
        if str(candidate.get("session_id")) in gold_session_ids:
            reason = str(candidate.get("reason") or "").strip()
            return reason or "unknown"
    return None


def load_manifest(path: Path) -> LongMemManifest:
    raw_text = path.read_text(encoding="utf-8")
    try:
        value = json.loads(raw_text)
    except json.JSONDecodeError:
        import yaml

        value = yaml.safe_load(raw_text)
    if not isinstance(value, dict):
        raise ValueError("longmemeval answer manifest must be an object")
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    cases_value = value.get("cases")
    if not isinstance(cases_value, list) or not cases_value:
        raise ValueError("longmemeval answer manifest requires non-empty cases")
    cases = tuple(
        LongMemManifestCase(
            case_id=str(item.get("case_id") or "").strip(),
            question_type=str(item.get("question_type") or "").strip(),
        )
        for item in cases_value
    )
    if any(not case.case_id or not case.question_type for case in cases):
        raise ValueError("longmemeval manifest cases require case_id and question_type")
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("longmemeval manifest contains duplicate case IDs")
    mode = str(value.get("execution_mode", "")).strip().lower()
    if mode not in {"native", "graph"}:
        raise ValueError("manifest execution_mode must be native or graph")
    dataset_path = Path(str(value.get("dataset_path") or "")).expanduser()
    if not dataset_path.is_absolute():
        dataset_path = (path.parent / dataset_path).resolve()
    return LongMemManifest(
        name=str(value.get("name") or "").strip(),
        version=int(value.get("version", 1)),
        seed=int(value.get("seed", 0)),
        execution_mode=mode,
        dataset_path=dataset_path,
        cases=cases,
        manifest_hash=hashlib.sha256(canonical.encode()).hexdigest(),
    )


def resolve_cases(manifest: LongMemManifest) -> list[ResolvedLongMemCase]:
    by_id = {
        case.case_id: case for case in load_longmemeval_cases(manifest.dataset_path)
    }
    resolved: list[ResolvedLongMemCase] = []
    missing: list[str] = []
    for spec in manifest.cases:
        case = by_id.get(spec.case_id)
        if case is None:
            missing.append(spec.case_id)
            continue
        if case.question_type != spec.question_type:
            raise ValueError(
                f"case {spec.case_id} expected question_type {spec.question_type!r}, "
                f"found {case.question_type!r}"
            )
        resolved.append(ResolvedLongMemCase(spec=spec, case=case))
    if missing:
        raise ValueError(f"unknown LongMemEval case IDs: {', '.join(missing)}")
    return resolved


class JudgeStageError(RuntimeError):
    pass


def run_evaluation(
    manifest: LongMemManifest,
    *,
    models: EvaluationModels,
    config: AppConfig,
    options: RunOptions,
    executor: LongMemEvalAnswerExecutor | None = None,
    judge_client: JudgeClient | None = None,
) -> dict[str, Any]:
    if options.execution_mode != manifest.execution_mode:
        raise ValueError("CLI execution mode must match the frozen manifest")
    resolved = resolve_cases(manifest)
    if options.max_cases is not None:
        resolved = resolved[: max(0, options.max_cases)]
    dry_plan = {
        "evaluation_level": "answer",
        "evaluation_version": EVALUATION_VERSION,
        "manifest_name": manifest.name,
        "manifest_hash": manifest.manifest_hash,
        "cases": len(resolved),
        "execution_mode": options.execution_mode,
        "production_lifecycle_equivalent": True,
        "structured_memory_enabled": True,
        "production_gist_finalization": True,
        "direct_derived_memory_injection": False,
        "answer_model": models.answer_model,
        "judge_model": models.judge_model,
        "judge_endpoint": models.judge_endpoint,
        "secondary_judge_model": models.secondary_judge_model,
        "estimated_generation_calls": len(resolved),
        "estimated_judge_calls": len(resolved),
        "output_paths": artifact_paths(options.output_dir),
        "dry_run": options.dry_run,
        "dataset_path": str(manifest.dataset_path),
        "routing_mode_used": config.routing_mode,
    }
    if options.dry_run:
        return dry_plan
    if executor is None or judge_client is None:
        raise ValueError("non-dry evaluation requires executor and judge client")

    results_path = options.output_dir / RESULTS_FILE
    prior_rows = read_jsonl(results_path) if options.resume else []
    run_id = str(uuid4())
    generation_calls = 0
    judge_calls = 0
    skipped_completed = 0
    application_hash = stable_hash(
        {
            "model_name": config.model_name,
            "application_context_cap": config.application_context_cap,
            "base_memory_budget": config.base_memory_budget,
            "chat_memory_cap": config.chat_memory_cap,
            "document_memory_cap": config.document_memory_cap,
            "multi_scope_memory_cap": config.multi_scope_memory_cap,
            "long_document_memory_cap": config.long_document_memory_cap,
            "required_evidence_headroom_ratio": (
                config.required_evidence_headroom_ratio
            ),
            "minimum_optional_candidate_utility": (
                config.minimum_optional_candidate_utility
            ),
            "routing_mode": config.routing_mode,
            "routing_path": "fixture-assisted-route-planner",
        }
    )
    for resolved_case in resolved:
        answer_key = stable_hash(
            {
                "manifest_hash": manifest.manifest_hash,
                "case_id": resolved_case.spec.case_id,
                "execution_mode": options.execution_mode,
                "answer_model": models.answer_model,
                "generation_parameters": ANSWER_PARAMETERS,
                "application_configuration_hash": application_hash,
                "evaluation_version": EVALUATION_VERSION,
            }
        )
        identity = stable_hash(
            {
                "manifest_hash": manifest.manifest_hash,
                "case_id": resolved_case.spec.case_id,
                "evaluation_version": EVALUATION_VERSION,
                "execution_mode": options.execution_mode,
                "answer_model": models.answer_model,
            }
        )
        cached_answer = (
            find_answer(prior_rows, answer_key=answer_key) if options.resume else None
        )
        if cached_answer is not None:
            judge_key = stable_hash(
                {
                    "question": resolved_case.case.question,
                    "reference": resolved_case.case.gold_answer,
                    "question_type": resolved_case.case.question_type,
                    "generated_answer": str(cached_answer["generated_answer"]),
                    "evaluation_version": EVALUATION_VERSION,
                    "judge_endpoint": models.judge_endpoint,
                    "judge_model": models.judge_model,
                    "judge_parameters": judge_parameters(),
                }
            )
            completed = find_completed_judge(
                prior_rows,
                answer_key=answer_key,
                judge_key=judge_key,
            )
            if completed is not None:
                skipped_completed += 1
                continue

        answer_record: dict[str, Any] | None = None
        try:
            if cached_answer is None:
                generation_calls += 1
                execution = executor.execute(resolved_case)
                answer_record = base_record(
                    run_id,
                    manifest,
                    resolved_case,
                    models,
                    options,
                    identity,
                    answer_key,
                )
                answer_record.update(
                    {
                        "generated_answer": execution.generated_answer,
                        "context_diagnostics": execution.context_diagnostics,
                        "selected_evidence_hash": stable_hash(
                            execution.selected_evidence_for_judge
                        ),
                        "latency_ms": {
                            **execution.latency_ms,
                            "judge": 0.0,
                        },
                        "status": "answer_completed",
                        "error": None,
                        "answer_metadata": execution.raw_metadata,
                        "official_metric": execution.official_metric.to_dict(),
                    }
                )
                append_jsonl(results_path, answer_record)
                prior_rows.append(answer_record)
            else:
                answer_record = dict(cached_answer)

            generated_answer = str(answer_record["generated_answer"])
            judge_key = stable_hash(
                {
                    "question": resolved_case.case.question,
                    "reference": resolved_case.case.gold_answer,
                    "question_type": resolved_case.case.question_type,
                    "generated_answer": generated_answer,
                    "evaluation_version": EVALUATION_VERSION,
                    "judge_endpoint": models.judge_endpoint,
                    "judge_model": models.judge_model,
                    "judge_parameters": judge_parameters(),
                }
            )
            judge_started = time.perf_counter()
            judge_calls += 1
            try:
                judged = evaluate_with_judge(
                    judge_client,
                    question=resolved_case.case.question,
                    references=(resolved_case.case.gold_answer,),
                    generated_answer=generated_answer,
                )
            except Exception as error:
                raise JudgeStageError(
                    f"{type(error).__name__}: {error}"
                ) from error
            judge_latency = (time.perf_counter() - judge_started) * 1000
            if judged.result is None:
                raise JudgeStageError(judged.error or "judge parse failed")
            completed_record = dict(answer_record)
            generation_total = float(answer_record["latency_ms"].get("total", 0.0))
            completed_record.update(
                {
                    "run_id": run_id,
                    "judge_model": models.judge_model,
                    "judge_endpoint": models.judge_endpoint,
                    "secondary_judge_model": models.secondary_judge_model,
                    "judge": judged.result.to_dict(),
                    "judge_attempts": judged.attempts,
                    "judge_prompt_version": JUDGE_PROMPT_VERSION,
                    "judge_cache_key": judge_key,
                    "latency_ms": {
                        **answer_record["latency_ms"],
                        "judge": round(judge_latency, 3),
                        "total": round(generation_total + judge_latency, 3),
                    },
                    "status": "completed",
                    "error": None,
                }
            )
            append_jsonl(results_path, completed_record)
            prior_rows.append(completed_record)
        except Exception as error:
            failed_stage = "judge" if isinstance(error, JudgeStageError) else "generation"
            failed = base_record(
                run_id,
                manifest,
                resolved_case,
                models,
                options,
                identity,
                answer_key,
            )
            if answer_record is not None:
                failed.update(answer_record)
            if failed_stage == "judge":
                failed["judge"] = JudgeResult(
                    correct=False,
                    complete=False,
                    brief_reason="Judge stage failed.",
                    raw_parse_status="invalid",
                ).to_dict()
            failed.update(
                {
                    "judge_model": models.judge_model,
                    "judge_endpoint": models.judge_endpoint,
                    "secondary_judge_model": models.secondary_judge_model,
                    "status": "failed",
                    "failed_stage": failed_stage,
                    "error": f"{type(error).__name__}: {error}"[:1000],
                }
            )
            append_jsonl(results_path, failed)
            prior_rows.append(failed)
            if options.fail_fast:
                raise

    latest = latest_results(prior_rows)
    metadata = {
        **dry_plan,
        "dry_run": False,
        "run_id": run_id,
        "generation_calls_this_invocation": generation_calls,
        "judge_calls_this_invocation": judge_calls,
        "skipped_completed": skipped_completed,
        "answer_parameters": ANSWER_PARAMETERS,
        "judge_parameters": judge_parameters(),
    }
    write_compact_artifacts(
        options.output_dir,
        results=latest,
        run_metadata=metadata,
    )
    write_judge_comparison(
        options.output_dir,
        rows=prior_rows,
        active_judge_model=models.judge_model,
        active_judge_endpoint=models.judge_endpoint,
    )
    return metadata


def run_judge_only(
    manifest: LongMemManifest,
    *,
    source_results_path: Path,
    models: EvaluationModels,
    options: RunOptions,
    judge_client: JudgeClient | None = None,
) -> dict[str, Any]:
    """Judge frozen answers without loading datasets or executing the answer path."""
    if options.execution_mode != manifest.execution_mode:
        raise ValueError("CLI execution mode must match the frozen manifest")
    source_rows = validate_frozen_answer_rows(
        manifest,
        read_jsonl(source_results_path),
        execution_mode=options.execution_mode,
        answer_model=models.answer_model,
    )
    if options.max_cases is not None:
        source_rows = source_rows[: max(0, options.max_cases)]
    source_hash = hashlib.sha256(source_results_path.read_bytes()).hexdigest()
    dry_plan = {
        "evaluation_level": "judge",
        "evaluation_version": EVALUATION_VERSION,
        "manifest_name": manifest.name,
        "manifest_hash": manifest.manifest_hash,
        "cases": len(source_rows),
        "execution_mode": options.execution_mode,
        "answer_model": models.answer_model,
        "judge_model": models.judge_model,
        "judge_endpoint": models.judge_endpoint,
        "secondary_judge_model": models.secondary_judge_model,
        "estimated_generation_calls": 0,
        "estimated_judge_calls": len(source_rows),
        "source_answer_results": str(source_results_path),
        "source_answer_results_sha256": source_hash,
        "output_paths": artifact_paths(options.output_dir),
        "dry_run": options.dry_run,
    }
    if options.dry_run:
        return dry_plan
    if judge_client is None:
        raise ValueError("judge-only evaluation requires a judge client")

    results_path = options.output_dir / RESULTS_FILE
    prior_rows = read_jsonl(results_path) if options.resume else []
    run_id = str(uuid4())
    judge_calls = 0
    skipped_completed = 0
    for source_row in source_rows:
        answer_key = str(source_row["answer_cache_key"])
        judge_key = frozen_answer_judge_key(source_row, models)
        completed = find_completed_judge(
            prior_rows,
            answer_key=answer_key,
            judge_key=judge_key,
        )
        if completed is not None:
            skipped_completed += 1
            continue

        try:
            judge_started = time.perf_counter()
            judge_calls += 1
            judged = evaluate_with_judge(
                judge_client,
                question=str(source_row["question"]),
                references=tuple(str(value) for value in source_row["reference_answer"]),
                generated_answer=str(source_row["generated_answer"]),
            )
            judge_latency = (time.perf_counter() - judge_started) * 1000
            if judged.result is None:
                raise JudgeStageError(judged.error or "judge parse failed")
            generation_total = float(source_row["latency_ms"].get("total", 0.0))
            completed_record = {
                **source_row,
                "source_answer_run_id": source_row.get("run_id"),
                "run_id": run_id,
                "judge_model": models.judge_model,
                "judge_endpoint": models.judge_endpoint,
                "secondary_judge_model": models.secondary_judge_model,
                "judge": judged.result.to_dict(),
                "judge_attempts": judged.attempts,
                "judge_prompt_version": JUDGE_PROMPT_VERSION,
                "judge_cache_key": judge_key,
                "latency_ms": {
                    **source_row["latency_ms"],
                    "judge": round(judge_latency, 3),
                    "total": round(generation_total + judge_latency, 3),
                },
                "status": "completed",
                "error": None,
            }
            append_jsonl(results_path, completed_record)
            prior_rows.append(completed_record)
        except Exception as error:
            failed = {
                **source_row,
                "source_answer_run_id": source_row.get("run_id"),
                "run_id": run_id,
                "judge_model": models.judge_model,
                "judge_endpoint": models.judge_endpoint,
                "secondary_judge_model": models.secondary_judge_model,
                "judge": JudgeResult(
                    correct=False,
                    complete=False,
                    brief_reason="Judge stage failed.",
                    raw_parse_status="invalid",
                ).to_dict(),
                "status": "failed",
                "failed_stage": "judge",
                "error": f"{type(error).__name__}: {error}"[:1000],
            }
            append_jsonl(results_path, failed)
            prior_rows.append(failed)
            if options.fail_fast:
                raise

    latest = latest_results(prior_rows)
    metadata = {
        **dry_plan,
        "dry_run": False,
        "run_id": run_id,
        "generation_calls_this_invocation": 0,
        "judge_calls_this_invocation": judge_calls,
        "skipped_completed": skipped_completed,
        "answer_parameters": ANSWER_PARAMETERS,
        "judge_parameters": judge_parameters(),
    }
    write_compact_artifacts(
        options.output_dir,
        results=latest,
        run_metadata=metadata,
    )
    write_judge_comparison(
        options.output_dir,
        rows=prior_rows,
        active_judge_model=models.judge_model,
        active_judge_endpoint=models.judge_endpoint,
    )
    return metadata


def validate_frozen_answer_rows(
    manifest: LongMemManifest,
    rows: list[dict[str, Any]],
    *,
    execution_mode: str,
    answer_model: str,
) -> list[dict[str, Any]]:
    """Return frozen answer rows in manifest order or reject the source file."""
    expected = {case.case_id: case for case in manifest.cases}
    by_case: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = str(row.get("case_id") or "")
        if case_id not in expected:
            raise ValueError(f"non-frozen LongMemEval answer row: {case_id or '<missing>'}")
        if case_id in by_case:
            raise ValueError(f"duplicate LongMemEval answer row: {case_id}")
        if row.get("status") != "answer_completed":
            raise ValueError(
                f"LongMemEval answer row {case_id} is not frozen answer_completed"
            )
        if row.get("manifest_name") != manifest.name:
            raise ValueError(f"manifest name mismatch for LongMemEval row {case_id}")
        if row.get("manifest_hash") != manifest.manifest_hash:
            raise ValueError(f"manifest hash mismatch for LongMemEval row {case_id}")
        if row.get("evaluation_version") != EVALUATION_VERSION:
            raise ValueError(f"evaluation version mismatch for LongMemEval row {case_id}")
        if row.get("execution_mode") != execution_mode:
            raise ValueError(f"execution mode mismatch for LongMemEval row {case_id}")
        if row.get("answer_model") != answer_model:
            raise ValueError(f"answer model mismatch for LongMemEval row {case_id}")
        if row.get("question_type") != expected[case_id].question_type:
            raise ValueError(f"question type mismatch for LongMemEval row {case_id}")
        require_frozen_answer_fields(row, case_id=case_id)
        by_case[case_id] = row
    missing = [case.case_id for case in manifest.cases if case.case_id not in by_case]
    if missing:
        raise ValueError(f"missing LongMemEval answer rows: {', '.join(missing)}")
    return [by_case[case.case_id] for case in manifest.cases]


def require_frozen_answer_fields(row: dict[str, Any], *, case_id: str) -> None:
    required_strings = (
        "answer_cache_key",
        "generated_answer",
        "selected_evidence_hash",
        "question",
        "result_identity",
    )
    for field in required_strings:
        if not isinstance(row.get(field), str) or not row[field]:
            raise ValueError(f"LongMemEval answer row {case_id} lacks {field}")
    if not isinstance(row.get("reference_answer"), list) or not row["reference_answer"]:
        raise ValueError(f"LongMemEval answer row {case_id} lacks reference_answer")
    for field in ("context_diagnostics", "official_metric", "latency_ms"):
        if not isinstance(row.get(field), dict):
            raise ValueError(f"LongMemEval answer row {case_id} lacks {field}")


def frozen_answer_judge_key(
    row: dict[str, Any],
    models: EvaluationModels,
) -> str:
    return stable_hash(
        {
            "question": row["question"],
            "reference": row["reference_answer"],
            "question_type": row["question_type"],
            "generated_answer": row["generated_answer"],
            "selected_evidence_hash": row["selected_evidence_hash"],
            "evaluation_version": row["evaluation_version"],
            "judge_endpoint": models.judge_endpoint,
            "judge_model": models.judge_model,
            "judge_parameters": judge_parameters(),
        }
    )


def base_record(
    run_id: str,
    manifest: LongMemManifest,
    resolved_case: ResolvedLongMemCase,
    models: EvaluationModels,
    options: RunOptions,
    identity: str,
    answer_key: str,
) -> dict[str, Any]:
    return {
        "evaluation_level": "answer",
        "evaluation_version": EVALUATION_VERSION,
        "run_id": run_id,
        "manifest_name": manifest.name,
        "manifest_hash": manifest.manifest_hash,
        "case_id": resolved_case.spec.case_id,
        "dataset": "longmemeval",
        "execution_mode": options.execution_mode,
        "question_type": resolved_case.spec.question_type,
        "answer_model": models.answer_model,
        "judge_model": models.judge_model,
        "judge_endpoint": models.judge_endpoint,
        "secondary_judge_model": models.secondary_judge_model,
        "question": resolved_case.case.question,
        "reference_answer": [resolved_case.case.gold_answer],
        "answer_cache_key": answer_key,
        "result_identity": identity,
        "generation_parameters": ANSWER_PARAMETERS,
    }


def find_answer(rows: list[dict[str, Any]], *, answer_key: str) -> dict[str, Any] | None:
    for row in reversed(rows):
        if (
            row.get("answer_cache_key") == answer_key
            and row.get("generated_answer") is not None
            and row.get("status") in {"answer_completed", "completed", "failed"}
        ):
            return row
    return None


def find_completed_judge(
    rows: list[dict[str, Any]],
    *,
    answer_key: str,
    judge_key: str,
) -> dict[str, Any] | None:
    for row in reversed(rows):
        if (
            row.get("answer_cache_key") == answer_key
            and row.get("judge_cache_key") == judge_key
            and row.get("status") == "completed"
        ):
            return row
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run held-out LongMemEval answer-level evaluation."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--execution-mode", choices=("native", "graph"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--answer-model")
    parser.add_argument("--judge-model")
    parser.add_argument("--judge-base-url")
    parser.add_argument(
        "--judge-only-answers",
        type=Path,
        help="Judge frozen answer_completed rows without loading or replaying the dataset.",
    )
    parser.add_argument("--secondary-judge-model")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-models", action="store_true")
    args = parser.parse_args()

    config = AppConfig.from_env()
    if args.list_models:
        client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
        )
        try:
            model_ids = sorted(model.id for model in client.models.list().data)
        except OpenAIError as error:
            print(
                json.dumps(
                    {
                        "models": None,
                        "endpoint_model_listing_available": False,
                        "error": f"{type(error).__name__}: {error}"[:500],
                    },
                    indent=2,
                )
            )
            return
        print(
            json.dumps(
                {
                    "models": model_ids,
                    "endpoint_model_listing_available": True,
                    "error": None,
                },
                indent=2,
            )
        )
        return

    manifest = load_manifest(args.manifest)
    execution_mode = args.execution_mode or manifest.execution_mode
    answer_model = args.answer_model or config.model_name
    judge_model = args.judge_model or os.getenv("JUDGE_MODEL")
    if not judge_model:
        parser.error("configure --judge-model or JUDGE_MODEL explicitly")
    judge_base_url = (
        args.judge_base_url
        or os.getenv("JUDGE_BASE_URL")
        or config.openai_base_url
    ).rstrip("/")
    judge_api_key = os.getenv("JUDGE_API_KEY")
    if not args.dry_run and not judge_api_key:
        parser.error("JUDGE_API_KEY is required for a real judge run")
    models = EvaluationModels(
        answer_model,
        judge_model,
        args.secondary_judge_model or os.getenv("SECONDARY_JUDGE_MODEL"),
        judge_endpoint=judge_base_url,
    )
    options = RunOptions(
        output_dir=args.output_dir,
        execution_mode=execution_mode,
        resume=args.resume,
        max_cases=args.max_cases,
        fail_fast=args.fail_fast,
        dry_run=args.dry_run,
    )
    executor = None
    judge_client = None
    if not args.dry_run and args.judge_only_answers is None:
        answer_wrapper = EvaluationAnswerModel(
            ModelWrapper(config, model_name=answer_model)
        )
        executor = LongMemEvalAnswerExecutor(
            model=answer_wrapper,
            config=config,
            execution_mode=execution_mode,
            routing_mode=config.routing_mode,
        )
    if not args.dry_run:
        judge_client = OpenAIJudgeClient(
            config,
            judge_model,
            base_url=judge_base_url,
            api_key=judge_api_key,
        )
    if args.judge_only_answers is not None:
        report = run_judge_only(
            manifest,
            source_results_path=args.judge_only_answers.resolve(),
            models=models,
            options=options,
            judge_client=judge_client,
        )
    else:
        report = run_evaluation(
            manifest,
            models=models,
            config=config,
            options=options,
            executor=executor,
            judge_client=judge_client,
        )
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
