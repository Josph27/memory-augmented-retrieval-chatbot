from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = Path(__file__).parent / "datasets" / "squad_subset.jsonl"


def main() -> int:
    """Prepare a small SQuAD validation subset as JSONL."""
    parser = argparse.ArgumentParser(description="Prepare a SQuAD document QA subset.")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of validation examples to write.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSONL path.",
    )
    args = parser.parse_args()

    try:
        dataset = load_squad_validation()
    except Exception:
        print("Could not prepare SQuAD subset. Install datasets and ensure internet access.")
        return 1

    rows = []
    for index, example in enumerate(dataset):
        if len(rows) >= args.limit:
            break
        try:
            rows.append(squad_example_to_row(example, index=index))
        except ValueError:
            continue

    write_jsonl(args.output, rows)
    print(f"Wrote {len(rows)} SQuAD examples to {args.output}")
    return 0


def load_squad_validation() -> Any:
    """Load the standard SQuAD validation split with an optional dependency."""
    try:
        from datasets import load_dataset
    except ImportError as error:
        raise RuntimeError("datasets package is not installed") from error
    return load_dataset("squad", split="validation")


def squad_example_to_row(example: dict[str, Any], index: int) -> dict[str, str]:
    """Convert one Hugging Face SQuAD example into the local JSONL schema."""
    context = str(example.get("context", "")).strip()
    question = str(example.get("question", "")).strip()
    example_id = str(example.get("id") or f"validation_{index}")
    answers = example.get("answers") or {}
    answer_texts = answers.get("text") if isinstance(answers, dict) else None
    if not context or not question or not answer_texts:
        raise ValueError("SQuAD example is missing context, question, or answers")

    first_answer = str(answer_texts[0]).strip()
    if not first_answer:
        raise ValueError("SQuAD example has an empty first answer")

    return {
        "case_id": f"squad_validation_{index:04d}",
        "source": "squad",
        "document_id": example_id,
        "document_text": context,
        "question": question,
        "expected_answer": first_answer,
        "supporting_evidence": context,
        "answer_anchor": first_answer,
        "category": "standard_document_qa",
    }


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    """Write converted rows to JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
