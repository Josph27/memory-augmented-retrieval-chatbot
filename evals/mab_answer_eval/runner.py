from __future__ import annotations

import hashlib
import json
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
from evals.mab_answer_eval.metrics import score_official
from evals.mab_answer_eval.schemas import (
    AnswerExecution,
    AnswerManifest,
    EvaluationModels,
    ResolvedCase,
)
from evals.memory_agent_bench.adapter import (
    ChatModel,
    ProductionLikeHarness,
    run_example,
)
from src.agents.context_manager_agent import ContextManagerAgent
from src.config import AppConfig
from src.context.dynamic_budget import MemoryBudgetPolicy
from src.model_wrapper import ModelWrapper
from src.orchestration.demo_orchestration import LANGGRAPH_DEMO, NATIVE


ANSWER_PARAMETERS = {"temperature": 0}
ANSWER_CACHE_VERSION = "mab-answer-v1"


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
    ) -> None:
        self.model = model
        self.config = config
        self.execution_mode = execution_mode

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
                chat_memory_cap=self.config.chat_memory_cap,
                document_memory_cap=self.config.document_memory_cap,
                multi_scope_memory_cap=self.config.multi_scope_memory_cap,
                long_document_memory_cap=self.config.long_document_memory_cap,
                required_evidence_headroom_ratio=(
                    self.config.required_evidence_headroom_ratio
                ),
            ),
            minimum_optional_candidate_utility=(
                self.config.minimum_optional_candidate_utility
            ),
        )
        harness = ProductionLikeHarness(
            model,
            mock_answer=mock_answer,
            deterministic_memory_updates=True,
            reranker_mode="deterministic",
            orchestration_mode=(
                LANGGRAPH_DEMO if self.execution_mode == "graph" else NATIVE
            ),
            context_manager_agent=context_manager,
        )
        rows = run_example(
            case.example,
            mock_answer=mock_answer,
            model=model,
            harness=harness,
            orchestration_mode=(
                LANGGRAPH_DEMO if self.execution_mode == "graph" else NATIVE
            ),
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
        return AnswerExecution(
            generated_answer=str(row["prediction"]),
            context_diagnostics={
                "gold_candidate_present": bool(
                    diagnostics.get("retrieved_candidate_ids_with_gold_text")
                ),
                "gold_context_present": bool(
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
            },
            selected_evidence_for_judge=str(row.get("context_packet_summary", "")),
            latency_ms={
                "total": float(timings.get("total_turn", 0.0) or 0.0),
                "generation": float(timings.get("main_model_call", 0.0) or 0.0),
            },
            raw_metadata={
                "prompt_source": workflow.get("prompt_source"),
                "tokenizer_mode": token_accounting.get("tokenizer_mode"),
            },
        )


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
        "manifest_name": manifest.name,
        "manifest_hash": manifest.manifest_hash,
        "cases": len(resolved),
        "execution_mode": options.execution_mode,
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
            official = score_official(
                spec.official_metric,
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
                "chat": config.chat_memory_cap,
                "document": config.document_memory_cap,
                "multi_scope": config.multi_scope_memory_cap,
                "long_document": config.long_document_memory_cap,
                "required_headroom": config.required_evidence_headroom_ratio,
                "minimum_utility": config.minimum_optional_candidate_utility,
            },
            "memory_limits": {
                "raw_message_limit": config.raw_message_limit,
                "memory_update_batch_size": config.memory_update_batch_size,
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
