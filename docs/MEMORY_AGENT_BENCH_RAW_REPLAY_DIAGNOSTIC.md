# MemoryAgentBench Raw Replay Diagnostic

## Goal

Measure whether direct retrieval over replayed benchmark chunks recovers
evidence missed by lossy previous-chat gist retrieval and single-window gist
expansion.

This is an eval-only diagnostic. It does not change the production chatbot.

## Why Raw Replay Retrieval Is Eval-Only

MemoryAgentBench `Test_Time_Learning` includes nearest-example/classification
tasks over thousands of replayed demonstrations. This differs from ordinary
episodic chat recall:

- the desired answer may be an example/class label;
- many replay chunks are semantically similar;
- deterministic gists retain only compact first/last excerpts;
- the benchmark may require nearest-neighbor retrieval over raw examples.

Adding this index to production from one benchmark would conflate benchmark
examples with normal chat memory. The diagnostic therefore lives entirely
under `evals/memory_agent_bench`.

## Method

When explicitly enabled, the adapter:

1. records each replayed user chunk with session, chunk, chat, and SQLite
   message IDs;
2. tokenizes the benchmark question deterministically;
3. scores every replayed chunk by normalized query-term overlap;
4. selects a bounded top-k;
5. keeps at most the configured character limit per chunk;
6. emits `MemoryCandidate(source="eval_raw_replay_chunk")`;
7. routes candidates through an adapter-local wrapper around the existing
   raw-span context budget/layout;
8. restores the eval-only source label in `ContextPacket`;
9. compares retrieved/context candidates with gold only after retrieval.

Defaults:

```text
enabled = false
top_k = 8
max_chars = 4000
```

No runtime scoring function accepts a gold answer.

## Commands

```bash
uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --dataset-id ai-hyz/MemoryAgentBench \
  --split Accurate_Retrieval \
  --limit 20 \
  --question-limit 1 \
  --answer-mode mock \
  --enable-raw-replay-chunk-retrieval \
  --raw-replay-top-k 8 \
  --raw-replay-max-chars 4000 \
  --output reports/memory_agent_bench_accurate_retrieval_raw_replay_diag.jsonl
```

```bash
uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --dataset-id ai-hyz/MemoryAgentBench \
  --split Test_Time_Learning \
  --limit 20 \
  --question-limit 1 \
  --answer-mode mock \
  --enable-raw-replay-chunk-retrieval \
  --raw-replay-top-k 8 \
  --raw-replay-max-chars 4000 \
  --output reports/memory_agent_bench_test_time_learning_raw_replay_diag.jsonl
```

The official `Test_Time_Learning` split exposed only six rows, so that run
completed 6 rather than 20 examples.

## Results

| Diagnostic | Accurate Retrieval | Test-Time Learning |
|---|---:|---:|
| Examples completed | 20 | 6 |
| Replay chunks | 6,066 | 2,034 |
| Provenance present | 20/20 | 6/6 |
| Any eval raw candidate reached ContextPacket | 15/20 | 3/6 |
| Eval raw candidate contained literal gold | 2/20 | 5/6 |
| Gold-bearing eval raw candidate reached ContextPacket | 0/20 | 2/6 |
| Previous-chat gist text contained literal gold | 1/20 | 1/6 |
| Overall literal gold in ContextPacket | 1/20 | 5/6 |
| Live answer grounding tested | No | No |

The mock prediction match rate is 1.0 by construction and is not meaningful
model accuracy.

### Failure classifications

Accurate Retrieval:

- 17 `dataset_or_metric_gold_not_in_replay`;
- 2 `context_budget_or_context_selection`;
- 1 literal gold reached context.

Test-Time Learning:

- 5 literal gold reached context;
- 1 `gist_retrieval_or_raw_window_selection` (`7008`).

## Comparison With Gist-Based Retrieval

At candidate stage, raw replay retrieval found more literal gold than gist text:

- Accurate Retrieval: 2 raw replay versus 1 gist;
- Test-Time Learning: 5 raw replay versus 1 gist.

This shows that bypassing lossy gist summaries can expose answer-bearing replay
chunks.

However, candidate recall did not translate directly into final context:

- neither Accurate Retrieval gold-bearing raw candidate survived
  reranking/budgeting into ContextPacket;
- only two of five Test-Time Learning gold-bearing raw candidates survived;
- numeric labels in Test-Time Learning occur frequently, so several literal
  hits may be unrelated false positives.

The diagnostic therefore separates:

```text
raw candidate found
raw candidate with gold found
any raw candidate reached context
gold-bearing raw candidate reached context
```

## 7008 Case Revisited

`recsys_redial_full-row-1` remained a miss.

Raw replay top-8 selected chunks:

```text
565, 717, 1494, 1228, 1179, 428, 273, 1504
```

The gold chunk was 1210. Under deterministic lexical scoring:

- chunk 1210 score: `0.6098`;
- raw lexical rank: `473/1545`;
- gold label `7008` was not in any raw top-eight candidate;
- one unrelated eval raw candidate reached ContextPacket;
- neither gist nor raw replay recovered the correct example.

This confirms that the case is not solved merely by bypassing gists. It is a
nearest-example retrieval problem among many highly similar movie dialogues.
A semantic embedding or CrossEncoder over a much larger candidate pool is more
appropriate than lexical top-8.

## Interpretation

### Does raw replay recover evidence missed by previous-chat gists?

Sometimes at candidate stage. It found additional literal-gold chunks in both
splits. Final ContextPacket improvement was limited by ranking/budgeting and by
weak literal metrics.

### Should production add raw replay retrieval?

Not from this evidence. The project already has provenance-linked raw spans for
normal episodic recall. This benchmark diagnostic indexes every replay chunk as
a training example, which is a different workload.

### Main bottlenecks

- lossy gist summaries: demonstrated;
- raw-window selection: relevant for some gist paths;
- lexical nearest-example retrieval: dominant for `7008`;
- context ranking/budgeting: gold-bearing raw candidates were sometimes found
  but not included;
- metric ambiguity: numeric labels and next-event answers make literal
  containment unreliable;
- multi-hop reasoning: remains separate and was not tested here.

## Production Implications

Production `PreviousChatGistRetriever`, routing defaults, ContextBuilder,
ChatService, and CoordinatorAgent were not modified.

If a general product improvement is later pursued, evaluate:

1. a default-off semantic index over raw episodic chunks;
2. typed provenance back to SQLite messages;
3. bounded pre-rerank candidate pools;
4. CrossEncoder reranking;
5. explicit latency and privacy constraints.

That should be justified by real user recall cases, not only benchmark labels.

## Limitations

- Mock answers do not test generated-answer grounding.
- This is not official MemoryAgentBench scoring.
- Literal gold is weak for numeric labels and next-event tasks.
- Accurate Retrieval contains many rows whose expected answer is not literally
  present in replay.
- Lexical scoring has no embeddings, synonym handling, or learned relevance.
- Top-k eight is intentionally bounded.
- Gold-aware fields are post-hoc diagnostics only.
- The generated JSONL files remain local and untracked.

## Recommended Next Step

Keep this mode eval-only and default-off.

The next experiment should compare:

```text
lexical raw top-k
→ embedding raw top-k
→ optional CrossEncoder rerank
```

Use query-only retrieval and report candidate recall separately from
ContextPacket inclusion. Before increasing context budgets, determine whether
the correct example enters the candidate pool at all.

## Embedding Retrieval Comparison

An eval-only comparison added `lexical`, `embedding`, and reciprocal-rank
`hybrid` modes. The default remains lexical. Embedding/hybrid runs use
`sentence-transformers/all-MiniLM-L6-v2`, a candidate pool of 50, and final
top-k eight. Gold answers are used only after retrieval to calculate ranks and
containment.

| Split | Mode | Rows | Gold raw candidate | Gold raw candidate in ContextPacket |
|---|---:|---:|---:|---:|
| Accurate Retrieval | lexical | 20 | 2/20 | 0/20 |
| Accurate Retrieval | embedding | 20 | 3/20 | 0/20 |
| Accurate Retrieval | hybrid | 20 | 2/20 | 0/20 |
| Test-Time Learning | lexical | 6 | 5/6 | 2/6 |
| Test-Time Learning | embedding | 6 | 5/6 | 1/6 |
| Test-Time Learning | hybrid | 6 | 5/6 | 5/6 |

Embedding improved the `7008` chunk from lexical rank 473 to embedding rank
100, but it remained outside candidate pool 50; hybrid rank was 179. Therefore
none of these modes recovered `7008`.

The comparison supports two narrow conclusions:

- embedding can improve candidate recall where lexical overlap is weak;
- hybrid ranking can improve downstream inclusion for Test-Time Learning when
  a gold-bearing candidate is already retrieved.

It does not establish a production retrieval choice. Accurate Retrieval still
had low literal candidate recall, no mode put a gold-bearing raw candidate into
ContextPacket, and mock answers do not test live-model grounding. Generated
JSONL reports remain local and untracked.
