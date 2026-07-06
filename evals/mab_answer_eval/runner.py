from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

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
    evaluate_with_judge,
    judge_parameters,
)
from evals.mab_answer_eval.manifest import CatalogLoader, resolve_cases
from evals.mab_answer_eval.metrics import score_official_for_case
from evals.mab_answer_eval.schemas import (
    AnswerExecution,
    AnswerManifest,
    EvaluationModels,
    ResolvedCase,
)
from evals.memory_agent_bench.adapter import (
    ChatModel,
    ProductionLikeHarness,
    ROLELESS_HISTORY_INPUT_MODALITY,
    ROLELESS_HISTORY_STRUCTURED_MEMORY_POLICY,
    run_example,
)
from evals.memory_agent_bench.metrics import normalize_text
from src.agents.context_manager_agent import ContextManagerAgent
from src.config import AppConfig
from src.context.dynamic_budget import MemoryBudgetPolicy
from src.model_wrapper import ModelWrapper
from src.orchestration.demo_orchestration import LANGGRAPH_DEMO, NATIVE


ANSWER_PARAMETERS = {"temperature": 0}
EVALUATION_VERSION = "lifecycle_v2"
ANSWER_CACHE_VERSION = f"mab-answer-{EVALUATION_VERSION}"


class CaseExecutor(Protocol):
    def execute(self, case: ResolvedCase) -> AnswerExecution:
        """Generate one answer through the existing application pipeline."""
        ...

    def evidence_for_judge(self, case: ResolvedCase) -> str:
        """Rebuild selected evidence without making an answer-model call."""
        ...


class EvaluationAnswerModel:
    """Apply deterministic generation parameters through the existing model wrapper."""

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


class MABAnswerExecutor:
    """Reuse MAB ingestion and Coordinator/ChatAgent answer generation."""

    def __init__(
        self,
        *,
        model: ChatModel,
        config: AppConfig,
        execution_mode: str,
        history_question_counts: dict[tuple[str, str, int], int] | None = None,
    ) -> None:
        self.model = model
        self.config = config
        self.execution_mode = execution_mode
        self.history_question_counts = history_question_counts or {}
        self._prepared_root = tempfile.TemporaryDirectory(prefix="mab_answer_prepared_")
        self._prepared_histories: dict[tuple[str, str, int], PreparedHistorySnapshot] = {}

    def execute(self, case: ResolvedCase) -> AnswerExecution:
        return self._execute(case, model=self.model, mock_answer=False)

    def evidence_for_judge(self, case: ResolvedCase) -> str:
        from evals.memory_agent_bench.adapter import MockAnswerModel

        return self._execute(
            case,
            model=MockAnswerModel(),
            mock_answer=True,
        ).selected_evidence_for_judge

    def _execute(
        self,
        case: ResolvedCase,
        *,
        model: ChatModel,
        mock_answer: bool,
    ) -> AnswerExecution:
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
        prepared = self._prepared_snapshot(case, model=model, mock_answer=mock_answer)
        case_dir = Path(tempfile.mkdtemp(prefix="mab_answer_case_", dir=self._prepared_root.name))
        case_db_path = case_dir / "case.db"
        shutil.copy2(prepared.snapshot_path, case_db_path)
        harness = ProductionLikeHarness(
            model,
            mock_answer=False,
            reranker_mode="deterministic",
            orchestration_mode=(
                LANGGRAPH_DEMO if self.execution_mode == "graph" else NATIVE
            ),
            context_manager_agent=context_manager,
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
            direct_raw_retrieval_candidates=(
                self.config.direct_raw_retrieval_candidates
            ),
            database_path=case_db_path,
        )
        harness.replayed_chunks = [dict(chunk) for chunk in prepared.replayed_chunks]
        rows = run_example(
            case.example,
            mock_answer=mock_answer,
            model=model,
            harness=harness,
            finalize_sessions=False,
            orchestration_mode=(
                LANGGRAPH_DEMO if self.execution_mode == "graph" else NATIVE
            ),
            skip_replay=True,
        )
        if len(rows) != 1:
            raise RuntimeError(f"expected one answer row, received {len(rows)}")
        row = rows[0]
        workflow = row["workflow_trace"]
        context_manager_metadata = workflow.get("context_manager") or {}
        evidence_selection = context_manager_metadata.get("evidence_selection") or {}
        token_accounting = context_manager_metadata.get("token_accounting") or {}
        diagnostics = row["evidence_diagnostics"]
        timings = workflow.get("timings_ms") or {}
        route_plan = row.get("route_plan") or {}
        required_scopes = list(
            ((route_plan.get("metadata") or {}).get("required_scopes") or [])
        )
        evidence_selection = context_manager_metadata.get("evidence_selection") or {}
        ranked_gold_rank = gold_rank(
            row.get("ranked_candidates", []),
            diagnostics.get("normalized_gold_answers", []),
        )
        return AnswerExecution(
            generated_answer=str(row["prediction"]),
            context_diagnostics={
                "gold_candidate_present": bool(
                    diagnostics.get("retrieved_evidence_complete")
                ),
                "gold_context_present": bool(
                    diagnostics.get("context_evidence_complete")
                ),
                "gold_candidate_literal_present": bool(
                    diagnostics.get("retrieved_candidate_ids_with_gold_text")
                ),
                "gold_context_literal_present": bool(
                    diagnostics.get("context_candidate_ids_with_gold_text")
                ),
                "selected_source_types": list(row.get("sources", [])),
                "selected_evidence_ids": list(row.get("selected_evidence_ids", [])),
                "evidence_contract_satisfied": bool(
                    evidence_selection.get("evidence_contract_satisfied", True)
                ),
                "selected_memory_tokens": int(
                    evidence_selection.get("token_usage", 0) or 0
                ),
                "final_prompt_tokens": int(
                    token_accounting.get("final_prompt_tokens", 0) or 0
                ),
                "enabled_sources": list(route_plan.get("active_sources", [])),
                "required_scopes": required_scopes,
                "gold_candidate_rank": ranked_gold_rank,
                "gold_context_drop_reason": first_gold_drop_reason(
                    diagnostics.get("retrieved_candidate_ids_with_gold_text", []),
                    evidence_selection.get("dropped_candidates")
                    or row.get("workflow_trace", {})
                    .get("context_manager", {})
                    .get("evidence_selection", {})
                    .get("dropped_candidates", []),
                ),
                "working_memory_budget": int(
                    context_manager_metadata.get("working_memory_budget", 0) or 0
                ),
                "hard_input_budget": int(
                    context_manager_metadata.get("hard_input_budget", 0) or 0
                ),
                "prompt_source": workflow.get("prompt_source"),
                "fallback_reason": workflow.get("fallback_reason"),
                "route_intent": route_plan.get("intent"),
                "route_context_profile": route_plan.get("context_profile"),
                "mab_failure_stage": diagnostics.get("failure_stage"),
                "dropped_candidates": list(diagnostics.get("dropped_candidates", [])),
            },
            selected_evidence_for_judge=str(row.get("context_packet_summary", "")),
            latency_ms={
                "total": float(timings.get("total_turn", 0.0) or 0.0),
                "generation": float(timings.get("main_model_call", 0.0) or 0.0),
            },
            raw_metadata={
                "evaluation_version": EVALUATION_VERSION,
                "memory_ingestion_semantics": (
                    "production_persistence_finalization_with_modality_aware_memory_formation"
                ),
                "memory_scheduling_profile": "offline_replay",
                "token_batching_enabled": True,
                "direct_derived_memory_injection": False,
                "history_input_modality": prepared.history_input_modality,
                "structured_memory_policy": prepared.structured_memory_policy,
                "production_gist_generated": prepared.gist_count > 0,
                "history_reused_for_multiple_questions": prepared.shared_question_count > 1,
                "prepared_state_reused": prepared.shared_question_count > 1,
                "prepared_history_key": list(prepared.history_key),
                "prepared_history_ingestion_count": 1,
                "prepared_history_question_count": prepared.shared_question_count,
                "prepared_history_reuse_count": max(0, prepared.shared_question_count - 1),
                "structured_updater_call_count": prepared.structured_updater_call_count,
                "timestamp_preservation_status": (
                    "not_available_for_roleless_context_replay"
                ),
                "prompt_source": workflow.get("prompt_source"),
                "tokenizer_mode": token_accounting.get("tokenizer_mode"),
            },
        )

    def _prepared_snapshot(
        self,
        case: ResolvedCase,
        *,
        model: ChatModel,
        mock_answer: bool,
    ) -> "PreparedHistorySnapshot":
        history_key = (
            case.spec.split,
            case.spec.source_dataset,
            case.spec.row_index,
        )
        existing = self._prepared_histories.get(history_key)
        if existing is not None:
            return existing

        prepare_dir = Path(self._prepared_root.name) / f"prepare-{stable_hash(history_key)[:12]}"
        prepare_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = prepare_dir / "prepared.db"
        harness = ProductionLikeHarness(
            model,
            mock_answer=mock_answer,
            reranker_mode="deterministic",
            orchestration_mode=(
                LANGGRAPH_DEMO if self.execution_mode == "graph" else NATIVE
            ),
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
            database_path=prepare_dir / "working.db",
        )
        harness.prepare_history(case.example)
        harness.copy_database_to(snapshot_path)
        snapshot = PreparedHistorySnapshot(
            history_key=history_key,
            snapshot_path=snapshot_path,
            replayed_chunks=[dict(chunk) for chunk in harness.replayed_chunks],
            history_ingestion_count=1,
            structured_updater_call_count=harness.memory_update_calls,
            history_input_modality=harness.history_input_modality,
            structured_memory_policy=harness.structured_memory_policy,
            gist_count=harness.prepared_history_gist_count,
            shared_question_count=self.history_question_counts.get(history_key, 1),
        )
        harness.close()
        self._prepared_histories[history_key] = snapshot
        return snapshot


@dataclass(frozen=True)
class PreparedHistorySnapshot:
    history_key: tuple[str, str, int]
    snapshot_path: Path
    replayed_chunks: list[dict[str, Any]]
    history_ingestion_count: int
    structured_updater_call_count: int
    history_input_modality: str
    structured_memory_policy: str
    gist_count: int
    shared_question_count: int


@dataclass(frozen=True)
class RunOptions:
    output_dir: Path
    execution_mode: str
    resume: bool = False
    max_cases: int | None = None
    fail_fast: bool = False
    dry_run: bool = False
    store_evidence_text: bool = False


def run_evaluation(
    manifest: AnswerManifest,
    *,
    models: EvaluationModels,
    config: AppConfig,
    options: RunOptions,
    executor: CaseExecutor | None = None,
    judge_client: JudgeClient | None = None,
    catalog_loader: CatalogLoader | None = None,
) -> dict[str, Any]:
    if options.execution_mode != manifest.execution_mode:
        raise ValueError("CLI execution mode must match the frozen manifest")
    resolved = resolve_cases(manifest, catalog_loader=catalog_loader)
    if options.max_cases is not None:
        resolved = resolved[: max(0, options.max_cases)]
    application_hash = application_configuration_hash(config)
    dry_plan = {
        "evaluation_level": "answer",
        "evaluation_version": EVALUATION_VERSION,
        "manifest_name": manifest.name,
        "manifest_hash": manifest.manifest_hash,
        "cases": len(resolved),
        "execution_mode": options.execution_mode,
        "memory_ingestion_semantics": (
            "production_persistence_finalization_with_modality_aware_memory_formation"
        ),
        "history_input_modality": ROLELESS_HISTORY_INPUT_MODALITY,
        "structured_memory_policy": ROLELESS_HISTORY_STRUCTURED_MEMORY_POLICY,
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
    }
    if options.dry_run:
        return dry_plan
    if executor is None or judge_client is None:
        raise ValueError("non-dry evaluation requires answer executor and judge client")

    results_path = options.output_dir / RESULTS_FILE
    prior_rows = read_jsonl(results_path) if options.resume else []
    run_id = str(uuid4())
    generation_calls = 0
    judge_calls = 0
    skipped_completed = 0
    for resolved_case in resolved:
        answer_record: dict[str, Any] | None = None
        spec = resolved_case.spec
        answer_key = answer_cache_key(
            manifest,
            resolved_case,
            execution_mode=options.execution_mode,
            answer_model=models.answer_model,
            application_hash=application_hash,
        )
        identity = result_identity(
            manifest,
            spec.case_id,
            options.execution_mode,
            models.answer_model,
        )
        cached_answer = find_answer(prior_rows, answer_key) if options.resume else None
        expected_judge_key = None
        if cached_answer is not None:
            expected_judge_key = judge_cache_key(
                resolved_case,
                generated_answer=str(cached_answer["generated_answer"]),
                judge_model=models.judge_model,
                judge_endpoint=models.judge_endpoint,
            )
            completed = find_completed_judge(
                prior_rows,
                answer_key=answer_key,
                judge_key=expected_judge_key,
            )
            if completed is not None:
                if (
                    completed.get("judge_model") != models.judge_model
                    or completed.get("judge_endpoint") != models.judge_endpoint
                ):
                    corrected = {
                        **completed,
                        "run_id": run_id,
                        "judge_model": models.judge_model,
                        "judge_endpoint": models.judge_endpoint,
                        "secondary_judge_model": models.secondary_judge_model,
                    }
                    append_jsonl(results_path, corrected)
                    prior_rows.append(corrected)
                skipped_completed += 1
                continue

        try:
            if cached_answer is None:
                generation_calls += 1
                execution = executor.execute(resolved_case)
                selected_evidence_hash = stable_hash(
                    execution.selected_evidence_for_judge
                )
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
                        "selected_evidence_hash": selected_evidence_hash,
                        "latency_ms": {
                            **execution.latency_ms,
                            "judge": 0.0,
                        },
                        "status": "answer_completed",
                        "error": None,
                        "answer_metadata": execution.raw_metadata,
                    }
                )
                if options.store_evidence_text:
                    answer_record["selected_evidence_text"] = (
                        execution.selected_evidence_for_judge
                    )
                append_jsonl(results_path, answer_record)
                prior_rows.append(answer_record)
            else:
                answer_record = dict(cached_answer)

            generated_answer = str(answer_record["generated_answer"])
            references = resolved_case.example.answers[0]
            official, normalization = score_official_for_case(
                spec,
                generated_answer,
                references,
            )
            current_judge_key = judge_cache_key(
                resolved_case,
                generated_answer=generated_answer,
                judge_model=models.judge_model,
                judge_endpoint=models.judge_endpoint,
            )
            judge_started = time.perf_counter()
            judge_calls += 1
            try:
                judged = evaluate_with_judge(
                    judge_client,
                    question=resolved_case.example.questions[0],
                    references=references,
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
                    "official_metric": official.to_dict(),
                    "normalized_answer": normalization.get("normalized_answer"),
                    "output_normalization": normalization,
                    "judge": judged.result.to_dict(),
                    "judge_attempts": judged.attempts,
                    "judge_prompt_version": JUDGE_PROMPT_VERSION,
                    "judge_cache_key": current_judge_key,
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
            failed_record = base_record(
                run_id,
                manifest,
                resolved_case,
                models,
                options,
                identity,
                answer_key,
            )
            if (
                answer_record is not None
                and answer_record.get("answer_cache_key") == answer_key
            ):
                failed_record.update(answer_record)
                failed_record["run_id"] = run_id
            if failed_stage == "judge":
                failed_record["official_metric"] = official.to_dict()
                failed_record["normalized_answer"] = normalization.get(
                    "normalized_answer"
                )
                failed_record["output_normalization"] = normalization
                failed_record["judge"] = {
                    "correct": False,
                    "complete": False,
                    "brief_reason": "Judge stage failed.",
                    "raw_parse_status": "invalid",
                }
                failed_record.pop("judge_cache_key", None)
            failed_record.update(
                {
                    "judge_model": models.judge_model,
                    "judge_endpoint": models.judge_endpoint,
                    "secondary_judge_model": models.secondary_judge_model,
                    "status": "failed",
                    "failed_stage": failed_stage,
                    "error": f"{type(error).__name__}: {error}"[:1000],
                }
            )
            append_jsonl(results_path, failed_record)
            prior_rows.append(failed_record)
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
        "application_configuration_hash": application_hash,
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


class JudgeStageError(RuntimeError):
    pass


def base_record(
    run_id: str,
    manifest: AnswerManifest,
    case: ResolvedCase,
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
        "case_id": case.spec.case_id,
        "dataset": case.spec.dataset,
        "execution_mode": options.execution_mode,
        "question_type": case.spec.question_type,
        "answer_model": models.answer_model,
        "judge_model": models.judge_model,
        "judge_endpoint": models.judge_endpoint,
        "secondary_judge_model": models.secondary_judge_model,
        "question": case.example.questions[0],
        "reference_answer": list(case.example.answers[0]),
        "answer_cache_key": answer_key,
        "result_identity": identity,
        "generation_parameters": ANSWER_PARAMETERS,
    }


def answer_cache_key(
    manifest: AnswerManifest,
    case: ResolvedCase,
    *,
    execution_mode: str,
    answer_model: str,
    application_hash: str,
) -> str:
    return stable_hash(
        {
            "version": ANSWER_CACHE_VERSION,
            "manifest_hash": manifest.manifest_hash,
            "case_id": case.spec.case_id,
            "execution_mode": execution_mode,
            "answer_model": answer_model,
            "generation_parameters": ANSWER_PARAMETERS,
            "application_configuration_hash": application_hash,
        }
    )


def judge_cache_key(
    case: ResolvedCase,
    *,
    generated_answer: str,
    judge_model: str,
    judge_endpoint: str | None,
) -> str:
    return stable_hash(
        {
            "question": case.example.questions[0],
            "references": case.example.answers[0],
            "rubric": case.spec.question_type,
            "generated_answer": generated_answer,
            "evaluation_version": EVALUATION_VERSION,
            "judge_endpoint": judge_endpoint,
            "judge_model": judge_model,
            "judge_parameters": judge_parameters(),
        }
    )


def result_identity(
    manifest: AnswerManifest,
    case_id: str,
    execution_mode: str,
    answer_model: str,
) -> str:
    return stable_hash(
        {
            "manifest_hash": manifest.manifest_hash,
            "case_id": case_id,
            "evaluation_version": EVALUATION_VERSION,
            "execution_mode": execution_mode,
            "answer_model": answer_model,
        }
    )


def find_answer(
    rows: list[dict[str, Any]],
    answer_key: str,
) -> dict[str, Any] | None:
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


def stable_hash(value: Any) -> str:
    serialized = (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


def application_configuration_hash(config: AppConfig) -> str:
    return stable_hash(
        {
            "model_context": {
                "endpoint": config.endpoint_context_window,
                "application_cap": config.application_context_cap,
            },
            "memory_budgets": {
                "base": config.base_memory_budget,
                "memory_recall": config.memory_recall_budget_tokens,
                "chat": config.chat_memory_cap,
                "document": config.document_memory_cap,
                "multi_scope": config.multi_scope_memory_cap,
                "long_document": config.long_document_memory_cap,
                "global_summary": config.global_summary_budget_tokens,
                "global_summary_max": config.global_summary_max_budget_tokens,
                "global_summary_reserve": config.global_summary_reserved_tokens,
                "required_headroom": config.required_evidence_headroom_ratio,
                "minimum_utility": config.minimum_optional_candidate_utility,
            },
            "memory_limits": {
                "raw_message_limit": config.raw_message_limit,
                "memory_update_batch_size": config.memory_update_batch_size,
                "recent_messages_max_count": config.recent_messages_max_count,
                "memory_update_trigger_tokens": config.memory_update_trigger_tokens,
                "memory_update_max_input_tokens": config.memory_update_max_input_tokens,
                "memory_update_max_messages": config.memory_update_max_messages,
                "memory_recent_protection_tokens": config.memory_recent_protection_tokens,
                "memory_replay_trigger_tokens": config.memory_replay_trigger_tokens,
                "memory_replay_max_input_tokens": config.memory_replay_max_input_tokens,
                "memory_replay_max_messages": config.memory_replay_max_messages,
            },
            "retrieval": {
                "gist_candidates": config.gist_retrieval_candidates,
                "direct_raw_candidates": config.direct_raw_retrieval_candidates,
                "raw_span_overlap_threshold": config.raw_span_overlap_threshold,
                "query_simplification": (
                    config.enable_retrieval_query_simplification
                ),
            },
            "routing_mode": "fixture-assisted-rule",
            "reranker_mode": "deterministic",
            "raw_replay": False,
        }
    )


def artifact_paths(output_dir: Path) -> dict[str, str]:
    return {
        name: str(output_dir / name)
        for name in (
            "results.jsonl",
            "summary.json",
            "failures.jsonl",
            "disagreements.jsonl",
            "judge_comparison.json",
            "run_metadata.json",
        )
    }


def gold_rank(
    candidates: list[dict[str, Any]],
    normalized_gold_answers: list[str],
) -> int | None:
    for index, candidate in enumerate(candidates, start=1):
        content = normalize_text(str(candidate.get("content", "")))
        if any(gold and gold in content for gold in normalized_gold_answers):
            return index
    return None


def first_gold_drop_reason(
    retrieved_gold_ids: list[str],
    dropped_candidates: list[dict[str, Any]],
) -> str | None:
    if not retrieved_gold_ids:
        return None
    gold_records = {
        candidate_id.split(":", 1)[1]
        for candidate_id in retrieved_gold_ids
        if ":" in candidate_id
    }
    for candidate in dropped_candidates:
        record_id = str(candidate.get("record_id") or "")
        if record_id and record_id in gold_records:
            reason = str(candidate.get("reason") or "").strip()
            return reason or "unknown"
    return None
