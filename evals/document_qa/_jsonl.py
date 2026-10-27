"""JSONL reader with file and line diagnostics for document QA evaluations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read nonblank JSON values and report malformed input with its location."""
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as error:
                msg = f"Invalid JSONL at {path}:{line_number}: {error}"
                raise ValueError(msg) from error
    return rows
