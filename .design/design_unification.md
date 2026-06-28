# Design Unification Analysis

**Sources:**

- `.design/design_description.txt` — authoritative design specification
- `.design/diagram1.6.png` / `.design/design1.6_report.md` — Token-Bounded Conversation RAG
- `.design/diagram2.0.png` / `.design/design2.0_report.md` — Indefinite Memory Maintenance
- `context.md` — current codebase reconnaissance

---

## 1. Executive Verdict

**The design specification is a deliberate hybrid of both diagrams.** Diagram 2.0
scores higher overall (60.8% vs 52.3% weighted), but neither diagram alone
captures the full specification. The spec takes the **memory model and GIST
lifecycle from Diagram 2.0** while retaining the **linear turn pipeline,
augmentation, reranking, and document handling from Diagram 1.6**.

```
Design Spec = D2.0 (memory) + D1.6 (pipeline) + net-new (ChainLit UI)
```

---

## 2. Design vs. Diagrams — Component Scoring

| Component | Weight | D1.6 Score | D2.0 Score | Winner | Rationale |
|-----------|--------|------------|------------|--------|-----------|
| **Memory Model & Lifecycle** | 25% | 15% | **95%** | D2.0 | Spec requires MEMORY_UPDATE_AGENT with [update/delete/pass] tri-state operations, GIST-based memory processing, and information valuation — all D2.0 features. D1.6 only has passive append-only embedding. |
| **Query Processing** | 15% | **95%** | 40% | D1.6 | Spec explicitly requires query decomposition (split sub-queries) + semantic expansion (inject keywords, prompt-based). D1.6 diagrams this in detail. D2.0 mentions augmentation but leaves it as a unexpanded box. |
| **Retrieval Architecture** | 15% | **60%** | 55% | D1.6 | Spec requires per-sub-query, per-source (lt_mem, docs) dense retrieval with conditional doc retrieval. D1.6's hierarchy (current > docs > old) and multi-source dispatch is closer. D2.0's autoload approach is present but focused on GISTs only. |
| **Reranking** | 10% | **85%** | 50% | D1.6 | Spec specifies @RE_RANK_AGENT[CROSS_ENCODER] with [0-1] scoring and top-k cutoff (mem_k > doc_k). D1.6 explicitly shows a re-ranking stage with model validation. D2.0 does not diagram a separate reranker. |
| **Prompt Assembly** | 10% | **80%** | 30% | D1.6 | Spec specifies ordered placement: `system | doc_chunks (hi-lo) | lt_mem_chunks (lo-hi) | raw user query`. D1.6 diagrams prompt construction with source fusion. D2.0 omits assembly details. |
| **Document Handling** | 10% | **75%** | 10% | D1.6 | Spec requires separate doc vecdb, CHUNKING_AGENT, EMBEDDING_AGENT, SUPPRESS_DOC_ACTION. D1.6 has explicit doc input → vector store flow and a doc hierarchy. D2.0 focuses exclusively on memory, not documents. |
| **GIST Lifecycle** | 10% | 10% | **90%** | D2.0 | Spec defines @GISTING_AGENT (creates gists from Q/A), gist storage (SQLite per chat_id), and gist-based memory processing. D2.0 is built entirely around GISTs as the core semantic unit. D1.6 has no GIST concept. |
| **Memory Update Operations** | 5% | 5% | **95%** | D2.0 | Spec requires explicit [update/delete/pass] tri-state decisions on existing lt_mem. D2.0's [UPDATE/DELETE/SKIP] is an exact match. D1.6 has no mutation operations — it only appends. |
| **Weighted Total** | **100%** | **52.3%** | **60.8%** | **D2.0** | D2.0 wins by 8.5 percentage points, driven by memory model dominance (heaviest weight). |

---

## 3. Spec-to-Diagram Mapping: What Comes From Where

### 3.1 Sourced from Diagram 2.0 (Indefinite Memory Maintenance)

| Spec Element | D2.0 Equivalent | Match Quality |
|-------------|-----------------|---------------|
| MEMORY_UPDATE_AGENT with [update/delete/pass] | Memory Agent update cycle: [UPDATE/DELETE/SKIP] | **Exact match** |
| GISTING_AGENT creating gists from Q/A | for each new user GIST (generated from conversation) | **Exact match** |
| Gists stored in SQLite (per chat_id) | Vector store + structured GIST records | **Strong match** |
| Information valuation before commit | assert non-zero information value → discard noise | **Exact match** |
| PROCESS_INTO_MEMORY (compressions → new-memories) | NEW embedding → vector store | **Strong match** |
| PRUNE_MEMORIES_ACTION | prune memory (vector store) at retrieval time | **Partial match** — spec has pruning as CHAT_END action, D2.0 prunes at read-time |
| Separate lt_mem vecdb with metadata (use_count, last_used) | autoload last n updated embeddings | **Conceptual match** — both track recency |

### 3.2 Sourced from Diagram 1.6 (Token-Bounded RAG)

| Spec Element | D1.6 Equivalent | Match Quality |
|-------------|-----------------|---------------|
| QUERY_AUGMENTATION_AGENT: query decomposition | split query into multiple subqueries | **Exact match** |
| QUERY_AUGMENTATION_AGENT: semantic expansion | inject keywords + rephrasing | **Exact match** |
| RETRIEVAL_AGENT: per-sub-query, per-source dispatch | query vec db for information (hierarchy) | **Strong match** |
| RE_RANK_AGENT with CROSS_ENCODER scoring | small local model re-rank & validate accuracy | **Strong match** |
| Prompt stitching with ordered placement | prompt construction: system + context + retrieved | **Conceptual match** — D1.6 fuses sources; spec orders them |
| Separate doc vecdb (larger chunks) | current instance > input docs > old conversations | **Strong match** |
| CHUNKING_AGENT + EMBEDDING_AGENT | chunk (Q,A) pairs → vector store | **Strong match** |
| SUPPRESS_DOC_ACTION | Not explicit, but doc hierarchy supports it | **Weak match** |

### 3.3 Net-New (Not in Either Diagram)

| Spec Element | Notes |
|-------------|-------|
| ChainLit UI with 5 tabs (landing, chat, chats_list, docs_list, memories_list) | Neither diagram addresses UI |
| Breadcrumb menu | Neither diagram addresses UI |
| CHAT_FORK_ACTION | Neither diagram addresses chat forking |
| DELETE_MEMORY_ACTION (UI-driven manual delete) | Neither diagram addresses manual memory operations via UI |
| ADD_MEMORY_ACTION (UI-driven manual insert) | Neither diagram addresses manual memory operations via UI |
| NEW_CHAT_ACTION | Neither diagram addresses explicit new-chat initialisation |

---

## 4. Current Codebase vs. Both Diagrams

The current implementation (per `context.md`) is a **different hybrid** than the
design spec — it aligns more closely with Diagram 1.6's pipeline structure but
incorporates several Diagram 2.0 memory concepts.

### 4.1 Pipeline Structure: ~55% D1.6, ~35% D2.0, ~10% neither

```
CoordinatorAgent.run_turn()
  → RoutingAgent.route()              [D1.6: query analysis, NOT decomposition]
  → RetrieverDispatcher.retrieve()    [D1.6: multi-source dispatch]
  → MemoryReranker.rank_with_trace()  [D1.6: re-ranking with fallback]
  → ContextManagerAgent.build()       [D1.6: prompt construction]
  → ChatAgent.generate()              [D1.6: LLM API call]
  → ShortTermMemory.update_memory()   [D2.0: LangMem ops = UPDATE/DELETE/SKIP]
  → AgentTurnResult + WorkflowTrace   [Neither: comprehensive tracing]
```

### 4.2 Feature-by-Feature Comparison

| Spec Feature | In Current Codebase? | Closer to Which Diagram? |
|-------------|---------------------|--------------------------|
| Query decomposition (split sub-queries) | ❌ Not implemented | D1.6 (if it were) |
| Semantic expansion (inject keywords) | Partial — lexical signals in QueryAnalyzer | D1.6 |
| Multi-source retrieval (lt_mem + docs) | ✅ RetrieverDispatcher with 6 sources | D1.6 |
| Separate doc vecdb + lt_mem vecdb | ✅ Separate backends (Chroma + long_term_memories) | Both |
| Cross-encoder reranking | ❌ Not implemented (uses feature-scoring or LLM) | Neither fully |
| [update/delete/pass] on lt_mem | ✅ LangMem upsert/supersede/delete | **D2.0** |
| GISTING_AGENT | ❌ Gist retrieval DISABLED; stubs exist | D2.0 (if enabled) |
| Information valuation before commit | Partial — LangMem structures confidence | D2.0 |
| Autoload last-n updated embeddings | Partial — updated_at ordering exists | D2.0 |
| Read-time memory pruning | ❌ Pruning only in update cycle | Neither (D2.0 has it; codebase doesn't) |
| Ordered prompt placement (system \| docs hi-lo \| mem lo-hi \| query) | ❌ Uses budget-fitting with overflow drops | Neither |
| ChainLit tabbed UI | ❌ Single chat page in current app.py | Neither |
| CHAT_FORK_ACTION, SUPPRESS_DOC, manual memory ops | ❌ Not implemented | Neither |

### 4.3 Gaps Between Codebase and Both Diagrams

| Gap | Diagram Source | Severity |
|-----|---------------|----------|
| No sub-query decomposition | D1.6 | Medium — limits complex query handling |
| No cross-encoder reranking | D1.6 | Medium — relies on simpler feature scoring |
| GIST retrieval disabled | D2.0 | High — GIST table exists but unused |
| No read-time pruning | D2.0 | Medium — memory drift risk over time |
| No ordered prompt placement | D1.6 | Low — budget-fitting is a valid alternative |
| UI mismatches | Neither | Low — UI is net-new per spec |

---

## 5. Architectural Evolution Narrative

```
Diagram 1.6 ──────────►  Diagram 2.0 ──────────►  Design Spec
(passive RAG)            (active memory)           (hybrid synthesis)
     │                        │                          │
     │  chunk & embed         │  GIST lifecycle          │  D2.0 memory model
     │  linear pipeline       │  tri-state updates       │  + D1.6 pipeline
     │  token-bound trigger   │  read-time pruning       │  + ChainLit UI
     │  multi-source retrieve │  info valuation          │  + manual memory ops
     │                        │                          │
     └────────────┬───────────┘                          │
                  │                                      │
                  ▼                                      ▼
          Current Codebase                         Target Architecture
          (~55% D1.6 + ~35% D2.0)                  (60.8% D2.0 + 52.3% D1.6
          ≠ spec yet                               + net-new UI components)
```

### 5.1 Key Insight

The design spec in `design_description.txt` is an **intentional merger** of the
two diagram philosophies:

- **From D1.6**: proven pipeline structure (augment → retrieve → rerank → assemble → generate), document handling, multi-source dispatch
- **From D2.0**: active memory management (GIST lifecycle, tri-state operations, information valuation, pruning)
- **Net-new**: ChainLit tabbed UI with explicit memory/document management surfaces

The current codebase implements pieces of both but has not yet reached the full
spec. It is closer to being D1.6-dominant (due to the complete turn pipeline)
with D2.0 memory concepts bolted on through LangMem, while missing the GIST
layer, cross-encoder, sub-query decomposition, and UI features the spec
requires.

---

## 6. Verdict Summaries

### Which diagram reflects the implementation specified in design_description.txt?

**Diagram 2.0 (60.8%)** is the closer match, but only by an 8.5 percentage-point
margin. The spec is a **hybrid**: it inherits D2.0's memory architecture and
GIST abstraction while retaining D1.6's query pipeline and document handling.
Neither diagram alone is sufficient — the spec is a deliberate synthesis of both.

### Which diagram does the current codebase (context.md) more closely resemble?

**Diagram 1.6 (pipeline dominance)**. The `CoordinatorAgent.run_turn()` method
is a nearly 1:1 match to D1.6's linear RAG flow. D2.0's memory features exist
(LangMem operations, GIST table) but are either disabled or not fully
integrated into the retrieval path.

### What would it take for the codebase to match the spec?

1. Enable GIST retrieval pipeline (activate `chat_gists` retrievers)
2. Implement `@QUERY_AUGMENTATION_AGENT` with sub-query decomposition + semantic expansion
3. Add cross-encoder reranking (`@RE_RANK_AGENT[CROSS_ENCODER]`)
4. Implement ordered prompt placement (system | docs hi-lo | mem lo-hi | query)
5. Build ChainLit multi-tabbed UI (landing, chats_list, docs_list, memories_list)
6. Add manual memory/document CRUD operations (DELETE_MEMORY, ADD_MEMORY, SUPPRESS_DOC, CHAT_FORK)
7. Implement read-time memory pruning in the retrieval path

---

*Generated by oracle analysis of `.design/design_description.txt` vs. `diagram1.6.png` and `diagram2.0.png`, cross-referenced with `context.md`.*

---

## 7. Codebase vs. Design Spec Alignment

**Sources:**
- `.design/design_description.txt` — authoritative design specification
- `context.md` — current codebase reconnaissance

**Question:** Are the current codebase and the formal design spec aligned? Where do they differ, to what degree are they compatible, and what are the main differences?

---

### 7.1 Store Alignment

| Spec Store | Codebase Equivalent | Score |
|-----------|-------------------|-------|
| **documents vecdb** (Chroma, meta={src doc}, larger raw chunks) | LangChain-Chroma vector store + `documents`/`document_chunks`/`document_chunk_embeddings` SQLite tables | ✅ **MATCH** — Chroma for vectors, SQLite for metadata/chunks; chunks are raw text as specified. Missing: single `{src doc}` meta field (codebase uses `title` + `source` separately). |
| **lt_mem vecdb** (SQLite, meta={use_count, last_used}, smaller condensed chunks) | `long_term_memories` SQLite table + optional Chroma vector index (`long_term_memory_vector_index.py`) | ⚠️ **PARTIAL** — SQLite namespace/key store exists. Vector index is optional, not the primary path. Metadata: `updated_at` exists but **`use_count` is missing**. "Smaller condensed chunks" is not a distinct chunk size — structured key-value pairs replace raw chunk embedding. |
| **gists** (SQLite indexed by chat_id, contains: retrieved lt_mem list, st_mem gist+text JSON, new memories JSON) | `chat_gists` SQLite table (indexed by `chat_id`+`source_type`) with `gist_text`, `topics_json`, `decisions_json`, `open_tasks_json` | ⚠️ **PARTIAL** — Table and indexing exist. But: no "retrieved lt_mem list", no `{id, gist, info}` JSON structure, no `{id, memory, embed ID}` JSON. Gist schema differs from spec. |
| **Separate vecdbs for easier manipulation** | Documents use Chroma; lt_mem uses SQLite primary + optional Chroma secondary | ✅ **MATCH** — Physically separate backends. |

**Store Alignment: ~55%** — Foundation is solid, but metadata gaps (use_count) and GIST schema divergence are notable.

---

### 7.2 Agent Alignment

| Spec Agent | Codebase Equivalent | Score | Detail |
|-----------|-------------------|-------|--------|
| `@CHUNKING_AGENT` | `DocumentIngestionAgent` + `src/documents/splitters.py` | ⚠️ **PARTIAL** | Document chunking exists (custom paragraph splitter + LangChain adapter). But no agent for *memory* chunking — LangMem handles structured extraction, not semantic chunking of memory. |
| `@EMBEDDING_AGENT` | `sentence-transformers/all-MiniLM-L6-v2` via HuggingFace, used by both Chroma doc retriever and long-term memory vector index | ⚠️ **PARTIAL** | Functional embedding pipeline exists but is not encapsulated as an `@EMBEDDING_AGENT` class. It's a deterministic service call embedded in retrievers. |
| `@MEMORY_UPDATE_AGENT` | `LangMemStructuredMemoryState` + `ShortTermMemory.update_memory_if_needed()` | ✅ **STRONG MATCH** | Implements [upsert/supersede/delete] = [update/delete/pass]. Batch-triggered (≥6 unsummarized messages). Full tri-state decision engine. |
| `@QUERY_AUGMENTATION_AGENT` | `QueryAnalyzer` (lexical signal detection) + `RoutePlanner` (source planning) | ❌ **MISSING** | No sub-query decomposition. No semantic keyword injection. Lexical signals ≠ semantic expansion. Spec requires LLM-prompt-based augmentation; codebase does deterministic lexical matching. |
| `@RETRIEVAL_AGENT` | `RetrieverDispatcher` (6 sources) + `RoutingAgent` (enable/disable decisions) | ⚠️ **PARTIAL** | Multi-source dispatch exists. Doc retrieval is conditional (auto-enable on document-like queries). But retrieval is NOT per-sub-query (no sub-queries exist) and does NOT use `@RETRIEVAL_AGENT` evaluating each sub-query independently. |
| `@RE_RANK_AGENT[CROSS_ENCODER]` | `MemoryReranker` (deterministic weighted features / LLM JSON / hybrid) | ❌ **MISSING** | Reranking exists but uses **different mechanism**: no cross-encoder model, no [0-1] pairwise scoring. Deterministic mode uses lexical overlap + source priority + recency; LLM mode uses JSON output. Neither is a cross-encoder. |
| `@GISTING_AGENT` | `chat_gist_summarizer.py` (generation), `current_chat_gist_retriever.py` + `previous_chat_gist_retriever.py` (retrieval) | ⚠️ **PARTIAL** | Infrastructure exists but **retrieval is DISABLED** (`PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED=false`, `PREVIOUS_CHAT_GIST_GENERATION_ENABLED=false`). Gists are generated but not integrated into the memory processing pipeline — LangMem processes raw messages directly. No agent creates gists from Q/A pairs *and* appends them into st_mem as specified. |

**Agent Alignment: ~35%** — Core agents exist (@MEMORY_UPDATE, basic retrieval) but key spec agents (@QUERY_AUGMENTATION, @RE_RANK[CROSS_ENCODER]) have no equivalents, and @GISTING is implemented but disabled.

---

### 7.3 Pipeline Alignment

#### Spec SINGLE_REQUEST_ACTION vs. Codebase CoordinatorAgent.run_turn()

| Spec Stage | Codebase Stage | Match | Detail |
|-----------|---------------|-------|--------|
| **query decomposition** (split into sub-queries) | — | ❌ | Not implemented. QueryAnalyzer detects lexical signals but does not split. |
| **semantic expansion** (inject keywords, prompt-based) | `QueryAnalyzer` lexical signal detection | ❌ | Lexical matching ≠ semantic expansion. No keyword injection, no rephrasing. |
| **retrieval** (per-sub-query, per-source [lt_mem, docs]) | `RetrieverDispatcher.retrieve()` (all enabled sources, single pass) | ⚠️ **PARTIAL** | Per-source dispatch exists. But no per-sub-query iteration. Retrieval is a single flat pass over enabled sources, not nested loops. |
| **re-ranking** (per-sub-query, per-source, cross-encoder [0-1]) | `MemoryReranker.rank_with_trace()` (single pass over all candidates) | ⚠️ **PARTIAL** | Ranking exists but mechanism differs (feature scoring vs. cross-encoder). No per-sub-query, per-source separation. |
| **prompt stitching** (ordered: system \| docs hi-lo \| lt_mem lo-hi \| raw query) | `ContextManagerAgent.build_context_packet()` (budget-fitting with overflow drops) + legacy `ShortTermMemoryAgent.build_context()` | ❌ | Codebase uses **budget-fitting** (profile-based token allocation, overflow drops lowest-ranked). Spec uses **static ordered placement** to minimize "lost in the middle". Fundamentally different assembly strategies. |
| **LLM API call** | `ChatAgent.generate()` via `ModelWrapper` | ✅ | Direct match. |
| **reply processing** (@GISTING_AGENT: gist from Q/A → st_mem) | `ShortTermMemory.update_memory_if_needed()` (LangMem extraction from raw messages) | ⚠️ **PARTIAL** | Memory update occurs. But mechanism differs: LangMem extracts from raw messages, not from GISTs. No @GISTING_AGENT step between reply and memory. |
| **Extra codebase stages** | `database.save_message(user)`, legacy `ShortTermMemoryAgent.build_context()`, `ContextComparator.compare()`, `prompt_messages` validation, `AgentTurnResult`+`WorkflowTrace` | ➕ | Codebase additions beyond spec — comprehensive tracing and validation that the spec does not require but are valuable. |

**Pipeline Alignment: ~40%** — The core "retrieve → rerank → LLM" spine matches. The spec's front-end (decomposition, expansion) and back-end (GISTING) are missing. Prompt assembly strategy diverges fundamentally.

---

### 7.4 Memory Model Alignment

| Spec Memory Feature | Codebase Equivalent | Match |
|-------------------|-------------------|-------|
| **[update/delete/pass] tri-state on lt_mem** | LangMem `upsert`/`supersede`/`delete` operations | ✅ **EXACT** |
| **Information valuation before commit** | LangMem `confidence` field (default 0.5) on structured memories | ⚠️ **PARTIAL** — Confidence tracked but no explicit "non-zero information value" gate that discards before embedding. |
| **use_count metadata on lt_mem** | Not tracked | ❌ **MISSING** — `updated_at` exists but `use_count` (how many times a memory was retrieved) is not stored. |
| **last_used metadata on lt_mem** | `updated_at` field exists | ⚠️ **PARTIAL** — `updated_at` tracks last modification, not "last used in retrieval". Different semantics. |
| **Separate lt_mem vecdb** | `long_term_memories` SQLite + optional `long_term_memory_vector_index` Chroma | ✅ **MATCH** |
| **Smaller chunks for lt_mem vs. docs** | Not explicitly differentiated — same embedding model for both | ❌ **MISSING** — No chunk size distinction. Documents use `DOCUMENT_CHUNK_SIZE=1000`; memory uses LangMem key-value structures, not chunked embeddings. |
| **Remove old embedding by ID & re-embed on update** | LangMem handles internally; no explicit re-embed step in codebase | ⚠️ **PARTIAL** — Functionally equivalent (LangMem manages updates), but not an explicit vector store operation the codebase controls. |
| **Chat-end trigger for memory processing** | Batch trigger (`MEMORY_UPDATE_BATCH_SIZE=6` unsummarized messages) | ⚠️ **PARTIAL** — Different trigger mechanism. Spec triggers at explicit chat end; codebase triggers mid-conversation when batch fills. |
| **New memories list → commit into vecdb** | LangMem creates structured operations → stored in `long_term_memories` | ✅ **MATCH** |
| **GIST-based memory processing** | LangMem processes raw messages, not GISTs | ❌ **MISSING** — GISTs are a bypassed layer; the codebase goes directly from messages to LangMem extraction. |

**Memory Model Alignment: ~65%** — The core [update/delete/pass] machinery is a near-perfect match via LangMem. Missing: use_count, GIST-based processing pipeline, and distinct chunk sizing for lt_mem.

---

### 7.5 GIST Lifecycle Gap Quantification

| GIST Feature | Spec Requirement | Codebase Status | Gap |
|-------------|-----------------|-----------------|-----|
| **GIST table** | SQLite indexed by chat_id | ✅ `chat_gists` exists, indexed by `chat_id`+`source_type` | None |
| **GIST generation** | @GISTING_AGENT from Q/A pairs | ✅ `chat_gist_summarizer.py` exists | None |
| **GIST retrieval** | Integrated into memory processing | ❌ DISABLED (`PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED=false`) | **Critical** |
| **st_mem gist+text JSON** | `{id, gist, info}` per gist | ❌ Fields are `gist_text`, `topics_json`, `decisions_json`, `open_tasks_json` | Schema mismatch |
| **Retrieved lt_mem list in gist** | Track which memories were retrieved | ❌ Not stored in gist record | Missing field |
| **New memories JSON** | `{id, memory, embed ID}` per new memory | ❌ Not stored in gist record | Missing field |
| **GISTs feed memory update** | MEMORY_UPDATE_AGENT reads gists | ❌ LangMem reads raw messages, not gists | Architectural bypass |
| **GIST appended into st_mem** | GIST stored in short-term memory context | ❌ No st_mem integration path | Missing integration |

**GIST Lifecycle Alignment: ~15%** — The table and generation code exist but are entirely disconnected from the active pipeline. GISTs are a dormant architectural layer, not an active component.

---

### 7.6 UI Alignment

| Spec UI Feature | Codebase Status | Match |
|---------------|-----------------|-------|
| **ChainLit framework** | ✅ Chainlit 2.x (`app.py`) | Foundation match |
| **landing_page** tab | ❌ No landing page — app opens directly to chat | Missing |
| **chat_page** tab | ✅ Single chat page with message interface | Partial — chat exists but as only page, not a tab |
| **chats_list_page** tab | ❌ No chat listing page | Missing |
| **docs_list_page** tab | ❌ No document management page | Missing |
| **memories_list_page** tab | ❌ No memory management page | Missing |
| **Breadcrumbs** (Home/Chats/Documents/Memories) | ❌ No breadcrumb navigation | Missing |
| **Active/inactive chat distinction** | ❌ All chats are always active (no archive concept) | Missing |
| **Document upload** | ✅ File upload via Chainlit hooks → `DocumentIngestionAgent` | Partial — upload works but no list management page |
| **Manual memory CRUD** | ❌ No add/delete memory from UI | Missing |
| **Action trigger buttons** (per spec action mapping) | ❌ No explicit action buttons | Missing |
| **DEMO_MEMORY_TRACE** | ✅ Debug UI for memory trace | Extra — codebase has this, spec doesn't require it |

**UI Alignment: ~10%** — Same framework (Chainlit), but a single-page app vs. the spec's 5-tab application with list management. This is the single largest divergence between codebase and spec.

---

### 7.7 Action Coverage

| Spec Action | Codebase Equivalent | Score | Detail |
|------------|-------------------|-------|--------|
| **DOC_INPUT_ACTION** | `DocumentIngestionAgent` + `scripts/index_document_file.py` | ⚠️ **PARTIAL** | Documents can be loaded and indexed (via CLI or Chainlit upload). But no integrated "add docs" UI button on a docs_list_page. Chunking and embedding exist per spec. |
| **CHAT_END_ACTION** | No explicit chat end/archive. Memory update is batch-triggered mid-conversation. | ❌ **MISSING** | Spec requires PROCESS_INTO_MEMORY_ACTION at chat end + marking chat inactive. Codebase has no chat lifecycle beyond creation. |
| **SINGLE_REQUEST_ACTION** | `CoordinatorAgent.run_turn()` | ⚠️ **PARTIAL** | Core turn exists but missing: decomposition, semantic expansion, cross-encoder, ordered stitching. |
| **PRUNE_MEMORIES_ACTION** | No standalone prune. LangMem can delete during update cycle. | ❌ **MISSING** | Spec defines PRUNE as PROCESS_INTO_MEMORY. Codebase has delete operations in LangMem but no explicit prune trigger or action. |
| **SUPPRESS_DOC_ACTION** | No document activation/suppression. | ❌ **MISSING** | Documents table has no `active`/`inactive` flag. All indexed documents participate in retrieval forever. |
| **DELETE_MEMORY_ACTION** | No UI-driven delete. LangMem can delete programmatically. | ❌ **MISSING** | Memory can be deleted internally by LangMem but no user-facing delete from UI. |
| **ADD_MEMORY_ACTION** | No manual memory insertion. | ❌ **MISSING** | Memories are created only via LangMem extraction. No path to "forcefully add information to the system" from UI. |
| **NEW_CHAT_ACTION** | Chainlit creates new chat on conversation start. SQLite `chats` row created on first message. | ✅ **FULL** | Direct match. |
| **CHAT_FORK_ACTION** | No chat forking. | ❌ **MISSING** | No mechanism to duplicate chat state into a new active chat. |

**Action Coverage: 1 FULL, 2 PARTIAL, 6 MISSING** — ~20% coverage. The codebase handles the core SINGLE_REQUEST and basic DOC_INPUT, but the spec's operational actions (CHAT_END, PRUNE, SUPPRESS, DELETE_MEMORY, ADD_MEMORY, CHAT_FORK) are almost entirely absent.

---

### 7.8 Overall Compatibility Assessment

#### Are the codebase and spec fundamentally compatible?

**YES — the foundations are compatible.** Both use:
- Same framework (Chainlit + SQLite + vector DBs)
- Same core concepts (multi-agent, typed memory, document RAG, GISTs)
- Same memory mutation model ([update/delete/pass] ≈ upsert/supersede/delete)
- Same separation of concerns (routing, retrieval, reranking, context, generation)

There are **no architectural contradictions** that would require a rewrite. The gaps are additions, not incompatibilities.

#### Can the codebase evolve toward the spec without a rewrite?

**YES.** The codebase is on a convergent trajectory. The path requires:

| Category | Approach | Effort |
|---------|----------|--------|
| Enable GIST pipeline | Flip config flags (`PREVIOUS_CHAT_GIST_*_ENABLED=true`), integrate gist retrievers into memory update path | Low |
| Query decomposition | New `QueryDecomposer` module in `src/routing/` | Medium |
| Semantic expansion | New `SemanticExpander` module (LLM-prompt-based keyword injection) | Medium |
| Cross-encoder reranker | New `CrossEncoderReranker` in `src/retrieval/` as new `RERANKER_MODE` | Medium-High |
| Ordered prompt placement | New `OrderedPlacementBuilder` or extend `ContextBuilder` with a new profile | Low-Medium |
| UI tabs | New Chainlit elements (`@cl.on_chat_start`, custom `@cl.step`, `@cl.Actions`) in `app.py` | High |
| Chat lifecycle (END/FORK) | Add `active`/`inactive` flag to `chats` table, implement CHAT_END and CHAT_FORK | Medium |
| Manual memory CRUD | UI endpoints for ADD_MEMORY, DELETE_MEMORY, SUPPRESS_DOC | Medium |
| use_count tracking | Add `use_count` column to `long_term_memories`, increment on retrieval | Low |

#### Key Architectural Decision Points

1. **GIST-first vs. LangMem-first**: The spec routes memory processing *through GISTs*. The codebase routes memory processing *directly through LangMem*. Reconciling these requires deciding whether GISTs become the primary memory pipeline or remain a secondary layer.

2. **Batch trigger vs. chat-end trigger**: The codebase triggers memory updates mid-conversation (≥6 messages). The spec triggers at chat end. These can coexist (batch during chat, comprehensive at chat end) but the chat lifecycle must exist first.

3. **Budget-fitting vs. ordered placement**: The codebase's budget-aware assembly with overflow handling is arguably more robust than the spec's static placement. This is a design choice, not a gap — either strategy is valid, and the codebase's approach may be preferable.

---

### 7.9 Prioritized Gap List

| Priority | Gap | Domain | Rationale |
|---------|-----|--------|-----------|
| **P0** | Enable GIST pipeline | GIST | Table exists, code exists, only config flags need flipping. Highest value for lowest effort. Unlocks GIST-based retrieval and memory processing. |
| **P1** | Query decomposition | Pipeline | Foundation for per-sub-query retrieval and reranking. Without this, the spec's nested retrieval loops cannot exist. |
| **P1** | Semantic expansion | Pipeline | Complements decomposition. Required for the spec's prompt-based keyword injection. |
| **P2** | CHAT_END_ACTION + chat lifecycle | Actions | Required for the spec's memory processing trigger model. Also enables CHAT_FORK. |
| **P2** | Cross-encoder reranker | Reranking | Specified as `@RE_RANK_AGENT[CROSS_ENCODER]`. Improves reranking accuracy but current feature-scoring reranker is functional. |
| **P3** | Ordered prompt placement | Prompt | Alternative to current budget-fitting. Lower priority since budget-fitting is already robust. |
| **P3** | use_count metadata | Memory | Simple schema change. Improves memory quality metrics but not blocking. |
| **P4** | ChainLit multi-tab UI | UI | Largest effort. Required for spec compliance but backend can evolve independently. |
| **P4** | Manual memory/document CRUD | Actions | UI-dependent. Cannot exist without the tabbed UI pages. |

---

### 7.10 Verdict

| Question | Answer |
|---------|--------|
| **Are codebase and spec aligned?** | Partially. The codebase is on a compatible trajectory but is ~35-40% of the way to the full spec. |
| **Where do they differ?** | Primarily in: (1) missing query processing front-end, (2) disabled GIST pipeline, (3) absent UI, (4) different prompt assembly strategy, (5) missing operational actions. |
| **Degree of compatibility?** | **High (~80%)**. Same foundations, same concepts. No rewrite needed. The 20% gap is net-new features, not contradictions. |
| **Main differences?** | Spec has richer query processing (decomposition + expansion), explicit GIST lifecycle integration, cross-encoder reranking, tabbed UI with manual operations. Codebase has better tracing (WorkflowTrace), budget-aware assembly, comprehensive evaluation infrastructure, and deterministic-first reliability. |
| **Is the codebase on track?** | **Yes.** The codebase has built solid infrastructure that can be extended toward the spec. Current work prioritized reliability and traceability (deterministic routing, WorkflowTrace, budget-aware context) over spec features that require UI or LLM-heavy components. This is a reasonable implementation order. |

---

*Generated by oracle analysis of `context.md` vs. `.design/design_description.txt`, cross-referenced with earlier diagram analysis.*
