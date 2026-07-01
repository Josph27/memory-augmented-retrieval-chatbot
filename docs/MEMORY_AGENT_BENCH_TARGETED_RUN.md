# MemoryAgentBench Targeted Run

## Goal

Run small official MemoryAgentBench subsets that are closer to the current
typed-memory system's strengths than `Conflict_Resolution`, then inspect
retrieval, ContextPacket evidence, provenance, and failure stages.

This is a mock-answer diagnostic run. It is not official benchmark scoring and
does not test generated-answer grounding.

## Environment

- Branch: `integration/playground-demo`
- Commit before run: `96d7f45`
- Dataset: official `ai-hyz/MemoryAgentBench` through Hugging Face
- Dataset access: available; unauthenticated Hub requests succeeded
- Splits: `Accurate_Retrieval`, `Test_Time_Learning`
- Rows: 5 per split
- Questions: 1 per row
- Answer mode: mock
- Routing: benchmark-controlled `FixedBenchmarkRoutePlanner`
- Orchestration: existing `CoordinatorAgent` adapter path
- Reranking: deterministic
- Storage: isolated temporary SQLite database per example
- Session finalization: `ChatEndAction`, once per selected row
- Live model calls: none
- LangGraph/Semantic Router v2: not used by this adapter

The runs include the committed anchor-preserving raw-span formatter because the
existing dispatcher and gist expander use that production retrieval code.

## Why These Splits

`Accurate_Retrieval` is relevant to evidence recall and ContextPacket
readiness. It tests whether information replayed into long histories can be
found and retained as context.

`Test_Time_Learning` is relevant to incremental replay and memory-lifecycle
wiring. In mock mode, however, the structured-memory backend is deliberately a
recording no-op. This run proves update-path invocation, not learned
classification or LangMem extraction quality.

`Conflict_Resolution` was intentionally excluded. Prior diagnostics showed that
it requires conflict-aware consolidation and distant multi-hop relation
assembly beyond the current single-window gist/span approach.

## Commands

```bash
uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --dataset-id ai-hyz/MemoryAgentBench \
  --split Accurate_Retrieval \
  --limit 5 \
  --question-limit 1 \
  --answer-mode mock \
  --output reports/memory_agent_bench_accurate_retrieval_mock_after_router_span.jsonl
```

```bash
uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --dataset-id ai-hyz/MemoryAgentBench \
  --split Test_Time_Learning \
  --limit 5 \
  --question-limit 1 \
  --answer-mode mock \
  --output reports/memory_agent_bench_test_time_learning_mock_after_router_span.jsonl
```

## Results Summary

| Diagnostic | Accurate Retrieval | Test-Time Learning |
|---|---:|---:|
| Examples completed | 5/5 | 5/5 |
| Questions reported | 5 | 5 |
| Incremental chunks replayed | 2,814 | 1,934 |
| Per-row chunks | 280, 516, 577, 793, 648 | 1,545, 103, 93, 93, 100 |
| ChatEndAction calls | 5 | 5 |
| Literal gold in ContextPacket | 2/5 | 4/5 |
| Provenance present | 5/5 | 5/5 |
| Stale/deactivated candidate present | 0/5 | 0/5 |
| WorkflowTrace errors | 0 | 0 |
| Generated-answer grounding tested | No | No |

Observed ContextPacket sources were `previous_chat_gist` and
`raw_message_span`. Every row reached the Coordinator path and exported route,
candidate, reranker, budget, context, provenance, lifecycle, and diagnostic
fields.

The normalized mock-answer match rate was 1.0 by construction: mock mode emits
the gold answer. It must not be interpreted as model accuracy.

## Accurate Retrieval Findings

### Literal evidence outcomes

- Two RULER QA rows reported literal gold in ContextPacket.
- Three EventQA rows were classified
  `dataset_or_metric_gold_not_in_replay`: their expected subsequent-event
  answer strings were not literal substrings of the replayed source text.
- Those three misses therefore do not isolate retrieval quality. They expose a
  mismatch between a next-event task and the adapter's simple answer-in-history
  evidence metric.

The first RULER row provides the clearest positive retrieval result:

- question: `In what country is Normandy located?`
- gold: `France`
- gold appeared in replay;
- a gist-expanded raw span covered the gold-bearing message;
- the raw candidate retained the gold text;
- the candidate reached ContextPacket.

The second RULER row reported `yes` in context, but `yes` occurred in many
replay locations. Literal containment alone does not prove that both
nationality facts needed by the question were assembled correctly.

### Candidate and budget behavior

- Sources: previous-chat gists and derived raw spans.
- Provenance: present in all five rows.
- Source budgets were nonzero.
- Twenty-one candidate drops were reported as `source_budget_exceeded`.
- At least one raw span still reached ContextPacket in every row.
- No row was classified as raw-span formatting/character truncation failure.

## Test-Time Learning Findings

### Literal evidence outcomes

- Four rows reported literal gold labels in ContextPacket.
- One recommendation row (`recsys_redial_full-row-1`) missed label `7008` and
  was classified `gist_retrieval_or_raw_window_selection`.
- Its gold appeared once in replay, but no retrieved gist/raw candidate
  contained it. This is a coarse gist retrieval or bounded raw-window selection
  miss, not a context-budget or character-truncation miss.

The other four rows use short numeric class labels such as `28`, `19`, `43`,
and `4`. These labels occur many times in the replay data:

- the adapter found 69, 70, 85, and 100 literal replay locations respectively;
- a matching label in ContextPacket may be unrelated to the specific query;
- the reported 4/5 containment rate therefore overstates task-specific
  retrieval quality.

### Incremental lifecycle behavior

- Every chunk was replayed as a user turn with an assistant acknowledgement.
- The normal memory-update orchestration hook was called once per chunk.
- Each session was finalized through `ChatEndAction`.
- Mock structured extraction returned
  `langmem_no_valid_memories`, so no durable structured learning was evaluated.
- Because valid normal-turn no-ops remain pending, the recording backend was
  called repeatedly on old batches. Backend calls were approximately twice
  the chunk count. This is an efficiency limitation in the mock replay path.

The run validates incremental lifecycle wiring, not actual test-time learning.

## Evidence Preservation Findings

All expanded raw candidates were bounded and reported `truncated=true`, which
is expected for these long histories. After anchor-preserving truncation:

- no row received the diagnostic
  `raw_span_formatting_or_char_truncation`;
- the strongest Accurate Retrieval success retained its gold-bearing raw
  message through ContextPacket;
- Test-Time Learning rows 2–4 retained raw candidates whose provenance
  overlapped gold-label messages;
- the Test-Time Learning miss had no selected raw span covering its unique
  gold message, so truncation was not the failure stage.

This is evidence that the previous tail-cutting failure did not recur in these
ten rows. It is not proof that every anchor or multi-message evidence chain is
preserved.

## Common Miss Reasons

1. **Dataset/metric mismatch:** EventQA expects a subsequent event that is not
   necessarily a literal substring of replay history.
2. **Metric false positives:** short labels and common answers can appear in
   unrelated candidates.
3. **Gist/window selection:** one unique recommendation label was in replay but
   not in any selected raw window.
4. **Source budget pressure:** 26 candidates across both runs were dropped due
   to per-source budget limits, although this was not the classified cause of
   the observed unique-answer miss.
5. **Mock no-op update repetition:** pending semantic batches are revisited,
   increasing replay work without testing LangMem learning.

No stale/deactivated memory was observed, and WorkflowTrace reported no errors.

## Limitations

- Answer mode was mock; live-model correctness and grounding were not tested.
- Five rows per split are not representative benchmark samples.
- The adapter uses fixture-assisted source routing through CoordinatorAgent.
- It does not use the default-off LangGraph pipeline or Semantic Router v2.
- Evidence scoring is normalized literal containment, not official
  MemoryAgentBench scoring.
- Numeric/class labels produce substantial false-positive risk.
- Mock structured updates do not test LangMem extraction, consolidation, or
  test-time learning.
- The runs do not test conflict resolution or multi-hop reasoning.
- Console/runtime timings include local replay overhead and are not model
  latency benchmarks.

## Recommended Next Steps

1. Add task-aware evidence metrics for classification and next-event rows,
   rather than treating the answer label/string as source evidence.
2. Add an optional adapter path through the default-off LangGraph spike with
   Semantic Router v2, without changing production defaults.
3. Diagnose the unique `7008` window-selection miss using its source chunk and
   gist provenance.
4. Run a small `Accurate_Retrieval` subset whose gold answers are explicit
   source facts, excluding next-event cases for a cleaner retrieval metric.
5. Run one opt-in real-model Test-Time Learning smoke case to separate LangMem
   learning from episodic gist/span recall.
6. Keep `Conflict_Resolution` as future stress work until bounded multi-hop and
   conflict-aware consolidation exist.

## Follow-up Diagnosis

The `7008` miss was subsequently localized to replay message `2421`, inside
gist segment `2401–2480`. That parent gist was not among the top eight retrieved
gists, so no downstream raw-window selector could recover the message.

This motivated a related conservative improvement: adjacent retrieved gist
segments are no longer merged into one large provenance range before selecting
a bounded raw window. See `docs/GIST_RAW_WINDOW_SELECTION.md`. Historical
results above are unchanged; the targeted run was not rerun as part of that
implementation.

## Broader Native Whole-Pipeline Run

The native adapter path was rerun without raw replay retrieval, embedding,
hybrid retrieval, or CrossEncoder reranking:

```bash
uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --dataset-id ai-hyz/MemoryAgentBench \
  --split Accurate_Retrieval --limit 50 --question-limit 1 \
  --answer-mode mock \
  --output reports/memory_agent_bench_accurate_retrieval_native_50.jsonl

uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --dataset-id ai-hyz/MemoryAgentBench \
  --split Test_Time_Learning --limit 50 --question-limit 1 \
  --answer-mode mock \
  --output reports/memory_agent_bench_test_time_learning_native_50.jsonl

uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --dataset-id ai-hyz/MemoryAgentBench \
  --split Long_Range_Understanding --limit 20 --question-limit 1 \
  --answer-mode mock \
  --output reports/memory_agent_bench_long_range_native_20.jsonl
```

| Split | Available/completed | Replayed chunks | Provenance | Gold in retrieved candidates | Gold in ContextPacket |
|---|---:|---:|---:|---:|---:|
| Accurate Retrieval | 22/22 | 6,876 | 22/22 | 3/22 | 2/22 |
| Test-Time Learning | 6/6 | 2,034 | 6/6 | 5/6 | 5/6 |
| Long Range Understanding | 20/20 | 5,689 | 20/20 | 0/20 | 0/20 |

All 48 available rows completed. Every row invoked the incremental memory
update path and one `ChatEndAction`; WorkflowTrace reported no errors. Observed
context sources were `previous_chat_gist` and `raw_message_span`.

The literal metric has important limits. Nineteen Accurate Retrieval rows and
all twenty Long Range rows were classified as
`dataset_or_metric_gold_not_in_replay`, so their zero literal containment
cannot be interpreted as ordinary retrieval failure. Among the remaining
Accurate Retrieval rows, two reached ContextPacket and one gold-bearing
candidate was dropped during context selection. Test-Time Learning had one
gist-retrieval/raw-window miss and five literal successes, with the prior
short-label false-positive caveat still applying.

This run demonstrates native lifecycle and context-pipeline reliability on a
broader external sample. It does not test live-model grounding, official
MemoryAgentBench scoring, real LangMem learning in mock mode, multi-hop
reasoning, or conflict resolution. It does not establish that the production
chatbot improved.
