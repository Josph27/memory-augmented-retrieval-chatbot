# MAB Answer-Level Evaluation

> Held-out MemoryAgentBench answer evaluation with a judge model. Takes a
> manifest of MemoryAgentBench cases, replays their conversation histories
> through the production pipeline, generates answers, and grades correctness
> with a deterministic LLM judge.

## Purpose

This eval suite measures the quality of **generated answers** on a frozen
held-out subset of MemoryAgentBench. Unlike raw retrieval metrics (hit@k),
this scores the full pipeline end-to-end: memory ingestion → context assembly
→ answer generation → judge evaluation.

Each case connects a MemoryAgentBench conversation history to a specific
question. The history is ingested through the production `ProductionLikeHarness`
(with roleless-history structured-memory policy), then the question is
answered via `CoordinatorAgent + ChatAgent`, and the answer is graded by a
separate judge model.

## CLI Entry Point

```bash
uv run python -m evals.mab_answer_eval \
  --manifest evals/mab_answer_eval/manifest.json \
  --output-dir reports/mab_answer_eval/ \
  --judge-model gemini-2.5-pro
```

### Required

| Flag | Description |
|------|-------------|
| `--manifest` | JSON or YAML manifest of MAB cases |
| `--output-dir` | Directory for results, JSONL, and summary artifacts |
| `--judge-model` | Model used for answer correctness evaluation |

### Optional

| Flag | Description |
|------|-------------|
| `--execution-mode` | `native` or `graph` (overrides manifest) |
| `--answer-model` | Model for answer generation (defaults to`MODEL_NAME`) |
| `--judge-base-url` | Base URL for judge endpoint (defaults to `OPENAI_BASE_URL`) |
| `--secondary-judge-model` | Secondary judge for comparison artifacts |
| `--resume` | Skip already-completed cases; reuse cached answers |
| `--max-cases` | Run at most N cases |
| `--fail-fast` | Stop on first generation or judge error |
| `--dry-run` | Print execution plan without running |
| `--store-evidence-text` | Include selected evidence in output records |
| `--list-models` | List available model IDs from the configured endpoint |

## Manifest Format

JSON or YAML files with:

```json
{
  "name": "heldout-selection-v1",
  "version": 1,
  "seed": 42,
  "execution_mode": "native",
  "dataset_id": "ai-hyz/MemoryAgentBench",
  "cases": [
    {
      "dataset": "icl_banking77",
      "split": "test",
      "source_dataset": "banking77",
      "row_index": 0,
      "question_index": 0,
      "case_id": "banking77-test-0-q0",
      "question_type": "multiple_choice",
      "official_metric": "normalized_substring"
    }
  ]
}
```

`execution_mode` must be `native` or `graph`. `split` maps to the MAB
competency split (e.g., `test`, `nq`). `question_index` picks which of the
example's `questions[]` to answer (one case per question).

## Execution Modes

| Mode | Orchestration path |
|------|--------------------|
| `native` | `CoordinatorAgent` imperative pipeline (no LangGraph) |
| `graph` | LangGraph with SemanticRouter, evidence contract validation |

Both modes ingest conversation history identically — only the
retrieval/context path differs. Each mode produces separate answer and judge
records.

## Judge Integration

Uses `OpenAIJudgeClient` — a small deterministic client that calls the
configured judge model with `temperature=0`, `max_tokens=300`, and
`response_format={"type": "json_object"}`.

The judge prompt (`mab-correctness-judge-v2-deepseek`) evaluates:

- **correctness**: semantic match with reference answer
- **completeness**: whether all required information is present

The judge does **not** evaluate faithfulness or hallucination. Prompt schema:

```json
{"correct": true, "complete": true, "brief_reason": "Concise reason."}
```

Parse repair: if the first response is not valid JSON, a single repair request
is sent. If that also fails, the case is marked as a judge failure.

## Metrics

Three official metrics, selected per-case from the manifest's `official_metric` field:

| Metric | Pass condition |
|--------|---------------|
| `normalized_substring` | Normalized reference text appears anywhere in normalized prediction |
| `normalized_exact_match` | Normalized prediction equals a normalized reference |
| `normalized_token_f1` | F1 score ≥ 0.5 over normalized tokens |

Per-dataset output normalization (for `icl_banking77` and `detective_qa`):

- `icl_banking77`: extracts a single numeric label from the prediction.
- `detective_qa`: extracts `"answer"` fields from JSON payloads or resolves
  single option labels (A–D) to full reference strings.

## Artifact I/O

All output is deterministic and atomic (temp-file → rename).

| File | Contents |
|------|----------|
| `results.jsonl` | One record per case: generated answer, judge result, context diagnostics, latency |
| `summary.json` | Pass rates, latencies, token distributions, dataset counts |
| `failures.jsonl` | Generation/judge failures with error messages |
| `disagreements.jsonl` | Cases where official metric and judge disagree |
| `judge_comparison.json` | Cross-judge-model agreement comparison |
| `run_metadata.json` | Full run configuration and call counts |

Each `results.jsonl` record includes:

- `case_id`, `dataset`, `execution_mode`, `question_type`
- `generated_answer`, `reference_answer`
- `judge`: `correct`, `complete`, `brief_reason`
- `official_metric`: `passed`, `score`
- `context_diagnostics`: selected source types, evidence contract, token usage, gold candidate rank, drop reasons
- `latency_ms`: `total`, `generation`, `judge`
- `answer_cache_key`, `judge_cache_key`, `result_identity` for resume support

### Resume

`--resume` reads existing `results.jsonl`, skips completed cases (same
answer+judge key), and reuses cached answers for cases that have an answer
record but no completed judge.

Answer and judge caches are content-addressed (SHA-256 of configuration +
question + answer). Changing any parameter produces new cache keys.

## File Index

| File | Lines | Role |
|------|-------|------|
| `__main__.py` | 137 | CLI entry point, arg parsing, wiring |
| `__init__.py` | 1 | Module docstring |
| `schemas.py` | 83 | Data models: `ManifestCase`, `AnswerManifest`, `JudgeResult`, `AnswerExecution`, `EvaluationModels` |
| `manifest.py` | 93 | Manifest loading, validation, case resolution from HuggingFace datasets |
| `runner.py` | 515 | `MABAnswerExecutor`, `run_evaluation()`, answer caching, `ProductionLikeHarness` integration |
| `judge.py` | 139 | `OpenAIJudgeClient`, judge prompt, parse/repair |
| `metrics.py` | 200 | `normalized_substring`, `normalized_exact_match`, `normalized_token_f1`, per-dataset normalization |
| `artifacts.py` | 214 | JSONL append, atomic writes, summary generation, judge comparison, distribution stats |
