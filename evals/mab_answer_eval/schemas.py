from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evals.memory_agent_bench.schemas import MABenchExample


@dataclass(frozen=True)
class ManifestCase:
    dataset: str
    split: str
    source_dataset: str
    row_index: int
    question_index: int
    case_id: str
    question_type: str
    official_metric: str


@dataclass(frozen=True)
class AnswerManifest:
    name: str
    version: int
    seed: int
    execution_mode: str
    dataset_id: str
    cases: tuple[ManifestCase, ...]
    manifest_hash: str


@dataclass(frozen=True)
class ResolvedCase:
    spec: ManifestCase
    example: MABenchExample


@dataclass(frozen=True)
class OfficialMetricResult:
    name: str
    score: float
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "score": self.score, "passed": self.passed}


@dataclass(frozen=True)
class JudgeResult:
    correct: bool
    complete: bool
    brief_reason: str
    faithful_to_selected_context: bool | None = None
    appropriate_abstention: bool | None = None
    unsupported_claims: tuple[str, ...] = ()
    raw_parse_status: str = "valid"

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "correct": self.correct,
            "complete": self.complete,
            "brief_reason": self.brief_reason,
            "raw_parse_status": self.raw_parse_status,
        }
        if self.faithful_to_selected_context is not None:
            result["faithful_to_selected_context"] = (
                self.faithful_to_selected_context
            )
        if self.appropriate_abstention is not None:
            result["appropriate_abstention"] = self.appropriate_abstention
        if self.unsupported_claims:
            result["unsupported_claims"] = list(self.unsupported_claims)
        return result


@dataclass(frozen=True)
class AnswerExecution:
    generated_answer: str
    context_diagnostics: dict[str, Any]
    selected_evidence_for_judge: str
    latency_ms: dict[str, float]
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationModels:
    answer_model: str
    judge_model: str
    secondary_judge_model: str | None = None
    judge_endpoint: str | None = None
