# Typed-Memory End-to-End Benchmark

> Deterministic E2E benchmark validating the full typed-memory pipeline:
> multi-chat ingestion, gist finalization, source routing, retrieval,
> evidence contract enforcement, and context assembly — all without LLM calls.

## Purpose

This 43-case benchmark exercises the typed-memory architecture across the
complete lifecycle: chat creation → message persistence → chat-end gist
generation → structured memory upsert → semantic routing → source-level
retrieval → evidence contract validation → context packet assembly.

It runs in **mock mode only** — the LangGraph pipeline produces context
packets and evidence contract decisions, but no LLM generates answers. Every
assertion is checked against the `ContextPacket` structure, not against
generated text.

## Usage

Run all 43 cases:

```bash
uv run python evals/typed_memory_e2e/run_typed_memory_e2e.py \
  --output reports/typed_memory_e2e.jsonl
```

Filter by case name or category:

```bash
uv run python evals/typed_memory_e2e/run_typed_memory_e2e.py \
  --case same_chat_exact_quote_1 \
  --category structured_memory_recall
```

## Case Categories

| Category | Cases | What it tests |
|----------|-------|---------------|
| `same_chat_exact_quote` | 6 | Exact wording survives recent-window variation; `current_chat_span` activated |
| `previous_chat_exact_quote` | 8 | Ended-chat gist expands to exact raw transcript evidence |
| `gist_orientation` | 4 | `previous_chat_gist` supplies lossy orientation for recall queries |
| `gist_only_exact_quote_fails` | 4 | Orientation without raw-span provenance fails closed (insufficient evidence) |
| `structured_memory_recall` | 6 | SQLite structured memory retrievable and used for preference/fact recall |
| `recent_message_suffix_and_context_budget` | 4 | Recent messages appear in context, query-safe, no expensive sources |
| `raw_span_anchor_truncation` | 4 | Tight raw-span formatting preserves matched anchor through character truncation |
| `provenance_preservation` | 4 | Expanded previous-chat evidence retains parent gist provenance |
| `casual_chat_minimal_memory` | 3 | Casual queries avoid expensive memory sources (raw span, gist, document) |

## Data Model

Core types from `schemas.py`:

### `TypedMemoryCase`

A single test case with:

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Unique case identifier |
| `category` | `str` | Logical grouping |
| `sessions` | `tuple[BenchmarkSession, ...]` | One or more chat sessions with messages |
| `query` | `str` | User query to evaluate |
| `expected_sources` | `tuple[str, ...]` | Sources that must be present in context |
| `forbidden_sources` | `tuple[str, ...]` | Sources that must not appear |
| `required_text_in_context` | `tuple[str, ...]` | Text fragments that must appear |
| `requires_raw_span` | `bool` | Whether a raw span source is required |
| `requires_structured_memory` | `bool` | Whether structured_memory must be present |
| `expected_insufficient_evidence` | `bool` | Whether the evidence contract should fail |
| `expected_provenance` | `bool` | Whether candidates must carry provenance |
| `fixture` | `dict` | Test fixtures (gist text, structured memory, span config) |

### `BenchmarkSession`

| Field | Type | Purpose |
|-------|------|---------|
| `chat_name` | `str` | Session label (e.g., "active", "ended", "current", "source") |
| `messages` | `tuple[BenchmarkMessage, ...]` | Role+content pairs |
| `end_chat` | `bool` | Whether to run `ChatEndAction` after this session |

### `TypedMemoryCaseResult`

Per-case result with pass/fail and detailed assertions:

| Field | Type |
|-------|------|
| `passed` | `bool` |
| `sources_observed` | `tuple[str, ...]` |
| `required_sources_present` | `bool` |
| `forbidden_sources_absent` | `bool` |
| `required_text_present` | `bool` |
| `raw_span_present` | `bool` |
| `structured_memory_present` | `bool` |
| `provenance_present` | `bool` |
| `insufficient_evidence` | `bool` |
| `failure_reasons` | `tuple[str, ...]` |

## Runner Execution

`runner.py` creates per-case, isolated temp SQLite databases. For each case:

1. **Create chats**: One per `BenchmarkSession` with prescribed messages.
2. **End chats**: Run `ChatEndAction` for sessions with `end_chat=True`.
   Uses `NoopChatEndMemoryProcessor` to exercise gist finalization without
   external LangMem LLM calls.
3. **Setup fixtures**: Inject synthetic gist records or structured memory
   entries via direct SQLite/Chroma writes.
4. **Build LangGraph pipeline**: `SemanticRouter` + all 5 retrievers
   (`RecentMessagesRetriever`, `CurrentChatSpanRetriever`,
   `PreviousChatGistRetriever`, `RawMessageSpanRetriever`,
   `StructuredMemoryRetriever`) wired through `RetrieverDispatcher`.
5. **Run pipeline**: `run_langgraph_memory_pipeline()` → full
   route → retrieve → expand_gists → rerank → build_context →
   validate_evidence trace.
6. **Assert**: Check all required/forbidden sources, required text,
   raw span presence, structured memory presence, provenance,
   evidence contract outcome, query count.

## Result Format

Output JSONL with a summary header and one JSON object per case:

```json
{"summary": {"benchmark":"typed_memory_e2e","num_cases":43,"num_passed":43,...}}
{"name":"same_chat_exact_quote_1","category":"same_chat_exact_quote","passed":true,...}
{"name":"previous_chat_exact_quote_1","category":"previous_chat_exact_quote","passed":true,...}
```

The summary includes `pass_rate_by_category` and `failures_by_reason`.

## File Index

| File | Lines | Role |
|------|-------|------|
| `cases.py` | 193 | 43 test cases across 9 categories, factory functions |
| `schemas.py` | 61 | `BenchmarkMessage`, `BenchmarkSession`, `TypedMemoryCase`, `TypedMemoryCaseResult` |
| `runner.py` | 205 | Per-case execution, LangGraph pipeline wiring, assertions, JSONL output |
| `run_typed_memory_e2e.py` | 49 | CLI entry point, case filtering |
| `__init__.py` | 0 | Empty |
