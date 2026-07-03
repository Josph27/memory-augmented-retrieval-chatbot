from __future__ import annotations

from collections import Counter
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


def normalized_token_f1(
    prediction: str,
    references: tuple[str, ...],
) -> OfficialMetricResult:
    prediction_tokens = normalize_text(prediction).split()
    if not prediction_tokens:
        return OfficialMetricResult("normalized_token_f1", 0.0, False)
    best = 0.0
    for reference in references:
        reference_tokens = normalize_text(reference).split()
        if not reference_tokens:
            continue
        overlap = Counter(prediction_tokens) & Counter(reference_tokens)
        shared = sum(overlap.values())
        if shared <= 0:
            continue
        precision = shared / len(prediction_tokens)
        recall = shared / len(reference_tokens)
        score = 2 * precision * recall / (precision + recall)
        best = max(best, score)
    return OfficialMetricResult(
        "normalized_token_f1",
        round(best, 4),
        best >= 0.5,
    )


METRICS: dict[str, MetricFunction] = {
    "normalized_substring": normalized_substring,
    "normalized_exact_match": normalized_exact_match,
    "normalized_token_f1": normalized_token_f1,
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
