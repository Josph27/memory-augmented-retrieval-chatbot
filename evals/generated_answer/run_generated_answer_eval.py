from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evals.document_qa.answer_generation import (  # noqa: E402
    AnswerGenerator,
    answer_is_unknown,
    build_default_answer_generator,
)


DEFAULT_DATASET = Path(__file__).parent / "datasets" / "generated_answer_sample.jsonl"
REQUIRED_CASE_FIELDS = {
    "case_id",
    "task_type",
    "query",
    "expected_sources",
    "expected_answer_contains",
    "forbidden_answer_contains",
    "should_abstain",
}


class ModelModeUnavailable(RuntimeError):
    """Raised when optional model mode has no configured endpoint."""


@dataclass(frozen=True)
class GeneratedAnswerResult:
    """Metrics and trace data for one generated-answer eval case."""

    case_id: str
    task_type: str
    answer: str
    answer_contains_expected: bool
    forbidden_claim_violations: list[str]
    abstain_correct: bool | None
    expected_source_used: bool
    retrieved_context_used: bool
    overall_case_pass: bool
    failed_reasons: list[str]
    trace: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run generated-answer memory/RAG evaluation."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--mode",
        choices=("mock", "model", "replay"),
        default="mock",
        help="mock is deterministic; model calls configured endpoint; replay uses saved answers.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--replay-answers",
        type=Path,
        help="JSONL with case_id and answer fields for replay mode.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON report output path.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    return parser.parse_args()


def load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Load and validate generated-answer cases from JSONL."""
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {error}") from error
            validate_case(case, path=path, line_number=line_number)
            cases.append(case)
            if limit is not None and len(cases) >= limit:
                break
    return cases


def validate_case(case: object, path: Path, line_number: int) -> None:
    """Validate required adapter-compatible case fields."""
    if not isinstance(case, dict):
        raise ValueError(f"Expected object at {path}:{line_number}")
    missing = sorted(REQUIRED_CASE_FIELDS - set(case))
    if missing:
        raise ValueError(f"Missing fields at {path}:{line_number}: {missing}")


def load_replay_answers(path: Path) -> dict[str, str]:
    """Load saved answers keyed by case_id."""
    answers: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            case_id = row.get("case_id") if isinstance(row, dict) else None
            answer = row.get("answer") if isinstance(row, dict) else None
            if not isinstance(case_id, str) or not isinstance(answer, str):
                raise ValueError(
                    f"Replay row at {path}:{line_number} requires case_id and answer"
                )
            answers[case_id] = answer
    return answers


def run_cases(
    cases: list[dict[str, Any]],
    mode: str = "mock",
    answer_generator: AnswerGenerator | None = None,
    replay_answers: dict[str, str] | None = None,
) -> list[GeneratedAnswerResult]:
    """Run all cases with mock, model, or replay answer generation."""
    return [
        run_case(
            case,
            mode=mode,
            answer_generator=answer_generator,
            replay_answers=replay_answers,
        )
        for case in cases
    ]


def run_case(
    case: dict[str, Any],
    mode: str = "mock",
    answer_generator: AnswerGenerator | None = None,
    replay_answers: dict[str, str] | None = None,
) -> GeneratedAnswerResult:
    """Generate and score one answer from controlled retrieved contexts."""
    contexts = context_rows(case)
    answer = answer_for_case(
        case,
        mode=mode,
        contexts=[row["content"] for row in contexts],
        answer_generator=answer_generator,
        replay_answers=replay_answers,
    )
    return score_case(case=case, answer=answer, contexts=contexts, mode=mode)


def context_rows(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Return normalized source-tagged context fixture rows."""
    setup = case.get("setup_fixture")
    raw_contexts = setup.get("retrieved_contexts", []) if isinstance(setup, dict) else []
    contexts = []
    for raw_context in raw_contexts:
        if not isinstance(raw_context, dict):
            continue
        contexts.append(
            {
                "source": str(raw_context.get("source") or "unknown"),
                "content": str(raw_context.get("content") or ""),
                "chat_id": raw_context.get("chat_id"),
                "source_message_ids": list(raw_context.get("source_message_ids") or []),
                "metadata": dict(raw_context.get("metadata") or {}),
            }
        )
    return contexts


def answer_for_case(
    case: dict[str, Any],
    mode: str,
    contexts: list[str],
    answer_generator: AnswerGenerator | None,
    replay_answers: dict[str, str] | None,
) -> str:
    """Return one answer for the requested eval mode."""
    if mode == "mock":
        if case.get("mock_answer") is not None:
            return str(case["mock_answer"])
        if case.get("gold_answer") is not None:
            return str(case["gold_answer"])
        return "I don't know." if case.get("should_abstain") else ""
    if mode == "replay":
        case_id = str(case["case_id"])
        if replay_answers and case_id in replay_answers:
            return replay_answers[case_id]
        if case.get("replay_answer") is not None:
            return str(case["replay_answer"])
        raise ValueError(f"No replay answer available for case {case_id!r}")
    if mode == "model":
        if answer_generator is None:
            raise ModelModeUnavailable("Model mode requires an answer generator.")
        return answer_generator.generate(str(case["query"]), contexts)
    raise ValueError(f"Unsupported answer mode: {mode}")


def score_case(
    case: dict[str, Any],
    answer: str,
    contexts: list[dict[str, Any]],
    mode: str,
) -> GeneratedAnswerResult:
    """Score deterministic answer, grounding, source use, and abstention metrics."""
    normalized_answer = normalize_text(answer)
    expected_fragments = [
        str(fragment)
        for fragment in case.get("expected_answer_contains", [])
        if str(fragment).strip()
    ]
    forbidden_fragments = [
        str(fragment)
        for fragment in case.get("forbidden_answer_contains", [])
        if str(fragment).strip()
    ]
    expected_sources = {
        str(source) for source in case.get("expected_sources", [])
    }
    retrieved_sources = {row["source"] for row in contexts}
    context_text = normalize_text("\n".join(row["content"] for row in contexts))

    answer_contains_expected = all(
        normalize_text(fragment) in normalized_answer for fragment in expected_fragments
    )
    violations = [
        fragment
        for fragment in forbidden_fragments
        if normalize_text(fragment) in normalized_answer
    ]
    should_abstain = bool(case.get("should_abstain"))
    abstain_correct = answer_is_unknown(answer) if should_abstain else None
    expected_source_used = expected_sources.issubset(retrieved_sources)
    retrieved_context_used = context_use_check(
        expected_fragments=expected_fragments,
        answer=normalized_answer,
        context=context_text,
        should_abstain=should_abstain,
    )

    failed_reasons = []
    if not answer_contains_expected:
        failed_reasons.append("expected_answer_missing")
    if violations:
        failed_reasons.append("forbidden_claim_present")
    if abstain_correct is False:
        failed_reasons.append("abstain_failed")
    if not expected_source_used:
        failed_reasons.append("expected_source_missing")
    if not retrieved_context_used:
        failed_reasons.append("retrieved_context_not_used")

    return GeneratedAnswerResult(
        case_id=str(case["case_id"]),
        task_type=str(case["task_type"]),
        answer=answer,
        answer_contains_expected=answer_contains_expected,
        forbidden_claim_violations=violations,
        abstain_correct=abstain_correct,
        expected_source_used=expected_source_used,
        retrieved_context_used=retrieved_context_used,
        overall_case_pass=not failed_reasons,
        failed_reasons=failed_reasons,
        trace={
            "case_id": str(case["case_id"]),
            "task_type": str(case["task_type"]),
            "query": str(case["query"]),
            "mode": mode,
            "expected_sources": sorted(expected_sources),
            "retrieved_sources": sorted(retrieved_sources),
            "retrieved_contexts": contexts,
            "answer": answer,
            "gold_answer": case.get("gold_answer"),
            "gold_evidence": list(case.get("gold_evidence") or []),
            "benchmark_name": case.get("benchmark_name"),
            "split": case.get("split"),
            "notes": case.get("notes"),
        },
    )


def context_use_check(
    expected_fragments: list[str],
    answer: str,
    context: str,
    should_abstain: bool,
) -> bool:
    """Check whether answer evidence appears in both answer and retrieved context."""
    if should_abstain:
        return not context and (
            "i don t know" in answer or "i do not know" in answer
        )
    return any(
        normalize_text(fragment) in answer and normalize_text(fragment) in context
        for fragment in expected_fragments
    )


def normalize_text(value: str) -> str:
    """Normalize text for deterministic substring metrics."""
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def summarize_results(results: list[GeneratedAnswerResult]) -> dict[str, Any]:
    """Return aggregate generated-answer metrics."""
    abstain_results = [
        result.abstain_correct
        for result in results
        if result.abstain_correct is not None
    ]
    return {
        "total_cases": len(results),
        "answer_contains_expected": rate(
            result.answer_contains_expected for result in results
        ),
        "forbidden_claim_violations": sum(
            len(result.forbidden_claim_violations) for result in results
        ),
        "abstain_accuracy": rate(abstain_results),
        "expected_source_used": rate(
            result.expected_source_used for result in results
        ),
        "retrieved_context_used": rate(
            result.retrieved_context_used for result in results
        ),
        "overall_case_pass_rate": rate(
            result.overall_case_pass for result in results
        ),
        "failed_case_ids": [
            result.case_id for result in results if not result.overall_case_pass
        ],
    }


def rate(values: Any) -> float:
    """Return truthy fraction, or zero for an empty iterable."""
    items = list(values)
    if not items:
        return 0.0
    return sum(1 for item in items if item) / len(items)


def report_payload(
    results: list[GeneratedAnswerResult],
    mode: str,
    model_name: str | None = None,
) -> dict[str, Any]:
    """Return JSON-ready generated-answer report."""
    return {
        "eval_name": "generated_answer_memory_rag",
        "mode": mode,
        "model_name": model_name,
        "summary": summarize_results(results),
        "cases": [
            {
                "case_id": result.case_id,
                "task_type": result.task_type,
                "answer": result.answer,
                "answer_contains_expected": result.answer_contains_expected,
                "forbidden_claim_violations": result.forbidden_claim_violations,
                "abstain_correct": result.abstain_correct,
                "expected_source_used": result.expected_source_used,
                "retrieved_context_used": result.retrieved_context_used,
                "overall_case_pass": result.overall_case_pass,
                "failed_reasons": result.failed_reasons,
                "trace": result.trace,
            }
            for result in results
        ],
    }


def write_report(path: Path, payload: dict[str, Any]) -> None:
    """Write generated-answer report JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def print_summary(
    results: list[GeneratedAnswerResult],
    mode: str,
    model_name: str | None,
    json_output: bool,
) -> None:
    """Print readable or JSON report."""
    payload = report_payload(results, mode=mode, model_name=model_name)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"generated_answer_eval mode={mode}")
    if model_name:
        print(f"model_name={model_name}")
    for key, value in payload["summary"].items():
        print(f"{key}={value}")
    for result in results:
        status = "PASS" if result.overall_case_pass else "FAIL"
        print(
            "case_result "
            f"case_id={result.case_id} "
            f"task_type={result.task_type} "
            f"status={status} "
            f"failed_reasons={result.failed_reasons}"
        )


def configured_model_generator() -> AnswerGenerator:
    """Build configured generator or fail clearly when endpoint config is missing."""
    load_dotenv()
    required = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL_NAME")
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise ModelModeUnavailable(
            "Model mode skipped: missing environment configuration "
            + ", ".join(missing)
        )
    return build_default_answer_generator()


def main() -> int:
    args = parse_args()
    cases = load_jsonl(args.dataset, limit=args.limit)
    replay_answers = None
    answer_generator = None
    model_name = None
    if args.mode == "replay":
        if args.replay_answers is None:
            print("Replay mode requires --replay-answers JSONL.")
            return 2
        replay_answers = load_replay_answers(args.replay_answers)
    if args.mode == "model":
        try:
            answer_generator = configured_model_generator()
        except ModelModeUnavailable as error:
            print(error)
            return 2
        model_name = answer_generator.model_name

    try:
        results = run_cases(
            cases,
            mode=args.mode,
            answer_generator=answer_generator,
            replay_answers=replay_answers,
        )
    except (ModelModeUnavailable, ValueError) as error:
        print(f"generated_answer_eval_unavailable reason={error}")
        return 2

    payload = report_payload(results, mode=args.mode, model_name=model_name)
    if args.output:
        write_report(args.output, payload)
        print(f"wrote_report={args.output}")
    print_summary(
        results,
        mode=args.mode,
        model_name=model_name,
        json_output=args.json,
    )
    return 1 if payload["summary"]["failed_case_ids"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
