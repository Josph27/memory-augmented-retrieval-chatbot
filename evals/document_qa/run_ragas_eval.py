from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load exported RAGAS-compatible rows."""
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
