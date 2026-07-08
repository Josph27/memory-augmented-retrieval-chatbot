# Evaluation

The repository includes several evaluation layers. Generated outputs are local
artifacts and should normally remain untracked.

## Evaluation layers at a glance

| Layer | What it validates | Main command | Current interpretation |
| --- | --- | --- | --- |
| Repository tests | Unit and integration behavior for services, agents, retrieval, memory, document lifecycle, UI helpers, and evaluation utilities. | `uv run pytest -q` | Primary regression gate. |
| Browser E2E | Real Chainlit browser flows: Home, sidebar navigation, active/ended chats, lifecycle controls, uploads, and Inspector UI. | `uv run pytest -q tests/e2e` | Product smoke for the live UI; needs localhost/browser access. |
| Product Behavior | 50 product-level oracle cases across repository, service, handler, and browser layers. | `uv run python -m evals.product_behavior.runner` | Main product-behavior benchmark; expected 48/50 with two documented limitations. |
| MAB answer-level | MemoryAgentBench conversational-memory tasks through fixed manifests and the production-shaped answer path. | `uv run python -m evals.mab_answer_eval ...` | Held-out answer-quality diagnostic, not an uploaded-document RAG test. |
| LongMemEval pilot | Long-session conversational-memory questions through a local adapter. | `uv run python -m evals.longmemeval_answer_eval ...` | Pilot evidence only; not an official leaderboard protocol. |
| Document QA | Small document retrieval/grounding checks over local JSONL fixtures/subsets. | `uv run python -m evals.document_qa.run_document_qa_eval` | Subsystem regression signal, not yet a full RAG benchmark. |
| Structured-memory eval | Controlled checks for memory extraction/retrieval/update behavior. | `uv run python -m evals.structured_memory.run_structured_memory_eval` | Focused memory subsystem validation. |
| Typed-memory E2E | Internal typed-memory source-selection and answer-grounding scenarios. | `uv run python -m evals.typed_memory_e2e.run_typed_memory_e2e` | Small end-to-end control set for typed sources. |

## Metric terminology

Some answer-level reports intentionally keep multiple scores separate:

- **Official metric**: the benchmark or adapter's deterministic/task-specific
  metric, for example exact/substring match, label matching, or a pilot
  evidence-session score.
- **Semantic valid**: cases counted after excluding judge results that are not
  considered comparable for that run.
- **Semantic conservative**: the same semantic correctness count divided by the
  complete frozen manifest size.

The semantic and official metrics answer different questions. Official metrics
are strict and reproducible, but can be brittle for formatting. Semantic judging
is better for answer meaning, but depends on the configured judge and should not
be treated as official leaderboard scoring.

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

MemoryAgentBench (MAB) is a conversational-memory benchmark. The project uses a
fixed answer-level adapter that replays benchmark history, asks frozen
questions, records official metrics where available, and can run a separate
judge pass. It is used to diagnose retrieval, context-selection, and answer-use
failures, not to tune individual cases.

The MAB manifests used here mainly cover these task families:

| Family | What it tests | Current notes |
| --- | --- | --- |
| RULER QA2 / Accurate Retrieval | Locate exact facts in long conversational context. | Works best when the answer-bearing raw span is retrieved and selected; failures often indicate retrieval or context-selection misses. |
| FactConsolidation single-hop | Use one updated/synthetic fact from history. | Sensitive to raw-span preservation and answer policy when facts conflict with general world knowledge. |
| FactConsolidation multi-hop | Combine multiple facts or updates. | Harder for the current single-pass retrieval/answer path; strong multi-hop synthesis is not fully solved. |
| EventQA | Event or temporal facts from conversation history. | Requires robust temporal retrieval/reasoning; current architecture exposes evidence but does not add a special temporal workflow. |
| Test-Time Learning / TTL | Apply labels or patterns introduced in history. | Often behaves like task-specific classification; strong performance would require workflows beyond generic memory QA. |
| DetectiveQA | Strict output formatting over narrative facts. | Some failures are output-contract issues rather than pure retrieval failures. |
| InfBench summarization | Broad summary-style requests over supplied history. | Tests global coverage more than pinpoint recall; current single-pass retrieval is not a hierarchical summarizer. |

MAB is not primarily an uploaded-document RAG benchmark. Role-less benchmark
history is replayed as raw messages and finalized with production
persistence/gist behavior; personal structured-memory extraction is explicitly
marked not applicable for role-less context.

Current frozen manifests:

- `evals/manifests/mab_answer_heldout_v1.yaml`
- `evals/manifests/mab_answer_smoke_v1.yaml`
- `evals/manifests/mab_answer_judge_calibration_v1.yaml`

Established held-out result:

```text
semantic valid:        10 / 27
semantic conservative: 10 / 33
official metric:       12 / 33
```

The valid semantic denominator excludes cases where the configured semantic
judge result is not considered comparable. The conservative denominator counts
the full frozen manifest.

## LongMemEval answer-level pilot

LongMemEval is a long-conversation memory benchmark. The local path is a project
pilot, not an official leaderboard scorer. It replays role-preserved sessions
through the production chat lifecycle, finalizes each historical chat, and asks
the final question from a separate active chat.

The frozen pilot manifest samples categories such as:

| Category | What it tests | Current notes |
| --- | --- | --- |
| Single-session user | Recall facts stated by the user in one session. | Closest fit to the current structured/raw conversational-memory path. |
| Single-session assistant | Recall assistant-provided information. | Depends on replayed assistant turns and final gist/raw evidence. |
| Multi-session | Recall across multiple finalized chats. | Tests previous-chat gists plus raw/session provenance. |
| Temporal reasoning | Use ordering across sessions. | Approximate because timestamp visibility and gold-session heuristics are limited. |
| Knowledge update | Prefer later corrected facts over earlier facts. | Tests ordering and conflict handling, but no special conflict-resolution UI exists. |
| Preference | Recall durable user preferences. | Fits structured-memory behavior when extraction succeeds. |
| Abstention / insufficient evidence | Avoid unsupported answers. | Labels are not always exposed cleanly in local data; scoring remains pilot-level. |

Current frozen manifest:

- `evals/manifests/longmemeval_answer_heldout_v1.yaml`

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

## Document QA and structured-memory evals

Subsystem commands:

```bash
uv run python -m evals.document_qa.run_document_qa_eval
uv run python -m evals.structured_memory.run_structured_memory_eval
uv run python -m evals.typed_memory_e2e.run_typed_memory_e2e
```

Use these for smaller checks of document retrieval, answer grounding, and
structured-memory behavior.

The document QA code covers local fixture/subset-style evidence, chunk
retrieval, and answer grounding. It is useful for regression testing document
RAG mechanics, including document scoping and chunk selection. It should not be
described as a comprehensive RAG benchmark unless a larger dataset run is
separately executed and reported.

The structured-memory and typed-memory E2E suites are controlled internal
benchmarks. They are better suited to proving that specific memory sources,
metadata transitions, and source-selection paths work than to measuring general
assistant intelligence.

## Configuration used for canonical evaluation

Canonical local evaluation should use the same defaults as the app unless a
specific ablation says otherwise:

| Variable | Canonical value | Evaluation status |
| --- | --- | --- |
| `ORCHESTRATION_MODE` | `langgraph_demo` | Product/browser/full-app evaluation default. Answer-level MAB and LongMemEval CLIs use explicit `graph` execution rather than this live-app string. |
| `DOCUMENT_RETRIEVAL_MODE` | `langchain_chroma` | Canonical document retrieval backend. |
| `STRUCTURED_MEMORY_RETRIEVAL_MODE` | `sqlite` | Canonical structured-memory retrieval backend. |
| `RERANKER_MODE` | `deterministic` | Canonical reranking mode. |

CrossEncoder ablation summary: deterministic reranking remains the default.
The CrossEncoder path did not change first-stage candidate recall, improved
final context inclusion by two cases in the relevant ablation, and substantially
increased runtime. It is therefore documented as an advanced ablation, not a
default recommendation.

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
