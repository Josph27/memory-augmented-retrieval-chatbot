# Evaluation

The repository includes several evaluation layers. Generated outputs are local
artifacts and should normally remain untracked.

## Product Behavior Benchmark

Purpose: product-level behavior for navigation, chat lifecycle, persistence,
documents, failure handling, races, and idempotency.

Command:

```bash
ORCHESTRATION_MODE=langgraph_demo \
uv run python -m evals.product_behavior.runner
```

Expected current result in a full local environment:

```text
48 passed
2 documented failures
0 errors
0 not executed
```

Documented remaining failures:

- `PB-PERSIST-005`: multi-user isolation is outside the current fixed-local-user
  scope.
- `PB-FAIL-010`: cross-operation idempotency beyond upload remains future work.

Browser E2E cases require permission to bind a localhost port and launch Chrome.
Restricted sandboxes may fail before app startup with a socket permission error.

## Browser E2E

Command:

```bash
ORCHESTRATION_MODE=langgraph_demo \
PRODUCT_E2E_HEADED=0 \
uv run pytest -q tests/e2e
```

These tests cover Home, navigation, active/ended chats, lifecycle controls,
forking, document upload timing, and the Answer Inspector.

## MAB answer-level evaluation

The MemoryAgentBench answer-level adapter uses fixed manifests, production-like
history preparation, Graph execution, official metrics where available, and a
separate configurable judge pass. It is used to diagnose retrieval,
context-selection, and answer-use failures, not to tune individual cases.

Current frozen manifests:

- `evals/manifests/mab_answer_heldout_v1.yaml`
- `evals/manifests/mab_answer_smoke_v1.yaml`
- `evals/manifests/mab_answer_judge_calibration_v1.yaml`

MAB role-less benchmark history is replayed as raw messages and finalized with
production persistence/gist behavior. Personal structured-memory extraction is
not applicable to role-less benchmark context and is skipped explicitly.

### How the MAB run is performed

The held-out answer run is deliberately production-shaped:

1. The manifest identifies fixed MemoryAgentBench rows and question indices.
2. Each benchmark history is loaded from the Hugging Face dataset and replayed
   into an isolated local SQLite database.
3. Role-less MAB histories are stored as raw messages. They are finalized with
   the same persistence and gist lifecycle used by the application, but personal
   structured-memory extraction is skipped because the benchmark context is not
   a real user conversation.
4. The final question is asked through the Graph execution path.
5. Routing, retrieval, reranking, context budgeting, prompt assembly, and answer
   generation run through the same production-shaped contracts used by the app:
   retrieved evidence becomes `MemoryCandidate` objects and selected evidence is
   assembled into a `ContextPacket`.
6. The answer-generation pass writes one `answer_completed` row per case. The
   judge pass is separate and must not regenerate answers.

This means MAB is closer to an answer-level systems test than a pure retrieval
metric. A case can fail because the source fact was not retrieved, because the
right candidate was retrieved but not selected, because the answer model ignored
selected evidence, or because the benchmark requires a strict output format.

### MAB task families in the frozen held-out manifest

The frozen held-out manifest contains 33 cases:

| Family / source dataset | Cases | Main ability tested | Why it is hard |
|---|---:|---|---|
| `ruler_qa2` / short-answer retrieval | 5 | Direct factual lookup from a long synthetic history | Requires locating an exact fact or comparison evidence in a large raw-message space. |
| `event_qa` / event retrieval | 5 | Recall of event facts and actions | Often needs the right event mention, not just a semantically nearby sentence. |
| `fact_consolidation_sh` / single-hop knowledge update | 4 | Use the latest corrected fact | Tests whether the system trusts supplied conversation evidence over prior world knowledge. |
| `fact_consolidation_mh` / multi-hop knowledge update | 4 | Combine or compare updated facts | Stresses multi-hop retrieval and context selection; the current system does not implement iterative graph traversal. |
| `icl_banking77` / in-context classification | 5 | Infer a numeric label from examples | This is closer to task-specific classification than general memory QA. Strict exact-label output matters. |
| `detective_qa` / natural-language reasoning | 5 | Answer multiple-choice reasoning questions from long narrative context | Requires long-range reading and strict option/JSON formatting. |
| `infbench_summarization` / summarization | 5 | Summarize a long supplied book-like history | Requires broad coverage; the system has no map-reduce or hierarchical summarizer. |

Grouped by MemoryAgentBench split, the same manifest contains 10
`Accurate_Retrieval`, 8 `Conflict_Resolution`, 5 `Test_Time_Learning`, and 10
`Long_Range_Understanding` cases. Official metrics are per-case:
`normalized_substring` for 18 cases, `normalized_exact_match` for 10 cases, and
`normalized_token_f1` for 5 cases.

Established held-out result:

```text
semantic valid:        10 / 27
semantic conservative: 10 / 33
official metric:       12 / 33
```

The valid semantic denominator excludes cases where the configured semantic
judge result is not considered comparable. The conservative denominator counts
the full frozen manifest.

Interpretation for presentations: MAB mainly stresses conversational memory,
answer use, and long-context behavior. It does **not** primarily test uploaded
document RAG. The current system does well on some direct retrieval and
single-hop update cases, but struggles with whole-history summarization,
multi-hop consolidation, strict classification labels, and benchmark-specific
output formats. Those failures are useful diagnostics, not the same thing as
Product Behavior feature failures.

## LongMemEval answer-level pilot

The LongMemEval path is a project pilot, not an official leaderboard scorer.
It replays role-preserved sessions through the production chat lifecycle,
finalizes each historical chat, and asks the final question from a separate
active chat.

Current frozen manifest:

- `evals/manifests/longmemeval_answer_heldout_v1.yaml`

### How the LongMemEval pilot is performed

The LongMemEval adapter is intentionally labelled as a pilot because it is a
local project integration, not the official leaderboard scorer. The held-out
manifest uses a local cleaned dataset file and 19 fixed cases.

For each case:

1. Historical sessions are replayed with their speaker roles preserved.
2. The replay uses isolated local state for that case.
3. Historical chats are finalized so the app can expose previous-chat memory.
4. Unlike role-less MAB, LongMemEval uses real structured-memory updates during
   replay. This exercises the LangMem-backed memory extraction path and the
   long-term-memory store.
5. The final question is asked from a separate active chat.
6. Retrieval may use recent messages, structured memory, previous-chat gists,
   and raw/message-span evidence depending on the controlled route.
7. The answer pass writes frozen answer rows. The judge-only pass should read
   those rows and call only the judge model.

Because it replays full role-preserved histories and performs real memory
updates, LongMemEval is slower and more operationally fragile than Product
Behavior or routing tests. Model endpoint failures, memory-update failures, or
vector-sync problems can contaminate a run and should be reported separately
from answer-quality failures.

### LongMemEval task families in the frozen pilot manifest

The frozen LongMemEval pilot manifest contains 19 cases:

| Question type | Cases | Main ability tested | Why it is hard |
|---|---:|---|---|
| `single-session-user` | 5 | Recall a user-related fact from one prior session | Requires preserving and retrieving the right personal detail. |
| `single-session-assistant` | 2 | Recall information stated by the assistant | Tests role-preserved replay, not just user-fact memory. |
| `multi-session` | 4 | Retrieve evidence across multiple sessions | Requires cross-chat/session access and correct source selection. |
| `temporal-reasoning` | 3 | Use timing or order of events | The system has limited explicit temporal reasoning. |
| `knowledge-update` | 3 | Prefer corrected/latest facts over stale facts | Requires update ordering and conflict handling. |
| `single-session-preference` | 2 | Recall user preferences | Matches the structured-memory use case most closely. |

LongMemEval metrics and gold-session failure-stage heuristics are approximate
and should be reported as pilot evidence.

Corrected frozen-answer pilot result:

```text
semantic valid:        12 / 16
semantic conservative: 12 / 19
official pilot metric: 10 / 19
```

Combined MAB plus LongMemEval:

```text
semantic valid:        22 / 43 = 51.2%
semantic conservative: 22 / 52 = 42.3%
```

Interpretation for presentations: LongMemEval is closer to a long-term
conversation-memory stress test than a product acceptance benchmark. It is
useful because it exercises role-preserved replay, previous-chat recall, and
structured-memory updates. It should not be presented as proof of document RAG
quality, and its pilot metrics should be described conservatively.

## Document QA and structured-memory evals

Subsystem commands:

```bash
uv run python -m evals.document_qa.run_document_qa_eval
uv run python -m evals.structured_memory.run_structured_memory_eval
uv run python -m evals.typed_memory_e2e.run_typed_memory_e2e
```

Use these for smaller checks of document retrieval, answer grounding, and
structured-memory behavior.

## Generated outputs

Common output roots:

```text
artifacts/product_behavior/
artifacts/eval_runs/
artifacts/evals/
reports/
```

Raw result JSONL, screenshots, traces, timestamped run directories, and
temporary diagnostic outputs are generated artifacts. Keep them locally when
useful, but do not commit them as canonical documentation.
