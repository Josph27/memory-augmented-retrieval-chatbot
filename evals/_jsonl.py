"""Shared JSONL reading for the deterministic fixture evaluations."""

from __future__ import annotations

import json
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
