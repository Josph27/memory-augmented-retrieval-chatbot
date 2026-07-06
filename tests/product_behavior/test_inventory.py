from __future__ import annotations

from collections import Counter
from pathlib import Path

from evals.product_behavior.loader import EXPECTED_CATEGORY_COUNTS, load_cases
from evals.product_behavior.oracle import ORACLES, UNSUPPORTED_ORACLES


ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = ROOT / "evals/product_behavior/cases"


def test_product_behavior_inventory_is_exactly_50_and_frozen_by_category() -> None:
    cases = load_cases(CASE_DIR)

    assert len(cases) == 50
    assert len({case.id for case in cases}) == 50
    assert Counter(case.category for case in cases) == EXPECTED_CATEGORY_COUNTS
    assert sum(case.execution_layer == "browser E2E" for case in cases) == 8


def test_every_case_has_an_explicit_oracle() -> None:
    cases = load_cases(CASE_DIR)
    known = {*ORACLES, *UNSUPPORTED_ORACLES}

    assert {case.oracle for case in cases} <= known


def test_case_ids_are_numbered_by_required_inventory() -> None:
    cases = load_cases(CASE_DIR)
    expected = {
        *{f"PB-NAV-{index:03d}" for index in range(1, 9)},
        *{f"PB-LIFE-{index:03d}" for index in range(1, 11)},
        *{f"PB-PERSIST-{index:03d}" for index in range(1, 8)},
        *{f"PB-DOC-{index:03d}" for index in range(1, 16)},
        *{f"PB-FAIL-{index:03d}" for index in range(1, 11)},
    }

    assert {case.id for case in cases} == expected

