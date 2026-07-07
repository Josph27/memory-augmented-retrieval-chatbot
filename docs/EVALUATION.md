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

The LongMemEval path is a project pilot, not an official leaderboard scorer.
It replays role-preserved sessions through the production chat lifecycle,
finalizes each historical chat, and asks the final question from a separate
active chat.

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
