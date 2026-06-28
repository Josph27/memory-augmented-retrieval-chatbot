# LongMemEval Pilot Adapter

This directory contains an **unofficial external-benchmark adapter scaffold**
for LongMemEval-style long-term conversation memory cases. It does not
implement or claim the official LongMemEval leaderboard scorer.

The adapter provides:

- normalization of common LongMemEval-style fields into a stable local schema;
- isolated SQLite state for every case;
- execution through the existing `CoordinatorAgent`, dispatcher, reranker,
  context manager, answer path, and `WorkflowTrace`;
- `recent_only` and `full` pilot comparisons;
- deterministic mock mode for tests;
- opt-in configured model mode;
- transparent exact/contains, abstention, and optional evidence-retrieval
  checks;
- JSON report export.

## Dataset handling

Benchmark datasets are intentionally not committed. Pass a local JSON or JSONL
path with `--dataset-path`. The loader recognizes normalized fields and common
aliases including:

- `question_id` / `case_id`
- `question`
- `answer` / `gold_answer`
- `question_type`
- `haystack_sessions` / `sessions` / `history`
- optional textual `expected_evidence`

The exact public dataset release may contain additional metadata. Unrecognized
fields are preserved under case metadata.

## Modes

### Memory modes

- `recent_only`: stores all history in the current chat, while the real recent
  retriever exposes only its configured recent window.
- `full`: stores sessions as previous chats and creates deterministic
  transcript-backed `previous_chat_gist` rows, then uses the existing gist
  retriever. This avoids injecting gold answers into memory.
- `structured` and `structured_vector`: reserved CLI values. The first scaffold
  rejects them clearly because safe preparation requires model-derived memory
  extraction and index lifecycle handling. It does not fake structured memory
  from gold answers.

The controlled route isolates the memory-mode comparison. This adapter does not
evaluate production `RoutingAgent` classification accuracy.

### Answer modes

- `mock`: deterministic fixture/gold answer, no API calls. This validates the
  adapter, storage, retrieval, context, scoring, and report contracts. Its
  answer score is not meaningful benchmark evidence.
- `model`: opt-in use of the existing configured `ModelWrapper`. This is the
  mode required for an answer-quality pilot.

## Commands

Offline fixture smoke test:

```bash
uv run python evals/longmemeval_adapter/run_longmemeval_adapter.py \
  --fixture \
  --answer-mode mock
```

Small full-memory model pilot:

```bash
uv run python evals/longmemeval_adapter/run_longmemeval_adapter.py \
  --dataset-path path/to/longmemeval.jsonl \
  --limit 20 \
  --memory-mode full \
  --answer-mode model \
  --output reports/longmemeval_pilot_full_model.json
```

Recent-window baseline:

```bash
uv run python evals/longmemeval_adapter/run_longmemeval_adapter.py \
  --dataset-path path/to/longmemeval.jsonl \
  --limit 20 \
  --memory-mode recent_only \
  --answer-mode model \
  --output reports/longmemeval_pilot_recent_only_model.json
```

## Report interpretation

The report is labelled `longmemeval_pilot_adapter` and uses
`unofficial_normalized_exact_contains` scoring. It includes:

- total cases and failed case IDs;
- normalized contains/exact rates;
- abstention accuracy when applicable;
- retrieval hit rate only when textual expected evidence is supplied;
- average adapter latency;
- per-question-type summaries;
- retrieved source/candidate snippets;
- context source inclusion and workflow trace summaries.

Compare `recent_only` and `full` using the same dataset, limit, model, and
configuration. Record the model and endpoint configuration separately.

## Limitations and next work

- This is not the official LongMemEval scorer or leaderboard protocol.
- Mock answer results validate plumbing, not model quality.
- `full` currently represents prior sessions as deterministic transcript-backed
  gists; it does not run model-based consolidation over every benchmark case.
- Structured and structured-vector preparation are explicit future adapter
  stages.
- Public benchmark metadata/evidence may need release-specific mapping.
- Large runs need cost, latency, checkpointing, and failure-resume controls.
- Reports can contain benchmark conversation text and should be reviewed before
  committing.
