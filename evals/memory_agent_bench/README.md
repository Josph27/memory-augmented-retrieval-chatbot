# MemoryAgentBench Evaluation Adapter

**TL;DR:** Optional pilot adapter that replays external
[HuggingFace MemoryAgentBench](https://huggingface.co/datasets/ai-hyz/MemoryAgentBench)
sessions through the production typed-memory pipeline and scores memory recall
against gold answers without requiring the benchmark's official scorer. Mock
answer mode isolates retrieval/context quality from answer-generation
confidence.

---

## Design goals

- Replay incremental multi-session conversations exactly as the benchmark models them.
- Test retrieval → context selection → evidence coverage without LLM-judge
  complexity.
- Keep the adapter optional: no dependency on `datasets` unless you run it.
- Expose retrieval-failure stages so the developer can localise problems
  (retrieval vs. selection vs. truncation vs. budget).

---

## Two execution modes

### 1. Mock answer (default)

The model stub always answers with the **first gold answer** for a question.
Only one metric matters:

| Metric | Meaning |
|---|---|
| `normalized_substring_match` | Does the correct snippet appear somewhere in retrieved context? |

This gives a pure retrieval/context-pipeline score — answer generation is
not part of the measurement.

### 2. Model answer (`--answer-mode model`)

Uses a real `ModelWrapper` for answer generation. Adds:

| Metric | Meaning |
|---|---|
| `exact_match` | Prediction text equals a gold answer (normalised) |
| `substring_match` | Gold answer appears in prediction |
| `evidence_contains_answer` | Gold answer appears in the retrieved context sent to the LLM |

---

## ProductionLikeHarness

`ProductionLikeHarness` (`adapter.py`) recreates the full typed-memory
lifecycle in an isolated temp SQLite database:

1. **Session replay** — each benchmark session becomes one chat; chunks are
   injected as user-assistant pairs. Sessions are ended between replays to
   trigger `ChatEndAction` + previous-chat gisting.
2. **Question handling** — a fresh question chat is created; the coordinator
   runs one turn with `task_context="memory_qa"` and fixture-assisted routing.
3. **Lifecycle** — structured memory updates run through a
   `RecordingNoopUpdater` (mock mode) or the real `StructuredMemoryUpdater`
   (model mode). `SkipStructuredMemoryForRolelessHistory` prevents LangMem
   from trying to extract structured memories from role-less benchmark
   contexts.

Key design decisions:

- **Temp SQLite**: no contamination of the production database.
- **FixedBenchmarkRoutePlanner**: exposes `recent_messages`,
  `structured_memory`, `previous_chat_gist`, `raw_message_span`, and
  `current_chat_span` at confidence 1.0 — document memory is explicitly
  disabled.
- **QueryEchoExcludingRecentRetriever**: prevents the question text from being
  counted as "recent memory" for the same-turn retrieval.
- **`ROLELESS_HISTORY`** markers: warn that benchmark sessions are not
  conversational — gist extraction and structured memory policies are
  explicitly controlled.

---

## Raw replay diagnostics (`raw_replay.py`)

An eval-only raw-chunk retriever supplements the production retrievers for
diagnostic purposes. Three ranking modes:

| Mode | Behaviour |
|---|---|
| `lexical` (default) | Query term overlap on replay chunk text |
| `embedding` | Cosine similarity via `SentenceTransformers` |
| `hybrid` | Lexical + embedding with downstream dedup |

Diagnostic output per question:

- `raw_replay_gold_literal_found` — gold answer text present in any chunk.
- `raw_replay_gold_message_found` — gold answer mapped to a specific message ID.
- `raw_replay_reached_context` — at least one raw-replay chunk survived into
  the context packet.
- `raw_replay_gold_rank` (when applicable) — post-hoc rank of the gold-bearing
  chunk.

The raw replay retriever is **never the production path** — it is an eval-only
diagnostic gated by `--enable-raw-replay-chunk-retrieval`.

---

## Selected suites (`selected_suite.py`)

Three fixed subsets of MemoryAgentBench designed for repeatable smoke tests:

| Suite | Split | Sources | Max questions |
|---|---|---|---|
| `ruler_qa1` | `Accurate_Retrieval` | `ruler_qa1_197K` only | 20/each |
| `test_time_learning` | `Test_Time_Learning` | all | 1/each |
| `aligned` | Both above | `ruler_qa1_197K` + all | 21/each |

Dataset ID: `ai-hyz/MemoryAgentBench`. HuggingFace `datasets` is required.

Selected-suite execution skips raw replay and forces mock-answer mode. The
results validate that the typed-memory pipeline does not regress against
known MemoryAgentBench cases.

---

## Dataset loading (`loader.py`)

Two modes:

1. **Local JSON/JSONL** — `load_examples(path)` handles native fixture files
   (used for `--dataset`).
2. **HuggingFace streaming** — `load_huggingface_examples()` streams from
   HuggingFace with source-dataset filtering (include/exclude allowlists),
   competency-split selection, and question-limit capping.

The `normalize_record()` function converts arbitrary external formats into the
internal `MABenchExample` schema, handling `context` → chunked `sessions`,
answer normalisation, and metadata stitching.

---

## Schemas (`schemas.py`)

Two frozen dataclasses with validation:

| Type | Fields |
|---|---|
| `MABenchSession` | `session_id`, `chunks` (non-empty) |
| `MABenchExample` | `example_id`, `competency`, `sessions` (≥1), `questions`, `answers` (aligned), `metadata` |

All fields are validated at construction — empty IDs, empty chunks, or
mismatched question/answer counts raise `ValueError`.

---

## Metrics (`metrics.py`)

Deterministic, no LLM judge. `score_answer()` returns:

- `exact_match` — normalised prediction equals a gold.
- `substring_match` — gold appears (case-insensitive) in prediction.
- `normalized_substring_match` — gold appears after punctuation-stripping + whitespace collapsing.
- `evidence_contains_answer` — gold appears in retrieved context.

`rank_diagnostics` (in `raw_replay.py`) computes MRR and Hit@k across
eval-only raw-replay candidates.

---

## Running

```bash
# Mock mode (retrieval-only quality):
python -m evals.memory_agent_bench.run_memory_agent_bench

# Selected suite (requires HuggingFace datasets):
python -m evals.memory_agent_bench.run_memory_agent_bench \
  --selected-suite aligned --limit 50

# Model mode (answer quality):
python -m evals.memory_agent_bench.run_memory_agent_bench \
  --answer-mode model --dataset-id ai-hyz/MemoryAgentBench

# Raw replay diagnostics:
python -m evals.memory_agent_bench.run_memory_agent_bench \
  --enable-raw-replay-chunk-retrieval --raw-replay-retrieval-mode hybrid
```

Key flags:

| Flag | Default | Purpose |
|---|---|---|
| `--answer-mode` | `mock` | `mock` or `model` |
| `--dataset-id` | — | HuggingFace dataset (overrides `--dataset`) |
| `--split` | `Conflict_Resolution` | Competency split |
| `--limit` | — | Max examples |
| `--selected-suite` | — | Fixed suite: `ruler_qa1`, `test_time_learning`, `aligned` |
| `--enable-raw-replay-chunk-retrieval` | off | Diagnostic raw-chunk retriever |
| `--raw-replay-retrieval-mode` | `lexical` | `lexical`, `embedding`, or `hybrid` |
| `--enable-cross-encoder` | off | Cross-encoder reranker for eval |
| `--output` | — | Report JSONL path |

---

## Limitations

- Not an official MemoryAgentBench scorer — the run header explicitly sets
  `official_scoring: false`.
- Mock mode only measures retrieval quality, not answer-consistency or
  hallucination rates.
- The adapter requires one ChatLifecycle (ChatEndAction) per session. This is
  faithful to production but limits throughput to ~1 example/second.
- Raw replay is an eval-only diagnostic — it never feeds results back into
  the production pipeline.

---

## File index

| File | Lines | Role |
|---|---|---|
| `run_memory_agent_bench.py` | 189 | CLI entry point, argument parsing, selected-suite dispatch |
| `adapter.py` | 482 | `ProductionLikeHarness`, `run_example()`, evidence diagnostics, answer scoring |
| `schemas.py` | 36 | `MABenchExample`, `MABenchSession` frozen dataclasses |
| `loader.py` | 215 | JSON/JSONL + HuggingFace dataset loading, record normalisation |
| `runner.py` | 122 | `run_benchmark()`, `summarize()`, `write_jsonl_report()` |
| `metrics.py` | 49 | `score_answer()` — deterministic substring/exact match |
| `raw_replay.py` | 543 | `EvalRawReplayChunkRetriever`, embedding/lexical/hybrid modes, rank diagnostics |
| `selected_suite.py` | 254 | `SELECTED_SUITES`, `load_selected_suite()`, `run_selected_suite()` |
| `selection.py` | 155 | `filter_likely_single_evidence()` — heuristic question filtering |
| `__init__.py` | 3 | Package marker |
