from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from evals.mab_answer_eval.artifacts import read_jsonl
from evals.mab_answer_eval.judge import (
    JUDGE_PROMPT_VERSION,
    OpenAIJudgeClient,
    evaluate_with_judge,
    parse_judge_result,
)
from evals.mab_answer_eval.manifest import load_manifest, resolve_cases
from evals.mab_answer_eval.runner import (
    MABAnswerExecutor,
    RunOptions,
    judge_cache_key,
    run_evaluation,
)
from evals.mab_answer_eval.schemas import (
    AnswerExecution,
    EvaluationModels,
)
from src.config import AppConfig


VALID_JUDGE = json.dumps(
    {
        "correct": True,
        "complete": True,
        "faithful_to_selected_context": True,
        "appropriate_abstention": None,
        "unsupported_claims": [],
        "brief_reason": "Supported by the selected evidence.",
    }
)


class FakeJudge:
    def __init__(self, model_name: str = "judge-a", responses: list[str] | None = None):
        self.model_name = model_name
        self.responses = responses or [VALID_JUDGE]
        self.calls = 0

    def judge(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        return self.responses[min(self.calls - 1, len(self.responses) - 1)]


class FakeExecutor:
    def __init__(self, answers: dict[str, str] | None = None, fail_on: str | None = None):
        self.answers = answers or {}
        self.fail_on = fail_on
        self.calls: list[str] = []
        self.evidence_calls: list[str] = []

    def execute(self, case) -> AnswerExecution:  # type: ignore[no-untyped-def]
        case_id = case.spec.case_id
        self.calls.append(case_id)
        if case_id == self.fail_on:
            raise RuntimeError("injected generation failure")
        answer = self.answers.get(case_id, case.example.answers[0][0])
        return AnswerExecution(
            generated_answer=answer,
            context_diagnostics={
                "gold_candidate_present": True,
                "gold_context_present": True,
                "selected_source_types": ["raw_message_span"],
                "selected_evidence_ids": [f"raw_message_span:{case_id}"],
                "evidence_contract_satisfied": True,
                "selected_memory_tokens": 12,
                "final_prompt_tokens": 24,
            },
            selected_evidence_for_judge=f"evidence for {case_id}",
            latency_ms={"total": 10.0, "generation": 4.0},
        )

    def evidence_for_judge(self, case) -> str:  # type: ignore[no-untyped-def]
        self.evidence_calls.append(case.spec.case_id)
        return f"evidence for {case.spec.case_id}"


class CountingAnswerModel:
    model_name = "offline-test-model"

    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del temperature
        self.calls.append(messages)
        return "cobalt"


class FakeOpenAIClient:
    def __init__(self, *, response: str = VALID_JUDGE, error: Exception | None = None):
        self.response = response
        self.error = error
        self.kwargs: dict[str, Any] = {}
        self.chat = self
        self.completions = self

    def create(self, **kwargs):  # type: ignore[no-untyped-def]
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        message = type("Message", (), {"content": self.response})()
        choice = type("Choice", (), {"message": message})()
        return type("Completion", (), {"choices": [choice]})()


def manifest_value(cases: int = 2) -> dict[str, Any]:
    values = []
    for index in range(cases):
        values.append(
            {
                "dataset": f"dataset-{index}",
                "split": "split",
                "source_dataset": f"source-{index}",
                "row_index": index,
                "question_index": 0,
                "case_id": f"case-{index}",
                "question_type": "short_answer",
                "official_metric": "normalized_substring",
            }
        )
    return {
        "name": "offline-manifest",
        "version": 1,
        "seed": 7,
        "execution_mode": "graph",
        "dataset_id": "offline",
        "cases": values,
    }


def write_manifest(path: Path, value: dict[str, Any]) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def catalog(_: str, __: str):  # type: ignore[no-untyped-def]
    for index in range(3):
        yield {
            "context": f"The answer is answer-{index}.",
            "question": f"What is answer {index}?",
            "answer": f"answer-{index}",
            "metadata": {"source": f"source-{index}"},
        }


def config() -> AppConfig:
    return replace(
        AppConfig.from_env(),
        model_name="offline-test-model",
        raw_message_limit=8,
        memory_update_batch_size=2,
    )


def models(
    judge: str = "judge-a",
    endpoint: str = "https://judge-a.example",
) -> EvaluationModels:
    return EvaluationModels(
        "answer-a",
        judge,
        "judge-secondary",
        judge_endpoint=endpoint,
    )


def test_manifest_parsing_preserves_deterministic_order(tmp_path: Path) -> None:
    manifest = load_manifest(write_manifest(tmp_path / "manifest.yaml", manifest_value()))

    assert [case.case_id for case in manifest.cases] == ["case-0", "case-1"]
    assert len(manifest.manifest_hash) == 64


def test_manifest_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    value = manifest_value()
    value["cases"][1]["case_id"] = "case-0"

    with pytest.raises(ValueError, match="duplicate"):
        load_manifest(write_manifest(tmp_path / "manifest.yaml", value))


def test_case_resolution_rejects_unknown_case(tmp_path: Path) -> None:
    value = manifest_value(1)
    value["cases"][0]["row_index"] = 99
    manifest = load_manifest(write_manifest(tmp_path / "manifest.yaml", value))

    with pytest.raises(ValueError, match="unknown manifest rows"):
        resolve_cases(manifest, catalog_loader=catalog)


def test_dry_run_makes_no_calls_or_artifact_writes(tmp_path: Path) -> None:
    manifest = load_manifest(write_manifest(tmp_path / "manifest.yaml", manifest_value()))
    executor = FakeExecutor()
    judge = FakeJudge()
    output = tmp_path / "artifacts"

    report = run_evaluation(
        manifest,
        models=models(),
        config=config(),
        options=RunOptions(output, "graph", dry_run=True),
        executor=executor,
        judge_client=judge,
        catalog_loader=catalog,
    )

    assert report["estimated_generation_calls"] == 2
    assert executor.calls == []
    assert judge.calls == 0
    assert not output.exists()


def test_answer_and_judge_endpoint_configuration_are_independent(
    monkeypatch,
) -> None:
    captured: dict[str, str] = {}
    fake = FakeOpenAIClient()

    def build_client(*, api_key: str, base_url: str) -> FakeOpenAIClient:
        captured.update({"api_key": api_key, "base_url": base_url})
        return fake

    monkeypatch.setattr("evals.mab_answer_eval.judge.OpenAI", build_client)
    client = OpenAIJudgeClient(
        config(),
        "deepseek-v4-pro",
        base_url="https://api.deepseek.com",
        api_key="test-only-secret",
    )

    assert client.judge([{"role": "user", "content": "Return JSON."}])
    assert captured["base_url"] == "https://api.deepseek.com"
    assert captured["api_key"] == "test-only-secret"
    assert config().openai_base_url != captured["base_url"]
    assert fake.kwargs["response_format"] == {"type": "json_object"}
    assert fake.kwargs["temperature"] == 0


def test_judge_client_error_does_not_expose_credentials(monkeypatch) -> None:
    secret = "test-only-secret"
    fake = FakeOpenAIClient(error=RuntimeError(f"transport included {secret}"))
    monkeypatch.setattr(
        "evals.mab_answer_eval.judge.OpenAI",
        lambda **_: fake,
    )
    client = OpenAIJudgeClient(
        config(),
        "deepseek-v4-pro",
        base_url="https://api.deepseek.com",
        api_key=secret,
    )

    with pytest.raises(RuntimeError) as captured:
        client.judge([{"role": "user", "content": "Return JSON."}])

    assert secret not in str(captured.value)


def test_answer_execution_uses_existing_answer_agent_and_graph_path(
    tmp_path: Path,
) -> None:
    manifest = load_manifest(
        write_manifest(tmp_path / "manifest.yaml", manifest_value(1))
    )
    case = resolve_cases(manifest, catalog_loader=catalog)[0]
    answer_model = CountingAnswerModel()
    executor = MABAnswerExecutor(
        model=answer_model,
        config=config(),
        execution_mode="graph",
    )

    result = executor.execute(case)

    assert result.generated_answer == "cobalt"
    assert answer_model.calls
    assert result.raw_metadata["prompt_source"] == "context_packet"
    assert result.context_diagnostics["selected_memory_tokens"] <= 4096


def test_result_is_persisted_and_failure_keeps_prior_case(tmp_path: Path) -> None:
    manifest = load_manifest(write_manifest(tmp_path / "manifest.yaml", manifest_value()))
    output = tmp_path / "artifacts"
    executor = FakeExecutor(fail_on="case-1")

    run_evaluation(
        manifest,
        models=models(),
        config=config(),
        options=RunOptions(output, "graph"),
        executor=executor,
        judge_client=FakeJudge(),
        catalog_loader=catalog,
    )

    rows = read_jsonl(output / "results.jsonl")
    assert any(row["case_id"] == "case-0" and row["status"] == "completed" for row in rows)
    assert any(row["case_id"] == "case-1" and row["status"] == "failed" for row in rows)


def test_resume_reuses_completed_answer_and_judge(tmp_path: Path) -> None:
    manifest = load_manifest(write_manifest(tmp_path / "manifest.yaml", manifest_value()))
    output = tmp_path / "artifacts"
    first_executor = FakeExecutor()
    first_judge = FakeJudge()
    run_evaluation(
        manifest,
        models=models(),
        config=config(),
        options=RunOptions(output, "graph"),
        executor=first_executor,
        judge_client=first_judge,
        catalog_loader=catalog,
    )
    row_count = len(read_jsonl(output / "results.jsonl"))
    resumed_executor = FakeExecutor()
    resumed_judge = FakeJudge()

    report = run_evaluation(
        manifest,
        models=models(),
        config=config(),
        options=RunOptions(output, "graph", resume=True),
        executor=resumed_executor,
        judge_client=resumed_judge,
        catalog_loader=catalog,
    )

    assert resumed_executor.calls == []
    assert resumed_judge.calls == 0
    assert report["skipped_completed"] == 2
    assert len(read_jsonl(output / "results.jsonl")) == row_count


def test_resume_continues_from_failed_case(tmp_path: Path) -> None:
    manifest = load_manifest(write_manifest(tmp_path / "manifest.yaml", manifest_value()))
    output = tmp_path / "artifacts"
    run_evaluation(
        manifest,
        models=models(),
        config=config(),
        options=RunOptions(output, "graph"),
        executor=FakeExecutor(fail_on="case-1"),
        judge_client=FakeJudge(),
        catalog_loader=catalog,
    )
    resumed = FakeExecutor()

    run_evaluation(
        manifest,
        models=models(),
        config=config(),
        options=RunOptions(output, "graph", resume=True),
        executor=resumed,
        judge_client=FakeJudge(),
        catalog_loader=catalog,
    )

    assert resumed.calls == ["case-1"]


def test_changing_judge_model_invalidates_only_judge_cache(tmp_path: Path) -> None:
    manifest = load_manifest(
        write_manifest(tmp_path / "manifest.yaml", manifest_value(1))
    )
    output = tmp_path / "artifacts"
    run_evaluation(
        manifest,
        models=models("judge-a"),
        config=config(),
        options=RunOptions(output, "graph"),
        executor=FakeExecutor(),
        judge_client=FakeJudge("judge-a"),
        catalog_loader=catalog,
    )
    resumed = FakeExecutor()
    judge_b = FakeJudge("judge-b")

    report = run_evaluation(
        manifest,
        models=models("judge-b"),
        config=config(),
        options=RunOptions(output, "graph", resume=True),
        executor=resumed,
        judge_client=judge_b,
        catalog_loader=catalog,
    )

    assert resumed.calls == []
    assert resumed.evidence_calls == []
    assert judge_b.calls == 1
    assert report["generation_calls_this_invocation"] == 0
    assert read_jsonl(output / "results.jsonl")[-1]["judge_model"] == "judge-b"


def test_changing_judge_endpoint_invalidates_only_judge_cache(
    tmp_path: Path,
) -> None:
    manifest = load_manifest(
        write_manifest(tmp_path / "manifest.yaml", manifest_value(1))
    )
    output = tmp_path / "artifacts"
    run_evaluation(
        manifest,
        models=models(endpoint="https://judge-a.example"),
        config=config(),
        options=RunOptions(output, "graph"),
        executor=FakeExecutor(),
        judge_client=FakeJudge(),
        catalog_loader=catalog,
    )
    before = read_jsonl(output / "results.jsonl")[-1]["official_metric"]
    resumed = FakeExecutor()

    report = run_evaluation(
        manifest,
        models=models(endpoint="https://judge-b.example"),
        config=config(),
        options=RunOptions(output, "graph", resume=True),
        executor=resumed,
        judge_client=FakeJudge(),
        catalog_loader=catalog,
    )

    after = read_jsonl(output / "results.jsonl")[-1]
    assert resumed.calls == []
    assert report["generation_calls_this_invocation"] == 0
    assert report["judge_calls_this_invocation"] == 1
    assert after["judge_endpoint"] == "https://judge-b.example"
    assert after["official_metric"] == before
    comparison = json.loads((output / "judge_comparison.json").read_text())
    assert comparison["cases"][0]["previous_correct"] is True
    assert comparison["cases"][0]["current_correct"] is True


def test_changed_answer_invalidates_judge_cache_key(tmp_path: Path) -> None:
    manifest = load_manifest(
        write_manifest(tmp_path / "manifest.yaml", manifest_value(1))
    )
    case = resolve_cases(manifest, catalog_loader=catalog)[0]

    first = judge_cache_key(
        case,
        generated_answer="answer one",
        judge_model="judge",
        judge_endpoint="https://judge.example",
    )
    second = judge_cache_key(
        case,
        generated_answer="answer two",
        judge_model="judge",
        judge_endpoint="https://judge.example",
    )

    assert first != second


def test_malformed_judge_output_is_rejected() -> None:
    with pytest.raises(ValueError, match="valid JSON"):
        parse_judge_result("not-json")


def test_empty_judge_output_receives_at_most_one_retry() -> None:
    judge = FakeJudge(responses=["", VALID_JUDGE])

    result = evaluate_with_judge(
        judge,
        question="Question?",
        references=("answer",),
        generated_answer="answer",
    )

    assert result.result is not None
    assert result.attempts == 2
    assert judge.calls == 2


def test_judge_allows_one_bounded_repair_attempt() -> None:
    judge = FakeJudge(responses=["bad", VALID_JUDGE])

    result = evaluate_with_judge(
        judge,
        question="Question?",
        references=("answer",),
        generated_answer="answer",
    )

    assert result.result is not None
    assert result.attempts == 2
    assert judge.calls == 2


def test_second_malformed_judge_response_is_not_a_pass() -> None:
    judge = FakeJudge(responses=["bad", "still bad"])

    result = evaluate_with_judge(
        judge,
        question="Question?",
        references=("answer",),
        generated_answer="answer",
    )

    assert result.result is None
    assert result.attempts == 2
    assert result.error


def test_malformed_judge_is_persisted_as_invalid_not_passing(
    tmp_path: Path,
) -> None:
    manifest = load_manifest(
        write_manifest(tmp_path / "manifest.yaml", manifest_value(1))
    )
    output = tmp_path / "artifacts"

    run_evaluation(
        manifest,
        models=models(),
        config=config(),
        options=RunOptions(output, "graph"),
        executor=FakeExecutor(),
        judge_client=FakeJudge(responses=["bad", "still bad"]),
        catalog_loader=catalog,
    )

    failed = read_jsonl(output / "results.jsonl")[-1]
    assert failed["status"] == "failed"
    assert failed["failed_stage"] == "judge"
    assert failed["official_metric"]["passed"] is True
    assert failed["judge"]["correct"] is False
    assert failed["judge"]["raw_parse_status"] == "invalid"


def test_official_metric_and_judge_are_persisted_separately(tmp_path: Path) -> None:
    manifest = load_manifest(
        write_manifest(tmp_path / "manifest.yaml", manifest_value(1))
    )
    output = tmp_path / "artifacts"

    run_evaluation(
        manifest,
        models=models(),
        config=config(),
        options=RunOptions(output, "graph"),
        executor=FakeExecutor({"case-0": "wrong"}),
        judge_client=FakeJudge(),
        catalog_loader=catalog,
    )

    completed = read_jsonl(output / "results.jsonl")[-1]
    assert completed["official_metric"]["passed"] is False
    assert completed["judge"]["correct"] is True
    assert completed["judge_prompt_version"] == JUDGE_PROMPT_VERSION


def test_compact_summary_and_disagreement_artifacts(tmp_path: Path) -> None:
    manifest = load_manifest(
        write_manifest(tmp_path / "manifest.yaml", manifest_value(1))
    )
    output = tmp_path / "artifacts"

    run_evaluation(
        manifest,
        models=models(),
        config=config(),
        options=RunOptions(output, "graph"),
        executor=FakeExecutor({"case-0": "wrong"}),
        judge_client=FakeJudge(),
        catalog_loader=catalog,
    )

    summary = json.loads((output / "summary.json").read_text())
    disagreements = read_jsonl(output / "disagreements.jsonl")
    assert summary["completed"] == 1
    assert summary["official_pass_rate"] == 0
    assert len(disagreements) == 1
    assert "question" not in disagreements[0]


def test_artifacts_do_not_store_secrets_prompts_or_evidence_by_default(
    tmp_path: Path,
) -> None:
    manifest = load_manifest(
        write_manifest(tmp_path / "manifest.yaml", manifest_value(1))
    )
    output = tmp_path / "artifacts"
    secret_config = replace(config(), openai_api_key="super-secret-token")

    run_evaluation(
        manifest,
        models=models(),
        config=secret_config,
        options=RunOptions(output, "graph"),
        executor=FakeExecutor(),
        judge_client=FakeJudge(),
        catalog_loader=catalog,
    )

    serialized = "\n".join(
        path.read_text(encoding="utf-8") for path in output.iterdir()
    )
    assert "super-secret-token" not in serialized
    assert "You are a deterministic answer evaluator" not in serialized
    assert "evidence for case-0" not in serialized


def test_context_pipeline_contract_fields_are_preserved(tmp_path: Path) -> None:
    manifest = load_manifest(
        write_manifest(tmp_path / "manifest.yaml", manifest_value(1))
    )
    output = tmp_path / "artifacts"

    run_evaluation(
        manifest,
        models=models(),
        config=config(),
        options=RunOptions(output, "graph"),
        executor=FakeExecutor(),
        judge_client=FakeJudge(),
        catalog_loader=catalog,
    )

    row = read_jsonl(output / "results.jsonl")[-1]
    diagnostics = row["context_diagnostics"]
    assert diagnostics["evidence_contract_satisfied"] is True
    assert diagnostics["selected_source_types"] == ["raw_message_span"]
    assert diagnostics["selected_memory_tokens"] == 12
    assert row["execution_mode"] == "graph"
