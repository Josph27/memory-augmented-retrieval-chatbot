from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


ExecutionStatus = Literal["passed", "failed", "not_executed", "error"]


@dataclass(frozen=True)
class ProductBehaviorCase:
    id: str
    category: str
    description: str
    initial_state: dict[str, Any]
    actions: list[str]
    expected_state: dict[str, Any]
    required_events: list[str]
    forbidden_events: list[str]
    deterministic: bool
    execution_layer: str
    repetitions: int
    oracle: str
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OracleObservation:
    status: ExecutionStatus
    actual: dict[str, Any]
    root_cause: str | None = None
    database_state_diff: dict[str, Any] = field(default_factory=dict)
    required_event_mismatch: list[str] = field(default_factory=list)
    forbidden_side_effect: str | None = None
    error: str | None = None
    trace_path: str | None = None


@dataclass(frozen=True)
class ProductBehaviorResult:
    case: ProductBehaviorCase
    observation: OracleObservation
    duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case.id,
            "category": self.case.category,
            "description": self.case.description,
            "expected_invariant": {
                "expected_state": self.case.expected_state,
                "required_events": self.case.required_events,
                "forbidden_events": self.case.forbidden_events,
            },
            "execution_layer": self.case.execution_layer,
            "deterministic": self.case.deterministic,
            "repetitions": self.case.repetitions,
            "tags": self.case.tags,
            "status": self.observation.status,
            "actual_result": self.observation.actual,
            "root_cause": self.observation.root_cause,
            "database_state_diff": self.observation.database_state_diff,
            "required_call_or_event_mismatch": (
                self.observation.required_event_mismatch
            ),
            "forbidden_side_effect": self.observation.forbidden_side_effect,
            "trace_or_screenshot_path": self.observation.trace_path,
            "error": self.observation.error,
            "duration_ms": round(self.duration_ms, 3),
        }


def case_to_dict(case: ProductBehaviorCase) -> dict[str, Any]:
    return asdict(case)

