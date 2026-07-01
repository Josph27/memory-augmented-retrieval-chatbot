from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.typed_memory_e2e.cases import all_cases  # noqa: E402
from evals.typed_memory_e2e.runner import run_benchmark, write_jsonl  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the deterministic typed-memory E2E benchmark."
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--answer-mode", choices=("mock",), default="mock")
    parser.add_argument(
        "--use-langgraph-semantic-router",
        action="store_true",
        help="Compatibility flag; the isolated benchmark always uses this path.",
    )
    args = parser.parse_args()
    cases = select_cases(
        all_cases(),
        names=set(args.case),
        categories=set(args.category),
    )
    report = run_benchmark(cases)
    if args.output:
        write_jsonl(args.output, report)
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))


def select_cases(cases, *, names: set[str], categories: set[str]):  # type: ignore[no-untyped-def]
    return [
        case
        for case in cases
        if (not names or case.name in names)
        and (not categories or case.category in categories)
    ]


if __name__ == "__main__":
    main()
