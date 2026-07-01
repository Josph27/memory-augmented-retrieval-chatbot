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
from src.config import AppConfig  # noqa: E402
from src.model_wrapper import ModelWrapper  # noqa: E402


DEFAULT_FIXTURE = Path(__file__).parent / "fixtures" / "tiny_sample.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the optional MemoryAgentBench lifecycle adapter."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_FIXTURE)
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
    parser.add_argument("--output", type=Path)
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
    model = (
        ModelWrapper(AppConfig.from_env()) if args.answer_mode == "model" else None
    )
    raw_replay_embedding_backend = (
        HuggingFaceReplayEmbeddingBackend(args.raw_replay_embedding_model)
        if args.enable_raw_replay_chunk_retrieval
        and args.raw_replay_retrieval_mode in {"embedding", "hybrid"}
        else None
    )
    examples = (
        load_huggingface_examples(
            args.dataset_id,
            split=args.split,
            limit=args.limit,
            question_limit=args.question_limit,
            context_chunk_chars=args.context_chunk_chars,
        )
        if args.dataset_id
        else load_examples(args.dataset, limit=args.limit)
    )
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
    )
    if args.output:
        write_jsonl_report(args.output, report)
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
