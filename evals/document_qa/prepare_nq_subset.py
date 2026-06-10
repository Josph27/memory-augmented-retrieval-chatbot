from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = Path(__file__).parent / "datasets" / "nq_subset.jsonl"
NQ_DATASET_IDS = (
    "sjhallo07/natural_questions",
    "cjlovering/natural-questions-short",
)

QUESTION_KEYS = ("question", "questions", "query")
CONTEXT_KEYS = (
    "document_text",
    "context",
    "contexts",
    "text",
    "passage",
    "long_answer",
    "document",
    "page_content",
)
ANSWER_KEYS = (
    "short_answer",
    "short_answers",
    "answer",
    "answers",
    "answer_text",
    "target",
)
ID_KEYS = ("id", "example_id", "question_id", "document_id")


def main() -> int:
    """Prepare a filtered Natural Questions style document QA subset."""
    parser = argparse.ArgumentParser(description="Prepare a Natural Questions style subset.")
    parser.add_argument("--limit", type=int, default=200, help="Maximum rows to write.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSONL path.",
    )
    parser.add_argument("--split", default="train", help="Dataset split to load.")
    parser.add_argument("--seed", type=int, default=13, help="Shuffle seed.")
    parser.add_argument(
        "--dataset-name",
        default=None,
        help="Optional Hugging Face dataset ID override.",
    )
    parser.add_argument(
        "--require-answer-in-context",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Keep only rows whose answer anchor appears in the document text.",
    )
    args = parser.parse_args()

    try:
        dataset, dataset_name = load_nq_style_dataset(
            dataset_name=args.dataset_name,
            split=args.split,
        )
    except Exception as error:
        print(
            "Could not prepare Natural Questions subset. Install datasets and ensure "
            "internet/dataset access. "
            f"Last error: {type(error).__name__}: {error}"
        )
        return 1

    rows, stats = convert_dataset(
        dataset=dataset,
        dataset_name=dataset_name,
        split=args.split,
        limit=args.limit,
        seed=args.seed,
        require_answer_in_context=args.require_answer_in_context,
    )
    write_jsonl(args.output, rows)
    print("Natural Questions subset preparation")
    print(f"dataset used: {dataset_name}")
    print(f"split used: {args.split}")
    print(f"examples scanned: {stats['scanned']}")
    print(f"examples written: {stats['written']}")
    print(f"examples skipped: {stats['skipped']}")
    print(f"output path: {args.output}")
    print(
        "filtering assumptions: non-empty question/context/answer; "
        f"require_answer_in_context={args.require_answer_in_context}"
    )
    return 0


def load_nq_style_dataset(dataset_name: str | None, split: str) -> tuple[Any, str]:
    """Load the first available configured Natural Questions style dataset."""
    try:
        from datasets import load_dataset
    except ImportError as error:
        raise RuntimeError("datasets package is not installed") from error

    dataset_ids = (dataset_name,) if dataset_name else NQ_DATASET_IDS
    last_error: Exception | None = None
    for dataset_id in dataset_ids:
        if not dataset_id:
            continue
        try:
            dataset = load_dataset(dataset_id, split=split)
            return dataset, dataset_id
        except Exception as error:
            last_error = error
    if last_error is not None:
        raise RuntimeError(
            "failed to load an NQ-style split from "
            f"{', '.join(dataset_id for dataset_id in dataset_ids if dataset_id)}; "
            f"last error was {type(last_error).__name__}: {last_error}"
        ) from last_error
    raise RuntimeError("no Natural Questions style dataset IDs configured")


def convert_dataset(
    dataset: Any,
    dataset_name: str,
    split: str,
    limit: int,
    seed: int,
    require_answer_in_context: bool = True,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Convert an iterable dataset into local JSONL rows."""
    rows: list[dict[str, str]] = []
    scanned = 0
    skipped = 0
    for output_index, example in enumerate(shuffled_examples(dataset, seed=seed)):
        scanned += 1
        try:
            row = nq_example_to_row(
                example=dict(example),
                index=output_index,
                dataset_name=dataset_name,
                split=split,
                require_answer_in_context=require_answer_in_context,
            )
        except ValueError:
            skipped += 1
            continue
        rows.append(row)
        if len(rows) >= max(0, limit):
            break
    return rows, {"scanned": scanned, "written": len(rows), "skipped": skipped}


def shuffled_examples(dataset: Any, seed: int) -> list[Any]:
    """Return examples in deterministic shuffled order when possible."""
    if hasattr(dataset, "shuffle"):
        try:
            return list(dataset.shuffle(seed=seed))
        except Exception:
            pass
    examples = list(dataset)
    random.Random(seed).shuffle(examples)
    return examples


def nq_example_to_row(
    example: dict[str, Any],
    index: int,
    dataset_name: str,
    split: str,
    require_answer_in_context: bool = True,
) -> dict[str, str]:
    """Convert one NQ-style example into the document QA JSONL schema."""
    question = first_text_for_keys(example, QUESTION_KEYS)
    document_text = first_text_for_keys(example, CONTEXT_KEYS)
    expected_answer = first_text_for_keys(example, ANSWER_KEYS)

    if not question:
        raise ValueError("missing question")
    if not document_text:
        raise ValueError("missing document text")
    if not expected_answer:
        raise ValueError("missing answer")

    answer_anchor = expected_answer.strip()
    if not answer_anchor:
        raise ValueError("missing answer anchor")

    if require_answer_in_context and find_case_insensitive(document_text, answer_anchor) < 0:
        raise ValueError("answer anchor not found in document text")

    document_id = first_text_for_keys(example, ID_KEYS) or f"{split}_{index}"
    supporting_evidence = evidence_for_answer(
        document_text=document_text,
        answer_anchor=answer_anchor,
        fallback_context=first_text_for_keys(example, ("supporting_evidence", "evidence")),
    )
    return {
        "case_id": f"nq_{split}_{index:04d}",
        "source": source_name(dataset_name),
        "document_id": document_id,
        "document_text": document_text,
        "question": question,
        "expected_answer": expected_answer,
        "supporting_evidence": supporting_evidence,
        "answer_anchor": answer_anchor,
        "category": "natural_questions",
    }


def first_text_for_keys(example: dict[str, Any], keys: tuple[str, ...]) -> str:
    """Extract the first non-empty text value from likely field names."""
    for key in keys:
        if key in example:
            text = first_text(example[key])
            if text:
                return text
    return ""


def first_text(value: Any) -> str:
    """Extract text from common NQ-style scalar/list/dict shapes."""
    if value is None:
        return ""
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, int | float | bool):
        return clean_text(str(value))
    if isinstance(value, list | tuple):
        for item in value:
            text = first_text(item)
            if text:
                return text
        return ""
    if isinstance(value, dict):
        for key in (
            "text",
            "span_text",
            "input_text",
            "answer",
            "short_answer",
            "short_answers",
            "answers",
            "value",
            "normalized_value",
            "document_text",
            "context",
            "passage",
        ):
            if key in value:
                text = first_text(value[key])
                if text:
                    return text
    return ""


def evidence_for_answer(
    document_text: str,
    answer_anchor: str,
    fallback_context: str = "",
    window_chars: int = 450,
) -> str:
    """Return a long-answer field or a compact excerpt around the answer."""
    if fallback_context and (
        not answer_anchor or find_case_insensitive(fallback_context, answer_anchor) >= 0
    ):
        return fallback_context

    answer_index = find_case_insensitive(document_text, answer_anchor)
    if answer_index < 0:
        return document_text[:window_chars].strip()
    half_window = max(1, window_chars // 2)
    start = max(0, answer_index - half_window)
    end = min(len(document_text), answer_index + len(answer_anchor) + half_window)
    return document_text[start:end].strip()


def find_case_insensitive(text: str, needle: str) -> int:
    """Return the first case-insensitive index of needle in text."""
    return text.lower().find(needle.lower())


def clean_text(value: str) -> str:
    """Normalize whitespace and strip lightweight HTML tags."""
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", without_tags).strip()


def source_name(dataset_name: str) -> str:
    """Return a compact source label for converted NQ-style rows."""
    if not dataset_name:
        return "natural_questions"
    return f"natural_questions:{dataset_name}"


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    """Write converted rows to JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
