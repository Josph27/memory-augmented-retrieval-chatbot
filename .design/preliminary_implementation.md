# Preliminary Implementation Plan — Bridging Codebase to Design Spec

**Based on:** `design_description.txt` and oracle gap analysis (`design_unification.md` §7)
**Current codebase coverage:** ~35–40% of full spec
**Estimated total effort:** 2–3 weeks (3–4 devs) or 6–8 weeks (1 dev)

---

## Priority Legend

| Tier | Meaning | Urgency |
|------|---------|---------|
| **P0** | Blocking prerequisites — trivial effort, high payoff | Do first |
| **P1** | Core pipeline features — unlock dependent work | Immediately after P0 |
| **P2** | Spec compliance — specific agents/actions | After P1, parallelisable |
| **P3** | Quality improvements — not blocking | When convenient |
| **P4** | UI surface — largest effort, backend-independent | Last, or parallel |

---

## P0 — Enable GIST Pipeline (Effort: Low)

> **Status:** `chat_gists` table exists, `chat_gist_summarizer.py` exists, retrieval DISABLED.
> **Goal:** Activate the dormant GIST layer so the memory pipeline can route through GISTs per spec.

### Step P0.1 — Enable GIST retrieval flags

- **File:** `src/config.py` (AppConfig)
- **Change:** Flip defaults:
  - `PREVIOUS_CHAT_GIST_GENERATION_ENABLED`: `false` → `true`
  - `PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED`: `false` → `true`
- **Dependencies:** None
- **Risk:** GIST retrieval may return empty/noisy results on first enable — expected, will improve as GISTs accumulate.
- **Test:** Run existing tests (`test_context_manager_agent.py`, `test_structured_memory_eval.py`) to verify no regressions. Manual test: start a chat, generate several turns, verify `chat_gists` table populates.
- **Effort:** 0.5h

### Step P0.2 — Integrate GIST retrievers into active memory pipeline

- **Files (modify):**
  - `src/retrieval/retriever_dispatcher.py` — ensure GIST retrievers are dispatched when RoutePlan enables them
  - `src/routing/route_planner.py` — add GIST sources to source plans when appropriate
  - `src/memory/short_term.py` — wire GIST-based retrieval into memory update path
- **Files (new):** None
- **Changes:**
  - `RoutePlanner`: enable `current_chat_gist` and `previous_chat_gist` in `RoutePlan` when `PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED` is true
  - `RetrieverDispatcher`: verify gist retrievers produce `MemoryCandidate` objects
  - `ShortTermMemory.update_memory_if_needed()`: after LangMem extraction, also trigger `@GISTING_AGENT` to store a gist record (currently gists are generated but not linked to the memory update cycle)
- **Dependencies:** P0.1
- **Risk:** Current gist retrievers are "lexical stubs" per `context.md`. They may need enhancement to use semantic search before being useful. Monitor retrieval quality.
- **Test:** Add integration test: send 3+ messages in a chat, call `update_memory_if_needed()`, verify `chat_gists` has new rows with correct `source_type`.
- **Effort:** 2h

### Step P0.3 — Align GIST schema with spec

- **File:** `src/database.py` — `init_schema()` and `Database` methods
- **Change:** Add columns to `chat_gists`:
  - `retrieved_lt_mem_list_json TEXT NOT NULL DEFAULT '[]'` — tracks which lt_mem IDs were retrieved
  - `new_memories_json TEXT NOT NULL DEFAULT '[]'` — `{id, memory, embed_id}` per new memory
- **Migration:** Use `_ensure_*_column()` pattern (existing pattern in `database.py` for `messages.summarized`, `chats.model_name`)
- **Dependencies:** P0.1
- **Risk:** Existing rows have NULL for new columns — default handles this. No data loss.
- **Test:** Verify `init_schema()` creates new columns. Verify `INSERT`/`SELECT` work correctly with new fields.
- **Effort:** 1.5h

### Step P0.4 — Add `use_count` metadata to `long_term_memories`

- **File:** `src/database.py`
- **Change:** Add `use_count INTEGER NOT NULL DEFAULT 0` column to `long_term_memories`
- **Migration:** `_ensure_long_term_memories_use_count_column()`
- **Files (modify):** `src/memory/long_term_store.py` — increment `use_count` on every retrieval
- **Dependencies:** None (can be done independently of P0.1-P0.3)
- **Risk:** Minimal — additive schema change.
- **Test:** Retrieve a memory, verify `use_count` increments.
- **Effort:** 1h

---

## P1 — Query Decomposition & Semantic Expansion (Effort: Medium)

> **Status:** Not implemented. `QueryAnalyzer` does deterministic lexical signal detection only.
> **Goal:** Implement `@QUERY_AUGMENTATION_AGENT` with sub-query decomposition + keyword injection.

### Step P1.1 — Create `QueryDecomposer` module

- **File (new):** `src/routing/query_decomposer.py`
- **Dataclass (new in `src/core/contracts.py`):**

  ```python
  @dataclass(frozen=True)
  class SubQuery:
      text: str
      intent: str | None = None
      sources: tuple[str, ...] = ()
  ```

- **Class:** `QueryDecomposer`
  - Accepts `ModelWrapper` for LLM-backed decomposition
  - Method: `decompose(query: str) -> list[SubQuery]`
  - Deterministic fallback: if LLM returns invalid/empty, return single SubQuery with original text
  - LLM prompt: "Split this query into independent sub-queries..."
- **Style:** Follows `QueryAnalyzer` pattern. Dataclass contract in `contracts.py`, logic class in `routing/`.
- **Dependencies:** None (uses existing `ModelWrapper`)
- **Risk:** LLM may over-split or hallucinate sub-queries. Deterministic fallback is critical.
- **Test:** Unit test: simple query → single sub-query; compound query → multiple sub-queries; empty query → handled.
- **Effort:** 4h

### Step P1.2 — Create `SemanticExpander` module

- **File (new):** `src/routing/semantic_expander.py`
- **Class:** `SemanticExpander`
  - Accepts `ModelWrapper`
  - Method: `expand(sub_query: SubQuery) -> str` — injects relevant keywords into sub-query text
  - Prompt-based: "Add up to 5 relevant search keywords to the following query..."
  - Deterministic fallback: return original sub-query text unchanged
- **Dependencies:** P1.1 (operates on `SubQuery`)
- **Risk:** Keyword injection may introduce noise. Expansion should be conservative (≤5 keywords).
- **Test:** Verify keywords are appended, not replacing. Verify fallback on LLM failure.
- **Effort:** 3h

### Step P1.3 — Create `QueryAugmentationAgent`

- **File (new):** `src/agents/query_augmentation_agent.py`
- **Class:** `QueryAugmentationAgent`
  - Wraps `QueryDecomposer` + `SemanticExpander`
  - Method: `augment(query: str) -> list[SubQuery]` — decompose → expand each sub-query
  - Acts as the `@QUERY_AUGMENTATION_AGENT` from the spec
- **Dataclass:** Returns `AugmentedQuery(sub_queries: list[SubQuery], original: str)` via contracts
- **Dependencies:** P1.1, P1.2
- **Risk:** None — thin wrapper. Errors in P1.1/P1.2 propagate.
- **Test:** Integration test: query → sub-queries with expanded text.
- **Effort:** 1h

### Step P1.4 — Integrate into `CoordinatorAgent.run_turn()`

- **File:** `src/agents/coordinator_agent.py`
- **Change:** Insert augmentation stage between routing and retrieval:

  ```python
  route_plan = self._routing_agent.route(query)
  augmented = self._query_augmentation_agent.augment(query)
  # Use augmented sub-queries for retrieval (see P1.5)
  ```

- **File:** `src/core/contracts.py` — add `augmented_queries: list[SubQuery]` to `WorkflowTrace` and `AgentTurnResult` (or separate trace field)
- **Dependencies:** P1.3
- **Risk:** Adding a new stage to the pipeline may affect timing (trace it). Keep existing routing intact — augmentation is additive.
- **Test:** Integration test: full `run_turn()` with compound query, verify `WorkflowTrace` contains augmentation data.
- **Effort:** 2h

### Step P1.5 — Per-sub-query retrieval loop

- **File:** `src/agents/coordinator_agent.py`
- **Change:** Replace single `RetrieverDispatcher.retrieve()` call with per-sub-query loop:

  ```python
  all_candidates: list[MemoryCandidate] = []
  for sub_query in augmented.sub_queries:
      candidates = self._retriever_dispatcher.retrieve(
          chat_id=chat_id,
          route_plan=route_plan,
          query=sub_query.text,  # ← new parameter
      )
      all_candidates.extend(candidates)
  # Deduplicate by record_id before reranking
  ```

- **Files (modify):** `src/retrieval/retriever_dispatcher.py` — add optional `query` parameter (default: use original query)
- **Dependencies:** P1.4
- **Risk:** Retrieval time scales with sub-query count. Set a `MAX_SUB_QUERIES` constant (default: 3). Document retrieval may be heavy — spec says "docs (sometimes) dense retrieval"; RoutePlanner should gate doc retrieval per sub-query.
- **Test:** Verify deduplication. Verify retrieval trace includes per-sub-query timing.
- **Effort:** 3h

---

## P2 — Cross-Encoder Reranker & Chat Lifecycle (Effort: Medium-High)

> **Status:** Reranking exists (feature-scoring + LLM) but not cross-encoder. Chat lifecycle absent.
> **Goal:** Add `@RE_RANK_AGENT[CROSS_ENCODER]` and implement CHAT_END_ACTION + CHAT_FORK_ACTION.

### Step P2.1 — Add cross-encoder dependency

- **File:** `pyproject.toml`
- **Change:** Add `sentence-transformers` dependency (if not already via HuggingFace). The `all-MiniLM-L6-v2` is already used for embeddings — cross-encoder may use a different model (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`).
- **File:** `src/config.py` — add config fields:
  - `CROSS_ENCODER_MODEL_NAME: str` (default: `cross-encoder/ms-marco-MiniLM-L-6-v2`)
  - `CROSS_ENCODER_TOP_K: int` (default: `20`, how many candidates to re-score)
  - `CROSS_ENCODER_MEM_K: int` (default: `8`, memory top-k after scoring)
  - `CROSS_ENCODER_DOC_K: int` (default: `4`, document top-k after scoring, implements spec `mem_k > doc_k`)
- **Dependencies:** None
- **Risk:** Cross-encoder models are ~100–400MB. Loading on startup adds latency. Lazy-load on first use.
- **Test:** Unit test: model loads and scores a pair.
- **Effort:** 2h

### Step P2.2 — Create `CrossEncoderReranker`

- **File (new):** `src/retrieval/cross_encoder_reranker.py`
- **Class:** `CrossEncoderReranker`
  - Wraps `sentence_transformers.CrossEncoder`
  - Method: `rank(query: str, candidates: list[MemoryCandidate]) -> list[MemoryCandidate]`
  - For each candidate: score = `model.predict([query, candidate.content])` → [0-1] score
  - Separate cutoff by source: `mem_k` for structured_memory, `doc_k` for document_memory
  - Returns `RankedMemoryCandidate[]` (subclass with `ce_score: float`)
- **File:** `src/core/contracts.py` — add `RankedMemoryCandidate` dataclass or add `ce_score` field to `MemoryCandidate`
- **Dependencies:** P2.1
- **Risk:** N×M pairwise scoring can be slow for large candidate sets. `CROSS_ENCODER_TOP_K` limits input. Deterministic pre-filter can reduce candidate count before cross-encoder.
- **Test:** Unit test: 10 candidates, verify scores are [0-1], sorted descending.
- **Effort:** 5h

### Step P2.3 — Register cross-encoder as reranker mode

- **File:** `src/retrieval/reranker.py` — integrate with existing `MemoryReranker`
- **Change:** Add `cross_encoder` to `RERANKER_MODE` options. When mode=`cross_encoder`, `rank_with_trace()` delegates to `CrossEncoderReranker.rank()`.
- **File:** `src/config.py` — update `RERANKER_MODE` docs to include `cross_encoder`
- **Dependencies:** P2.2
- **Risk:** Ensure fallback to `deterministic` if cross-encoder fails (model not loaded, error). Follow existing pattern (LLM reranker falls back to deterministic).
- **Test:** Integration test: `MemoryReranker` with `mode=cross_encoder` produces scored candidates.
- **Effort:** 2h

### Step P2.4 — Implement `chat_active` flag & chat lifecycle

- **File:** `src/database.py`
- **Change:** Add `active INTEGER NOT NULL DEFAULT 1` to `chats` table via `_ensure_*_column()`
- **New methods:**
  - `mark_chat_inactive(chat_id: str) -> None` — sets `active=0`
  - `mark_chat_active(chat_id: str) -> None` — sets `active=1`
  - `list_active_chats() -> list[dict]` — queries `active=1`
  - `list_inactive_chats() -> list[dict]` — queries `active=0`
- **Dependencies:** None
- **Risk:** Existing queries may need `WHERE active=1` filter. Audit all `SELECT` on `chats` table.
- **Test:** Create chat → verify active=1 → mark inactive → verify active=0 → list methods.
- **Effort:** 2h

### Step P2.5 — Implement `CHAT_END_ACTION`

- **File (new):** `src/actions/chat_end.py`
- **Class:** `ChatEndAction`
  - Triggers `PROCESS_INTO_MEMORY_ACTION` (spec §CHAT_END_ACTION):
    1. Process gists: `@MEMORY_UPDATE_AGENT` reads unprocessed gist+text blocks → compressions → new-memories
    2. Update existing: foreach lt_mem, decide [update/delete/pass] based on gists+text
    3. Commit: embed new, re-embed updated (remove old by ID)
  - Calls `mark_chat_inactive(chat_id)`
- **Files (modify):** `src/memory/short_term.py` — enhance `update_memory_if_needed()` to support chat-end trigger (process ALL unsummarized, not just batch)
- **Dependencies:** P2.4, P0.2 (GIST pipeline active)
- **Risk:** Chat-end processing may be expensive (many messages). Run synchronously for now; move to background if needed. Ensure idempotent — calling twice on same chat should be safe.
- **Test:** Create chat with 10 messages → end chat → verify memories created, chat marked inactive.
- **Effort:** 4h

### Step P2.6 — Implement `CHAT_FORK_ACTION`

- **File (new):** `src/actions/chat_fork.py`
- **Class:** `ChatForkAction`
  - Duplicates: `chats` row (new UUID), all `messages` rows (new chat_id), `chat_memory_state` row, `chat_gists` rows
  - Sets new chat as `active=1`
  - Returns new `chat_id`
- **Dependencies:** P2.4
- **Risk:** Large chats may have many messages → fork is a heavy DB operation. Consider transaction wrapping.
- **Test:** Fork a chat with 5 messages → verify all data copied, new chat is active.
- **Effort:** 2h

### Step P2.7 — Implement `PRUNE_MEMORIES_ACTION`

- **File:** `src/memory/short_term.py` or new `src/actions/prune_memories.py`
- **Change:** Per spec, PRUNE_MEMORIES = PROCESS_INTO_MEMORY. This means pruning is the update cycle itself (LangMem determines what to delete). Add explicit prune trigger:
  - Method: `prune_memories(namespace: tuple[str, ...]) -> int` — forces a full memory pass, returns count of deleted memories
- **Dependencies:** P2.5 (chat lifecycle enables chat-end pruning)
- **Risk:** Aggressive pruning may delete recently valid memories. LangMem confidence threshold prevents this.
- **Test:** Create stale memories → prune → verify only low-confidence/stale memories removed.
- **Effort:** 2h

---

## P3 — Prompt Assembly & Metadata Enhancements (Effort: Low-Medium)

> **Status:** Budget-fitting context assembly exists. Ordered placement not implemented.
> **Goal:** Add ordered placement mode (not replacing budget-fitting). Add use_count metadata.

### Step P3.1 — Implement ordered prompt placement

- **File (new):** `src/context/ordered_placement_builder.py`
- **Class:** `OrderedPlacementBuilder`
  - Implements spec's static placement: `system_prompt | doc_chunks (hi→lo score) | lt_mem_chunks (lo→hi score) | raw user query`
  - "Lost in the middle" mitigation: highest doc scores at top, lowest memory scores in middle
  - Respects token budget: trims from middle (lt_mem) first when overflowing
- **File:** `src/context/context_builder.py` — add `placement` parameter (`budget_fitting` or `ordered`)
- **File:** `src/config.py` — add `CONTEXT_PLACEMENT_MODE` env var (default: `budget_fitting`)
- **Dependencies:** None (operates on ranked candidates from reranker)
- **Risk:** Ordered placement may perform worse than budget-fitting for certain query types. Keep both modes, make configurable.
- **Test:** Compare output of both modes for same input. Verify order follows spec: system, docs(hi-lo), mem(lo-hi), query.
- **Effort:** 3h

### Step P3.2 — Track `last_used` for lt_mem (in addition to `use_count`)

- **File:** `src/database.py` — add `last_used TEXT` column (ISO timestamp, NULL by default)
- **File:** `src/memory/long_term_store.py` — set `last_used=NOW()` on retrieval
- **File:** `src/memory/long_term_vector_index.py` — set `last_used` on vector retrieval hits
- **Dependencies:** P0.4 (use_count), but can be parallel
- **Risk:** Schema change is additive. Existing rows NULL for last_used.
- **Test:** Retrieve memory → verify `last_used` updated, `use_count` incremented.
- **Effort:** 1.5h

### Step P3.3 — Distinct chunk sizes for lt_mem vs. docs

- **File:** `src/config.py` — add `LT_MEM_CHUNK_SIZE` env var (default: `256`, smaller than `DOCUMENT_CHUNK_SIZE=1000`)
- **File:** `src/memory/langmem_structured.py` — apply smaller chunk size when preparing memory for embedding
- **File:** `src/documents/splitters.py` — no change (docs keep current chunking)
- **Dependencies:** None
- **Risk:** Smaller chunks may reduce embedding quality for complex memories. Test with existing memory eval.
- **Test:** Verify memory chunks are ≤ `LT_MEM_CHUNK_SIZE` tokens; doc chunks remain at `DOCUMENT_CHUNK_SIZE`.
- **Effort:** 1h

---

## P4 — ChainLit Multi-Tab UI & Manual Operations (Effort: High)

> **Status:** Single `app.py` chat page only. No tabbed navigation, no list pages.
> **Goal:** Full 5-tab ChainLit UI per spec §User Interface.

### Step P4.1 — Design UI layout & navigation

- **File:** `app.py` — restructure into tabbed layout
- **Approach:** Use Chainlit's `@cl.on_chat_start` to present a custom landing page with navigation. Use `@cl.set_chat_profiles` or custom Chainlit elements for tab switching.
- **ChainLit elements:** `cl.ChatSettings`, `cl.Action`, `cl.CustomElement` for tab content
- **Navigation:** Breadcrumbs via `cl.Element` at top: Home | Chats | Documents | Memories
- **Dependencies:** None (UI can be developed in parallel with all backend work)
- **Risk:** Chainlit 2.x does not natively support multi-tab UIs. May need to implement as single-page with conditional rendering (switch content based on current "tab" state). Research Chainlit 2.x API thoroughly.
- **Effort:** 4h (design + prototyping)

### Step P4.2 — Implement landing_page

- **File:** `app.py`
- **Features:**
  - Central "New Chat" button (triggers `NEW_CHAT_ACTION`)
  - Below: list of active chats (or "No active chats" message)
  - Each active chat clickable → opens in chat_page
- **Dependencies:** P2.4 (active/inactive chat distinction)
- **Effort:** 3h

### Step P4.3 — Implement chat_page (enhance existing)

- **File:** `app.py`
- **Features:**
  - Left sidebar: list of active chats (reuse from P4.2)
  - Middle: chat interface (existing `@cl.on_message` logic)
  - Right side: (optional) debug panel / memory trace
  - Action buttons below chat input: NEW_CHAT, END_CHAT, FORK_CHAT, UPLOAD_DOC
- **Dependencies:** P2.5 (CHAT_END), P2.6 (CHAT_FORK)
- **Effort:** 5h

### Step P4.4 — Implement chats_list_page

- **File:** `app.py`
- **Features:**
  - Search bar at top (filter by chat title)
  - List of active chats (click to open)
  - Below: list of inactive chats
  - Hover inactive chat → "Activate" button
- **Dependencies:** P2.4
- **Effort:** 3h

### Step P4.5 — Implement docs_list_page

- **File:** `app.py`
- **Features:**
  - Central column: list of all documents
  - Inactive documents grayed out
  - Top button: "Add Docs" (file upload)
  - Each document: "Suppress" and "Delete" buttons
- **Dependencies:** None (backend doc management exists via `Database` + `DocumentIngestionAgent`)
- **New backend methods:** `Database.suppress_document(doc_id)`, `Database.delete_document(doc_id)`, `Database.list_documents(active_only: bool)`
- **Effort:** 4h (UI) + 2h (backend methods)

### Step P4.6 — Implement memories_list_page

- **File:** `app.py`
- **Features:**
  - Central column: list of all lt_mem entries
  - Top button: "Add Memory" (opens input for manual memory insertion)
  - Each memory: "Delete" button
  - Search bar (filter by key/value content)
- **Dependencies:** P0.4 (use_count metadata enhances display)
- **New backend methods:** `Database.insert_manual_memory(namespace, key, value, category)`, `Database.delete_memory_by_id(memory_id)`, `Database.list_all_memories(search: str | None)`
- **Effort:** 4h (UI) + 2h (backend methods)

### Step P4.7 — Wire UI actions to backend

- **File:** `app.py`
- **Change:** For each action button, call corresponding backend action:
  - NEW_CHAT → `ChatService.create_chat()` → navigate to chat_page
  - CHAT_END → `ChatEndAction.execute(chat_id)` → navigate to landing_page
  - CHAT_FORK → `ChatForkAction.execute(chat_id)` → navigate to new chat
  - SUPPRESS_DOC → `Database.suppress_document(doc_id)` → refresh docs_list_page
  - DELETE_MEMORY → `Database.delete_memory_by_id(memory_id)` → refresh memories_list_page
  - ADD_MEMORY → `Database.insert_manual_memory(...)` → refresh memories_list_page
- **Dependencies:** All prior P2 and P4 steps
- **Effort:** 4h

---

## Dependency Graph

```
P0.1 (enable flags) ──► P0.2 (integrate GIST) ──► P0.3 (align GIST schema)
                                                    │
P0.4 (use_count) ──────────────────────────────────┤
                                                    │
P1.1 (decomposer) ──► P1.2 (expander) ──► P1.3 (augmentation agent) ──► P1.4 (coordinator integ) ──► P1.5 (per-sub-query loop)
                                                                              │
P2.1 (cross-enc dep) ──► P2.2 (cross-enc class) ──► P2.3 (reranker mode) ───┤
                                                                              │
P2.4 (chat active) ──► P2.5 (chat end) ──► P2.6 (chat fork) ──► P2.7 (prune)┤
                                                                              │
P3.1 (ordered placement) ────────────────────────────────────────────────────┤
P3.2 (last_used) ────────────────────────────────────────────────────────────┤
P3.3 (chunk sizes) ──────────────────────────────────────────────────────────┤
                                                                              │
P4.1 (UI design) ──► P4.2 (landing) ──► P4.3 (chat page) ──► P4.4 (chats list)
                         │                     │
P4.5 (docs list) ───────┘                     │
P4.6 (memories list) ─────────────────────────┘
                         │
P4.7 (wire actions) ────┘
```

### Parallelisation Opportunities

- **P0 + P1 + P2 backend** can all develop in parallel (different files, no conflicts)
- **P3** is fully independent of P0-P2
- **P4** can start after P2.4 (chat_active flag), but can prototype earlier with mock data
- **Testing** can be written alongside each step (not after)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **GIST pipeline low quality** | GIST retrievers are lexical stubs; enabling them may produce noisy/no results | P0.2 includes monitoring step. If quality is low, enhance with semantic search before broad enable. |
| **Cross-encoder model size/latency** | 100–400MB model load + pairwise scoring may add 1–5s per query | Lazy-load, pre-filter candidates to TOP_K before cross-encoder, cache model. |
| **Chainlit 2.x limitations** | Chainlit may not support multi-tab/full-SPA navigation | Prototype in P4.1 first. Fallback: multi-page app with separate `app_*.py` files loaded via Chainlit config. |
| **Schema migrations** | New columns may break existing deployments | Use `_ensure_*_column()` pattern. All migrations are additive (no DROP, no data loss). |
| **LLM dependency for augmentation** | P1 relies on LLM for decomposition + expansion | Every LLM call has deterministic fallback. Augmentation is optional per spec. |
| **Per-sub-query retrieval explosion** | 3 sub-queries × 6 sources = 18 retrieval calls per turn | Set `MAX_SUB_QUERIES=3`, doc retrieval gated per sub-query by RoutePlanner, cached embeddings. |
| **Chat-end processing slowness** | Processing entire chat at end may block UI | Run synchronously for now. Future: background task/queue. Idempotent — safe to retry. |

---

## Files Summary

### New Files (12 expected)

```
src/routing/query_decomposer.py           # P1.1 — LLM-backed query decomposition
src/routing/semantic_expander.py          # P1.2 — LLM-backed keyword injection
src/agents/query_augmentation_agent.py    # P1.3 — wraps decomposer + expander
src/retrieval/cross_encoder_reranker.py   # P2.2 — cross-encoder ranking
src/actions/__init__.py                   # P2.5 — actions package
src/actions/chat_end.py                   # P2.5 — CHAT_END_ACTION
src/actions/chat_fork.py                  # P2.6 — CHAT_FORK_ACTION
src/actions/prune_memories.py             # P2.7 — PRUNE_MEMORIES_ACTION
src/context/ordered_placement_builder.py  # P3.1 — ordered prompt placement
```

### Modified Files (11 expected)

```
src/config.py                         # P0.1, P2.1, P2.3, P3.1, P3.3 — new config fields
src/database.py                       # P0.3, P0.4, P2.4, P3.2, P4.5, P4.6 — schema changes + new methods
src/core/contracts.py                # P1.1, P1.3, P2.2 — new dataclasses (SubQuery, etc.)
src/routing/route_planner.py          # P0.2 — enable GIST sources
src/retrieval/retriever_dispatcher.py # P0.2 — integrate GIST retrievers
src/memory/short_term.py             # P0.2, P2.5, P2.7 — GIST integration + chat-end + prune
src/memory/long_term_store.py         # P0.4, P3.2 — use_count + last_used
src/memory/long_term_vector_index.py  # P0.4, P3.2 — use_count + last_used
src/memory/langmem_structured.py      # P3.3 — smaller chunk size
src/retrieval/reranker.py            # P2.3 — cross_encoder mode
src/agents/coordinator_agent.py       # P1.4, P1.5 — augmentation + per-sub-query loop
app.py                                # P4.1–P4.7 — full UI rework
pyproject.toml                        # P2.1 — sentence-transformers dep
```

### New Tests Expected (15+)

```
tests/test_query_decomposer.py
tests/test_semantic_expander.py
tests/test_query_augmentation_agent.py
tests/test_cross_encoder_reranker.py
tests/test_chat_end_action.py
tests/test_chat_fork_action.py
tests/test_prune_memories_action.py
tests/test_ordered_placement_builder.py
tests/test_gist_integration.py
tests/test_chat_lifecycle.py (P0.3 + P2.4)
tests/test_use_count_tracking.py (P0.4 + P3.2)
tests/test_database_migrations.py (schema changes)
tests/test_coordinator_with_augmentation.py (integration)
tests/test_per_subquery_retrieval.py (integration)
tests/test_ui_actions.py (UI smoke tests)
```

---

## Implementation Order Recommendation

### Sprint 1 (Week 1): Foundations

1. P0.1 → P0.2 → P0.3 (GIST pipeline enablement)
2. P0.4 (+ P3.2 + P3.3 in parallel — all schema/config)
3. P2.4 (chat_active flag — unblocks P4)

### Sprint 2 (Week 2): Pipeline

4. P1.1 → P1.2 → P1.3 → P1.4 → P1.5 (query augmentation chain)
2. P2.1 → P2.2 → P2.3 (cross-encoder)

### Sprint 3 (Week 3): Actions + Prompt

6. P2.5 → P2.6 → P2.7 (chat lifecycle actions)
2. P3.1 (ordered placement)

### Sprint 4 (Week 4+): UI

8. P4.1 → P4.2 → P4.3 → P4.4 → P4.5 → P4.6 → P4.7 (all UI)

---

*Generated from oracle gap analysis (§7 of design_unification.md) and formal design spec (design_description.txt).*
