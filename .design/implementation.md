# Implementation Plan — Codebase → Design Spec

**Based on:** `design_description.txt` (formal spec), oracle gap analysis
(`design_unification.md` §7), code-style conventions (`code-style.md`), and
two rounds of deep oracle review (25 + 28 findings).
**Current coverage:** ~35–40% of spec. **Target coverage:** ~92%+.

---

## 0. Execution Order (Dependency-Corrected, Post-Final-Oracle)

```
Phase 0 — GIST Pipeline + Metadata (prerequisites)
  P0.1 → P0.4
  P0.5 → P0.2 → P0.3          (GistingAgent created BEFORE integrated into coordinator)

Phase 1 — Query Processing (unlocks per-sub-query retrieval)
  P1.1 → P1.2 → P1.3 → P1.4 → P1.5

Phase 2 — Reranking + Chat Lifecycle
  P2.1 → P2.2 → P2.3 → P1.5  (cross-encoder feeds per-sub-query reranking)
  P2.4 → P2.5 → P2.6          (chat lifecycle; PRUNE_MEMORIES merged into P2.5)
  P0.2, P0.5 → P2.5           (CHAT_END reads GISTs; GistingAgent must exist)

Phase 3 — Prompt Assembly & Metadata
  P2.3 → P3.1                  (ordered placement uses cross-encoder scores)
  P0.4 → P3.2
  P3.3                         (at embedding layer, not LangMem)

Phase 4 — ChainLit UI + Manual Operations
  P4.1 → P4.2 → P4.3 → P4.4 → P4.5 → P4.6 → P4.7
  P2.4 → P4.2–P4.7             (UI needs active/inactive distinction)
  P2.5 → P4.7                  (CHAT_END wired to UI)
  P2.6 → P4.7                  (CHAT_FORK wired to UI)

Phase 5 — Evaluation Suites Update
  P5.1 → P5.2 → P5.3
```

---

## Architectural Note: Memory Processing Tension

The design specifies `GIST` records for tracking conversation summaries and
`LangMem` for structured memory processing. **GISTs populate for retrieval;
LangMem processes raw messages for memory operations. These are complementary,
not redundant.** The GIST pipeline provides rapid, summarization-based retrieval
candidates, while LangMem systematically extracts and manages structured facts
(the update/delete/skip tri-state). Both pipelines coexist to satisfy the full
design spec.

---

## Phase 0 — Enable GIST Pipeline & Metadata (Effort: ~7h)

### P0.1 — Flip GIST config flags

- **File:** `src/config.py` (AppConfig.from_env)
- **Change:** Change defaults:
  - `PREVIOUS_CHAT_GIST_GENERATION_ENABLED`: `false` → `true`
  - `PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED`: `false` → `true`
- **No new files**
- **Style:** Per `code-style.md` §1, all config fields are `@dataclass(frozen=True)` with env-var loading via `from_env()`. No change to structure needed.
- **Deps:** None.
- **Risk:** Low. GIST retrieval may initially return empty/noisy results until chats accumulate.
- **Verify:** Run `pytest tests/test_context_manager_agent.py tests/test_structured_memory_eval.py`. Manual: start chat, send 3+ turns, check `chat_gists` table populates.

### P0.4 — Add `use_count` to `long_term_memories`

- **File:** `src/database.py`
- **Change:** Add `use_count INTEGER NOT NULL DEFAULT 0` column via `_ensure_long_term_memories_use_count_column(conn)`.
- **Files (modify):** `src/memory/long_term_store.py` — increment `use_count` on every `retrieve()` call (after successful retrieval).
- **Deps:** None.
- **Risk:** Minimal. Additive schema.
- **Verify:** Test: retrieve a memory twice → `use_count` = 2.

### P0.5 — Create `GistingAgent`

- **File (new):** `src/agents/gisting_agent.py`
- **Class:** `GistingAgent`

  ```python
  @dataclass(frozen=True)
  class GistResult:
      gist_id: int
      gist_text: str
      topics_json: str
      retrieved_lt_mem_ids: list[int]  # populated during retrieval
      new_memories_json: str           # [{"id": ..., "memory": ..., "embed_id": ...}, ...]

  class GistingAgent:
      """Creates a GIST from a (query, answer) pair and persists it into chat_gists."""

      def __init__(self, database: Database, model: ModelWrapper) -> None: ...

      def create_gist(
          self, *, chat_id: str, query: str, answer: str,
          retrieved_memory_ids: list[int] | None = None,
          new_memory_entries: list[dict[str, str]] | None = None,
      ) -> GistResult:
          """Generate and persist a GIST record."""
  ```

  - Uses `ModelWrapper` to produce a short (1–3 sentence) gist from the (query, answer) pair.
  - Deterministic fallback: store the raw query as gist text if model fails.
  - Populates `retrieved_lt_mem_list_json` and `new_memories_json` from caller-supplied data.
- **DI Wiring (per oracle F7):** `CoordinatorAgent.__init__()` MUST accept and store a `gisting_agent: GistingAgent | None` parameter. Or wire through `ChatService`. This step MUST be verified: if `gisting_agent is None`, GIST creation is gracefully skipped (no crash). The `GistingAgent` is created/injected by `ChatService` during `CoordinatorAgent` construction.
- **Style:** Follows `code-style.md` §4 (Agent pattern): `@dataclass(frozen=True)` result, public method with keyword-only args, `_private` internal helper, `ModelWrapper` dependency injection.
- **Deps:** None (uses existing `Database` and `ModelWrapper`).
- **Risk:** Model call for gist generation adds latency. Mitigation: gist text is short (≤150 chars), model call is fast. Fallback handles model failure gracefully.
- **Growing concern (per oracle F15):** The `chat_gists` table grows unboundedly. Document this as a known limitation — future maintenance should add periodic gist compaction or a retention policy. Short-term: acceptable for project scope.
- **Verify:** Unit test: call `create_gist(query="...", answer="...")` → row in `chat_gists`. Test with `retrieved_memory_ids` → `retrieved_lt_mem_list_json` populated.
- **Rollback criteria (per oracle correction #16):** If after 10 queries fewer than 20% of gist retrievals return valid results (non-empty, relevant), log warning and auto-disable via `PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED=false`. Track in `WorkflowTrace.metadata["gist_quality"]`.

### P0.2 — Integrate GIST retrievers + wire GistingAgent into Coordinator

- **Files (modify):**
  - `src/routing/route_planner.py` — enable `current_chat_gist` and `previous_chat_gist` sources in `RoutePlan` when `PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED` is true.
  - `src/retrieval/retriever_dispatcher.py` — verify gist retrievers produce valid `MemoryCandidate` list for enabled gist sources. No structural changes if they already conform; add logging if empty.
  - **`src/agents/coordinator_agent.py`** — after `ChatAgent.generate()` and BEFORE `update_memory_if_needed()`, invoke `self._gisting_agent.create_gist()` to persist a gist record linking the turn's (Q,A) pair. (Per oracle F1: GIST creation belongs at SINGLE_REQUEST_ACTION reply-processing time in the coordinator turn pipeline, not in `short_term.py`.)
- **No new files**
- **Style:** `RetrieverDispatcher` already dispatches per-source per existing pattern (§4 of code-style.md). Keep the same method signature pattern.
- **Deps:** P0.1, P0.5.
- **Risk:** Gist retrievers are currently lexical stubs. If retrieval quality is poor, they still function but may produce low-value candidates — acceptable at this enablement phase.
- **Verify:** Integration test — create chat with 3+ messages, run coordinator turn, verify `chat_gists` has new row with correct `source_type`.

### P0.3 — Add GIST schema columns per spec

- **File:** `src/database.py`
- **Change:** Add columns to `chat_gists` via `_ensure_*_column()` pattern:
  - `retrieved_lt_mem_list_json TEXT NOT NULL DEFAULT '[]'` — tracks which lt_mem IDs were retrieved for this gist.
  - `new_memories_json TEXT NOT NULL DEFAULT '[]'` — `[{"id": ..., "memory": ..., "embed_id": ...}, ...]` per spec.
- **Migration:** `_ensure_chat_gists_retrieved_lt_mem_list_column(conn)` and `_ensure_chat_gists_new_memories_column(conn)` per existing pattern (`_ensure_messages_summarized_column`, `_ensure_chats_model_name_column`).
- **Deps:** P0.1.
- **Risk:** Zero data loss — defaults handle existing rows. Additive only.
- **Verify:** Run `pytest tests/test_database_migrations.py`. Manual: `INSERT INTO chat_gists ...` with new fields, `SELECT` back.

---

## Phase 1 — Query Decomposition & Semantic Expansion (Effort: ~13h)

### P1.1 — Create `QueryDecomposer`

- **File (new):** `src/routing/query_decomposer.py`
- **Contract (add to `src/core/contracts.py`):**

  ```python
  @dataclass(frozen=True)
  class SubQuery:
      text: str
      intent: str | None = None
      sources: list[str] = field(default_factory=list)  # MemorySourceType string names
  ```

  (Per oracle F3: use `list[str]` not `tuple[str, ...]` to match `MemorySourceType` string names used throughout the codebase.)

- **Class:** `QueryDecomposer`

  ```python
  class QueryDecomposer:
      """LLM-backed sub-query decomposition with deterministic fallback."""

      def __init__(self, model: ModelWrapper) -> None: ...
      def decompose(self, query: str) -> list[SubQuery]:
          """Split query into 1..N independent sub-queries."""
  ```

  - LLM prompt: "Split this query into independent sub-queries..." → parse structured output.
  - Deterministic fallback: if LLM returns empty/invalid, return single `SubQuery(text=query)`.
  - **[Oracle F6]** `MAX_SUB_QUERIES = 3` defined as module-level constant in `query_decomposer.py` (per `code-style.md` §3.4: UPPER_CASE at module level).
- **Style:** `code-style.md` §4 (Routing strategy pattern). `SubQuery` is `frozen=True` dataclass in `contracts.py`. LLM call wrapped with try/except → deterministic fallback.
- **Deps:** None (uses existing `ModelWrapper`).
- **Verify:** Unit test: `decompose("tell me about Python")` → 1 sub-query. `decompose("compare Python and Rust for web servers")` → 2+ sub-queries. Empty string → handled gracefully.

### P1.2 — Create `SemanticExpander`

- **File (new):** `src/routing/semantic_expander.py`
- **Class:** `SemanticExpander`

  ```python
  class SemanticExpander:
      """LLM-prompt-based keyword injection. No dictionaries."""

      def __init__(self, model: ModelWrapper) -> None: ...
      def expand(self, sub_query: SubQuery) -> str:
          """Inject ≤5 relevant search keywords into the sub-query text."""
  ```

  - Prompt: "Add up to 5 relevant search keywords to this query..."
  - Deterministic fallback: return `sub_query.text` unchanged.
  - Output: augmented text string (not a new dataclass — just modified text).
- **Deps:** P1.1 (operates on `SubQuery`).
- **Verify:** Unit test: `expand(SubQuery(text="How does Kafka work"))` → text contains keywords like "message broker", "partitioning". Test fallback on model failure.

### P1.3 — Create `QueryAugmentationAgent`

- **File (new):** `src/agents/query_augmentation_agent.py`
- **Contract (add to `src/core/contracts.py`):**

  ```python
  @dataclass(frozen=True)
  class AugmentedQuery:
      sub_queries: list[SubQuery]
      original: str
  ```

- **Class:** `QueryAugmentationAgent`

  ```python
  class QueryAugmentationAgent:
      """Wraps QueryDecomposer + SemanticExpander. Implements @QUERY_AUGMENTATION_AGENT."""

      def __init__(self, decomposer: QueryDecomposer, expander: SemanticExpander) -> None: ...
      def augment(self, query: str) -> AugmentedQuery:
          """Decompose → expand each sub-query → return AugmentedQuery."""
  ```

- **Deps:** P1.1, P1.2.
- **Style:** Thin wrapper per `code-style.md` §4 (Agent pattern). No new LLM calls — delegates to injected services.
- **Verify:** Integration test: `augment("compare Python and Rust")` → 2+ sub-queries, each with expanded text.

### P1.4 — Wire augmentation into `CoordinatorAgent`

- **Files (modify):**
  - `src/config.py` — add `QUERY_AUGMENTATION_ENABLED: bool = True` to `AppConfig` and env loading.
  - `src/agents/coordinator_agent.py`
- **Change per oracle correction #9 & H1:** Insert augmentation stage between routing and retrieval:

  ```python
  def run_turn(self, chat_id: str, content: str) -> AgentTurnResult:
      route_plan = self._routing_agent.route(query)
      # --- NEW: query augmentation ---
      if self.config.query_augmentation_enabled:
          augmented = self._query_augmentation_agent.augment(query)
      else:
          augmented = AugmentedQuery(sub_queries=[SubQuery(text=query, sources=route_plan.sources)], original=query)
      # Sub-queries inherit source enablement from the route plan
      # ---
      # Per-sub-query retrieval loop (see P1.5)
      ...
  ```

  - `QueryAnalyzer` still runs (provides lexical signals to `RoutePlanner`).
  - `RoutePlanner` output feeds into augmentation, not directly into retrieval.
  - Each `SubQuery` inherits source enablement from `route_plan.sources`.
- **Files (modify):** `src/core/contracts.py` — add `augmented_query: AugmentedQuery | None` field to `WorkflowTrace`.
- **Deps:** P1.3.
- **Risk:** Adding a new pipeline stage. Mitigation: make augmentation optional via config (`QUERY_AUGMENTATION_ENABLED`, default `true`). Keep existing routing fallback path.
- **Verify:** Integration test: `run_turn()` with compound query, verify `WorkflowTrace.augmented_query` populated.

### P1.5 — Per-sub-query retrieval loop

- **Files (modify):**
  - `src/agents/coordinator_agent.py` — per-sub-query loop with `replace()`-built `sub_route_plan`.
  - `src/retrieval/retriever_dispatcher.py` — no changes needed; `RetrieverDispatcher.retrieve()` already accepts a `RoutePlan` with modified `SourcePlan` objects. Per-sub-query routing is achieved by building a fresh `RoutePlan` via `dataclasses.replace()` (see code block below).
- **Change:**

  ```python
  from dataclasses import replace

  all_candidates: list[MemoryCandidate] = []
  for sub_query in augmented.sub_queries:
      try:
          # Per oracle F8: evaluate doc retrieval necessity per sub-query
          needs_docs = self._evaluate_doc_necessity(sub_query.text)
          sources_for_sub = list(sub_query.sources)
          if needs_docs and "document_memory" not in sources_for_sub:
              sources_for_sub.append("document_memory")
          # Build per-sub-query RoutePlan copies via replace() — never mutate frozen SourcePlan.
          # Bug fix: SourcePlan is frozen; sp.query = ... would raise FrozenInstanceError.
          # Bug fix: RetrieverDispatcher.retrieve() has no override_sources parameter.
          per_sub_sources = [
              replace(sp, query=sub_query.text)
              if sp.source in sources_for_sub
              else sp
              for sp in route_plan.sources
          ]
          sub_route_plan = replace(route_plan, sources=per_sub_sources)
          candidates = self._retriever_dispatcher.retrieve(
              chat_id=chat_id,
              route_plan=sub_route_plan,
          )
          all_candidates.extend(candidates)
      except Exception as exc:
          # Per oracle F19: isolate per-sub-query failures
          self._trace.errors.append(f"Sub-query '{sub_query.text[:50]}...' failed: {exc}")
          continue  # skip failed sub-query, continue with remaining
  # Deduplicate by record_id before reranking
  # Per oracle F12: if record_id is None, always keep. If not None and already seen, keep higher-scored.
  seen: dict[str | int, MemoryCandidate] = {}
  for c in all_candidates:
      key = c.record_id
      if key is None:
          seen[f"_none_{id(c)}"] = c  # synthetic key for None record_id (always keep)
      elif key not in seen or (c.score or 0) > (seen[key].score or 0):
          seen[key] = c
  all_candidates = list(seen.values())
  ```

- **Add private method in `CoordinatorAgent` (per oracle F8):**

  ```python
  def _evaluate_doc_necessity(self, query: str) -> bool:
      """Use QueryAnalyzer lexical signals to decide if this sub-query needs document retrieval."""
      # Bug fix: QueryAnalyzer is deterministic and stateless — instantiate standalone
      # rather than drilling through RoutingAgent -> RoutePlanner -> QueryAnalyzer.
      # self._query_analyzer is set in CoordinatorAgent.__init__ (see below).
      analysis = self._query_analyzer.analyze(query)
      return analysis.signals.asks_about_documents
  ```

  **CoordinatorAgent.__init__() must instantiate a standalone QueryAnalyzer:**

  ```python
  # Add to imports at top of coordinator_agent.py:
  from src.routing.query_analyzer import QueryAnalyzer

  # Add to CoordinatorAgent.__init__():
  self._query_analyzer = QueryAnalyzer()
  ```

  `QueryAnalyzer` is deterministic, stateless, and has no side effects — a second
  instance (separate from the one inside `RoutingAgent → RoutePlanner`) is harmless.
  The signal field is `signals.asks_about_documents` (not `is_document_query`).

- **Deps:** P1.4.
- **Risk:** Retrieval time scales with sub-query count × sources. Mitigation: `MAX_SUB_QUERIES=3` (P1.1), doc retrieval gated per sub-query, embedding calls are cached.
- **Edge-case tests (per oracle F13):**
  - 0 sub-queries returned → fallback to single original query.
  - Empty candidate list from all sub-queries → short-circuit reranking (return empty / graceful).
  - Empty answer gist → fallback to raw query as gist text (P0.5 already handles).
- **Verify:** Integration test: 2 sub-queries → verify `RetrieverDispatcher.retrieve()` called twice with distinct `source_plan.query` values. Verify deduplication. Verify retrieval trace in `WorkflowTrace`. Verify one sub-query failure doesn't kill others (F19).

---

## Phase 2 — Cross-Encoder Reranker & Chat Lifecycle (Effort: ~21h)

### P2.1 — Add cross-encoder dependency + config

- **File:** `pyproject.toml` — add `sentence-transformers` dependency (if not already transitive via HuggingFace embeddings).
- **File:** `src/config.py` — add config fields (frozen dataclass, loaded from env):
  - `cross_encoder_model_name: str` (default: `"cross-encoder/ms-marco-MiniLM-L-6-v2"`)
  - `cross_encoder_top_k: int` (default: `20`, limit candidates fed to cross-encoder)
  - `cross_encoder_mem_k: int` (default: `8`, memory top-k after scoring)
  - `cross_encoder_doc_k: int` (default: `4`, document top-k after scoring; implements spec `mem_k > doc_k`)
  - `cross_encoder_timeout_ms: int` (default: `2000`; per oracle correction #15, fall back to deterministic if exceeded)
- **Deps:** None.
- **Risk:** Cross-encoder model ~100–400 MB. Lazy-load on first use, not at startup.
- **Verify:** `pytest tests/test_config.py` — new fields have expected defaults.

### P2.2 — Create `CrossEncoderReranker`

- **File (new):** `src/retrieval/cross_encoder_reranker.py`
- **Class:** `CrossEncoderReranker`

  ```python
  import concurrent.futures

  class CrossEncoderReranker:
      """Cross-encoder pairwise scoring. Scores candidates [0-1] per query-chunk match."""

      def __init__(self, model_name: str) -> None: ...

      def rank(
          self, *, query: str, candidates: list[MemoryCandidate],
          mem_k: int, doc_k: int, timeout_ms: int,
      ) -> list[MemoryCandidate]:
          """Score candidates, separate cutoff by source (mem_k > doc_k)."""
  ```

  - For each candidate: `score = model.predict([query, candidate.content])` → [0-1].
  - **Per oracle correction #11:** Populate existing `MemoryCandidate.score` field with cross-encoder value. Track score source in `WorkflowTrace.metadata["ranking_source"]`. No new `RankedMemoryCandidate` dataclass needed.
  - Separate cutoff: take top `mem_k` from `structured_memory` source, top `doc_k` from `document_memory` source.
  - **Timeout + Fallback (per oracle H3):** Use `concurrent.futures.ThreadPoolExecutor` to execute scoring with `future.result(timeout=timeout_ms/1000)`. If scoring exceeds `timeout_ms` or raises `TimeoutError`, abort, return candidates with original scores, log warning. Fallback to deterministic reranker is handled by `MemoryReranker` (P2.3).
  - **ThreadPoolExecutor reuse [Oracle F3]:** Create `self._executor = ThreadPoolExecutor(max_workers=1)` in `CrossEncoderReranker.__init__()`. Reuse this single executor across all `rank()` calls. Add a `close()` method that calls `self._executor.shutdown(wait=True)`. This avoids the overhead of creating and destroying a thread pool per scoring invocation.
- **Style:** `code-style.md` §4 (Retriever pattern). Dependency injection via constructor.
- **Deps:** P2.1.
- **Risk:** N×M pairwise scoring is slow for large N. `cross_encoder_top_k` limits input. Deterministic pre-filter (top 20 by feature score) feeds into cross-encoder (see P2.3 for pre-filter wiring).
- **Verify:** Unit test: 10 candidates scored, all scores [0-1], sorted descending, mem_k=3 doc_k=2 applied. Test timeout mechanism.

### P2.3 — Register cross-encoder as reranker mode

- **File:** `src/retrieval/reranker.py`
- **Change:** Add `"cross_encoder"` to supported modes. When `RERANKER_MODE=cross_encoder`, `rank_with_trace()` delegates to `CrossEncoderReranker.rank()`. Fallback to `deterministic` if cross-encoder fails (model not loaded, timeout exceeded) — follow existing pattern (LLM reranker already falls back to deterministic).
- **Deterministic pre-filter (per oracle F16):** When `RERANKER_MODE=cross_encoder`, the `rank_with_trace()` method MUST:
  1. First run deterministic feature scoring to produce a top-K pre-filtered list (`cross_encoder_top_k=20` candidates).
  2. THEN pass only these `cross_encoder_top_k` candidates to `CrossEncoderReranker.rank()`.
  3. This prevents the cross-encoder from receiving hundreds of raw candidates.
- **File:** `src/config.py` — update `RERANKER_MODE` docstring: add `cross_encoder`.
- **Deps:** P2.2.
- **Verify:** Integration test: `MemoryReranker(mode="cross_encoder").rank_with_trace(candidates)` produces scored candidates. Test fallback: bad model name → falls to deterministic. Test pre-filter: 50 candidates in, only 20 reach cross-encoder.

### P2.4 — Add `active` flag to `chats` + lifecycle methods

- **File:** `src/database.py`
- **Change:**
  - Add `active INTEGER NOT NULL DEFAULT 1` to `chats` via `_ensure_chats_active_column(conn)`.
  - **[Oracle F5]** Enable `PRAGMA journal_mode=WAL` in `Database.__init__()` if not already active. WAL mode allows concurrent reads during writes, which is essential when multiple active chats may write simultaneously (e.g., CHAT_FORK while another chat is reading).
  - New methods:
    - `mark_chat_inactive(chat_id: str) -> None`
    - `mark_chat_active(chat_id: str) -> None`
    - `list_active_chats() -> list[dict]`
    - `list_inactive_chats() -> list[dict]`
- **Audit task (per oracle F9):** After adding `active` column, audit ALL existing callers that `SELECT * FROM chats` and add `WHERE active=1` filter where appropriate:
  - `list_chats_for_user()` → add `WHERE active=1` (default for active-only listing)
  - `ChatService` chat-loading path → add filter
  - `ChainLit` chat list callback → add filter
  - `list_inactive_chats()` → uses `WHERE active=0`
- **Deps:** None.
- **Risk:** Existing `SELECT` queries on `chats` may need `WHERE active=1`. Audit all call sites.
- **Verify:** Unit test: create chat → `active=1` → mark inactive → `active=0` → list methods return correct subsets. Verify all chat list paths respect active flag.

### P2.5 — Implement `CHAT_END_ACTION` + `ProcessIntoMemoryAction`

- **Files (new):** `src/actions/__init__.py`, `src/actions/chat_end.py`
- **Class:** `ChatEndAction` (implements spec §CHAT_END_ACTION)

  ```python
  class ChatEndAction:
      """CHAT_END_ACTION: trigger PROCESS_INTO_MEMORY, mark chat inactive."""

      def __init__(self, database: Database, memory: ShortTermMemory) -> None: ...

      def execute(self, chat_id: str) -> None:
          """1. Process all unsummarized messages into memory.
             2. Mark chat as inactive."""
          # Process into memory (same logic as PRUNE_MEMORIES_ACTION)
          self._process_into_memory(chat_id)
          # Mark inactive
          self.database.mark_chat_inactive(chat_id)

      def _process_into_memory(self, chat_id: str) -> None:
          """Per spec PROCESS_INTO_MEMORY_ACTION:
             1. Retrieve unprocessed gist+text blocks for this chat
             2. @MEMORY_UPDATE_AGENT extracts compressions → new-memories
             3. foreach existing lt_mem: [update/delete/pass]
             4. Commit: embed new, re-embed updated (remove old by ID)"""
  ```

- **Per oracle correction #7:** Merge PRUNE_MEMORIES into P2.5. `_process_into_memory()` is the shared logic for both manual prune and chat-end triggers. No separate `prune_memories.py` file.
- **Per oracle correction #10:** Keep `ShortTermMemory.update_memory_if_needed()` as-is (batch trigger ≥6 messages). Add new method `process_all_for_chat_end(chat_id)` on `ShortTermMemory` called by `ChatEndAction._process_into_memory()`. Do not change existing method semantics.
- **File (modify):** `src/memory/short_term.py` — add `process_all_for_chat_end(chat_id: str) -> None`:
  - Reads ALL unsummarized messages (not just batch).
  - Triggers LangMem extraction.
  - Produces gist records via `GistingAgent`.
  - Steps 1-4 of spec PROCESS_INTO_MEMORY.
  - **[Oracle F7]** LangMem already writes to the `chat_memory_state` mirror table during extraction. No separate mirror-sync step is needed; `process_all_for_chat_end()` inherits this behavior from the existing LangMem integration.
- **Edge-case tests (per oracle F13):**
  - CHAT_END on empty chat (0 messages) → no-op, chat still marked inactive.
  - CHAT_END on already-inactive chat → idempotent (graceful no-op or log warning).
- **Deps:** P0.2 (GIST pipeline active; CHAT_END reads GISTs), P0.5 (GistingAgent exists), P2.4 (chat_active flag). **NOT** P2.2 (cross-encoder) per oracle correction #13.
- **Verify:** Integration test: create chat with 10 messages → execute `ChatEndAction` → verify memories created, chat marked inactive, gists populated.

### P2.6 — Implement `CHAT_FORK_ACTION`

- **File (new):** `src/actions/chat_fork.py`
- **Class:** `ChatForkAction`

  ```python
  class ChatForkAction:
      """Duplicates all chat data into a new active chat."""

      def __init__(self, database: Database) -> None: ...
      def execute(self, chat_id: str) -> str:
          """Fork chat. Returns new chat_id."""
          # Duplicate: chats row (new UUID), all messages (new chat_id),
          # chat_memory_state, chat_gists. Set active=1.
  ```

  - Wrap in transaction for atomicity.
- **Edge-case test (per oracle F13):** CHAT_FORK on empty chat (0 messages, no memory state) → creates new empty chat with active=1 (no-op but valid).
- **Deps:** P2.4.
- **Verify:** Test: fork chat with 5 messages → verify all data copied to new chat_id, new chat is active.

---

## Phase 3 — Prompt Assembly & Metadata (Effort: ~7h)

### P3.1 — Ordered prompt placement as `ContextBuilder` strategy

- **Files (modify):** `src/context/context_builder.py`, `src/config.py`, **`src/agents/context_manager_agent.py`** (per oracle F2)
- **Per oracle F2:** `ContextManagerAgent` creates `ContextBuilder` internally. To pass `placement_mode` through, either:
  1. **Preferred:** Have `ContextBuilder.__init__()` read `AppConfig.CONTEXT_PLACEMENT_MODE` directly from the config (no DI chain change needed), OR
  2. Modify `ContextManagerAgent.__init__()` to accept and pass through `placement_mode: str = "budget_fitting"` to `ContextBuilder`.

  Choose approach #1 (simpler, avoids DI chain).

- **Per oracle correction #8:** Add ordered placement as a strategy *within* `ContextBuilder`, controlled by a `placement_mode: str` parameter (analogous to `RERANKER_MODE`). Do NOT create a standalone `OrderedPlacementBuilder` class.
- **Change in `ContextBuilder`:**

  ```python
  class ContextBuilder:
      def __init__(self, ..., placement_mode: str = "budget_fitting") -> None: ...

      def build(self, ...) -> ContextPacket:
          if self.placement_mode == "ordered":
              return self._build_ordered(...)
          return self._build_budget_fitting(...)

      def _build_ordered(self, ...) -> ContextPacket:
          """Spec placement: system_prompt | doc_chunks (hi→lo score) |
             lt_mem_chunks (lo→hi score) | raw user query."""
  ```

  - Implements spec "lost in the middle" mitigation: highest doc scores at top, lowest memory scores in middle.
  - Overflow handling: trim from middle (lt_mem) first when exceeding budget.
- **Config:** Add `CONTEXT_PLACEMENT_MODE` env var (default: `"budget_fitting"`, options: `"budget_fitting"`, `"ordered"`).
- **Deps:** P2.3 (cross-encoder scores are used for ordered placement; deterministic scores work too).
- **Style:** `code-style.md` §4 (Context builder pattern). Existing `ContextBuilder` already has private helper methods.
- **Verify:** Unit test: same candidates, both modes → compare output. Ordered mode: verify order is system, docs(hi-lo), mem(lo-hi), query. Budget exceeded → mem trimmed first.

### P3.2 — Track `last_used` on `long_term_memories`

- **File:** `src/database.py` — add `last_used TEXT` column (ISO timestamp, NULL default) via `_ensure_long_term_memories_last_used_column(conn)`.
- **Files (modify):**
  - `src/memory/long_term_store.py` — set `last_used=NOW()` on each `retrieve()`.
  - `src/memory/long_term_vector_index.py` — set `last_used` on vector retrieval hits.
  - **Note on L1:** In structured hybrid retrieval mode, both the SQLite path and the Chroma path could retrieve the same memory id, causing two consecutive updates to `last_used`. This is an acceptable side effect (last write wins) and requires no deduplication logic.
- **Deps:** P0.4 (`use_count` column must exist; can be done in parallel if P0.4 is not yet done).
- **Verify:** Retrieve memory → `last_used` updated, `use_count` incremented.

### P3.3 — Distinct chunk size for lt_mem at embedding layer

- **Files (modify):**
  - `src/config.py` — add `LT_MEM_EMBEDDING_CHUNK_SIZE: int` (default: `256`, smaller than `DOCUMENT_CHUNK_SIZE=1000`).
  - `src/memory/long_term_vector_index.py` — apply `LT_MEM_EMBEDDING_CHUNK_SIZE` when preparing memory text for the embedding model (truncate or summarize memory text to this character/token limit before calling `model.encode()`).
- **Per oracle correction #1:** Apply chunk size at the *embedding layer* in `long_term_vector_index.py`, NOT in `langmem_structured.py`. LangMem produces structured key-value pairs; the chunk size is a constraint on how much text is embedded, not on how LangMem extracts.
- **Deps:** None.
- **Verify:** Unit test: memory text longer than 256 chars → embedded text ≤ 256 chars. Doc chunks remain at 1000.

---

## Phase 4 — ChainLit Multi-Tab UI & Manual Operations (Effort: ~35h)

### P4.1 — UI layout & navigation prototype

- **File:** `app.py`
- **Per oracle correction #17:** Prototype single-page approach first:
  - Use `cl.ChatSettings` for tab selection.
  - Render each page as conditional `cl.Message` content blocks based on current tab state.
  - If Chainlit 2.x proves too limited, fallback: separate `app_landing.py`, `app_chat.py`, etc. with Chainlit multi-app profiles.
- **Persistence:** Store current tab in `cl.user_session`.
- **Breadcrumbs:** `cl.Text` elements at top: `[Home] [Chats] [Documents] [Memories]`.
- **Deps:** None.
- **Risk:** Chainlit 2.x does not natively support multi-tab UIs. The single-page approach with conditional rendering is a well-known workaround. If it fails, the fallback to separate entry points is safe.
- **Verify:** Manual: start app, see landing page. Click "Chats" breadcrumb, see chats list page. Click "Home", see landing page.

### P4.2 — Landing page

- **File:** `app.py`
- **Features:**
  - "New Chat" button → triggers `NEW_CHAT_ACTION` → navigates to chat_page.
  - Below: list of active chats (from `Database.list_active_chats()`) or "No active chats".
  - Each active chat clickable → opens in chat_page.
- **Deps:** P2.4 (active/inactive distinction), P4.1 (navigation).
- **Verify:** Click "New Chat" → new chat created in DB, UI navigates to chat page.

### P4.3 — Chat page (enhance existing)

- **File:** `app.py`
- **Features:**
  - Left sidebar: list of active chats (clickable).
  - Middle: existing chat interface (`@cl.on_message` logic).
  - Below chat input: action buttons — "New Chat", "End Chat", "Fork Chat", "Upload Doc".
  - **Per oracle correction #14:** "Upload Doc" button triggers `DocumentIngestionAgent.ingest()` from Chainlit file upload handler. Wire success/failure feedback to UI (`cl.Message` with result).
- **Deps:** P2.5 (CHAT_END), P2.6 (CHAT_FORK), P4.1.
- **Verify:** Upload a .txt file → document ingested, success message shown. Click "End Chat" → chat marked inactive, UI navigates to landing.

### P4.4 — Chats list page

- **File:** `app.py`
- **Features:**
  - Search bar (filter by `chats.title`).
  - Active chats listed (click to open).
  - Inactive chats listed below (hover → "Activate" button).
- **Deps:** P2.4.
- **Verify:** Searched chats filtered. Inactive chat activated.

### P4.5 — Docs list page

- **File:** `app.py`
- **Features:**
  - Central column: list of all documents.
  - Inactive documents grayed out (per `documents.active` flag — see P4.5b).
  - "Add Docs" button (file upload, wired to `DocumentIngestionAgent` per oracle correction #14).
  - Each document: "Suppress" and "Delete" buttons.
- **New backend (P4.5b):** `src/database.py` — add methods:
  - `suppress_document(doc_id)` — sets `active=0` on document and all its chunks.
  - `delete_document(doc_id)` — deletes document + cascade to chunks + embeddings.
  - `list_documents(active_only: bool = True)` — query with optional active filter.
- **Chroma metadata migration (per oracle F10 + H2):**
  1. Add schema migration for `documents.active` and `document_chunks.active` columns (both `INTEGER NOT NULL DEFAULT 1`).
  2. At ingestion time, ensure all Chroma document chunks have metadata `{"active": 1, "doc_id": ...}`.
  3. **Migration for existing chunks:** Write a one-shot migration script that iterates existing Chroma entries and adds `active=1` and `doc_id` metadata to each chunk's metadata dict. Without this, the `WHERE active=1` Chroma filter will silently exclude all pre-existing chunks.
  4. When `suppress_document()` is called, use `Chroma.collection.update(ids=chunk_ids, metadatas=[{"active": 0}] * len(chunk_ids))` to toggle each chunk's metadata.
     - **[Oracle F1]** Chroma requires `len(metadatas) == len(ids)`. Using `* len(chunk_ids)` ensures each chunk ID gets its own metadata dict.
  5. Add `WHERE active=1` filter in **both** the `LangChainChromaRetriever` metadata filter AND the SQLite chunk query path so suppressed chunks are entirely excluded.
  6. Store `chroma_id` in `document_chunks` table (or derive from chunk_id pattern) so the update can target the right Chroma documents.
- **Edge-case test (per oracle F13):** Suppress already-suppressed document → idempotent (active already 0, no-op or log).
- **Deps:** P4.1.
- **Verify:** Upload doc → appears in list. Suppress → grayed out, retrieval skips it (both SQLite and Chroma). Delete → removed.

### P4.6 — Memories list page

- **File:** `app.py`
- **Features:**
  - Central column: list of all lt_mem entries.
  - "Add Memory" button → opens input form (key, value, category, namespace).
  - Each memory: "Delete" button.
  - Search bar (filter by key/value).
- **New backend:** `src/database.py` — add methods:
  - `insert_manual_memory(namespace, key, value, category, confidence=1.0)` — per `ADD_MEMORY_ACTION` spec.
  - `delete_memory_by_id(memory_id)` — per `DELETE_MEMORY_ACTION` spec.
  - `list_all_memories(search: str | None = None)` — query with optional search.
- **New methods on `LongTermMemoryVectorIndex` (per oracle F6):**
  - Add `delete_by_memory_id(self, memory_id: str) -> None` method:
    - Remove the Chroma document by metadata filter `{"memory_id": memory_id}`.
    - Use `collection.delete(where={"memory_id": memory_id})`.
  - Add `embed_and_index(self, memory: dict) -> str` method:
    - Embed the memory's `key + " " + value` text using the existing embedding model.
    - **[Oracle F2]** Before upsert, verify `len(embedding) == collection.metadata.get('dimension', 384)`. If dimensions mismatch, raise a clear error with the expected and actual dimensions.
    - Upsert into Chroma with metadata `{"memory_id": memory["id"], ...}`.
    - Return the Chroma document ID.
- **Per oracle correction #4:** `delete_memory_by_id()` MUST call `LongTermMemoryVectorIndex.delete_by_memory_id(memory_id)` BEFORE deleting the SQLite row, to remove the embedding from Chroma while we still have the memory_id.
- **Per oracle correction #5:** `insert_manual_memory()` MUST call `LongTermMemoryVectorIndex.embed_and_index(memory)` AFTER the SQLite insert, to make the new memory searchable via dense retrieval.
- **Edge-case tests (per oracle F13):**
  - Delete already-deleted memory ID → graceful error (log, no crash).
  - Add duplicate memory key (same namespace/memory_id) → upsert (overwrite existing).
- **Memory Input Guard [Oracle F4]:** Add `MAX_MANUAL_MEMORY_CHARS = 2000` module-level constant (per `code-style.md` §3.4). Reject or truncate manual memory input on both the UI side (`maxLength` on the input field) and backend validation in `insert_manual_memory()`. Truncation should log a warning before applying.
- **Deps:** P0.4 (`use_count` metadata enhances memory display).
- **Verify:** Add memory → appears in list AND in Chroma (searchable). Delete memory → removed from SQLite AND Chroma. Delete already-deleted → graceful.

### P4.7 — Wire all UI actions to backend

- **File:** `app.py`
- **Changes:** Map every UI button/action to its backend:
  - NEW_CHAT → `ChatService.create_chat()` → navigate to chat_page.
  - CHAT_END → `ChatEndAction.execute(chat_id)` → navigate to landing_page.
  - CHAT_FORK → `ChatForkAction.execute(chat_id)` → navigate to new chat.
  - SUPPRESS_DOC → `Database.suppress_document(doc_id)` → refresh docs_list_page.
  - DELETE_DOC → `Database.delete_document(doc_id)` → refresh docs_list_page.
  - DELETE_MEMORY → `Database.delete_memory_by_id(memory_id)` → refresh memories_list_page.
  - ADD_MEMORY → `Database.insert_manual_memory(...)` → refresh memories_list_page.
  - UPLOAD_DOC → `DocumentIngestionAgent.ingest(file)` → feedback message → refresh docs_list_page.
- **Deps:** P2.5, P2.6, P4.2–P4.6.
- **Verify:** End-to-end: every button triggers correct backend action, UI refreshes with updated state.

---

## Phase 5 — Evaluation Suites Update (Effort: ~12h)

### P5.1 — Update Document QA Evals

- **Files (modify):** Scripts in `evals/document_qa/`
- **Change:** Ensure evaluations incorporate the new cross-encoder ranking. Validate that the evaluation framework accurately captures the reranker's score (`[0-1]`) and supports evaluating ordered placement in context construction.
- **Deps:** P2.2, P3.1.

### P5.2 — Update Structured Memory Evals

- **Files (modify):** Scripts in `evals/structured_memory/`
- **Change:** Integrate the `GistingAgent` and `GistResult` objects into the evaluation. Measure retrieval precision of GISTs and ensure the tri-state updates are correctly reflected in the memory extraction quality metrics.
- **Deps:** P0.5.

### P5.3 — Update End-to-End Scenarios

- **Files (modify):** Scripts in `evals/e2e_scenarios/`
- **Change:** Incorporate testing for query augmentation (`QueryDecomposer` and `SemanticExpander`). Validate that the multi-stage pipeline—including sub-query breakdown and specific retrieval—can execute successfully end-to-end within the eval harnesses.
- **Deps:** P1.3, P1.4.

---

## Files Summary

### New Files (13)

```
src/routing/query_decomposer.py            # P1.1
src/routing/semantic_expander.py           # P1.2
src/agents/query_augmentation_agent.py     # P1.3
src/agents/gisting_agent.py               # P0.5
src/retrieval/cross_encoder_reranker.py    # P2.2
src/actions/__init__.py                    # P2.5
src/actions/chat_end.py                    # P2.5 (+ merged PRUNE_MEMORIES)
src/actions/chat_fork.py                   # P2.6
```

### Modified Files (17)

```
src/config.py                              # P0.1, P1.4, P2.1, P2.3, P3.1, P3.3
src/database.py                            # P0.3, P0.4, P2.4, P3.2, P4.5b, P4.6
src/core/contracts.py                     # P1.1, P1.3 (SubQuery, AugmentedQuery)
src/routing/route_planner.py               # P0.2
src/retrieval/retriever_dispatcher.py      # P0.2, P1.5
src/retrieval/reranker.py                 # P2.3 (cross_encoder mode + pre-filter)
src/memory/short_term.py                  # P2.5 (process_all_for_chat_end)
src/memory/long_term_store.py              # P0.4, P3.2
src/memory/long_term_vector_index.py       # P3.3, P4.6 (delete_by_memory_id, embed_and_index)
src/memory/langmem_structured.py          # P3.2 (last_used tracking)
src/context/context_builder.py            # P3.1 (ordered placement strategy)
src/agents/coordinator_agent.py            # P0.2, P1.4, P1.5
src/agents/context_manager_agent.py        # P3.1 (placement_mode wiring, per oracle F2)
src/chat_service.py                        # P0.5 (GistingAgent DI wiring)
app.py                                     # P4.1–P4.7
pyproject.toml                             # P2.1
```

### New Tests Expected (18+)

```
tests/test_query_decomposer.py
tests/test_semantic_expander.py
tests/test_query_augmentation_agent.py
tests/test_gisting_agent.py
tests/test_cross_encoder_reranker.py
tests/test_chat_end_action.py
tests/test_chat_fork_action.py
tests/test_ordered_placement.py
tests/test_gist_integration.py
tests/test_chat_lifecycle.py
tests/test_use_count_tracking.py
tests/test_last_used_tracking.py
tests/test_database_migrations.py
tests/test_coordinator_with_augmentation.py
tests/test_per_subquery_retrieval.py
tests/test_doc_suppression.py
tests/test_memory_crud.py
tests/test_ui_actions.py
```

### Edge-Case Tests (per oracle F13 — add to respective test files)

| Test | Target File |
|------|-------------|
| 0 sub-queries → fallback to original query | `test_query_decomposer.py` |
| Empty candidate list → short-circuit reranking | `test_per_subquery_retrieval.py` |
| Empty answer GIST → raw query fallback | `test_gisting_agent.py` |
| CHAT_END on empty chat → no-op | `test_chat_end_action.py` |
| CHAT_FORK on empty chat → no-op | `test_chat_fork_action.py` |
| Delete already-deleted memory → graceful | `test_memory_crud.py` |
| Suppress already-suppressed doc → idempotent | `test_doc_suppression.py` |
| Add duplicate memory key → upsert | `test_memory_crud.py` |

---

## Risk Register (Top 5)

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| 1 | **Cross-encoder latency blocks pipeline.** Pairwise scoring of 20 candidates may add 1–5s. | Medium | `CROSS_ENCODER_TIMEOUT_MS=2000` with `ThreadPoolExecutor` + `future.result(timeout=...)` → automatic fallback to deterministic reranker. Pre-filter to top 20 by feature score before cross-encoder. Lazy-load model. |
| 2 | **GIST retrieval returns empty/low-quality results after enablement.** The current gist retrievers are lexical stubs. | High | Rollback criteria: auto-disable after 10 queries with <20% valid result rate, log warning. Short-term: gists still populate and grow; retrieval quality improves with volume. |
| 3 | **Chroma metadata migration for doc suppression leaves existing chunks unfiltered.** Existing Chroma entries lack `active` metadata. | High | Explicit one-shot migration script required (P4.5b). Without it, suppressed docs still appear in retrieval. |
| 4 | **ContextManagerAgent does not pass placement_mode to ContextBuilder.** Config is read at construction time, but the wiring path is not obvious. | Medium | Use approach #1: `ContextBuilder.__init__()` reads `AppConfig.CONTEXT_PLACEMENT_MODE` directly from config (P3.1). This eliminates the DI chain problem entirely. |
| 5 | **Chainlit 2.x multi-tab approach may fail.** Chainlit is designed for single-page chat, not multi-tab SPA navigation. | Medium | Prototype single-page approach with conditional rendering. If it fails, fall back to separate `app_*.py` entry points with Chainlit multi-app profiles. Safe fallback. |

---

## Spec Coverage

| Spec Action | Covered By | Status |
|------------|-----------|--------|
| `DOC_INPUT_ACTION` | P4.3 + P4.5 (UI upload + ingestion) | ✅ |
| `CHAT_END_ACTION` | P2.5 (`ChatEndAction`) | ✅ |
| `PROCESS_INTO_MEMORY_ACTION` | P2.5 (`_process_into_memory()`) | ✅ |
| `SINGLE_REQUEST_ACTION` — query decomposition | P1.1 + P1.3 | ✅ |
| `SINGLE_REQUEST_ACTION` — semantic expansion | P1.2 + P1.3 | ✅ |
| `SINGLE_REQUEST_ACTION` — per-sub-query retrieval | P1.5 | ✅ |
| `SINGLE_REQUEST_ACTION` — CROSS_ENCODER reranking | P2.2 + P2.3 | ✅ |
| `SINGLE_REQUEST_ACTION` — ordered prompt stitching | P3.1 | ✅ |
| `SINGLE_REQUEST_ACTION` — GISTING_AGENT | P0.5 + P0.2 (in coordinator) | ✅ |
| `PRUNE_MEMORIES_ACTION` | P2.5 (merged into PROCESS_INTO_MEMORY) | ✅ |
| `SUPPRESS_DOC_ACTION` | P4.5b (+ Chroma metadata migration) | ✅ |
| `DELETE_MEMORY_ACTION` | P4.6 + P4.7 (+ Chroma cleanup) | ✅ |
| `ADD_MEMORY_ACTION` | P4.6 + P4.7 (+ Chroma indexing) | ✅ |
| `NEW_CHAT_ACTION` | Existing `ChatService.create_chat()` + P4.7 wiring | ✅ |
| `CHAT_FORK_ACTION` | P2.6 | ✅ |
| `use_count` metadata | P0.4 | ✅ |
| `last_used` metadata | P3.2 | ✅ |
| `lt_mem smaller chunks` | P3.3 (at embedding layer) | ✅ |
| ChainLit 5-tab UI | P4.1–P4.7 | ✅ |

**Coverage: 19 of 19 spec actions + 0 gaps** (92%+ per target).

---

## Oracle Review Log

| Round | Date | Severities Found | Status |
|-------|------|-----------------|--------|
| 1 (preliminary → final) | 2026-06-28 | 17 corrections (1 blocker, 4 high, 7 medium, 4 low, 1 info) | ✅ All applied |
| 2 (final → revised) | 2026-06-28 | 28 findings (4 high, 8 medium, 16 low/info) | ✅ All applied |
| 3 (backend fixes) | 2026-06-28 | 7 findings (1 blocker, 2 high, 3 medium, 1 low) | ✅ All applied |
| 4 (deep re-review) | 2026-06-28 | 7 minor findings (0 blockers, 2 high impl details, 3 medium, 2 low) | ✅ All applied |

---

*Generated from oracle-reviewed plan, incorporating 53 total findings across
four full oracle review passes. All decisions traceable to `design_description.txt` spec actions
and `code-style.md` conventions.*
