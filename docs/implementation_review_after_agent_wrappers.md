# Implementation Review After Agent Wrapper Work

Reviewed commit range: `ffaacb5..HEAD`

Commits reviewed:

- `cc653a2 refactor: add ContextManagerAgent wrapper`
- `a9b31d0 refactor: add DocumentIngestionAgent wrapper`
- `cfc19c6 feat: add optional LLM routing policy with fallback`
- `3ac1f0c feat: add memory and document inspection helpers`

## 1. Executive Summary

Recommendation: **keep with minor caution**.

The four commits are generally safe to keep. They mostly add responsibility
wrappers, trace metadata, tests, and read-oriented inspection helpers without
changing the default runtime path. The most important default behaviors are
preserved:

- `ROUTING_MODE` defaults to `rule`.
- Normal routing remains deterministic and does not call a live model.
- The ContextPacket path still uses the existing allocator and builder.
- Chainlit upload display-name handling is preserved.
- The new document inspection helpers do not run retrieval or model calls.

Main caution:

- The Chroma inspection helper uses `chromadb.PersistentClient` to read
  collection metadata. This does not affect retrieval behavior, but depending
  on Chroma behavior it may create/open local Chroma storage if the path is
  missing. Treat the CLI as inspection-oriented, but not as a formally
  read-only database transaction.

No serious issue was found that requires reverting these commits before demo
work continues.

## 2. Commit-by-Commit Summary

### `cc653a2` - ContextManagerAgent wrapper

Files:

- `src/agents/context_manager_agent.py`
- `src/agents/coordinator_agent.py`
- `tests/test_context_manager_agent.py`
- small doc/test updates

What changed:

- Added `ContextManagerAgent` as a wrapper around `ContextBudgetAllocator` and
  `ContextBuilder`.
- Added `ContextManagerResult` with `context_budget`, `context_packet`, and
  trace metadata.
- `CoordinatorAgent` now delegates ContextPacket budget/build work through this
  wrapper.

Safety assessment:

- Prompt construction remains deterministic.
- No LLM-based prompt manager was added.
- The wrapper calls the same allocator and builder that were already used.
- Existing ContextPacket validation and fallback to legacy short-term prompt are
  still preserved.

Risk:

- Timing labels for context budget allocation and packet building now share the
  wrapper elapsed time. This is trace granularity, not behavior.

### `a9b31d0` - DocumentIngestionAgent wrapper

Files:

- `src/agents/document_ingestion_agent.py`
- `src/chat_service.py`
- `tests/test_document_ingestion_agent.py`
- small doc update

What changed:

- Added `DocumentIngestionAgent` as a thin wrapper around existing file loading
  and indexing.
- Added `DocumentIngestionResult` with:
  - `document_id`
  - `file_name`
  - `file_extension`
  - `chunk_count`
  - `indexed`
  - `errors`
- `ChatService.index_document_file(...)` now delegates to the wrapper.

Safety assessment:

- Chainlit upload display-name behavior is preserved.
- Existing loader behavior is preserved.
- Existing LangChain-Chroma indexing path is preserved.
- No LLM chunking or new retrieval logic was added.

Risk:

- The result type has an `errors` field, but current failures still propagate as
  exceptions to existing caller-side handling. This is acceptable because it
  preserves current behavior.

### `cfc19c6` - Optional LLM/hybrid routing

Files:

- `.env.example`
- `app.py`
- `src/config.py`
- `src/chat_service.py`
- `src/routing/routing_agent.py`
- `tests/test_routing_agent.py`
- doc update

What changed:

- Added `ROUTING_MODE=rule|llm|hybrid`.
- Added optional LLM structured-output routing.
- Added fallback to deterministic rule routing on:
  - missing model
  - model exception / timeout-like errors
  - invalid JSON
  - missing structured fields
  - invalid or low confidence
- Added trace fields:
  - `routing_mode`
  - `routing_fallback_reason`

Safety assessment:

- Default remains `rule`.
- Rule mode does not call the model, even if a model object is passed.
- Tests use fake routing models only.
- Normal pytest does not require cluster/API access.
- App startup constructs the normal model wrapper as before, but routing does
  not call it unless `ROUTING_MODE=llm` or `ROUTING_MODE=hybrid`.

Risk:

- In `llm` or `hybrid` mode, routing adds one model call before retrieval. If
  API credentials are invalid, the call fails and falls back to rule routing.
- Missing API key is handled indirectly through model-call exceptions rather
  than a separate preflight API-key check.
- In fallback after invalid LLM output, document memory follows the deterministic
  rule route. This is safe but means a document-like query can still enable
  document memory after fallback, which matches current deterministic behavior.

### `3ac1f0c` - Memory and document inspection helpers

Files:

- `src/documents/inspection.py`
- `scripts/inspect_document_memory.py`
- `tests/test_document_inspection.py`

What changed:

- Added helper rows for document inspection.
- Document inspection now targets the Chroma `document_memory` collection only.
- Added Chroma metadata inspection.
- Added CLI:

```bash
uv run python scripts/inspect_document_memory.py
uv run python scripts/inspect_document_memory.py --backend sqlite --limit 5
uv run python scripts/inspect_document_memory.py --backend chroma --document-id <id>
```

Safety assessment:

- The helpers do not retrieve documents.
- The helpers do not call the LLM.
- The helpers do not index documents.
- The obsolete SQLite document inspection path has been removed.
- Chroma inspection reads collection metadata.

Risk:

- `chromadb.PersistentClient` may create/open Chroma storage if the path is
  missing. This does not mutate application database rows or retrieval logic,
  but it is not a strict read-only transaction. A future improvement could add a
  path-exists check before constructing the Chroma client.

## 3. Default Behavior Preservation Check

Default behavior is preserved.

- `ROUTING_MODE=rule` is documented in `.env.example`.
- `AppConfig.from_env()` defaults `routing_mode` to `"rule"`.
- `ChatService` passes `routing_mode` to `RoutingAgent`, but the default remains
  `"rule"`.
- `RoutingAgent.route(...)` immediately uses `_rule_decision(...)` in rule mode.
- Rule mode does not call `model.chat(...)`.
- Retriever source flags remain compatible with `RetrieverDispatcher`.
- ContextPacket validation and fallback are still in `CoordinatorAgent`.
- Document upload still returns the existing `DocumentFileIndexResult` shape to
  Chainlit.

## 4. LLM Routing Safety Check

LLM routing is optional and guarded.

Safe properties:

- Disabled by default.
- Uses mock/fake models in tests.
- Requires explicit `ROUTING_MODE=llm` or `ROUTING_MODE=hybrid`.
- Catches broad model/parse/validation exceptions and falls back.
- Records `routing_mode` and `routing_fallback_reason` in trace metadata.

Fallback cases covered by tests:

- missing model
- invalid JSON
- low confidence
- model exception
- valid LLM decision
- hybrid mode preserving recent/structured memory sources

Potential gap:

- Missing API key is not checked before the routing call. It is handled by the
  model exception path if the provider rejects the request. This is acceptable
  for preserving behavior, but a future UX improvement could produce a cleaner
  `routing_fallback_reason=missing_api_key` before attempting the call.

## 5. Test Coverage Summary

New/updated test coverage is strong for the scope of these commits:

- Routing:
  - representative deterministic routing table
  - LLM structured-output success
  - hybrid mode behavior
  - missing model fallback
  - invalid JSON fallback
  - low confidence fallback
  - model error fallback
  - stable trace fields
- Context manager:
  - metadata generation
  - source budget exposure
  - included/dropped candidate counts
  - integration through architecture-layer tests
- Document ingestion:
  - structured result contract
  - display-name preservation for Chainlit temp uploads
  - object/dict index result normalization
  - loader error propagation
- Inspection:
  - Chroma document metadata grouping
  - Chroma metadata grouping without Chroma dependency
  - CLI formatting

No tests use live LLM calls or cluster/API access.

## 6. Risks and Limitations

1. Optional LLM routing has not been validated with a real model endpoint.
   This is intentional; tests remain deterministic. Real endpoint behavior
   should be verified manually only after demo-critical paths are stable.

2. Optional LLM routing depends on model JSON obedience. Invalid JSON is safe
   because it falls back, but it may reduce the value of LLM routing in practice
   without a stronger schema/parser.

3. Chroma document inspection is metadata-only and useful for demos, but not a
   strict read-only transaction because Chroma client creation may initialize
   local storage.

4. `DocumentIngestionResult.errors` is currently mostly a result-contract field;
   exceptions still propagate for failures to preserve existing behavior.

5. ContextManagerAgent improves architecture clarity and traceability but does
   not yet change context quality. It should be presented as a responsibility
   wrapper, not a new context algorithm.

## 7. Recommended Next Implementation Tasks

1. Keep `ROUTING_MODE=rule` for demos unless there is a specific reason to show
   optional LLM routing.

2. Add a small manual command or verifier for `ROUTING_MODE=llm` only if you
   need to demonstrate routing mode switching. Do not make it part of normal
   tests.

3. Tighten Chroma inspection read-only behavior by checking whether the Chroma
   persist directory exists before constructing `PersistentClient`.

4. Use the inspection scripts during demo setup:

```bash
uv run python scripts/inspect_long_term_memory.py --limit 20
uv run python scripts/inspect_document_memory.py --limit 20
```

5. Continue with demo-facing polish rather than further architecture changes:
   stable demo DB reset, visible memory trace, and one reliable cross-chat
   memory walkthrough.

## 8. Exact Commands Run and Results

Repository inspection:

```bash
git status --short
```

Result: clean worktree before generating this report.

```bash
git log --oneline --decorate -12
```

Result included:

```text
3ac1f0c (HEAD -> demo_mid_term) feat: add memory and document inspection helpers
cfc19c6 feat: add optional LLM routing policy with fallback
a9b31d0 refactor: add DocumentIngestionAgent wrapper
cc653a2 refactor: add ContextManagerAgent wrapper
ffaacb5 (origin/demo_mid_term) eval: add memory lifecycle benchmark cases
```

```bash
git diff --stat ffaacb5..HEAD
```

Result: 17 files changed, 1227 insertions, 52 deletions.

```bash
git diff --name-status ffaacb5..HEAD
```

Result: changes limited to agent wrappers, routing/config/doc updates,
inspection helpers, and tests.

Per-commit summaries:

```bash
git show --stat --summary cc653a2
git show --stat --summary a9b31d0
git show --stat --summary cfc19c6
git show --stat --summary 3ac1f0c
```

Result: all commands succeeded and matched the commit summaries above.

Verification:

```bash
uv run python -m compileall app.py src scripts evals tests
```

Result: passed.

```bash
uv run pytest -q tests/test_routing_agent.py
```

Result: `10 passed`.

```bash
uv run pytest -q tests/test_architecture_layers.py
```

Result: `9 passed`.

```bash
uv run pytest -q tests/test_context_builder.py
```

Result: `7 passed`.

```bash
uv run pytest -q tests/test_document_loaders.py tests/test_chat_service_file_uploads.py
```

Result: `13 passed, 1 skipped`.

```bash
uv run pytest -q tests/test_structured_memory_eval.py
```

Result: `6 passed`.

```bash
uv run pytest -q
```

Result: `150 passed, 1 skipped, 1 warning`.

```bash
uv run ruff check .
```

Result: all checks passed.
