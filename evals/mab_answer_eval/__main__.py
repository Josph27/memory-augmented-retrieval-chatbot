from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from openai import OpenAI
from openai import OpenAIError

from evals.mab_answer_eval.judge import OpenAIJudgeClient
from evals.mab_answer_eval.manifest import load_manifest
from evals.mab_answer_eval.runner import (
    EvaluationAnswerModel,
    MABAnswerExecutor,
    RunOptions,
    run_evaluation,
)
from evals.mab_answer_eval.schemas import EvaluationModels
from src.config import AppConfig
from src.model_wrapper import ModelWrapper


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run held-out MemoryAgentBench answer-level evaluation."
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--execution-mode", choices=("native", "graph"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--answer-model")
    parser.add_argument("--judge-model")
    parser.add_argument("--judge-base-url")
    parser.add_argument("--secondary-judge-model")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--store-evidence-text", action="store_true")
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List model IDs exposed by the configured OpenAI-compatible endpoint.",
    )
    args = parser.parse_args()
    config = AppConfig.from_env()
    if args.list_models:
        client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
        )
        try:
            model_ids = sorted(model.id for model in client.models.list().data)
        except OpenAIError as error:
            print(
                json.dumps(
                    {
                        "models": None,
                        "endpoint_model_listing_available": False,
                        "error": f"{type(error).__name__}: {error}"[:500],
                    },
                    indent=2,
                )
            )
            return
        print(
            json.dumps(
                {
                    "models": model_ids,
                    "endpoint_model_listing_available": True,
                    "error": None,
                },
                indent=2,
            )
        )
        return
    if args.manifest is None or args.output_dir is None:
        parser.error("--manifest and --output-dir are required")
    manifest = load_manifest(args.manifest)
    execution_mode = args.execution_mode or manifest.execution_mode
    answer_model = args.answer_model or os.getenv("ANSWER_MODEL") or config.model_name
    judge_model = args.judge_model or os.getenv("JUDGE_MODEL")
    if not judge_model:
        parser.error("configure --judge-model or JUDGE_MODEL explicitly")
    judge_base_url = (
        args.judge_base_url
        or os.getenv("JUDGE_BASE_URL")
        or config.openai_base_url
    ).rstrip("/")
    judge_api_key = os.getenv("JUDGE_API_KEY")
    if not args.dry_run and not judge_api_key:
        parser.error("JUDGE_API_KEY is required for a real judge run")
    secondary = args.secondary_judge_model or os.getenv("SECONDARY_JUDGE_MODEL")
    models = EvaluationModels(
        answer_model,
        judge_model,
        secondary,
        judge_endpoint=judge_base_url,
    )
    options = RunOptions(
        output_dir=args.output_dir,
        execution_mode=execution_mode,
        resume=args.resume,
        max_cases=args.max_cases,
        fail_fast=args.fail_fast,
        dry_run=args.dry_run,
        store_evidence_text=args.store_evidence_text,
    )
    executor = None
    judge_client = None
    if not args.dry_run:
        answer_wrapper = EvaluationAnswerModel(
            ModelWrapper(config, model_name=answer_model)
        )
        executor = MABAnswerExecutor(
            model=answer_wrapper,
            config=config,
            execution_mode=execution_mode,
        )
        judge_client = OpenAIJudgeClient(
            config,
            judge_model,
            base_url=judge_base_url,
            api_key=judge_api_key,
        )
    report = run_evaluation(
        manifest,
        models=models,
        config=config,
        options=options,
        executor=executor,
        judge_client=judge_client,
    )
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
