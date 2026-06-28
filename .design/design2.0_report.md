# Design 2.0: Indefinite Memory Maintenance — Pipeline Report

**Source:** `diagram2.0.png`
**Core Problem:** Memory grows unboundedly; stale/irrelevant facts degrade retrieval quality over time.

---

## 1. Core Paradigm

```
goal: indefinite memory maintenance
```

Design 2.0 abandons the passive "chunk-and-embed-everything" approach of Design 1.6
in favour of an **active memory agency**. A dedicated **Memory Agent** manages the
full lifecycle of long-term memory — retrieval, pruning, valuation, and
insertion/deletion — aiming to keep the knowledge store indefinitely useful
without human curation.

**Legend (from diagram):**

- **blue** = data store access (Vector Store reads / writes)
- **black** = pipeline logic (computations, decisions)

---

## 2. Pipeline Breakdown

### 2.1 Query Phase

```
user query
  │
  └── query augmentation
        │
        └── augmented query
```

The entry point mirrors Design 1.6: the user's raw query passes through an
augmentation step before any retrieval. The diagram does not detail the
augmentation sub-steps here, implying reuse of or compatibility with 1.6's
split/keywords/rephrase mechanism.

### 2.2 Memory Agent: Retrieval Cycle

```
                     ╔══════════════════════════╗
                     ║     MEMORY AGENT         ║
                     ║       retrieval          ║
                     ╚══════════════════════════╝
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
         ▼                      ▼                      ▼
   autoload last n        for each retrieved     prune memory
   updated embeddings     user GIST:
   as retrieved GISTS     ─ evaluate against     (vector store)
                          │  current query
                          │
                          └── ► scoring / filtering
```

| Step | Description |
|------|-------------|
| **Autoload last n updated embeddings as retrieved GISTS** | The agent does not search the entire vector store from scratch. Instead, it keeps a pointer to the **last $n$ embeddings that were updated** (inserted, modified, or re-confirmed). These become the "retrieved GISTS" — a pre-warmed set of facts that are likely still relevant. This is analogous to a write-through cache for memory. |
| **For each retrieved user GIST** | Each GIST is individually evaluated against the augmented query. The agent scores relevance and, critically, *prunes* the memory in-place if the GIST is determined to be stale, superseded, or contradictory. |
| **Prune memory (vector store)** | Pruning happens at **retrieval time**, not as a separate maintenance cron. Stale GISTs are removed from the active index so they never pollute future retrieval results. |

### 2.3 Memory Agent: Update Cycle

```
                     ╔══════════════════════════╗
                     ║     MEMORY AGENT         ║
                     ║       update             ║
                     ╚══════════════════════════╝
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
         ▼                      ▼                      ▼
   for each new             assert non-zero        check all new gists.
   user GIST:               information value      [UPDATE, DELETE, SKIP]
                                                    │
   ─ generate GIST          ─ discard if           ─ resolve against
     from conversation         redundant/empty        existing store
                                                    │
                                                    ▼
                                              NEW embedding
                                              → vector store
```

| Step | Description |
|------|-------------|
| **For each new user GIST** | After every user interaction, the Memory Agent extracts one or more "GISTs" — compact, structured semantic facts distilled from the conversation (e.g., "user prefers Python", "project uses uv package manager"). |
| **Assert non-zero information value** | Before anything is written to the vector store, the agent validates each GIST carries meaningful, non-redundant information. GISTs that duplicate existing knowledge or are empty are **discarded** immediately — no embedding cost, no storage cost, no retrieval noise. |
| **Check all new gists** | Surviving GISTs are compared against existing memory. The agent resolves conflicts and applies one of three atomic operations: |
| └ **UPDATE** | Supersedes an existing memory record — content changes, embedding is re-computed, timestamp refreshed. |
| └ **DELETE** | Removes an existing memory record — the fact is no longer true or relevant. |
| └ **SKIP** | No-op — the GIST adds nothing new, or it is identical to existing memory. |
| **NEW embedding → vector store** | Only after [UPDATE / DELETE] operations resolve does the vector store receive a **new embedding** (or a deletion command). SKIP produces no vector store I/O. |

---

## 3. Complete Data Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│   user query                                                         │
│     │                                                                │
│     ├── query augmentation                                           │
│     │                                                                │
│     └──► MEMORY AGENT (retrieval)                                    │
│            │                                                         │
│            ├── autoload last n updated embeddings → retrieved GISTS  │
│            ├── for each GIST: evaluate → prune memory (vector store) │
│            │                                                         │
│            └── final candidate set → (to prompt construction / LLM)  │
│                                                                      │
│   ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
│                                                                      │
│   conversation produces new user GIST(s)                             │
│     │                                                                │
│     └──► MEMORY AGENT (update)                                       │
│            │                                                         │
│            ├── assert non-zero information value → discard noise     │
│            ├── check all new gists: [UPDATE / DELETE / SKIP]         │
│            │                                                         │
│            └── NEW embedding → vector store (only on UPDATE/DELETE)  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. Design Philosophy: Read-Time Pruning + Write-Time Valuation

Design 2.0 introduces two novel architectural invariants that distinguish it
from passive embedding stores:

### 4.1 Read-Time Pruning

Traditional RAG systems (like Design 1.6) let stale facts accumulate in the
vector store and rely on re-rankers to push them down. Design 2.0 **reverses
the burden**: the retrieval step itself prunes memory. If a retrieved fact is
determined to be stale or contradictory, it is removed *during* the read path
— it never reaches the re-ranker or prompt assembler.

### 4.2 Write-Time Information Valuation

Instead of embedding every (Q,A) pair as in Design 1.6, Design 2.0 rejects
GISTs that carry **zero information value**. This eliminates the most common
source of vector drift: repeated, trivial, or empty embeddings that dilute
the semantic neighbourhood of real facts.

### 4.3 Structured Mutation Operations

The `[UPDATE, DELETE, SKIP]` tri-state resolution models memory as a
**mutable entity**, not an append-only log. This directly enables indefinite
maintenance: the agent can *correct* wrong facts and *remove* obsolete ones
without needing a full re-index.

---

## 5. Mapping to Current Codebase

| Diagram 2.0 Component | Current Implementation |
|------------------------|------------------------|
| Memory Agent (retrieval) | `src/retrieval/structured_memory_retriever.py` — `StructuredMemoryRetriever` queries `long_term_memories` + `chat_memory_state` fallback |
| Memory Agent (update) | `src/memory/langmem_structured.py` — `LangMemStructuredMemoryState`; `src/memory/short_term.py` — `ShortTermMemory.update_memory_if_needed()` triggers LangMem extraction when batch ≥ 6 |
| GIST extraction & assert non-zero value | LangMem's `create_structured_memory_store()` produces typed operations; the `confidence` field in `long_term_memories` (default 0.5) implicitly gates quality |
| [UPDATE, DELETE, SKIP] operations | LangMem operations: `upsert`, `supersede`, `delete` — exactly the three mutation types described in the diagram |
| autoload last n updated embeddings | `src/memory/long_term_store.py` — `SQLiteLongTermMemoryStore` queries by `updated_at` descending; `src/memory/long_term_vector_index.py` — Chroma-based search with recency weighting |
| prune memory (vector store) | Not fully implemented in current retrieval path. The `StructuredMemoryRetriever` reads but does not mutate the store at retrieval time. Pruning/deletion only happens in the update cycle. |
| query augmentation | `src/routing/query_analyzer.py` + `src/routing/route_planner.py` (lexical signals, not the subquery/keyword/rephrase triple from diagram 1.6) |

---

## 6. Gap Analysis: Diagram 2.0 vs. Current Implementation

| Feature from Diagram 2.0 | Status in Codebase |
|---------------------------|---------------------|
| Memory agent as unified class | **Partial** — retrieval and update are in separate modules (`structured_memory_retriever.py` vs. `langmem_structured.py` + `short_term.py`), not a single `MemoryAgent` class |
| Read-time pruning | **Not implemented** — pruning is only done in the update cycle (LangMem extraction), not during retrieval |
| Autoload last n updated embeddings | **Partial** — `updated_at` ordering exists but retrieval is query-driven, not a pre-warmed GIST cache |
| GIST as explicit semantic unit | **Partial** — `chat_gists` table exists with fields (`gist_text`, `topics_json`, `decisions_json`) but retrieval from gists is DISABLED by default |

---
*Generated from diagram2.0.png via Tesseract OCR + architectural analysis.*
