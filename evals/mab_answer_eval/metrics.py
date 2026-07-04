from __future__ import annotations

from collections import Counter
from collections.abc import Callable
import json
import re

from evals.mab_answer_eval.schemas import ManifestCase
from evals.mab_answer_eval.schemas import OfficialMetricResult
from evals.memory_agent_bench.metrics import normalize_text


MetricFunction = Callable[[str, tuple[str, ...]], OfficialMetricResult]


class JSONObjectPairs(list[tuple[str, object]]):
    """Distinguish JSON objects from arrays while retaining duplicate keys."""


OPTION_LABEL_PATTERN = re.compile(r"\b([A-D])\s*\.", re.IGNORECASE)
OPTION_ANSWER_CUE_PATTERN = re.compile(
    r"\b(?:answer|option)\s*(?:is|:)\s*([A-D])\b",
    re.IGNORECASE,
)
OPTION_CONFLICT_PATTERN = re.compile(
    r"\b(?:either|between)\s+([A-D])\b.*?\b(?:or|and)\s+([A-D])\b",
    re.IGNORECASE,
)
NUMERIC_LABEL_PATTERN = re.compile(
    r"\blabel\s*(?::|is)?\s*(\d{1,3})\b",
    re.IGNORECASE,
)
ANY_NUMBER_PATTERN = re.compile(r"(?<!\d)(\d{1,3})(?!\d)")


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


def normalize_prediction_for_case(
    case: ManifestCase,
    prediction: str,
    references: tuple[str, ...],
) -> dict[str, str | None]:
    """Apply narrow eval-only output normalization for strict task contracts."""
    if case.dataset == "icl_banking77":
        stripped = prediction.strip()
        exact_label = stripped if stripped.isdigit() and len(stripped) <= 3 else None
        labels = set(NUMERIC_LABEL_PATTERN.findall(prediction))
        if exact_label is not None:
            labels.add(exact_label)
        if len(labels) == 1:
            return {
                "status": "applied",
                "strategy": "single_numeric_label",
                "normalized_answer": next(iter(labels)),
            }
        if len(labels) > 1:
            return {
                "status": "ambiguous",
                "strategy": "single_numeric_label",
                "normalized_answer": None,
            }
        if len(set(ANY_NUMBER_PATTERN.findall(prediction))) > 1:
            return {
                "status": "ambiguous",
                "strategy": "single_numeric_label",
                "normalized_answer": None,
            }
    if case.dataset == "detective_qa":
        json_answers = extract_json_answers(prediction)
        if json_answers is not None:
            option = (
                normalize_option_answer(json_answers[0], references)
                if len(json_answers) == 1
                else None
            )
            return {
                "status": (
                    "applied"
                    if option is not None
                    else "ambiguous"
                    if len(json_answers) > 1
                    else "not_applicable"
                ),
                "strategy": "json_answer_field",
                "normalized_answer": option,
            }
        if looks_like_json_payload(prediction):
            return {
                "status": "not_applicable",
                "strategy": "json_answer_field",
                "normalized_answer": None,
            }
        conflict = OPTION_CONFLICT_PATTERN.search(prediction)
        if conflict and conflict.group(1).upper() != conflict.group(2).upper():
            return {
                "status": "ambiguous",
                "strategy": "single_option_label",
                "normalized_answer": None,
            }
        option = normalize_option_answer(prediction, references)
        if option is not None:
            return {
                "status": "applied",
                "strategy": "single_option_label",
                "normalized_answer": option,
            }
    return {
        "status": "not_applicable",
        "strategy": None,
        "normalized_answer": None,
    }


def score_official_for_case(
    case: ManifestCase,
    prediction: str,
    references: tuple[str, ...],
) -> tuple[OfficialMetricResult, dict[str, str | None]]:
    normalization = normalize_prediction_for_case(case, prediction, references)
    normalized_prediction = normalization.get("normalized_answer") or prediction
    return (
        score_official(case.official_metric, normalized_prediction, references),
        normalization,
    )


def extract_json_answers(prediction: str) -> tuple[str, ...] | None:
    """Return every top-level answer field, preserving duplicate JSON keys."""
    stripped = prediction.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped, object_pairs_hook=JSONObjectPairs)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, JSONObjectPairs):
        return None
    answers = tuple(
        str(value).strip()
        for key, value in parsed
        if key == "answer" and value is not None and str(value).strip()
    )
    return answers


def normalize_option_answer(
    prediction: str,
    references: tuple[str, ...],
) -> str | None:
    stripped = prediction.strip()
    if stripped in references:
        return stripped
    conflict = OPTION_CONFLICT_PATTERN.search(prediction)
    if conflict and conflict.group(1).upper() != conflict.group(2).upper():
        return None
    labels = {match.upper() for match in OPTION_LABEL_PATTERN.findall(prediction)}
    labels.update(
        match.upper() for match in OPTION_ANSWER_CUE_PATTERN.findall(prediction)
    )
    if re.fullmatch(r"[A-D]", stripped, flags=re.IGNORECASE):
        labels.add(stripped.upper())
    if len(labels) != 1:
        return None
    label = next(iter(labels))
    matches = [
        reference
        for reference in references
        if normalize_text(reference).startswith(normalize_text(f"{label}."))
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def looks_like_json_payload(prediction: str) -> bool:
    stripped = prediction.strip().lower()
    return (
        stripped.startswith("```json")
        or stripped.startswith("```")
        or stripped.startswith("{")
        or stripped.startswith("[")
    )
