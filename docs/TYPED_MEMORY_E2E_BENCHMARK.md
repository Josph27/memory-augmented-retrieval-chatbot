# Typed Memory E2E Benchmark

## Goal

Validate the project's intended typed-memory lifecycle, retrieval, provenance,
context construction, and evidence-contract behavior with deterministic cases.

## What It Tests

The 43 cases cover current/previous chat exact quotes, gist orientation,
gist-only fail-closed behavior, SQLite structured memory, recent-message
continuity, raw-span anchor preservation, provenance, and casual-chat routing.
Each case uses an isolated SQLite database and the default-off read-only
LangGraph pipeline with Semantic Router v2.

## What It Does Not Test

This is not a replacement for MemoryAgentBench. It excludes multi-hop
retrieval, conflict resolution, CrossEncoder tuning, production routing
integration, and live-model answer grounding. Document-memory cases are
deferred because this initial suite focuses on chat and memory lifecycle.

## How To Run

```bash
uv run python evals/typed_memory_e2e/run_typed_memory_e2e.py \
  --output reports/typed_memory_e2e_mock.jsonl
```

Use `--case NAME` or `--category CATEGORY` to select cases. Mock mode is the
only default and does not call a live answer model.

## Case Categories

- same-chat and previous-chat exact quote;
- gist orientation and gist-only abstention;
- structured-memory recall;
- recent-message suffix behavior;
- anchor-preserving raw spans;
- provenance preservation;
- casual-chat minimal retrieval.

## Metrics

Results report source requirements, forbidden sources, required context text,
raw/document/structured evidence, provenance, insufficient-evidence behavior,
context size, and bounded failure reasons. The summary includes pass rates by
category and failure counts.

## Limitations

Cases are intentionally synthetic and deterministic. Passing demonstrates
architecture invariants, not open-domain retrieval quality or generated-answer
correctness.
