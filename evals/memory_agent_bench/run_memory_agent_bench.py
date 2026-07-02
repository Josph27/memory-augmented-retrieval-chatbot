from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.memory_agent_bench.loader import (  # noqa: E402
    load_examples,
    load_huggingface_examples,
)
from evals.memory_agent_bench.runner import (  # noqa: E402
    run_benchmark,
    write_jsonl_report,
)
from evals.memory_agent_bench.raw_replay import (  # noqa: E402
    HuggingFaceReplayEmbeddingBackend,
)
from evals.memory_agent_bench.selection import (  # noqa: E402
    filter_likely_single_evidence,
)
from evals.memory_agent_bench.selected_suite import (  # noqa: E402
    OFFICIAL_DATASET_ID,
    SELECTED_SUITES,
    run_selected_suite,
    write_selected_jsonl,
)
from src.config import AppConfig  # noqa: E402
from src.model_wrapper import ModelWrapper  # noqa: E402
from src.orchestration.demo_orchestration import (  # noqa: E402
    LANGGRAPH_DEMO,
    NATIVE,
)
from src.retrieval.cross_encoder_reranker import (  # noqa: E402
    SentenceTransformersCrossEncoderBackend,
)


DEFAULT_FIXTURE = Path(__file__).parent / "fixtures" / "tiny_sample.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the optional MemoryAgentBench lifecycle adapter."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument(
        "--selected-suite",
        choices=SELECTED_SUITES,
        help="Run a fixed real-data suite through the native typed-memory path.",
    )
    parser.add_argument(
        "--dataset-id",
        help="Optional Hugging Face dataset id; overrides --dataset.",
    )
    parser.add_argument(
        "--split",
        default="Conflict_Resolution",
        help="External dataset competency split.",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--include-source-dataset",
        action="append",
        default=[],
        help="Eval-only exact metadata.source allowlist; repeat as needed.",
    )
    parser.add_argument(
        "--exclude-source-dataset",
        action="append",
        default=[],
        help="Eval-only exact metadata.source denylist; repeat as needed.",
    )
    parser.add_argument(
        "--filter-likely-single-evidence",
        action="store_true",
        help="Select questions with one literal, lexically related replay chunk.",
    )
    parser.add_argument(
        "--question-limit",
        type=int,
        help="Maximum questions evaluated from each external row.",
    )
    parser.add_argument(
        "--context-chunk-chars",
        type=int,
        default=4000,
        help="Bound for deterministic incremental context chunks.",
    )
    parser.add_argument("--answer-mode", choices=("mock", "model"), default="mock")
    parser.add_argument(
        "--orchestration-mode",
        choices=(NATIVE, LANGGRAPH_DEMO),
        default=NATIVE,
        help="Selected-suite context orchestration; native remains the baseline.",
    )
    parser.add_argument("--output", type=Path)
    cross_encoder_group = parser.add_mutually_exclusive_group()
    cross_encoder_group.add_argument(
        "--enable-cross-encoder",
        action="store_true",
        help="Use the current CrossEncoder reranker for this eval run only.",
    )
    cross_encoder_group.add_argument(
        "--disable-cross-encoder",
        action="store_true",
        help="Explicitly retain deterministic reranking for baseline runs.",
    )
    parser.add_argument(
        "--cross-encoder-model",
        default="BAAI/bge-reranker-v2-m3",
        help="Current CrossEncoder backend model used only when explicitly enabled.",
    )
    parser.add_argument("--cross-encoder-top-k", type=int, default=10)
    parser.add_argument("--cross-encoder-weight", type=float, default=0.65)
    parser.add_argument(
        "--enable-raw-replay-chunk-retrieval",
        action="store_true",
        help="Enable eval-only lexical retrieval over replayed raw chunks.",
    )
    parser.add_argument(
        "--raw-replay-top-k",
        type=int,
        default=8,
        help="Maximum eval-only raw replay candidates per question.",
    )
    parser.add_argument(
        "--raw-replay-max-chars",
        type=int,
        default=4000,
        help="Maximum characters retained in each eval-only replay candidate.",
    )
    parser.add_argument(
        "--raw-replay-retrieval-mode",
        choices=("lexical", "embedding", "hybrid"),
        default="lexical",
        help="Eval-only raw replay ranking mode; lexical remains the default.",
    )
    parser.add_argument(
        "--raw-replay-embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Embedding model used only for explicit embedding/hybrid runs.",
    )
    parser.add_argument(
        "--raw-replay-candidate-pool-size",
        type=int,
        default=50,
        help="Pre-context candidate pool used by eval-only raw replay ranking.",
    )
    parser.add_argument(
        "--no-finalize-sessions",
        action="store_true",
        help="Keep replay sessions active instead of invoking ChatEndAction.",
    )
    args = parser.parse_args()
    if args.selected_suite:
        if args.answer_mode != "mock":
            parser.error("selected suites currently require --answer-mode mock")
        if args.enable_raw_replay_chunk_retrieval:
            parser.error("selected suites do not allow raw replay diagnostics")
        cross_encoder_backend = (
            SentenceTransformersCrossEncoderBackend(args.cross_encoder_model)
            if args.enable_cross_encoder
            else None
        )
        report = run_selected_suite(
            args.selected_suite,
            dataset_id=args.dataset_id or OFFICIAL_DATASET_ID,
            limit=args.limit or 50,
            question_limit=args.question_limit,
            context_chunk_chars=args.context_chunk_chars,
            reranker_mode=(
                "cross_encoder" if args.enable_cross_encoder else "deterministic"
            ),
            cross_encoder_backend=cross_encoder_backend,
            cross_encoder_top_k=args.cross_encoder_top_k,
            cross_encoder_weight=args.cross_encoder_weight,
            orchestration_mode=args.orchestration_mode,
        )
        if args.output:
            write_selected_jsonl(args.output, report)
        print(json.dumps(report, indent=2, ensure_ascii=True))
        return
    model = (
        ModelWrapper(AppConfig.from_env()) if args.answer_mode == "model" else None
    )
    raw_replay_embedding_backend = (
        HuggingFaceReplayEmbeddingBackend(args.raw_replay_embedding_model)
        if args.enable_raw_replay_chunk_retrieval
        and args.raw_replay_retrieval_mode in {"embedding", "hybrid"}
        else None
    )
    selection_stats: dict[str, object] = {}
    examples = (
        load_huggingface_examples(
            args.dataset_id,
            split=args.split,
            limit=args.limit,
            question_limit=args.question_limit,
            context_chunk_chars=args.context_chunk_chars,
            include_source_datasets=tuple(args.include_source_dataset),
            exclude_source_datasets=tuple(args.exclude_source_dataset),
            selection_stats=selection_stats,
        )
        if args.dataset_id
        else load_examples(args.dataset, limit=args.limit)
    )
    if args.filter_likely_single_evidence:
        examples, heuristic_stats = filter_likely_single_evidence(examples)
        selection_stats.update(heuristic_stats)
    report = run_benchmark(
        examples,
        answer_mode=args.answer_mode,
        model=model,
        finalize_sessions=not args.no_finalize_sessions,
        raw_replay_enabled=args.enable_raw_replay_chunk_retrieval,
        raw_replay_top_k=args.raw_replay_top_k,
        raw_replay_max_chars=args.raw_replay_max_chars,
        raw_replay_retrieval_mode=args.raw_replay_retrieval_mode,
        raw_replay_embedding_backend=raw_replay_embedding_backend,
        raw_replay_candidate_pool_size=args.raw_replay_candidate_pool_size,
        dataset_selection=selection_stats,
    )
    if args.output:
        write_jsonl_report(args.output, report)
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
