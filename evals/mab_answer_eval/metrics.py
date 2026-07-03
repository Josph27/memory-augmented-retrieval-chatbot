from __future__ import annotations

from collections.abc import Callable

from evals.mab_answer_eval.schemas import OfficialMetricResult
from evals.memory_agent_bench.metrics import normalize_text


MetricFunction = Callable[[str, tuple[str, ...]], OfficialMetricResult]


def normalized_substring(
    prediction: str,
    references: tuple[str, ...],
) -> OfficialMetricResult:
    normalized_prediction = normalize_text(prediction)
    passed = any(
        normalized and normalized in normalized_prediction
        for normalized in map(normalize_text, references)
    )
    return OfficialMetricResult("normalized_substring", float(passed), passed)


def normalized_exact_match(
    prediction: str,
    references: tuple[str, ...],
) -> OfficialMetricResult:
    normalized_prediction = normalize_text(prediction)
    passed = normalized_prediction in {normalize_text(item) for item in references}
    return OfficialMetricResult("normalized_exact_match", float(passed), passed)


METRICS: dict[str, MetricFunction] = {
    "normalized_substring": normalized_substring,
    "normalized_exact_match": normalized_exact_match,
}


def score_official(
    metric_name: str,
    prediction: str,
    references: tuple[str, ...],
) -> OfficialMetricResult:
    try:
        metric = METRICS[metric_name]
    except KeyError as error:
        raise ValueError(f"unsupported official metric: {metric_name}") from error
    return metric(prediction, references)
