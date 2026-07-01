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

## Selected Single-Evidence / Non-Multihop Subset

Schema inspection found four common top-level fields: `context`, `questions`,
`answers`, and `metadata`. Every split exposes `metadata.source`, but there is
no general hop-count or single-hop field. Accurate Retrieval sources include
`ruler_qa1_197K`, `ruler_qa2_421K`, EventQA variants, and `longmemeval_s*`.
Only LongMemEval rows expose question types, and those describe session,
preference, update, or temporal categories rather than hop count.

Two eval-only selectors were added:

- exact `metadata.source` inclusion/exclusion;
- a conservative likely-single-evidence filter requiring one literal
  gold-bearing replay chunk, lexical question/evidence overlap, and no obvious
  temporal, conflict, or multi-evidence cue.

Gold is used only to select and report the evaluation cohort. It is not passed
to retrieval, ranking, or context construction.

The strict heuristic selected no first-question Accurate Retrieval rows:
13/22 lacked literal gold in replay, two had gold in multiple chunks, and seven
had temporal/conflict cues. Rather than weaken the criteria, the explicit
`ruler_qa1_197K` source was used as the cleaner QA1 cohort:

```bash
uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --dataset-id ai-hyz/MemoryAgentBench \
  --split Accurate_Retrieval --limit 50 --question-limit 20 \
  --answer-mode mock \
  --include-source-dataset ruler_qa1_197K \
  --output reports/memory_agent_bench_accurate_retrieval_ruler_qa1_native.jsonl

uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --dataset-id ai-hyz/MemoryAgentBench \
  --split Test_Time_Learning --limit 50 --question-limit 1 \
  --answer-mode mock \
  --output reports/memory_agent_bench_test_time_learning_native_selected.jsonl
```

| Cohort | Completed | Replayed chunks | Provenance | Gold in candidates | Gold in ContextPacket |
|---|---:|---:|---:|---:|---:|
| RULER QA1 | 20/20 questions | 280 | 20/20 | 17/20 | 9/20 |
| Test-Time Learning | 6/6 rows | 2,034 | 6/6 | 5/6 | 5/6 |

RULER QA1 had eight gold-bearing candidates dropped during context selection,
two gist-retrieval/raw-window misses, and one raw-span formatting classification.
This indicates that likely single-hop cases are not failing primarily because
gold is absent: candidate recall is relatively high, while bounded context
selection remains a substantial bottleneck. Test-Time Learning retained its
previous 5/6 literal result and short-label false-positive caveat.

Both runs used the native typed-memory adapter with deterministic reranking.
Raw replay, embedding/hybrid raw replay, and CrossEncoder paths were disabled.
There were no lifecycle, ChatEnd, retrieval, ContextPacket, or WorkflowTrace
errors. These are mock-answer diagnostics, not live answer accuracy or proof
that MemoryAgentBench is solved.

### RULER QA1 Candidate-to-Context Promotion Diagnostic

Eight of the seventeen questions with literal-gold candidates did not promote
one into `ContextPacket`. Every affected gold-bearing candidate:

- was a provenance-linked `raw_message_span`;
- retained the literal gold text before context building;
- had query-selected anchor metadata;
- survived deterministic reranking;
- was dropped as `source_budget_exceeded`.

| Question index | Gold | Best gold rank | Candidate tokens / raw budget | Primary classification |
|---:|---|---:|---:|---|
| 0 | France | 2 | 996 / 1,059 | `RERANKED_TOO_LOW` |
| 1 | 10th and 11th centuries | 2 | 1,000 / 1,123 | `RERANKED_TOO_LOW` |
| 6 | Richard I | 7 | 988 / 1,050 | `RERANKED_TOO_LOW` |
| 7 | Catholic | 2 | 949 / 1,134 | `RERANKED_TOO_LOW` |
| 9 | 9th century | 6 | 1,001 / 1,117 | `RERANKED_TOO_LOW` |
| 10 | 911 | 2 | 971 / 1,117 | `RERANKED_TOO_LOW` |
| 12 | Seine | 2 | 971 / 954 | `SOURCE_BUDGET_TOO_SMALL` |
| 14 | Catholicism | 3 | 999 / 1,075 | `RERANKED_TOO_LOW` |

The raw-span budget usually admits one roughly 950–1,000-token span. In every
affected case a different, higher-ranked raw span consumed that slot. The
included span generally did not overlap the gold source message. This is a
repeated ranking-plus-budget tradeoff, not an off-by-one, zero-budget,
candidate-formatting, or anchor-truncation bug.

Literal diagnostics also overstate relevance for common or short answers:
`France`, `Catholic`, `9th century`, `911`, `Seine`, and `Catholicism` occur in
multiple replay chunks. A literal-bearing candidate is not necessarily the
question's correct evidence. No runtime fix was made. Broadly increasing raw
budgets or top-k would change production context policy without establishing
that these ambiguous candidates should be promoted.

## Selected External MAB Suite

The selected-suite CLI packages two real MemoryAgentBench cohorts aligned with
the current project scope:

- `ruler_qa1`: `Accurate_Retrieval` source `ruler_qa1_197K`, first 20 questions;
- `test_time_learning`: all six available rows, one question per row;
- `aligned`: both components combined.

```bash
uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --selected-suite ruler_qa1 --answer-mode mock \
  --output reports/memory_agent_bench_selected_ruler_qa1.jsonl

uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --selected-suite test_time_learning --answer-mode mock \
  --output reports/memory_agent_bench_selected_test_time_learning.jsonl

uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --selected-suite aligned --answer-mode mock \
  --output reports/memory_agent_bench_selected_aligned.jsonl
```

| Suite | Completed | Pipeline errors | Gold candidates | Gold context | Provenance |
|---|---:|---:|---:|---:|---:|
| RULER QA1 | 20/20 | 0 | 17/20 | 9/20 | 20/20 |
| Test-Time Learning | 6/6 | 0 | 5/6 | 5/6 | 6/6 |
| Aligned | 26/26 | 0 | 22/26 | 14/26 | 26/26 |

These suites use official `ai-hyz/MemoryAgentBench` rows and the native
Coordinator-based typed-memory adapter. Raw replay, embedding/hybrid raw
retrieval, and CrossEncoder paths are disabled. Output rows are bounded and
record source/split identity, evidence containment, provenance, context size,
and coarse failure stage.

This selected external suite is distinct from `evals/typed_memory_e2e/`, which
contains synthetic deterministic architecture-regression cases. Mock answers
do not validate live-model grounding, and multi-hop retrieval and conflict
resolution are not primary goals of this selected suite.

### CrossEncoder Ablation on Selected Suites

The selected-suite runner can explicitly enable the current repository's
`BAAI/bge-reranker-v2-m3` CrossEncoder for evaluation. Deterministic reranking
remains the default; raw replay and its embedding/hybrid modes remained
disabled throughout this ablation.

| Suite | Mode | Completed | Gold candidates | Gold context | Provenance | Runtime |
|---|---|---:|---:|---:|---:|---:|
| RULER QA1 | deterministic | 20/20 | 17/20 | 9/20 | 20/20 | 11.849 s |
| RULER QA1 | CrossEncoder | 20/20 | 17/20 | 11/20 | 20/20 | 189.527 s |
| Test-Time Learning | deterministic | 6/6 | 5/6 | 5/6 | 6/6 | 16.423 s |
| Test-Time Learning | CrossEncoder | 6/6 | 5/6 | 5/6 | 6/6 | 75.227 s |
| Aligned | deterministic | 26/26 | 22/26 | 14/26 | 26/26 | 24.252 s |
| Aligned | CrossEncoder | 26/26 | 22/26 | 16/26 | 26/26 | 202.998 s |

CrossEncoder ordering promoted two previously missed RULER questions into the
context: question 0, "In what country is Normandy located?", and question 7,
"What religion were the Normans". No baseline success regressed. Candidate
sets and context budgets were unchanged, so these gains are attributable to
reranking-driven promotion under the existing raw-span budget.

The gain is measurable but modest and came with substantial model-load and CPU
inference cost. CrossEncoder should remain optional. These are mock-answer
evidence-containment results, not live-model answer accuracy or a reason to
change production defaults.
