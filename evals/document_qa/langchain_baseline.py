from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .metrics import (
        context_contains_answer_anchor,
        context_contains_evidence,
    )
    from .run_document_qa_eval import DEFAULT_DATASET, load_jsonl
except ImportError:
    from metrics import (
        context_contains_answer_anchor,
        context_contains_evidence,
    )
    from run_document_qa_eval import DEFAULT_DATASET, load_jsonl


DEFAULT_TOP_K = 4
DEFAULT_VECTORSTORE = "faiss"
VECTORSTORE_CHOICES = ("faiss", "chroma")
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


@dataclass(frozen=True)
class LangChainBaselineResult:
    """One retrieval result from the eval-only LangChain baseline."""

    case_id: str
    context_evidence_hit: bool
    context_answer_anchor_hit: bool
    context_expected_answer_hit: bool
    contexts: list[str]


@dataclass(frozen=True)
class LangChainBaselineSummary:
    """Aggregated retrieval metrics for the LangChain baseline."""

    cases: int
    top_k: int
    vectorstore: str
    ctx_evidence: float
    ctx_anchor: float
    ctx_expected: float
    failed_case_ids: list[str]
    backend_used: str
    skipped: bool = False
    skipped_reason: str | None = None


class LangChainBaselineUnavailable(RuntimeError):
    """Raised when optional LangChain baseline dependencies are unavailable."""


def main() -> None:
    """Run an eval-only LangChain document retrieval baseline."""
    parser = argparse.ArgumentParser(description="Run LangChain document RAG baseline.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to document QA JSONL dataset.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help="Number of retrieved chunks per question.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of dataset cases to evaluate.",
    )
    parser.add_argument(
        "--vectorstore",
        choices=VECTORSTORE_CHOICES,
        default=DEFAULT_VECTORSTORE,
        help="LangChain vector store backend.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary after the text summary.",
    )
    args = parser.parse_args()

    cases = load_baseline_cases(args.dataset, limit=args.limit)
    try:
        summary = run_langchain_baseline(
            cases=cases,
            top_k=args.top_k,
            vectorstore=args.vectorstore,
        )
    except LangChainBaselineUnavailable as error:
        summary = skipped_summary(
            cases=len(cases),
            top_k=args.top_k,
            vectorstore=args.vectorstore,
            reason=str(error),
        )

    print_summary(summary)
    if args.json:
        print(json.dumps(summary_to_dict(summary), indent=2))


def load_baseline_cases(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Load document QA cases for the LangChain baseline."""
    cases = load_jsonl(path)
    if limit is None:
        return cases
    return cases[: max(0, limit)]


def run_langchain_baseline(
    cases: list[dict[str, Any]],
    top_k: int = DEFAULT_TOP_K,
    vectorstore: str = DEFAULT_VECTORSTORE,
) -> LangChainBaselineSummary:
    """Run corpus-level retrieval with optional LangChain components."""
    retriever, backend_used = build_langchain_retriever(
        cases=cases,
        vectorstore=vectorstore,
        top_k=top_k,
    )
    results = [
        evaluate_case_with_retriever(case=case, retriever=retriever, top_k=top_k)
        for case in cases
    ]
    return aggregate_results(
        results=results,
        top_k=top_k,
        vectorstore=vectorstore,
        backend_used=backend_used,
    )


def build_langchain_retriever(
    cases: list[dict[str, Any]],
    vectorstore: str,
    top_k: int,
):
    """Build a LangChain vectorstore retriever over the full dataset corpus."""
    splitter_class = import_recursive_text_splitter()
    vectorstore_class, backend_used = import_vectorstore_class(vectorstore)
    embeddings = build_embeddings()

    splitter = splitter_class(
        chunk_size=DEFAULT_CHUNK_SIZE,
        chunk_overlap=DEFAULT_CHUNK_OVERLAP,
        add_start_index=True,
    )
    texts, metadatas = split_unique_documents(
        cases=cases,
        splitter=splitter,
    )
    if not texts:
        raise LangChainBaselineUnavailable("No document text was available to index.")

    store = vectorstore_class.from_texts(
        texts=texts,
        embedding=embeddings,
        metadatas=metadatas,
    )
    return store.as_retriever(search_kwargs={"k": top_k}), backend_used


def split_unique_documents(cases: list[dict[str, Any]], splitter) -> tuple[list[str], list[dict]]:
    """Split deduplicated dataset documents with a LangChain text splitter."""
    texts: list[str] = []
    metadatas: list[dict] = []
    seen_texts: set[str] = set()
    for case in cases:
        document_text = str(case.get("document_text", ""))
        if not document_text.strip() or document_text in seen_texts:
            continue
        seen_texts.add(document_text)
        chunks = splitter.create_documents(
            [document_text],
            metadatas=[
                {
                    "document_id": case.get("document_id"),
                    "source": case.get("source"),
                    "case_id": case.get("case_id"),
                }
            ],
        )
        for chunk_index, chunk in enumerate(chunks):
            chunk_text = chunk.page_content.strip()
            if not chunk_text:
                continue
            metadata = dict(chunk.metadata)
            metadata["chunk_index"] = chunk_index
            texts.append(chunk_text)
            metadatas.append(metadata)
    return texts, metadatas


def evaluate_case_with_retriever(
    case: dict[str, Any],
    retriever,
    top_k: int,
) -> LangChainBaselineResult:
    """Evaluate one case against a LangChain retriever."""
    del top_k
    documents = retriever.invoke(str(case["question"]))
    contexts = [document.page_content for document in documents]
    expected_answer = str(case["expected_answer"])
    answer_anchor = str(case["answer_anchor"])
    supporting_evidence = str(case["supporting_evidence"])
    return LangChainBaselineResult(
        case_id=str(case["case_id"]),
        context_evidence_hit=context_contains_evidence(contexts, supporting_evidence),
        context_answer_anchor_hit=context_contains_answer_anchor(contexts, answer_anchor),
        context_expected_answer_hit=context_contains_answer_anchor(contexts, expected_answer),
        contexts=contexts,
    )


def aggregate_results(
    results: list[LangChainBaselineResult],
    top_k: int,
    vectorstore: str,
    backend_used: str,
) -> LangChainBaselineSummary:
    """Aggregate LangChain baseline retrieval metrics."""
    failed_case_ids = [
        result.case_id
        for result in results
        if not (
            result.context_evidence_hit
            and result.context_answer_anchor_hit
            and result.context_expected_answer_hit
        )
    ]
    return LangChainBaselineSummary(
        cases=len(results),
        top_k=top_k,
        vectorstore=vectorstore,
        ctx_evidence=rate(results, "context_evidence_hit"),
        ctx_anchor=rate(results, "context_answer_anchor_hit"),
        ctx_expected=rate(results, "context_expected_answer_hit"),
        failed_case_ids=failed_case_ids,
        backend_used=backend_used,
    )


def skipped_summary(
    cases: int,
    top_k: int,
    vectorstore: str,
    reason: str,
) -> LangChainBaselineSummary:
    """Build a summary row for unavailable optional dependencies."""
    return LangChainBaselineSummary(
        cases=cases,
        top_k=top_k,
        vectorstore=vectorstore,
        ctx_evidence=0.0,
        ctx_anchor=0.0,
        ctx_expected=0.0,
        failed_case_ids=[],
        backend_used="unavailable",
        skipped=True,
        skipped_reason=reason,
    )


def print_summary(summary: LangChainBaselineSummary) -> None:
    """Print a concise LangChain baseline summary."""
    print("LangChain document RAG retrieval baseline")
    print(f"cases: {summary.cases}")
    print(f"top_k: {summary.top_k}")
    print(f"vectorstore: {summary.vectorstore}")
    print(f"backend_used: {summary.backend_used}")
    print(f"skipped: {'yes' if summary.skipped else 'no'}")
    if summary.skipped_reason:
        print(f"skipped_reason: {summary.skipped_reason}")
    print(f"ctx_evidence: {summary.ctx_evidence:.2f}")
    print(f"ctx_anchor: {summary.ctx_anchor:.2f}")
    print(f"ctx_expected: {summary.ctx_expected:.2f}")
    print(f"failed case IDs: {summary.failed_case_ids}")


def summary_to_dict(summary: LangChainBaselineSummary) -> dict[str, Any]:
    """Return a JSON-ready baseline summary."""
    return {
        "cases": summary.cases,
        "top_k": summary.top_k,
        "vectorstore": summary.vectorstore,
        "backend_used": summary.backend_used,
        "skipped": summary.skipped,
        "skipped_reason": summary.skipped_reason,
        "ctx_evidence": summary.ctx_evidence,
        "ctx_anchor": summary.ctx_anchor,
        "ctx_expected": summary.ctx_expected,
        "failed_case_ids": summary.failed_case_ids,
    }


def rate(results: list[LangChainBaselineResult], field: str) -> float:
    """Return fraction of results where a boolean field is true."""
    if not results:
        return 0.0
    return sum(1 for result in results if bool(getattr(result, field))) / len(results)


def import_recursive_text_splitter():
    """Import LangChain's recursive text splitter."""
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        return RecursiveCharacterTextSplitter
    except ImportError as error:
        msg = (
            "LangChain text splitter is unavailable. Install optional dependency "
            "`langchain-text-splitters` to run the LangChain baseline."
        )
        raise LangChainBaselineUnavailable(msg) from error


def import_vectorstore_class(vectorstore: str):
    """Import a LangChain vector store class."""
    if vectorstore == "faiss":
        try:
            from langchain_community.vectorstores import FAISS

            return FAISS, "langchain_community.vectorstores.FAISS"
        except ImportError as error:
            msg = (
                "LangChain FAISS vector store is unavailable. Install optional "
                "dependencies such as `langchain-community` and `faiss-cpu`."
            )
            raise LangChainBaselineUnavailable(msg) from error

    if vectorstore == "chroma":
        try:
            from langchain_chroma import Chroma

            return Chroma, "langchain_chroma.Chroma"
        except ImportError:
            try:
                from langchain_community.vectorstores import Chroma

                return Chroma, "langchain_community.vectorstores.Chroma"
            except ImportError as error:
                msg = (
                    "LangChain Chroma vector store is unavailable. Install optional "
                    "dependencies such as `langchain-chroma` or `langchain-community` "
                    "and `chromadb`."
                )
                raise LangChainBaselineUnavailable(msg) from error

    raise LangChainBaselineUnavailable(f"Unsupported vectorstore: {vectorstore}")


def build_embeddings():
    """Build embeddings compatible with LangChain vector stores."""
    try:
        from langchain_core.embeddings import Embeddings
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        msg = (
            "Embedding dependencies are unavailable. Install `sentence-transformers` "
            "and LangChain core dependencies to run the LangChain baseline."
        )
        raise LangChainBaselineUnavailable(msg) from error

    class SentenceTransformerEmbeddings(Embeddings):
        """Tiny adapter from sentence-transformers to LangChain embeddings."""

        def __init__(self) -> None:
            self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [embedding.tolist() for embedding in self.model.encode(texts)]

        def embed_query(self, text: str) -> list[float]:
            return self.model.encode(text).tolist()

    return SentenceTransformerEmbeddings()


if __name__ == "__main__":
    main()
