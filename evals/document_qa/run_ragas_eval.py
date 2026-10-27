from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


try:
    from ._jsonl import load_jsonl
except ImportError:
    from _jsonl import load_jsonl

def main() -> None:
    """Run optional RAGAS metrics over exported document QA rows."""
    parser = argparse.ArgumentParser(description="Run optional RAGAS eval over JSONL rows.")
    parser.add_argument("--input", type=Path, required=True, help="RAGAS-compatible JSONL input.")
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    try:
        scores = run_ragas(rows)
    except ImportError:
        print("RAGAS is not installed. Install it only if you want optional RAGAS evaluation.")
        return
    except Exception as error:
        print(f"Could not run RAGAS evaluation: {type(error).__name__}: {error}")
        return

    print("RAGAS evaluation result")
    print(scores)


def run_ragas(rows: list[dict[str, Any]]) -> Any:
    """Run a minimal optional RAGAS metric set if dependencies are available."""
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    dataset = Dataset.from_list(rows)
    return evaluate(
        dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ],
    )


if __name__ == "__main__":
    main()
