from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.product_behavior.models import ProductBehaviorCase


EXPECTED_CATEGORY_COUNTS = {
    "navigation": 8,
    "lifecycle": 10,
    "persistence": 7,
    "documents": 15,
    "failures": 10,
}
REQUIRED_FIELDS = {
    "id",
    "category",
    "description",
    "initial_state",
    "actions",
    "expected_state",
    "required_events",
    "forbidden_events",
    "deterministic",
    "execution_layer",
    "repetitions",
    "oracle",
}


def load_cases(case_dir: Path) -> list[ProductBehaviorCase]:
    """Load JSON-compatible YAML definitions and validate the frozen inventory."""
    values: list[dict[str, Any]] = []
    for path in sorted(case_dir.glob("*.yaml")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("cases") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise ValueError(f"{path} must contain a cases list")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"{path} contains a non-object case")
            missing = REQUIRED_FIELDS - set(row)
            if missing:
                raise ValueError(f"{path} case lacks fields: {sorted(missing)}")
            values.append(row)
    cases = [
        ProductBehaviorCase(
            id=str(value["id"]),
            category=str(value["category"]),
            description=str(value["description"]),
            initial_state=dict(value["initial_state"]),
            actions=[str(item) for item in value["actions"]],
            expected_state=dict(value["expected_state"]),
            required_events=[str(item) for item in value["required_events"]],
            forbidden_events=[str(item) for item in value["forbidden_events"]],
            deterministic=bool(value["deterministic"]),
            execution_layer=str(value["execution_layer"]),
            repetitions=int(value["repetitions"]),
            oracle=str(value["oracle"]),
            tags=[str(item) for item in value.get("tags", [])],
        )
        for value in values
    ]
    validate_inventory(cases)
    return cases


def validate_inventory(cases: list[ProductBehaviorCase]) -> None:
    if len(cases) != 50:
        raise ValueError(f"product benchmark requires exactly 50 cases, found {len(cases)}")
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("product benchmark contains duplicate case IDs")
    counts = {
        category: sum(case.category == category for case in cases)
        for category in EXPECTED_CATEGORY_COUNTS
    }
    if counts != EXPECTED_CATEGORY_COUNTS:
        raise ValueError(f"unexpected category counts: {counts}")
    browser_cases = [
        case for case in cases if case.execution_layer == "browser E2E"
    ]
    if len(browser_cases) != 8:
        raise ValueError(f"expected 8 browser E2E cases, found {len(browser_cases)}")
    for case in cases:
        if case.repetitions < 1:
            raise ValueError(f"{case.id} has invalid repetitions")

