# Product Behavior Benchmark

This benchmark freezes 50 application-level scenarios independently of MAB and
LongMemEval. It measures navigation, lifecycle, persistence, document product
behavior, failure handling, races, and idempotency.

The case files use JSON syntax inside `.yaml` files so they remain valid YAML
without adding a YAML parser dependency. Production behavior is never patched by
this benchmark.

## Inventory

| Category | Cases |
| --- | ---: |
| Navigation | 8 |
| Lifecycle | 10 |
| Persistence | 7 |
| Documents | 15 |
| Failures/races/idempotency | 10 |
| **Total** | **50** |

Eight scenarios are browser E2E. They execute when the local environment can
bind a localhost port and launch Chrome. Restricted sandboxes may fail before
app startup.

## Historical result

An earlier 48/50 result is historical, not an expected current result. Stage 5 recorded 39/42 non-browser oracle rows passing; see [audit readiness](../../docs/audit/stage5/readiness.md).

Expected remaining failures:

- `PB-PERSIST-005`: multi-user isolation is outside the current fixed-local-user
  scope.
- `PB-FAIL-010`: cross-operation idempotency beyond upload remains documented
  future work.

## Commands

The examples below explicitly select `langgraph_demo`; the application default is `native`. Use the root README isolated runner for offline regression checks.

```bash
# All 50 cases
ORCHESTRATION_MODE=langgraph_demo \
uv run python -m evals.product_behavior.runner

# Fast deterministic, non-browser cases
ORCHESTRATION_MODE=langgraph_demo \
uv run python -m evals.product_behavior.runner \
  --layer repository/service \
  --layer "Chainlit handler/data-layer"

# Document cases
ORCHESTRATION_MODE=langgraph_demo \
uv run python -m evals.product_behavior.runner --category documents

# Lifecycle cases
ORCHESTRATION_MODE=langgraph_demo \
uv run python -m evals.product_behavior.runner --category lifecycle

# Browser E2E tests
python3 scripts/run_isolated_tests.py --group browser --label local-browser --timeout 600

# Regenerate reports from an existing result file
uv run python -m evals.product_behavior.report \
  --results artifacts/product_behavior/<run_id>/results.jsonl \
  --output-dir artifacts/product_behavior/<run_id> \
  --run-id <run_id>
```

Output:

```text
artifacts/product_behavior/<run_id>/results.jsonl
artifacts/product_behavior/<run_id>/summary.json
artifacts/product_behavior/<run_id>/report.md
artifacts/product_behavior/<run_id>/failures.jsonl
artifacts/product_behavior/<run_id>/run_metadata.json
```

These outputs are generated artifacts and should not be committed as canonical
documentation.
