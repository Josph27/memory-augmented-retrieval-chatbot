# Design 1.6: Token-Bounded Conversation RAG — Pipeline Report

**Source:** `diagram1.6.png`
**Core Problem:** Conversation prompt exceeds the model's token limit.

---

## 1. Trigger Condition

```
conversation prompt > k tokens
  ⇒ prompt / reply pairs covering > 40% of current token size
```

When the total conversation context crosses the $k$-token threshold, the system
identifies which (question, answer) pairs consume more than 40% of that budget and
routes them through the compaction and retrieval pipeline.

---

## 2. Pipeline Breakdown

### 2.1 Prompt / Reply Preparation

```
conversation prompt > k tokens
  │
  ├── extract ALL (Q,A) pairs
  │     │
  │     └── chunk (Q,A) pairs ──► vector store (long-term memory)
  │
  └── extract last k (Q,A) pairs
        │
        └── summarize ──► context-overflow guard
```

- **Extract ALL (Q,A) pairs** — every user/assistant turn is extracted from the
  conversation.
- **chunk (Q,A) pairs → vector store** — all extracted pairs are chunked, embedded,
  and persisted in the **long-term vector store** so past conversations survive
  the active context window.
- **extract last k (Q,A) pairs → summarize** — the most recent $k$ pairs stay
  in the active buffer but are summarised into a compressed form to save token
  headroom. This is the primary "context overflow" defence: summarised recent
  history takes far fewer tokens than raw messages.

### 2.2 Query Augmentation

```
raw user query
  │
  ├── split query into multiple subqueries
  ├── inject keywords
  └── rephrasing
  │
  └── augmented query (for retrieval)
```

The original query is never sent directly to the vector database. Instead, three
transformations are applied deterministically:

| Step | Purpose |
|------|---------|
| **Split into multiple subqueries** | Decompose compound questions; each subquery targets a different facet. |
| **Inject keywords** | Add domain terms that improve recall in the embedding space. |
| **Rephrasing** | Normalise the surface form for better semantic alignment with stored embeddings. |

The output is one or more augmented queries ready for the retrieval tier.

### 2.3 Retrieval

```
augmented query
  │
  └── query the vec db for information
        │
        Priority hierarchy:
          1. current instance
          2. input docs
          3. old conversations
              │
              └── long-term vector store (docs)
```

Retrieval queries the vector database under a strict **three-level priority
hierarchy**:

1. **Current instance** — the most relevant, freshest context (current chat).
2. **Input docs** — documents explicitly uploaded or indexed for this session.
3. **Old conversations** — archival (Q,A) chunks stored in the long-term vector
   store from previous compaction cycles.

This hierarchy ensures that recent/live context always outweighs stale archive
hits before re-ranking even begins.

### 2.4 Re-Ranking

```
retrieved candidates
  │
  └── small local model re-rank
        │
        └── validate accuracy against query
```

A **small local model** (not the primary generation LLM) re-ranks every
retrieved item. Its job is twofold:

- **Re-score** candidates for relevance.
- **Validate** that the retrieved information is factually consistent with the
  query's intent, discarding hallucination-prone matches.

This is the same architectural role as the `MemoryReranker` (`deterministic` /
`llm` / `hybrid` modes) in the current codebase.

### 2.5 Prompt Construction & Generation

```
prompt construction
  │
  └── System prompts + Current chat context + Retrieved context
        │
        └── fused together ──► LLM API CALL
```

Three sources are fused into a single prompt packet:

| Source | Content |
|--------|---------|
| **System prompts** | Role instructions, behaviour rules, output format. |
| **Current chat context** | Summarised recent history (from §2.1) + any raw window messages. |
| **Retrieved context** | Re-ranked candidates from the vector store (from §2.4). |

This fused packet is sent to the **LLM API CALL**, and the response is returned
to the user.

### 2.6 End States

```
END: New doc           — a new document was ingested; pipeline cycle resets.
END: user query        — the current query was answered; conversation continues.
END: Conversation finished — terminal state.
END: Conversation too long — triggers another compaction cycle back to §2.1.
```

---

## 3. Data Flow Summary

```
┌─────────────────────────────────────────────────────────────┐
│ user query                                                   │
│   │                                                          │
│   ├── (if context > k tokens) extract & chunk (Q,A) pairs    │
│   │     └── embed → long-term vector store                   │
│   │                                                          │
│   └── (if context > k tokens) summarize last k (Q,A) pairs   │
│         └── compact recent context                           │
│                                                              │
│   ├── query augmentation (split / inject / rephrase)         │
│   │                                                          │
│   └── vec db retrieval (current > docs > old conversations)  │
│         │                                                    │
│         └── small local model re-rank & validate             │
│               │                                              │
│               └── prompt construction                        │
│                     └── LLM API CALL                         │
│                           └── response to user               │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Mapping to Current Codebase

| Diagram 1.6 Component | Current Implementation |
|------------------------|------------------------|
| extract ALL (Q,A) pairs, chunk | `src/memory/short_term.py` — `update_memory_if_needed()` extracts LangMem operations when `MEMORY_UPDATE_BATCH_SIZE=6` is reached; `mark_messages_summarized()` |
| summarize last k pairs | `src/memory/chat_gist_summarizer.py` — gist generation (disabled by default via `PREVIOUS_CHAT_GIST_GENERATION_ENABLED=false`) |
| query augmentation (split/keywords/rephrase) | `src/routing/query_analyzer.py` — `QueryAnalyzer` (deterministic lexical signal detection); `src/routing/route_planner.py` — builds `RoutePlan` |
| vec db retrieval (current/docs/old) | `src/retrieval/retriever_dispatcher.py` — dispatches to 6 retrievers by priority |
| small local model re-rank & validate | `src/retrieval/reranker.py` — `MemoryReranker` (`deterministic` / `llm` / `hybrid`); deterministic mode = weighted feature scoring (no LLM call) |
| prompt construction | `src/context/context_budget_allocator.py` + `src/context/context_builder.py` — token-budgeted `ContextPacket` assembly |
| LLM API CALL | `src/agents/chat_agent.py` — `ChatAgent.generate()` via `ModelWrapper` (OpenAI-compatible) |
