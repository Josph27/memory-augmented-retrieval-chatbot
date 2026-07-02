from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

try:
    from .answer_generation import (
        AnswerGenerator,
        answer_is_unknown,
        build_default_answer_generator,
    )
    from .metrics import (
        answer_contains_anchor,
        answer_contains_expected,
        context_contains_answer_anchor,
        context_contains_evidence,
        ragas_compatible_row,
    )
    from .ragas_export import results_to_ragas_rows, write_ragas_jsonl
except ImportError:
    from answer_generation import (
        AnswerGenerator,
        answer_is_unknown,
        build_default_answer_generator,
    )
    from metrics import (
        answer_contains_anchor,
        answer_contains_expected,
        context_contains_answer_anchor,
        context_contains_evidence,
        ragas_compatible_row,
    )
    from ragas_export import results_to_ragas_rows, write_ragas_jsonl


DEFAULT_DATASET = Path(__file__).parent / "datasets" / "squad_style_sample.jsonl"
RETRIEVAL_CONTEXT_MODES = {"langchain_chroma"}
ANSWER_MODE_CHOICES = ("oracle", "model")


@dataclass(frozen=True)
class EvalResult:
    """One deterministic scaffold result."""

    case_id: str
    answer_anchor_match: bool
    expected_answer_match: bool
    context_evidence_hit: bool
    context_answer_anchor_hit: bool
    context_expected_answer_hit: bool
    answer: str
    answer_mode: str
    model_name: str | None
    answer_unknown: bool
    ragas_row: dict[str, Any]


@dataclass(frozen=True)
class EvalResources:
    """Reusable optional resources for one eval run."""

    langchain_retriever: Any | None = None
    temp_directory: Any | None = None
    answer_generator: AnswerGenerator | None = None
    answer_mode: str = "oracle"
    model_name: str | None = None


def main() -> None:
    """Run the document QA scaffold eval."""
    parser = argparse.ArgumentParser(description="Run document QA scaffold eval.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to JSONL dataset.",
    )
    parser.add_argument(
        "--context-mode",
        choices=(
            "document_text",
            "supporting_evidence",
            "langchain_chroma",
        ),
        default="document_text",
        help="Placeholder context source until real retrieval exists.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=4,
        help="Number of retrieved document chunks for retrieval modes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of dataset cases to evaluate.",
    )
    parser.add_argument(
        "--retrieval-scope",
        choices=("isolated", "corpus"),
        default="isolated",
        help="Use one document per case or retrieve from a shared dataset corpus.",
    )
    parser.add_argument(
        "--answer-mode",
        choices=ANSWER_MODE_CHOICES,
        default="oracle",
        help="Use oracle placeholder answers or generate answers with the configured model.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print RAGAS-compatible JSON rows after the summary.",
    )
    parser.add_argument(
        "--export-ragas-jsonl",
        type=Path,
        default=None,
        help="Write RAGAS-compatible rows to JSONL without requiring RAGAS.",
    )
    args = parser.parse_args()

    cases = load_jsonl(args.dataset)
    if args.limit is not None:
        cases = cases[: max(0, args.limit)]
    try:
        resources = build_eval_resources(
            context_mode=args.context_mode,
            retrieval_scope=args.retrieval_scope,
            cases=cases,
            answer_mode=args.answer_mode,
        )
        results = [
            evaluate_case(
                case,
                context_mode=args.context_mode,
                top_k=args.top_k,
                resources=resources,
                retrieval_scope=args.retrieval_scope,
                answer_mode=args.answer_mode,
            )
            for case in cases
        ]
    except RetrievalModeUnavailable as error:
        print(str(error))
        return
    print_summary(
        results,
        context_mode=args.context_mode,
        retrieval_scope=args.retrieval_scope,
        top_k=args.top_k,
        answer_mode=args.answer_mode,
        model_name=resources.model_name,
    )
    ragas_rows = results_to_ragas_rows(
        results=results,
        cases=cases,
        retrieval_mode=args.context_mode,
        retrieval_scope=args.retrieval_scope,
        top_k=args.top_k,
        vector_backend=None,
    )
    if args.export_ragas_jsonl is not None:
        write_ragas_jsonl(ragas_rows, args.export_ragas_jsonl)
        print(f"exported RAGAS-compatible rows: {args.export_ragas_jsonl}")
    if args.json:
        print(json.dumps(ragas_rows, indent=2))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL cases from disk."""
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                cases.append(json.loads(stripped))
            except json.JSONDecodeError as error:
                msg = f"Invalid JSONL at {path}:{line_number}: {error}"
                raise ValueError(msg) from error
    return cases


def evaluate_case(
    case: dict[str, Any],
    context_mode: str = "document_text",
    top_k: int = 4,
    resources: EvalResources | None = None,
    retrieval_scope: str = "isolated",
    answer_mode: str = "oracle",
) -> EvalResult:
    """Evaluate one case with oracle or model-generated answer mode."""
    contexts = placeholder_contexts(
        case,
        context_mode=context_mode,
        top_k=top_k,
        resources=resources,
        retrieval_scope=retrieval_scope,
    )
    answer = answer_for_case(
        question=str(case["question"]),
        contexts=contexts,
        expected_answer=str(case["expected_answer"]),
        answer_mode=answer_mode,
        resources=resources,
    )
    expected_answer = str(case["expected_answer"])
    answer_anchor = str(case["answer_anchor"])
    supporting_evidence = str(case["supporting_evidence"])
    ragas_row = ragas_compatible_row(
        question=str(case["question"]),
        contexts=contexts,
        answer=answer,
        ground_truth=expected_answer,
        supporting_evidence=supporting_evidence,
        case_id=str(case["case_id"]),
        metadata={
            "document_id": case.get("document_id"),
            "category": case.get("category"),
            "answer_mode": answer_mode,
            "model_name": resources.model_name if resources else None,
        },
    )
    return EvalResult(
        case_id=str(case["case_id"]),
        answer_anchor_match=answer_contains_anchor(answer, answer_anchor),
        expected_answer_match=answer_contains_expected(answer, expected_answer),
        context_evidence_hit=context_contains_evidence(contexts, supporting_evidence),
        context_answer_anchor_hit=context_contains_answer_anchor(contexts, answer_anchor),
        context_expected_answer_hit=context_contains_answer_anchor(contexts, expected_answer),
        answer=answer,
        answer_mode=answer_mode,
        model_name=resources.model_name if resources else None,
        answer_unknown=answer_is_unknown(answer),
        ragas_row=ragas_row,
    )


def answer_for_case(
    question: str,
    contexts: list[str],
    expected_answer: str,
    answer_mode: str,
    resources: EvalResources | None,
) -> str:
    """Return oracle or model-generated answer for one eval case."""
    if answer_mode == "oracle":
        return expected_answer
    if resources is None or resources.answer_generator is None:
        raise RetrievalModeUnavailable("Model answer mode requires an answer generator.")
    return resources.answer_generator.generate(question=question, contexts=contexts)


def placeholder_contexts(
    case: dict[str, Any],
    context_mode: str,
    top_k: int = 4,
    resources: EvalResources | None = None,
    retrieval_scope: str = "isolated",
) -> list[str]:
    """Return placeholder contexts until real document retrieval exists."""
    if context_mode in RETRIEVAL_CONTEXT_MODES:
        if retrieval_scope == "corpus":
            return corpus_retrieval_contexts(
                case,
                context_mode=context_mode,
                top_k=top_k,
                resources=resources,
            )
        return retrieval_contexts(
            case,
            context_mode=context_mode,
            top_k=top_k,
            resources=resources,
        )
    if context_mode == "supporting_evidence":
        return [str(case["supporting_evidence"])]
    return [str(case["document_text"])]


class RetrievalModeUnavailable(RuntimeError):
    """Raised when optional retrieval mode dependencies are unavailable."""


def build_eval_resources(
    context_mode: str,
    retrieval_scope: str = "isolated",
    cases: list[dict[str, Any]] | None = None,
    answer_mode: str = "oracle",
) -> EvalResources:
    """Create reusable resources once for an eval run."""
    answer_generator = None
    model_name = None

    if answer_mode == "model":
        ensure_repo_root_on_path()
        try:
            answer_generator = build_default_answer_generator()
            model_name = answer_generator.model_name
        except Exception as error:
            msg = f"Skipping model answer eval: {type(error).__name__}: {error}"
            raise RetrievalModeUnavailable(msg) from error

    if context_mode == "langchain_chroma":
        ensure_repo_root_on_path()

    if retrieval_scope != "corpus" or context_mode not in RETRIEVAL_CONTEXT_MODES:
        return EvalResources(
            answer_generator=answer_generator,
            answer_mode=answer_mode,
            model_name=model_name,
        )

    if cases is None:
        raise RetrievalModeUnavailable("Corpus retrieval requires dataset cases.")

    return build_corpus_resources(
        cases=cases,
        context_mode=context_mode,
        answer_generator=answer_generator,
        answer_mode=answer_mode,
        model_name=model_name,
    )


def build_corpus_resources(
    cases: list[dict[str, Any]],
    context_mode: str,
    answer_generator: AnswerGenerator | None = None,
    answer_mode: str = "oracle",
    model_name: str | None = None,
) -> EvalResources:
    """Ingest the full eval dataset into one temporary document corpus."""
    ensure_repo_root_on_path()
    from src.retrieval.langchain_chroma_retriever import (
        LangChainChromaRetriever,
        LangChainChromaUnavailable,
    )

    temp_directory = TemporaryDirectory()
    langchain_retriever = None
    if context_mode == "langchain_chroma":
        try:
            langchain_retriever = LangChainChromaRetriever(
                persist_dir=Path(temp_directory.name) / "chroma",
            )
            seen_langchain_texts: set[str] = set()
            for case in cases:
                document_text = str(case["document_text"])
                if document_text in seen_langchain_texts:
                    continue
                seen_langchain_texts.add(document_text)
                langchain_retriever.index_text_document(
                    title=str(case["document_id"]),
                    text=document_text,
                    source=str(case.get("source", "document_qa_eval")),
                    metadata={
                        "document_id": str(case["document_id"]),
                        "case_id": case.get("case_id"),
                        "scope": "corpus",
                    },
                )
        except LangChainChromaUnavailable as error:
            raise RetrievalModeUnavailable(f"Skipping langchain_chroma: {error}") from error

    return EvalResources(
        langchain_retriever=langchain_retriever,
        temp_directory=temp_directory,
        answer_generator=answer_generator,
        answer_mode=answer_mode,
        model_name=model_name,
    )


def retrieval_contexts(
    case: dict[str, Any],
    context_mode: str,
    top_k: int = 4,
    resources: EvalResources | None = None,
) -> list[str]:
    """Run the document retriever in a temporary database."""
    ensure_repo_root_on_path()
    from src.core.contracts import SourcePlan
    from src.retrieval.langchain_chroma_retriever import (
        LangChainChromaRetriever,
        LangChainChromaUnavailable,
    )

    with TemporaryDirectory() as directory:
        if context_mode == "langchain_chroma":
            try:
                retriever = LangChainChromaRetriever(
                    persist_dir=Path(directory) / "chroma",
                )
                retriever.index_text_document(
                    title=str(case["document_id"]),
                    text=str(case["document_text"]),
                    source=str(case.get("source", "document_qa_eval")),
                    metadata={"case_id": case.get("case_id")},
                )
                candidates = retriever.retrieve(
                    chat_id="document-qa-eval",
                    source_plan=SourcePlan(
                        source="document_memory",
                        enabled=True,
                        query=str(case["question"]),
                        limit=top_k,
                    ),
                )
                return [candidate.content for candidate in candidates]
            except LangChainChromaUnavailable as error:
                raise RetrievalModeUnavailable(f"Skipping langchain_chroma: {error}") from error
    raise RetrievalModeUnavailable(f"Unsupported retrieval context mode: {context_mode}")


def corpus_retrieval_contexts(
    case: dict[str, Any],
    context_mode: str,
    top_k: int,
    resources: EvalResources | None,
) -> list[str]:
    """Retrieve contexts for one question from the shared dataset corpus."""
    ensure_repo_root_on_path()
    from src.core.contracts import SourcePlan

    if resources is None:
        raise RetrievalModeUnavailable("Corpus retrieval resources were not initialized.")

    if context_mode == "langchain_chroma":
        if resources.langchain_retriever is None:
            raise RetrievalModeUnavailable("LangChain-Chroma resources were not initialized.")
        candidates = resources.langchain_retriever.retrieve(
            chat_id="document-qa-eval-corpus",
            source_plan=SourcePlan(
                source="document_memory",
                enabled=True,
                query=str(case["question"]),
                limit=top_k,
            ),
        )
        return [candidate.content for candidate in candidates]

    raise RetrievalModeUnavailable(f"Unsupported retrieval context mode: {context_mode}")


def ensure_repo_root_on_path() -> None:
    """Allow this standalone eval script to import src modules."""
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def print_summary(
    results: list[EvalResult],
    context_mode: str,
    retrieval_scope: str = "isolated",
    top_k: int = 4,
    answer_mode: str = "oracle",
    model_name: str | None = None,
) -> None:
    """Print a concise deterministic summary."""
    total = len(results)
    print("Document QA eval scaffold")
    print("Mode: document QA eval")
    print(f"Answer mode: {answer_mode}")
    if model_name:
        print(f"Model: {model_name}")
    print(f"Retrieval scope: {retrieval_scope}")
    if context_mode == "langchain_chroma":
        print("Retrieval: LangChain-Chroma document RAG backend.")
    else:
        print("Retrieval: placeholder context, not real retrieval.")
    if answer_mode == "oracle":
        print("Oracle answers are placeholders; retrieval metrics are meaningful.")
    else:
        print("Model answers are generated from retrieved contexts.")
    print(f"Placeholder context mode: {context_mode}")
    print(f"top_k: {top_k}")
    print(f"total cases: {total}")
    print(f"answer_anchor_match rate: {rate(results, 'answer_anchor_match'):.2f}")
    print(f"expected_answer_match rate: {rate(results, 'expected_answer_match'):.2f}")
    print(f"answer_unknown rate: {rate(results, 'answer_unknown'):.2f}")
    print(f"context_evidence_hit@{top_k} rate: {rate(results, 'context_evidence_hit'):.2f}")
    print(
        f"context_answer_anchor_hit@{top_k} rate: "
        f"{rate(results, 'context_answer_anchor_hit'):.2f}"
    )
    print(
        f"context_expected_answer_hit@{top_k} rate: "
        f"{rate(results, 'context_expected_answer_hit'):.2f}"
    )
    failed_case_ids = [
        result.case_id
        for result in results
        if not (
            result.answer_anchor_match
            and result.expected_answer_match
            and result.context_evidence_hit
            and result.context_answer_anchor_hit
            and result.context_expected_answer_hit
        )
    ]
    print(f"failed case IDs: {failed_case_ids}")
    unknown_case_ids = [result.case_id for result in results if result.answer_unknown]
    print(f"unknown case IDs: {unknown_case_ids}")


def rate(results: list[EvalResult], field: str) -> float:
    """Return the fraction of results where a boolean field is true."""
    if not results:
        return 0.0
    passed = sum(1 for result in results if bool(getattr(result, field)))
    return passed / len(results)


if __name__ == "__main__":
    main()
