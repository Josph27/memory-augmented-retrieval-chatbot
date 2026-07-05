# Product Behavior Benchmark

This benchmark freezes 50 application-level scenarios independently of MAB and
LongMemEval. It measures navigation, lifecycle, persistence, document product
behavior, failure handling, races, and idempotency.

The case files use JSON syntax inside `.yaml` files so they remain valid YAML
without adding a YAML parser dependency. Production behavior is never patched
by this benchmark.

## Inventory

| Category | Cases |
|---|---:|
| Navigation | 8 |
| Lifecycle | 10 |
| Persistence | 7 |
| Documents | 15 |
| Failures/races/idempotency | 10 |
| **Total** | **50** |

Eight scenarios are explicitly browser E2E. When no browser run is available,
they are reported as `not_executed`, never replaced with passing mocks.

The document store is currently global by design. The benchmark expectation is
stricter: a document associated with one chat should not leak into another chat.
Until a persisted association/scope model exists, that case remains a failed,
explicit product gap.

## Commands

```bash
# All 50 cases
uv run python -m evals.product_behavior.runner

# Fast deterministic, non-browser cases
uv run python -m evals.product_behavior.runner \
  --layer repository/service \
  --layer "Chainlit handler/data-layer"

# Document cases
uv run python -m evals.product_behavior.runner --category documents

# Lifecycle cases
uv run python -m evals.product_behavior.runner --category lifecycle

# Browser E2E inventory/results (not executed unless browser support is added)
uv run python -m evals.product_behavior.runner --layer "browser E2E"

# Full repository regression
uv run pytest

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

After the first baseline, case definitions and expectations are frozen.
Production fixes must not edit benchmark expectations in the same change.

