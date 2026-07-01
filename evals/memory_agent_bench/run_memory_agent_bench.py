from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.memory_agent_bench.loader import load_examples  # noqa: E402
from evals.memory_agent_bench.runner import (  # noqa: E402
    run_benchmark,
    write_jsonl_report,
)
from src.config import AppConfig  # noqa: E402
from src.model_wrapper import ModelWrapper  # noqa: E402


DEFAULT_FIXTURE = Path(__file__).parent / "fixtures" / "tiny_sample.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the optional MemoryAgentBench lifecycle adapter."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--answer-mode", choices=("mock", "model"), default="mock")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--no-finalize-sessions",
        action="store_true",
        help="Keep replay sessions active instead of invoking ChatEndAction.",
    )
    args = parser.parse_args()
    model = (
        ModelWrapper(AppConfig.from_env()) if args.answer_mode == "model" else None
    )
    report = run_benchmark(
        load_examples(args.dataset, limit=args.limit),
        answer_mode=args.answer_mode,
        model=model,
        finalize_sessions=not args.no_finalize_sessions,
    )
    if args.output:
        write_jsonl_report(args.output, report)
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
