# Previous Chat Gist Retrieval Diagnostic

## Goal

Explain why the parent `previous_chat_gist` containing MemoryAgentBench answer
`7008` was not retrieved, distinguish that failure from downstream raw-window
selection, and identify the smallest defensible next experiment.

This is a diagnostic report. No production retrieval, routing, or context
behavior was changed.

## Case Summary

| Field | Observed value |
|---|---|
| Split | `Test_Time_Learning` |
| Example | `recsys_redial_full-row-1` |
| Question index | First question |
| Gold answer | `7008` |
| Gold replay chunk | 1210 |
| Gold user message ID | 2421 |
| Correct gist ID | 31 |
| Correct gist span | 2401–2480 |
| Gists stored | 39 |
| Benchmark gist limit | 8 |

The official row was reproduced in temporary SQLite by replaying the same
1,545 bounded chunks and finalizing deterministic 80-message gists. No
repository database or report was modified.

The gold answer is a dialogue identifier, not an ordinary fact stated in the
benchmark question. The task asks the system to find the closest prior
recommendation dialogue and return its ID.

## Current Retrieval Path

```text
all stored previous_chat_gist rows
→ tokenize query and gist_text
→ lexical set-overlap score
→ discard score == 0
→ sort score descending
→ take SourcePlan.limit (8 in MemoryAgentBench)
→ expand each retrieved gist to one bounded raw window
→ rerank gist and raw candidates
→ context budgeting
```

`PreviousChatGistRetriever`:

- scans every `previous_chat_gist` row from SQLite;
- searches only `gist_text`;
- does not search topics, metadata, source messages, chat ID, or provenance
  boundaries;
- uses whitespace token overlap without stemming, embeddings, or stopword
  removal;
- returns a numeric overlap score;
- filters only zero-score rows;
- applies the source limit before gist expansion and final reranking.

The MemoryAgentBench fixture route enabled `previous_chat_gist`, so source
planning did not exclude the correct source. `MemoryReranker` runs after
retrieval/expansion and cannot recover an omitted gist.

## What Was Retrieved

The top-eight parent gists were:

| Rank | Gist ID | Score | Span |
|---:|---:|---:|---|
| 1 | 30 | 0.3529 | 2321–2400 |
| 2 | 26 | 0.3529 | 2001–2080 |
| 3 | 36 | 0.3333 | 2801–2880 |
| 4 | 27 | 0.3333 | 2081–2160 |
| 5 | 35 | 0.3137 | 2721–2800 |
| 6 | 32 | 0.3137 | 2481–2560 |
| 7 | 25 | 0.3137 | 1921–2000 |
| 8 | 24 | 0.3137 | 1841–1920 |

These produced raw windows such as:

- 2061–2072;
- 2353–2364;
- 2539–2550;
- 2805–2816.

None covered message 2421. Context budgeting later dropped several lower
ranked candidates, but the correct gist/raw span was absent before budgeting.

## What Was Not Retrieved

Correct gist 31:

- existed in SQLite;
- had correct provenance boundaries 2401–2480;
- contained message 2421 inside its source range;
- received score `0.2941`;
- ranked 13th among 39 positive-score gists;
- was returned when the limit was increased to 100;
- was not returned at the configured limit of 8.

Therefore, increasing the candidate pool to at least 13 would admit the parent
gist in this reproduction.

However, that alone does not recover answer `7008`. When gist 31 was forced
through expansion:

- the selected raw window was 2451–2462;
- the anchor was message 2457;
- message 2421 was not included;
- `7008` was absent from formatted raw evidence.

Inside gist 31, message 2421 ranked 12th of 80 messages by the current lexical
query-overlap signal. Message 2457 had the strongest overlap.

This is a two-stage recall failure:

1. the correct parent gist fell outside top-k;
2. the single query-centered raw window inside that gist preferred another
   similar movie dialogue.

## Why Window Selection Could Not Recover

The adjacent-window fix improves downstream coverage only after a gist is
retrieved. It cannot recover a parent gist that was never retrieved.

Even with the parent forced into the candidate set, one lexical window is
insufficient for this row. The 80-message segment contains many semantically
similar movie-recommendation dialogues. The correct dialogue is not the
highest token-overlap message.

Anchor-preserving character truncation also cannot help because message 2421
never enters the selected message window. Truncation preserves selected
anchors; it does not choose anchors.

## Root Cause Classification

| Category | Applies? | Evidence |
|---|---|---|
| `RETRIEVAL_TOP_K_TOO_SMALL` | Contributing | Correct gist rank 13; configured limit 8 |
| `LOW_LEXICAL_OVERLAP` | Yes, relative | Correct gist score below eight competing summaries |
| `GIST_TOO_LOSSY` | Primary | Deterministic gist retains compact first/last user excerpts only |
| `SEGMENT_TOO_LARGE_OR_DIFFUSE` | Yes | 80 messages contain many unrelated/similar dialogues |
| `MISSING_ENTITY_METADATA` | Partial | Topics/metadata are not searched; dialogue identity is not represented |
| `RERANKING_DROPPED_CORRECT_GIST` | No | Correct gist never reached reranking |
| `SOURCE_PLAN_EXCLUDED_GIST` | No | Previous-chat gist source was explicitly enabled |
| `BUG_IN_GIST_STORAGE_OR_PROVENANCE` | No | Gist 31 and span 2401–2480 were correct |
| `BENCHMARK_METRIC_OR_GOLD_AMBIGUITY` | Yes | Gold is a dialogue ID requiring nearest-example retrieval |
| `MULTI_HOP_REQUIRED` | No | This is nearest-example recall, not relation chaining |

## Candidate Fixes

### 1. Increase gist candidate pool before reranking

- Expected benefit: gist 31 enters the pool at 13+ candidates.
- Limitation: forced expansion still misses message 2421.
- Runtime cost: more SQLite expansion reads, raw candidates, reranking work,
  and context-budget competition.
- Production impact: yes if made default; safer behind a source-specific
  configuration.
- Tests: candidate-pool recall, latency/candidate-count bounds, context-budget
  behavior.

This is necessary for this case but not sufficient.

### 2. Hybrid lexical/vector retrieval over gist text

- Expected benefit: improves paraphrase recall over lexical overlap.
- Limitation: embeddings cannot recover detail removed from gist text.
- Runtime cost: embedding/index maintenance and vector query latency.
- Production impact: optional derived index; SQLite should remain authoritative.
- Tests: index synchronization, fallback, deduplication, provenance mapping.

Useful for normal episodic recall, but uncertain for this benchmark row.

### 3. Add richer gist keywords/entities or smaller segments

- Expected benefit: more source concepts survive compression; smaller spans are
  less diffuse.
- Risk: more gist records, generation cost, retrieval competition, and storage.
- Production impact: changes gist generation/lifecycle semantics.
- Tests: bounded generation, fork remapping, chat-end idempotency, recall.

This needs broader design work and should not be rushed from one benchmark case.

### 4. Retrieve multiple raw windows per gist

- Expected benefit: improves within-segment coverage.
- Limitation: message 2421 ranks 12th by lexical overlap, so a small top-window
  count may still miss it.
- Runtime cost: candidate multiplication and additional context pressure.
- Production impact: yes unless default-off/configured.
- Tests: overlap deduplication, maximum windows, reranking, total budget.

### 5. Benchmark-specific raw replay-chunk retrieval

- Expected benefit: directly performs nearest-example retrieval over the
  original dialogue chunks instead of lossy first/last summaries.
- Risk: adapter-specific index complexity and metric alignment work.
- Runtime cost: lexical/BM25/vector retrieval over replay chunks.
- Production impact: none if confined to the eval adapter.
- Tests: exact source-message mapping, bounded candidate counts, no gold use,
  label-aware scoring separated from evidence scoring.

This best matches `Test_Time_Learning` classification semantics.

## Recommended Next Step

Do not change production gist limits from this case alone.

The safest next implementation is an **adapter-only raw replay-chunk retrieval
baseline**:

1. index bounded replay chunks with their message IDs;
2. retrieve a fixed top-k using query text only;
3. optionally rerank those chunks with the existing deterministic or
   CrossEncoder backend;
4. compare chunk recall against the current gist/span path;
5. keep gold answer IDs strictly in evaluation diagnostics.

In parallel, add candidate-pool sensitivity reporting for gist limits
`8/16/32`. This would show whether a larger production gist pool improves
ordinary episodic recall without claiming it solves within-gist selection.

If a production gist improvement is later desired, evaluate a default-off
hybrid gist index and a modest pre-rerank pool increase together. Preserve
SQLite provenance and existing fallback behavior.

## What Not To Claim

- The adjacent-window fix solves the `7008` case.
- Increasing top-k alone recovers `7008`.
- The reranker caused this miss.
- Gist provenance was corrupt.
- Literal answer containment is official MemoryAgentBench accuracy.
- Mock mode validates test-time learning or generated-answer grounding.

## Verification

The reproduction used:

- official `ai-hyz/MemoryAgentBench`, `Test_Time_Learning`, first row;
- 1,545 deterministic 4,000-character replay chunks;
- temporary SQLite only;
- deterministic 80-message gist finalization;
- the current lexical gist scorer and raw-window expander;
- no model calls and no repository data writes.

All diagnostic snippets in this report are bounded. Generated benchmark JSONL
reports remain local and untracked.
