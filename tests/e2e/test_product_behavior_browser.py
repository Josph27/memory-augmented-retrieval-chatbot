from __future__ import annotations

from pathlib import Path

import pytest

from evals.product_behavior.loader import load_cases


ROOT = Path(__file__).resolve().parents[2]
BROWSER_CASES = [
    case
    for case in load_cases(ROOT / "evals/product_behavior/cases")
    if case.execution_layer == "browser E2E"
]


@pytest.mark.parametrize("case", BROWSER_CASES, ids=lambda case: case.id)
def test_product_behavior_browser_case_requires_browser_harness(case) -> None:
    pytest.skip(
        f"{case.id}: browser harness unavailable; scenario remains not executed"
    )
