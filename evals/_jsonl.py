"""Shared JSONL reading for the deterministic fixture evaluations."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any


def load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Read nonblank JSON values; preserve the evaluators' existing limit behavior."""
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            cases.append(json.loads(line))
            if limit is not None and len(cases) >= limit:
                break
    return cases


def load_validated_jsonl(
    path: Path, limit: int | None, validate: Callable[[object, Path, int], None],
) -> list[dict[str, Any]]:
    """Read cases with the caller's schema and file/line JSON error contract."""
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {error}") from error
            validate(case, path, line_number)
            cases.append(case)
            if limit is not None and len(cases) >= limit:
                break
    return cases
