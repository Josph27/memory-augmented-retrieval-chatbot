from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

try:
    from .metrics import (
        answer_contains_anchor,
        answer_contains_expected,
        context_contains_answer_anchor,
        context_contains_evidence,
        ragas_compatible_row,
    )
except ImportError:
    from metrics import (
        answer_contains_anchor,
        answer_contains_expected,
        context_contains_answer_anchor,
        context_contains_evidence,
        ragas_compatible_row,
    )


DEFAULT_DATASET = Path(__file__).parent / "datasets" / "squad_style_sample.jsonl"
RETRIEVAL_CONTEXT_MODES = {"keyword_retrieval", "vector_retrieval", "hybrid_retrieval"}
VECTOR_BACKEND_CHOICES = ("sqlite_json", "sqlite_vec", "in_memory")


@dataclass(frozen=True)
class EvalResult:
    """One deterministic scaffold result."""

    case_id: str
    answer_anchor_match: bool
    expected_answer_match: bool
    context_evidence_hit: bool
    context_answer_anchor_hit: bool
    context_expected_answer_hit: bool
    ragas_row: dict[str, Any]


@dataclass(frozen=True)
class EvalResources:
    """Reusable optional resources for one eval run."""

    embedder: Any | None = None
    corpus_database: Any | None = None
    corpus_vector_store: Any | None = None
    temp_directory: Any | None = None
    vector_backend: str | None = None


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
            "keyword_retrieval",
            "vector_retrieval",
            "hybrid_retrieval",
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
        "--vector-backend",
        choices=VECTOR_BACKEND_CHOICES,
        default=None,
        help="Vector backend for vector/hybrid evals. Defaults to VECTOR_BACKEND env.",
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
            vector_backend=args.vector_backend,
        )
        results = [
            evaluate_case(
                case,
                context_mode=args.context_mode,
                top_k=args.top_k,
                resources=resources,
                retrieval_scope=args.retrieval_scope,
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
        vector_backend=resources.vector_backend,
    )


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
) -> EvalResult:
    """Evaluate one case with oracle placeholders."""
    contexts = placeholder_contexts(
        case,
        context_mode=context_mode,
        top_k=top_k,
        resources=resources,
        retrieval_scope=retrieval_scope,
    )
    answer = str(case["expected_answer"])
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
            "mode": "scaffold_oracle_placeholder",
        },
    )
    return EvalResult(
        case_id=str(case["case_id"]),
        answer_anchor_match=answer_contains_anchor(answer, answer_anchor),
        expected_answer_match=answer_contains_expected(answer, expected_answer),
        context_evidence_hit=context_contains_evidence(contexts, supporting_evidence),
        context_answer_anchor_hit=context_contains_answer_anchor(contexts, answer_anchor),
        context_expected_answer_hit=context_contains_answer_anchor(contexts, expected_answer),
        ragas_row=ragas_row,
    )


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
    vector_backend: str | None = None,
) -> EvalResources:
    """Create reusable resources once for an eval run."""
    embedder = None
    selected_vector_backend = normalize_vector_backend(vector_backend)

    if context_mode in {"vector_retrieval", "hybrid_retrieval"}:
        ensure_repo_root_on_path()
        from src.embeddings.base import EmbedderUnavailableError
        from src.embeddings.sentence_transformer_embedder import SentenceTransformerEmbedder

        try:
            embedder = SentenceTransformerEmbedder()
        except EmbedderUnavailableError as error:
            msg = (
                f"Skipping {context_mode}: embeddings/vector backend unavailable. "
                f"{error}"
            )
            raise RetrievalModeUnavailable(msg) from error

    if retrieval_scope != "corpus" or context_mode not in RETRIEVAL_CONTEXT_MODES:
        return EvalResources(embedder=embedder, vector_backend=selected_vector_backend)

    if cases is None:
        raise RetrievalModeUnavailable("Corpus retrieval requires dataset cases.")

    return build_corpus_resources(
        cases=cases,
        context_mode=context_mode,
        embedder=embedder,
        vector_backend=selected_vector_backend,
    )


def build_corpus_resources(
    cases: list[dict[str, Any]],
    context_mode: str,
    embedder: Any | None = None,
    vector_backend: str = "sqlite_json",
) -> EvalResources:
    """Ingest the full eval dataset into one temporary document corpus."""
    ensure_repo_root_on_path()
    from src.database import Database
    from src.documents.embedding_indexer import DocumentEmbeddingIndexer
    from src.documents.ingestion import DocumentIngestionService

    temp_directory = TemporaryDirectory()
    database = Database(Path(temp_directory.name) / "document_eval_corpus.db")
    ingestion = DocumentIngestionService(database)
    document_ids: list[int] = []
    seen_texts: set[str] = set()
    for case in cases:
        document_text = str(case["document_text"])
        if document_text in seen_texts:
            continue
        seen_texts.add(document_text)
        result = ingestion.ingest_text_document(
            title=str(case["document_id"]),
            text=document_text,
            source=str(case.get("source", "document_qa_eval")),
            metadata={"case_id": case.get("case_id"), "scope": "corpus"},
        )
        document_ids.append(result.document_id)

    vector_store = None
    if context_mode in {"vector_retrieval", "hybrid_retrieval"}:
        if embedder is None:
            raise RetrievalModeUnavailable("Corpus vector retrieval requires an embedder.")
        vector_store = create_vector_store(database, vector_backend)
        indexer = DocumentEmbeddingIndexer(database)
        for document_id in document_ids:
            indexer.index_document_chunks(
                document_id=document_id,
                embedder=embedder,
                vector_store=vector_store,
            )

    return EvalResources(
        embedder=embedder,
        corpus_database=database,
        corpus_vector_store=vector_store,
        temp_directory=temp_directory,
        vector_backend=vector_backend,
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
    from src.database import Database
    from src.documents.embedding_indexer import DocumentEmbeddingIndexer
    from src.documents.ingestion import DocumentIngestionService
    from src.retrieval.document_retriever import DocumentRetriever

    with TemporaryDirectory() as directory:
        database = Database(Path(directory) / "document_eval.db")
        ingestion = DocumentIngestionService(database)
        result = ingestion.ingest_text_document(
            title=str(case["document_id"]),
            text=str(case["document_text"]),
            source=str(case.get("source", "document_qa_eval")),
            metadata={"case_id": case.get("case_id")},
        )
        retrieval_mode = {
            "keyword_retrieval": "keyword",
            "vector_retrieval": "vector",
            "hybrid_retrieval": "hybrid",
        }[context_mode]
        embedder = None
        vector_store = None
        if retrieval_mode in {"vector", "hybrid"}:
            embedder = resources.embedder if resources else None
            if embedder is None:
                msg = f"Skipping {context_mode}: embedding model was not initialized."
                raise RetrievalModeUnavailable(msg)
            vector_backend = resources.vector_backend if resources else normalize_vector_backend(None)
            vector_store = create_vector_store(database, vector_backend)
            DocumentEmbeddingIndexer(database).index_document_chunks(
                document_id=result.document_id,
                embedder=embedder,
                vector_store=vector_store,
            )
        candidates = DocumentRetriever(
            database=database,
            retrieval_mode=retrieval_mode,
            embedder=embedder,
            vector_store=vector_store,
        ).retrieve(
            chat_id="document-qa-eval",
            source_plan=SourcePlan(
                source="document_memory",
                enabled=True,
                query=str(case["question"]),
                limit=top_k,
            ),
        )
        return [candidate.content for candidate in candidates]


def create_vector_store(database: Any, backend_name: str) -> Any:
    """Create the configured vector store for document QA evals."""
    ensure_repo_root_on_path()
    from src.vectorstores.base import VectorStoreUnavailableError
    from src.vectorstores.in_memory_store import InMemoryVectorStore
    from src.vectorstores.sqlite_json_store import SQLiteJsonVectorStore
    from src.vectorstores.sqlite_vec_store import SQLiteVecVectorStore

    if backend_name == "sqlite_json":
        return SQLiteJsonVectorStore(database)
    if backend_name == "in_memory":
        return InMemoryVectorStore()
    if backend_name == "sqlite_vec":
        try:
            return SQLiteVecVectorStore(database)
        except VectorStoreUnavailableError as error:
            msg = f"Skipping vector/hybrid eval: VECTOR_BACKEND=sqlite_vec unavailable. {error}"
            raise RetrievalModeUnavailable(msg) from error
    raise RetrievalModeUnavailable(f"Unsupported vector backend: {backend_name}")


def normalize_vector_backend(vector_backend: str | None) -> str:
    """Normalize CLI/env vector backend selection."""
    selected = (vector_backend or os.getenv("VECTOR_BACKEND", "sqlite_json")).strip()
    if selected not in VECTOR_BACKEND_CHOICES:
        return "sqlite_json"
    return selected


def corpus_retrieval_contexts(
    case: dict[str, Any],
    context_mode: str,
    top_k: int,
    resources: EvalResources | None,
) -> list[str]:
    """Retrieve contexts for one question from the shared dataset corpus."""
    ensure_repo_root_on_path()
    from src.core.contracts import SourcePlan
    from src.retrieval.document_retriever import DocumentRetriever

    if resources is None or resources.corpus_database is None:
        raise RetrievalModeUnavailable("Corpus retrieval resources were not initialized.")

    retrieval_mode = retrieval_mode_for_context(context_mode)
    candidates = DocumentRetriever(
        database=resources.corpus_database,
        retrieval_mode=retrieval_mode,
        embedder=resources.embedder,
        vector_store=resources.corpus_vector_store,
    ).retrieve(
        chat_id="document-qa-eval-corpus",
        source_plan=SourcePlan(
            source="document_memory",
            enabled=True,
            query=str(case["question"]),
            limit=top_k,
        ),
    )
    return [candidate.content for candidate in candidates]


def retrieval_mode_for_context(context_mode: str) -> str:
    """Map eval context mode to document retriever mode."""
    return {
        "keyword_retrieval": "keyword",
        "vector_retrieval": "vector",
        "hybrid_retrieval": "hybrid",
    }[context_mode]


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
    vector_backend: str | None = None,
) -> None:
    """Print a concise deterministic summary."""
    total = len(results)
    print("Document QA eval scaffold")
    print("Mode: scaffold / oracle-placeholder answer")
    print(f"Retrieval scope: {retrieval_scope}")
    if context_mode in {"vector_retrieval", "hybrid_retrieval"}:
        print(f"Vector backend: {vector_backend or normalize_vector_backend(None)}")
    if context_mode == "keyword_retrieval":
        print("Retrieval: plain-text chunks with simple keyword scoring.")
    elif context_mode in {"vector_retrieval", "hybrid_retrieval"}:
        print(f"Retrieval: optional {context_mode.replace('_', ' ')}.")
    else:
        print("Retrieval: placeholder context, not real retrieval.")
    print("This does not evaluate real answer generation yet.")
    print(f"Placeholder context mode: {context_mode}")
    print(f"top_k: {top_k}")
    print(f"total cases: {total}")
    print(f"answer_anchor_match rate: {rate(results, 'answer_anchor_match'):.2f}")
    print(f"expected_answer_match rate: {rate(results, 'expected_answer_match'):.2f}")
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


def rate(results: list[EvalResult], field: str) -> float:
    """Return the fraction of results where a boolean field is true."""
    if not results:
        return 0.0
    passed = sum(1 for result in results if bool(getattr(result, field)))
    return passed / len(results)


if __name__ == "__main__":
    main()
