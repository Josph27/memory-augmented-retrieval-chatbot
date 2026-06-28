from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evals.longmemeval_adapter.loader import load_longmemeval_cases  # noqa: E402
from evals.longmemeval_adapter.runner import (  # noqa: E402
    AdapterModeUnavailable,
    run_adapter,
    write_report,
)
from evals.longmemeval_adapter.schema import SUPPORTED_MEMORY_MODES  # noqa: E402


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "tiny_longmemeval_sample.jsonl"


def parse_args() -> argparse.Namespace:
    """Parse the adapter CLI."""
    parser = argparse.ArgumentParser(
        description="Run an unofficial LongMemEval pilot adapter."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dataset-path", type=Path)
    source.add_argument("--fixture", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--memory-mode",
        choices=sorted(SUPPORTED_MEMORY_MODES),
        default="full",
    )
    parser.add_argument(
        "--answer-mode",
        choices=("mock", "model"),
        default="mock",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true", help="Print the full report.")
    return parser.parse_args()


def main() -> int:
    """Run the selected pilot and print an honest summary."""
    load_dotenv()
    args = parse_args()
    dataset_path = FIXTURE_PATH if args.fixture else args.dataset_path
    assert dataset_path is not None
    try:
        cases = load_longmemeval_cases(dataset_path, limit=args.limit)
        report = run_adapter(
            cases,
            memory_mode=args.memory_mode,
            answer_mode=args.answer_mode,
        )
    except (ValueError, FileNotFoundError, AdapterModeUnavailable) as error:
        print(f"LongMemEval adapter could not run: {error}", file=sys.stderr)
        return 2

    report["dataset_path"] = None if args.fixture else str(dataset_path)
    report["fixture"] = bool(args.fixture)
    if args.output:
        write_report(args.output, report)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        summary = report["summary"]
        print("LongMemEval pilot adapter report (unofficial scoring)")
        print(f"dataset={'tiny fixture' if args.fixture else dataset_path}")
        print(f"answer_mode={args.answer_mode}")
        print(f"memory_mode={args.memory_mode}")
        print(f"total_cases={summary['total_cases']}")
        print(f"pass_rate={summary['pass_rate']:.3f}")
        print(f"contains_gold_rate={summary['contains_gold_rate']:.3f}")
        print(f"abstain_accuracy={summary['abstain_accuracy']}")
        print(f"retrieval_hit_rate={summary['retrieval_hit_rate']}")
        print(f"average_latency_ms={summary['average_latency_ms']}")
        print(f"failed_case_ids={summary['failed_case_ids']}")
        if args.output:
            print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
