from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Iterable

from evals.mab_answer_eval.schemas import (
    AnswerManifest,
    ManifestCase,
    ResolvedCase,
)
from evals.memory_agent_bench.loader import normalize_record


def load_manifest(path: Path) -> AnswerManifest:
    """Load a versioned YAML/JSON manifest and compute its canonical hash."""
    raw_text = path.read_text(encoding="utf-8")
    try:
        value = json.loads(raw_text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError as error:
            raise ValueError(
                "Non-JSON YAML manifests require PyYAML; JSON is valid YAML."
            ) from error
        value = yaml.safe_load(raw_text)
    if not isinstance(value, dict):
        raise ValueError("answer-evaluation manifest must be an object")
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    manifest_hash = hashlib.sha256(canonical.encode()).hexdigest()
    cases_value = value.get("cases")
    if not isinstance(cases_value, list) or not cases_value:
        raise ValueError("answer-evaluation manifest requires non-empty cases")
    cases = tuple(parse_case(item) for item in cases_value)
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("answer-evaluation manifest contains duplicate case IDs")
    mode = str(value.get("execution_mode", "")).strip().lower()
    if mode not in {"native", "graph"}:
        raise ValueError("manifest execution_mode must be native or graph")
    return AnswerManifest(
        name=required_string(value, "name"),
        version=int(value.get("version", 1)),
        seed=int(value.get("seed", 0)),
        execution_mode=mode,
        dataset_id=str(value.get("dataset_id") or "ai-hyz/MemoryAgentBench"),
        cases=cases,
        manifest_hash=manifest_hash,
    )


def parse_case(value: Any) -> ManifestCase:
    if not isinstance(value, dict):
        raise ValueError("manifest cases must be objects")
    return ManifestCase(
        dataset=required_string(value, "dataset"),
        split=required_string(value, "split"),
        source_dataset=required_string(value, "source_dataset"),
        row_index=int(value["row_index"]),
        question_index=int(value["question_index"]),
        case_id=required_string(value, "case_id"),
        question_type=required_string(value, "question_type"),
        official_metric=required_string(value, "official_metric"),
    )


def required_string(value: dict[str, Any], key: str) -> str:
    result = str(value.get(key, "")).strip()
    if not result:
        raise ValueError(f"manifest field {key!r} must not be empty")
    return result


CatalogLoader = Callable[[str, str], Iterable[dict[str, Any]]]


def resolve_cases(
    manifest: AnswerManifest,
    *,
    catalog_loader: CatalogLoader | None = None,
    context_chunk_chars: int = 4000,
) -> list[ResolvedCase]:
    """Resolve explicit rows/questions while preserving manifest order."""
    loader = catalog_loader or huggingface_catalog
    rows_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    requested_by_split: dict[str, set[int]] = {}
    for case in manifest.cases:
        requested_by_split.setdefault(case.split, set()).add(case.row_index)
    for split, requested_rows in requested_by_split.items():
        remaining = set(requested_rows)
        for index, row in enumerate(loader(manifest.dataset_id, split)):
            if index in remaining:
                rows_by_key[(split, index)] = dict(row)
                remaining.remove(index)
            if not remaining:
                break
        if remaining:
            missing = ", ".join(map(str, sorted(remaining)))
            raise ValueError(f"unknown manifest rows for {split}: {missing}")

    resolved: list[ResolvedCase] = []
    for case in manifest.cases:
        row = rows_by_key[(case.split, case.row_index)]
        metadata = row.get("metadata")
        source = str(metadata.get("source", "")) if isinstance(metadata, dict) else ""
        if source != case.source_dataset:
            raise ValueError(
                f"case {case.case_id} expected source {case.source_dataset!r}, "
                f"found {source!r}"
            )
        example = normalize_record(
            row,
            competency=case.split,
            example_index=case.row_index,
            context_chunk_chars=context_chunk_chars,
        )
        if case.question_index < 0 or case.question_index >= len(example.questions):
            raise ValueError(f"unknown question for case {case.case_id}")
        isolated = replace(
            example,
            questions=(example.questions[case.question_index],),
            answers=(example.answers[case.question_index],),
        )
        resolved.append(ResolvedCase(case, isolated))
    return resolved


def huggingface_catalog(dataset_id: str, split: str) -> Iterable[dict[str, Any]]:
    try:
        from datasets import load_dataset
    except ImportError as error:
        raise RuntimeError("MAB answer evaluation requires the datasets package") from error
    return load_dataset(dataset_id, split=split, streaming=True)
