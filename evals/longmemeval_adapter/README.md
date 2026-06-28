# LongMemEval Pilot Adapter

This directory contains an **unofficial external-benchmark adapter scaffold**
for LongMemEval-style long-term conversation memory cases. It does not
implement or claim the official LongMemEval leaderboard scorer.

The adapter provides:

- normalization of common LongMemEval-style fields into a stable local schema;
- isolated SQLite state for every case;
- execution through the existing `CoordinatorAgent`, dispatcher, reranker,
  context manager, answer path, and `WorkflowTrace`;
- `recent_only`, `gist_only`, `span_retrieval`, and `full` comparisons;
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

### Why message-span retrieval was added

The first pilot represented every previous session as one pseudo-gist containing
the complete transcript. Long sessions were noisy, lexical matches were coarse,
and candidates frequently exceeded the `ContextManagerAgent` source budget.
That representation remains available as `gist_only` for comparison, but it is
not the recommended LongMemEval retrieval unit.

The adapter now persists original session messages and builds bounded,
overlapping role-labelled spans. Oversized individual messages are split into
overlapping character windows so evidence beyond their beginning remains
retrievable. Every span preserves the benchmark case/session IDs, stable
start/end message IDs, message count, span index, and retrieval metadata.

The eval-only lexical span retriever returns standard
`MemoryCandidate(source="raw_message_span")` objects. Existing reranking and
context budgeting can therefore process the spans without changing normal
chatbot behavior.

### Memory modes

- `recent_only`: stores all history in the current chat, while the real recent
  retriever exposes only its configured recent window.
- `gist_only`: preserves the original whole-session pseudo-gist behavior for
  comparison.
- `span_retrieval`: retrieves compact message spans without pseudo-gists.
- `full`: combines message-span retrieval with the existing pseudo-gist path.
  Spans are the compact evidence representation; pseudo-gists remain an
  episodic/comparison source. Neither representation injects gold answers.
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

CrossEncoder span pilot:

```bash
uv run python evals/longmemeval_adapter/run_longmemeval_adapter.py \
  --dataset-path path/to/longmemeval.json \
  --limit 20 \
  --memory-mode span_retrieval \
  --answer-mode model \
  --reranker-mode cross_encoder \
  --output reports/longmemeval_pilot_span_cross_encoder.json
```

CrossEncoder/hybrid modes use the existing lazy backend and can download/load
the configured model. Normal tests use deterministic reranking and never load
it.

## Report interpretation

The report is labelled `longmemeval_pilot_adapter` and uses
`unofficial_normalized_exact_contains` scoring. It includes:

- total cases and failed case IDs;
- normalized contains/exact rates;
- abstention accuracy when applicable;
- retrieval hit rate only when textual expected evidence is supplied;
- average adapter latency;
- context inclusion rate, average included candidates, and empty-context cases;
- retrieved source counts and average retrieved candidates;
- reranker mode and CrossEncoder usage count;
- `"I don't know"` answer rate;
- per-question-type summaries;
- retrieved source/candidate snippets;
- context source inclusion and workflow trace summaries.

Compare `recent_only` and `full` using the same dataset, limit, model, and
configuration. Record the model and endpoint configuration separately.
For retrieval diagnosis, also compare `gist_only` with `span_retrieval`.

## Limitations and next work

- This is not the official LongMemEval scorer or leaderboard protocol.
- Mock answer results validate plumbing, not model quality.
- Span candidate generation is lexical. Semantically paraphrased questions can
  still require better first-stage retrieval; CrossEncoder only reranks spans
  that lexical retrieval returned.
- `full` retains deterministic transcript-backed pseudo-gists but no longer
  relies on them as the only history representation.
- The adapter does not run model-based consolidation over every benchmark case.
- Structured and structured-vector preparation are explicit future adapter
  stages.
- Public benchmark metadata/evidence may need release-specific mapping.
- Large runs need cost, latency, checkpointing, and failure-resume controls.
- Reports can contain benchmark conversation text and should be reviewed before
  committing.
