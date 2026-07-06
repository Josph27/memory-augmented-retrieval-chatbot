from __future__ import annotations

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):  # type: ignore[no-untyped-def]
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)
