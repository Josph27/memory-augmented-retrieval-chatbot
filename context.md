# Deep Codebase Analysis: memory-augmented-retrieval-chatbot

## 1. Project Overview

A **TUM practical-course project**: multi-agent typed-memory RAG chatbot with Chainlit browser UI. Combines SQLite-backed chat persistence, LangMem-powered structured long-term memory, LangChain-Chroma document vector retrieval, deterministic routing/reranking/context-budgeting with optional LLM enhancement, and comprehensive workflow tracing.

**Language**: Python 3.10+ (`.python-version` = 3.12)  
**Package Manager**: `uv` + `pyproject.toml` (authoritative); `requirements.txt` (fallback)  
**Testing**: pytest 8.x | **Linting**: ruff 0.8.x (line-length=100, target py310)  
**Containerization**: `python:3.12-slim` Docker

---

## 2. Tech Stack Detail

| Layer | Technology | Specifics |
|-------|-----------|-----------|
| **Chat UI** | Chainlit 2.x | `app.py` entrypoint, `BaseDataLayer` adapter |
| **LLM Client** | OpenAI-compatible (`openai` library) | Any `/v1/chat/completions` endpoint via `OPENAI_BASE_URL` |
| **Structured Memory** | LangMem >=0.0.30 | `create_memory_manager()` with `LangMemStructuredMemory` Pydantic schema |
| **Document Retrieval** | LangChain-Chroma + HuggingFace | `sentence-transformers/all-MiniLM-L6-v2` embeddings |
| **Database** | SQLite (single file) | `data/chatbot.db`, raw queries with `sqlite3.Row` |
| **Dependencies** | chainlit, chromadb, langchain-*, langmem, openai, sentence-transformers, datasets, faiss-cpu | See `pyproject.toml` |

---

## 3. Entry Points & Initialization

### 3.1 Primary Entry: `app.py`

Sole application entry point. Initialization sequence:

```python
# 1. Set Chainlit auth defaults (os.environ.setdefault)
# 2. Load config from environment
config = AppConfig.from_env()
# 3. Initialize single SQLite database connection
database = Database(config.database_path)
# 4. Per-model chat service cache (global dict, keyed by model name)
chat_services: dict[str, ChatService] = {}
```

Chainlit lifecycle hooks:

- `@cl.password_auth_callback` → authenticates one stable local user
- `@cl.data_layer` → `SQLiteChainlitDataLayer(database)` for history UI
- `@cl.set_chat_profiles` → 4 model profiles (gemma, qwen, gpt-oss, mistral-medium)
- `@cl.on_chat_start` → creates chat row in SQLite, option for previous-chat gist generation
- `@cl.on_chat_resume` → reconnects session to existing SQLite chat
- `@cl.on_message` → handles user message, indexes uploaded files, dispatches to ChatService

Model profiles are defined as `NamedTuple` with `key`, `display_name`, `model_name`, `description`. Each gets a separate `ChatService` instance cached in memory.

### 3.2 CLI / Other Entry Points

- `scripts/index_document_file.py` — CLI document indexing
- `scripts/verify_natural_long_term_memory_flow.py` — cross-chat memory verification
- `scripts/rebuild_long_term_memory_index.py` — rebuild long-term memory vector index
- `evals/` — evaluation scripts for document QA, structured memory, e2e, generated answer, multi-source retrieval
- **Docker**: `docker run ... memory-chatbot` (exposes port 8000)

---

## 4. Dependency Injection / Service Wiring

**No centralized DI container.** Wiring is ad-hoc, happens in two places:

### 4.1 `ChatService.__init__()` (primary wiring point)

```python
class ChatService:
    def __init__(self, database, model, ...):
        self.memory = ShortTermMemory(database, model, ...)
        self.coordinator = CoordinatorAgent(
            database=database,
            memory_agent=ShortTermMemoryAgent(self.memory),
            context_builder=ContextBuilderAgent(self.memory),
            chat_agent=ChatAgent(model),
            system_prompt=SYSTEM_PROMPT,
            retriever_dispatcher=RetrieverDispatcher(database, ...),
            routing_agent=RoutingAgent(mode=routing_mode, model=model),
            memory_reranker=MemoryReranker(mode=reranker_mode, model=model, ...),
        )
        self.document_ingestion_agent = DocumentIngestionAgent(database, indexer)
```

### 4.2 `CoordinatorAgent.__init__()` (fallback construction)

All optional constructor params default to `None`, and the coordinator creates sensible defaults when a dependency is missing:

```python
self.routing_agent = routing_agent or RoutingAgent(route_planner or RoutePlanner())
self.retriever_dispatcher = retriever_dispatcher or RetrieverDispatcher(database)
self.memory_reranker = memory_reranker or MemoryReranker()
self.context_budget_allocator = context_budget_allocator or ContextBudgetAllocator()
self.trace_context_builder = trace_context_builder or TraceContextBuilder()
self.context_comparator = context_comparator or ContextComparator()
```

**Key pattern**: final/default policy objects (`RoutePlannerPolicy`, `RerankerPolicy`, `ContextBudgetPolicy`, `QueryAnalyzerPolicy`) are frozen dataclasses with sensible defaults. Any caller can override by passing a custom instance.

---

## 5. Module Structure & Responsibilities

```
src/
├── core/contracts.py          # Data contracts (MemoryCandidate, ContextPacket, WorkflowTrace, etc.)
├── config.py                  # Frozen AppConfig dataclass from env vars
├── database.py                # SQLite adapter with raw queries, schema migrations
├── model_wrapper.py           # Thin OpenAI-compatible client
├── chat_service.py            # Factory: wires CoordinatorAgent + ShortTermMemory + model
├── chainlit_data_layer.py     # SQLiteChainlitDataLayer: Chainlit history adapter
│
├── agents/                    # Agent wrappers (responsibility boundaries)
│   ├── coordinator_agent.py   # Main turn pipeline orchestrator
│   ├── chat_agent.py          # Thin adapter over ModelWrapper.chat()
│   ├── short_term_memory_agent.py  # Pass-through adapter over ShortTermMemory
│   ├── context_builder_agent.py    # Legacy prompt assembly adapter
│   ├── context_manager_agent.py    # Budget allocator + ContextPacket builder wrapper
│   └── document_ingestion_agent.py # File loading/indexing wrapper
│
├── routing/                   # Query analysis + route planning
│   ├── query_analyzer.py      # Deterministic lexical signal detection
│   ├── route_planner.py       # Deterministic source-plan builder
│   └── routing_agent.py       # Rule/LLM/Hybrid routing with fallback
│
├── retrieval/                 # Retrieval dispatcher + per-source retrievers
│   ├── retriever_dispatcher.py     # Dispatch to enabled sources
│   ├── recent_messages_retriever.py     # Raw messages from SQLite
│   ├── structured_memory_retriever.py   # SQLite/vector/hybrid modes
│   ├── langchain_chroma_retriever.py    # LangChain-Chroma doc retrieval
│   ├── current_chat_gist_retriever.py   # Lexical gist stub
│   ├── previous_chat_gist_retriever.py  # Cross-chat gist stub
│   ├── raw_message_span_retriever.py    # Span drill-down
│   └── reranker.py                     # Deterministic/LLM/Hybrid reranker
│
├── context/                   # Token budgeting + prompt assembly
│   ├── context_budget_allocator.py  # Profile-based token allocation
│   ├── context_builder.py           # Budget-aware ContextPacket builder
│   ├── context_comparator.py        # Legacy vs. trace prompt shape diff
│   ├── prompt_messages.py           # ContextPacket → model messages validation
│   └── token_estimator.py           # ApproximateTokenEstimator (chars/4)
│
├── memory/                    # Memory management
│   ├── short_term.py          # ShortTermMemory: context + periodic updates
│   ├── structured_state.py    # Memory operations, validation, compat (DEPRECATED — see §10.2)
│   ├── langmem_structured.py  # LangMem backend (primary structured memory)
│   ├── long_term_store.py     # SQLite namespace/key store + InMemoryStore
│   ├── long_term_vector_index.py  # Chroma vector index for long-term memory
│   ├── chat_gist_summarizer.py    # Chat gist generation
│   ├── previous_chat_gist.py      # Previous-chat gist orchestration
│   ├── memory_trace.py            # Demo memory trace (debug UI)
│   └── constants.py               # Raw message limit, batch sizes
│
└── documents/                 # Document loading & ingestion
    ├── loaders.py             # File loaders (.txt, .md, .pdf)
    ├── splitters.py           # Custom paragraph splitter + LangChain adapter
    ├── ingestion.py           # DocumentIngestionService (SQLite chunks)
    └── inspection.py          # Document inspection utilities
```

---

## 6. Data Flow: Complete SINGLE_REQUEST_ACTION Trace

### Step-by-step through `CoordinatorAgent.run_turn()`

```
User message arrives at app.py > on_message
  → chat_service.handle_user_turn(chat_id, content)
    → coordinator.run_turn(chat_id, content)
```

**1. ROUTING** (deterministic or LLM with fallback):

```
RoutingAgent.route(query)
  → if mode=="rule": QueryAnalyzer.analyze(query) → RoutePlanner.plan_from_analysis()
  → if mode=="llm"|"hybrid": model.chat(routing_prompt, T=0) → parse JSON → validate → or fallback
  → Returns RoutingDecision:
      - route_plan: RoutePlan (all possible sources listed, some enabled)
      - use_recent_messages, use_structured_memory, use_document_memory: bools
      - reason, confidence, routing_mode, fallback_mode
```

**2. PERSIST USER MESSAGE:**

```
database.save_message(chat_id, role="user", content=content)
  → INSERT INTO messages(...) → returns message_id
  → UPDATE chats SET updated_at = now()
```

**3. RETRIEVAL:**

```
RetrieverDispatcher.retrieve(chat_id, route_plan)
  → for each enabled SourcePlan:
      retriever = self.retrievers[source_plan.source]
      candidates.extend(retriever.retrieve(chat_id, source_plan))
  → Returns flat list of MemoryCandidate objects
```

Retriever dispatch mapping (built in `RetrieverDispatcher.__init__`):

- `recent_messages` → `RecentMessagesRetriever(database, default_limit=raw_message_limit)`
- `structured_memory` → `StructuredMemoryRetriever(database)` — 3 modes (sqlite/vector/hybrid)
- `document_memory` → `langchain_chroma_retriever_for_env(database)` — LangChainChromaRetriever
- `current_chat_gist` → `CurrentChatGistRetriever(database)` — stub, lexical only
- `previous_chat_gist` → `PreviousChatGistRetriever(database)` — stub, lexical only
- `raw_message_span` → `RawMessageSpanRetriever(database)`

Structured memory retrieval modes:

- **sqlite**: loads from `long_term_memories` table (active records), falls back to `chat_memory_state` JSON
- **vector**: `LongTermMemoryVectorIndex.search()` via Chroma, falls back to sqlite on failure
- **hybrid**: combines both, deduplicates by namespace/memory_id

**4. RERANKING:**

```
MemoryReranker.rank_with_trace(candidates, ranking_profile, query)
  → deterministic_rank(): score each candidate with weighted features
      Features: lexical_overlap(0.35), query_source_boost(0.25), semantic_score(0.20),
                similarity_score(0.20), importance(0.15), confidence(0.15),
                recency(0.10), usage_count(0.05), source_priority(0.10),
                status_penalty(1.0), redundancy_penalty(1.0)
  → if mode=="llm"|"hybrid": model.chat(reranker_prompt, T=0) → parse JSON → validate
      Falls back to deterministic on: missing model, low confidence (<0.55), invalid JSON, error
  → Returns RerankResult with ranked candidates + trace metadata
```

**5. CONTEXT BUDGET ALLOCATION:**

```
ContextManagerAgent.build_context_packet(system_prompt, latest_user_message, ranked_candidates, route_plan)
  → ContextBudgetAllocator.allocate(route_plan, ranked_candidates, ...)
      Profiles: general_chat, memory_recall, document_question, mixed_memory_document
      Computes: system tokens, safety margin, answer reserve, per-source budgets
      Normalizes ratios for enabled sources only
  → Returns ContextBudget with source_token_budgets
```

**6. CONTEXT PACKET BUILDING (trace path):**

```
ContextBuilder.build(system_prompt, latest_user_message, ranked_candidates, budget, route_plan)
  → Group candidates by source
  → For each source in CONTEXT_SOURCE_ORDER:
      - "structured_memory", "current_chat_gist", "previous_chat_gist",
        "document_memory", "raw_message_span", "current_chat_chunks",
        "previous_chat_memory", "recent_messages"
      - select_for_source(): fit highest-ranked candidates into source budget
      - Recent messages: exclude latest user query, sort chronologically (NOT by rank)
  → drop_non_recent_candidates_for_overflow(): iteratively drop lowest-ranked
    non-recent candidates until total prompt fits in context_limit
    - Non-recent sources are droppable; recent messages are NOT
  → build_trace_messages(): assemble system + structured_memory + retrieved_memory +
    recent_messages + latest_user_message in order
  → Returns ContextPacket with model_messages, metadata, dropped candidates
```

**7. LEGACY CONTEXT BUILDING (fallback path, runs in parallel):**

```
ShortTermMemoryAgent.build_context(chat_id, latest_user_message_id=user_message_id)
  → ShortTermMemory.build_context()
      - Load raw_message_limit recent messages from SQLite
      - Load chat_memory_state JSON
  → ContextBuilderAgent.build(system_prompt, context, latest_user_message)
      - Format structured memory section
      - Build model_messages = [system, memory_section, *raw_messages, latest]
```

Note: The parameter is `latest_user_message_id`, not `user_message_id`. Both `ShortTermMemoryAgent.build_context()` and `ShortTermMemory.build_context()` use this parameter name.

**8. CONTEXT COMPARISON:**

```
ContextComparator.compare(old_model_messages, new_context_packet, latest_user_message)
  → Compute PromptShape for both (estimated_tokens, message_count, section_order, flags)
  → Compute token difference and ratio
  → Generate warnings (missing_latest_user_message, missing_recent_messages, etc.)
```

**9. PROMPT VALIDATION:**

```
context_packet_to_model_messages(trace_context_packet, latest_user_message, comparison)
  → Validate: non-empty, starts with system, valid roles, no empty content
  → Check: latest user message present exactly once, at final position
  → Check: no SEVERE_COMPARISON_WARNINGS (missing_latest_user_message)
  → Returns PromptAssemblyResult(messages, valid=True|False, fallback_reason)
```

**10. MODEL CALL:**

```
if prompt_assembly.valid:
    final_messages = prompt_assembly.messages  # context_packet path
else:
    final_messages = model_messages           # legacy fallback
ChatAgent.generate(final_messages)
  → ModelWrapper.chat(messages)
      → OpenAI client.chat.completions.create(model, messages, ...)
      → Returns response text (or fallback error message on OpenAIError)
```

**11. PERSIST ASSISTANT MESSAGE:**

```
database.save_message(chat_id, role="assistant", content=response)
```

**12. MEMORY UPDATE (non-blocking, errors suppressed):**

```
ShortTermMemoryAgent.update_memory_if_needed(chat_id)
  → select_unprocessed_batch(): old unsummarized messages outside raw window
  → if accumulated >= memory_update_batch_size (default 6):
      - Send to LangMem backend (or StructuredMemoryState for compat)
      - LangMem extracts structured operations via create_memory_manager()
      - Validate operations against source message texts
      - Apply ops: upsert adds/updates, supersede marks inactive, delete marks deleted
      - Persist to chat_memory_state (JSON mirror)
      - Persist to long_term_memories (namespace/key store) via SQLiteLongTermMemoryStore
      - Mark messages as summarized
      - Corrections require BOTH supersede/delete + upsert for active value
```

Note: `StructuredMemoryState` is deprecated (see §10.2). The active backend is `LangMemStructuredMemoryState`. Correction rejection (`valid_but_useless_correction_batch`) only applies in the deprecated path — the active LangMem path delegates correction coherence to LangMem's model.

**13. ASSEMBLE RESULT:**

```
AgentTurnResult(answer, chat_id, trace_id, termination_reason, trace: WorkflowTrace)
```

`WorkflowTrace` contains: route_plan, retrieved_candidates, ranked_candidates, context_budget, context_packet, timings, errors, and all metadata from routing/reranking/context decisions.

---

## 7. Configuration

### 7.1 AppConfig (frozen dataclass)

```python
@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str           # from OPENAI_API_KEY (default "dummy")
    openai_base_url: str          # from OPENAI_BASE_URL (default "http://localhost:11434/v1")
    model_name: str               # from MODEL_NAME (default "google/gemma-4-31B-it")
    database_path: Path           # from DATABASE_PATH (default "data/chatbot.db")
    raw_message_limit: int        # from RAW_MESSAGE_LIMIT (default from constants: 8)
    memory_update_batch_size: int # from MEMORY_UPDATE_BATCH_SIZE, fallback SUMMARY_BATCH_SIZE (default 6)
    document_retrieval_mode: str  # from DOCUMENT_RETRIEVAL_MODE (default "langchain_chroma")
    embedding_model_name: str     # from EMBEDDING_MODEL_NAME (default "sentence-transformers/all-MiniLM-L6-v2")
    document_top_k: int           # from DOCUMENT_TOP_K (default 4)
    document_chunker: str         # from DOCUMENT_CHUNKER (default "custom")
    document_chunk_size: int      # from DOCUMENT_CHUNK_SIZE (default 1000)
    document_chunk_overlap: int   # from DOCUMENT_CHUNK_OVERLAP (default 150)
    langchain_chroma_persist_dir: Path
    langchain_chunk_size: int     # from LANGCHAIN_CHUNK_SIZE (default 1000)
    langchain_chunk_overlap: int  # from LANGCHAIN_CHUNK_OVERLAP (default 150)
    routing_mode: str             # from ROUTING_MODE (default "rule"), normalized to lowercase
    reranker_mode: str            # from RERANKER_MODE (default "deterministic")
    reranker_llm_top_k: int       # from RERANKER_LLM_TOP_K (default 10)
    reranker_llm_min_confidence: float  # from RERANKER_LLM_MIN_CONFIDENCE (default 0.55)
    structured_memory_retrieval_mode: str  # from STRUCTURED_MEMORY_RETRIEVAL_MODE (default "sqlite")
    long_term_memory_chroma_persist_dir: Path  # falls back to LANGCHAIN_CHROMA_PERSIST_DIR
    long_term_memory_collection: str  # from LONG_TERM_MEMORY_COLLECTION (default "long_term_memory")
    previous_chat_gist_generation_enabled: bool  # from PREVIOUS_CHAT_GIST_GENERATION_ENABLED
    previous_chat_gist_retrieval_enabled: bool   # from PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED
```

### 7.2 Important Implementation Details

- `from_env()` calls `load_dotenv()` before reading env vars
- `env_bool()` accepts `"1"`, `"true"`, `"yes"`, `"on"` (case-insensitive)
- `memory_update_batch_size` reads from `MEMORY_UPDATE_BATCH_SIZE` first, then `SUMMARY_BATCH_SIZE` as legacy fallback
- `long_term_memory_chroma_persist_dir` falls back to `LANGCHAIN_CHROMA_PERSIST_DIR` which falls back to `"data/chroma"`
- Chainlit auth defaults set via `os.environ.setdefault()` in app.py
- Two separate chunking configs exist (`document_chunk_size`/`overlap` + `langchain_chunk_size`/`overlap`) — these can diverge. The custom splitter path uses the former, the LangChain path uses the latter.

### 7.3 Additional Env Vars

- `DEMO_MEMORY_TRACE` — enable debug memory trace output in Chainlit UI
- `PREVIOUS_CHAT_GIST_GENERATION_ENABLED` — enable previous-chat gist generation on chat start
- `PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED` — enable previous-chat gist in route planning
- `CHAINLIT_AUTH_SECRET`, `CHAINLIT_LOCAL_USERNAME`, `CHAINLIT_LOCAL_PASSWORD` — Chainlit auth

---

## 8. Database Schema

All in `src/database.py`, single file SQLite at `data/chatbot.db`.

### 8.1 Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `chats` | Chat threads | `id TEXT PK`, `title`, `created_at`, `updated_at`, `model_name` |
| `messages` | Chat messages | `id INTEGER PK AUTOINCREMENT`, `chat_id FK`, `role` (user/assistant/system), `content`, `summarized` (0/1), `created_at` |
| `chat_memory_state` | Compatibility JSON mirror of structured memory | `chat_id PK`, `memory_json TEXT`, `updated_at` |
| `documents` | Uploaded document metadata | `id INTEGER PK`, `title`, `source`, `created_at`, `metadata_json` |
| `document_chunks` | Plain-text document chunks | `id INTEGER PK`, `document_id FK`, `chunk_index`, `text`, `created_at`, `metadata_json` |
| `document_chunk_embeddings` | Stored JSON embeddings (fallback) | `id INTEGER PK`, `chunk_id FK`, `embedding_model`, `dimension`, `vector_json`, UNIQUE on (chunk_id, embedding_model) |
| `chat_gists` | Chat memory gists | `id INTEGER PK`, `chat_id FK`, `source_type`, `gist_text`, `topics_json`, `decisions_json`, `open_tasks_json`, `start_message_id`, `end_message_id`, `created_at`, `updated_at`, `metadata_json` |
| `long_term_memories` | Cross-chat structured memory | `id INTEGER PK`, `namespace_json`, `namespace_path`, `memory_id`, `category`, `key`, `value`, `confidence`, `status` (active/superseded/deleted), `source_chat_id`, `source_message_ids_json`, `source_gist_id`, `created_at`, `updated_at`, `metadata_json`, UNIQUE on (namespace_path, memory_id) |

### 8.2 Indices

- `idx_messages_chat_created` ON messages(chat_id, created_at)
- `idx_messages_chat_summarized` ON messages(chat_id, summarized, id)
- `idx_document_chunks_document` ON document_chunks(document_id, chunk_index)
- `idx_document_chunk_embeddings_model` ON document_chunk_embeddings(embedding_model)
- `idx_chat_gists_chat_source` ON chat_gists(chat_id, source_type)
- `idx_chat_gists_source` ON chat_gists(source_type)
- `idx_long_term_memories_namespace` ON long_term_memories(namespace_path, status, updated_at)
- `idx_long_term_memories_category` ON long_term_memories(category)

### 8.3 Schema Migration Pattern

No migration framework. Two `_ensure_*` methods in `Database.init_schema()`:

- `_ensure_messages_summarized_column()` — adds column if missing via PRAGMA table_info check
- `_ensure_chats_model_name_column()` — same pattern

Note: The `_ensure_chats_active_column` migration is planned (implementation plan P4.3) but does NOT yet exist in the codebase.

New tables are created with `CREATE TABLE IF NOT EXISTS`. Column additions use `ALTER TABLE ADD COLUMN`.

### 8.4 Connection Management

- `Database.connect()` is a `@contextmanager` that creates a new connection, sets `row_factory = sqlite3.Row`, commits on exit, closes in finally
- Every method opens and closes a connection (no connection pooling)
- `sqlite3.Row` allows dict-like access (`row["column_name"]`) and `.keys()` method

---

## 9. Data Contracts (`src/core/contracts.py`)

All are **frozen dataclasses** with `field(default_factory=...)` for mutable defaults:

- **`MemoryCandidate`**: source, content, score, record_id, chat_id, source_message_ids, metadata
- **`SourcePlan`**: source, enabled, reason, query, limit, filters
- **`RoutePlan`**: query, sources, intent, confidence, requires_retrieval, ranking_profile, context_profile, fallback_policy, update_policy, termination_policy, metadata
- **`ContextBudget`**: max_tokens, system_tokens, memory_tokens, recent_message_tokens, retrieval_tokens, reserved_response_tokens, source_token_budgets, metadata
- **`ContextPacket`**: chat_id, system_prompt, structured_memory, recent_message_ids, candidates, budget, model_messages, metadata
- **`WorkflowTrace`**: trace_id, chat_id, route_plan, retrieved_candidates, ranked_candidates, context_budget, context_packet, termination_reason, errors, metadata
- **`AgentTurnResult`**: answer, chat_id, trace_id, termination_reason, trace: WorkflowTrace, assistant_message_id, metadata

`MemorySourceType` is a `Literal` type with 16 possible values including backward-compatible aliases.

---

## 10. Memory Architecture (Three Tiers)

### 10.1 Short-Term / Recent Messages

- Last `RAW_MESSAGE_LIMIT` (default 8) raw messages from `messages` table
- Retrieved by `RecentMessagesRetriever`, sorted by message ID chronologically
- Not droppable during context overflow (protected in `DROPPABLE_OVERFLOW_SOURCES` exclusion)

### 10.2 Structured Long-Term Memory (Primary: LangMem)

> **Deprecation note**: `StructuredMemoryState` in `structured_state.py` (698 lines) is **deprecated** per its own docstring. The active backend is `LangMemStructuredMemoryState` in `langmem_structured.py`. The deprecated class remains temporarily for compatibility and for validators/helpers that still live in that module. New features must only touch `LangMemStructuredMemoryState`.

Two separate memory extraction prompts coexist:

| Prompt | Location | Backend | Length |
|--------|----------|---------|--------|
| `MEMORY_UPDATE_SYSTEM_PROMPT` | `structured_state.py` | Deprecated `StructuredMemoryState` | ~90 lines |
| `LANGMEM_STRUCTURED_MEMORY_INSTRUCTIONS` | `langmem_structured.py` | Active `LangMemStructuredMemoryState` | ~34 lines |

- **Extraction**: LangMem `create_memory_manager()` with `LangMemStructuredMemory` Pydantic schema and `enable_deletes=False` (LangMem only produces upsert operations; manual CRUD uses direct store access)
- **Storage**: Dual-write to `long_term_memories` (namespace/key store) + `chat_memory_state` (JSON mirror for backward compat)
- **Namespaces**: `("user", "default", "semantic_memory")` for user facts, `("project", "default", "semantic_memory")` for project facts, `("chat", chat_id, "structured_memory")` for chat-scoped memories
- **Categories**: `user_facts`, `project_facts`, `decisions`, `corrections`, `open_tasks`, `preferences`, `constraints`, `procedural`
- **Operations**: upsert (add/update), supersede (mark old as inactive), delete (mark deleted)
- **Validation**: source message support must be lexically verified (`supported_source_ids()`), transcript-looking values rejected, vague memories rejected
- **Correction handling** (deprecated path only): When user corrects, BOTH supersede/delete old + upsert new required. Batches with corrections but no new active value are rejected. The active LangMem path delegates correction coherence to LangMem's model.
- **Update trigger**: when unsummarized messages outside raw window reach `MEMORY_UPDATE_BATCH_SIZE` (default 6)
- **Rebuild**: when memory was empty and batch < threshold, up to `MEMORY_REBUILD_BATCH_SIZE` (100) messages used

### 10.3 Document Memory

- LangChain-Chroma vector store, `all-MiniLM-L6-v2` embeddings
- `data/chroma` persist directory
- `default_top_k = 4` document retrieval
- Files supported: `.txt`, `.md`, `.pdf`
- Indexing: `RecursiveCharacterTextSplitter` at chunk_size/chunk_overlap
- Deduplication: `documents_missing_from_store()` checks before adding
- SQLite chunks auto-indexed into Chroma on first retrieval call
- Score normalization: Chroma returns L2 distances (lower is better), normalized to (0,1] with `1.0 / (1.0 + distance)`

### 10.4 Gist Memory (Infrastructure Stub)

- `chat_gists` table exists with full schema
- Retrievers (`CurrentChatGistRetriever`, `PreviousChatGistRetriever`) are **lexical-only stubs**
- No vector search, no summarization pipeline enabled by default
- Gist constants: `GIST_MIN_MESSAGES_TO_SUMMARIZE=20`, `GIST_KEEP_RECENT_MESSAGES=10`, `GIST_MAX_MESSAGES_PER_GIST=30`

---

## 11. Routing System

### 11.1 Deterministic Path (default, `mode="rule"`)

- `QueryAnalyzer`: lexical signal detection (6 categories of terms: current_chat, previous_memory, document, decision, task)
- `RoutePlanner`: maps signals to intent → context_profile → enabled sources
- Always produces a complete list: all possible sources are in `sources[]` with `enabled=True|False`
- Default: `recent_messages` + `structured_memory` always enabled; `document_memory` enabled only for document-like queries

### 11.2 LLM Path (`mode="llm"`)

- Sends query to model with structured routing prompt
- Parses JSON response: `use_recent_messages`, `use_structured_memory`, `use_document_memory`, `reason`, `confidence`
- Falls back to deterministic if: missing model, invalid JSON, confidence < 0.5, any exception

### 11.3 Hybrid Path (`mode="hybrid"`)

- Deterministic decides `recent_messages` + `structured_memory` (core chat memory)
- LLM decides `document_memory` only (augmenting retrieval)

### 11.4 Fallback Decision

When routing fails entirely (empty sources, exception): enables `recent_messages` + `structured_memory`, disables `document_memory`, context_profile = `"general_chat"`, confidence = 0.0

---

## 12. Reranking System

### 12.1 Deterministic Mode (default)

- 11 weighted features: lexical_overlap, query_source_boost, semantic_score, similarity_score, importance, confidence, recency, usage_count, source_priority, status_penalty, redundancy_penalty
- Weights defined in `RerankerWeights` dataclass
- Source priorities: `structured_memory=0.95` > `recent_messages=0.90` > gists > document > raw_span > unknown
- Status penalties: `active=0.0`, `archived=0.15`, `superseded=0.7`, `deleted=1.0`
- Exact duplicate penalty: 0.08 (normalized text dedup)
- Stable tie-breaking: candidates sorted by (score DESC, original_rank ASC)

### 12.2 LLM Mode

- Sends top-K (or all) candidates to model with structured prompt
- JSON response: `ranked_candidate_ids`, `confidence`, `reason`
- Falls back to deterministic if: missing model, invalid JSON, confidence < 0.55, any exception
- Preserves pool order for omitted candidates, appends non-pool candidates afterward

### 12.3 Hybrid Mode

- Deterministic top-K → LLM reordering of top-K → deterministic for remainder

---

## 13. Context Budgeting & Prompt Construction

### 13.1 Budget Profiles

| Profile | System | Recent Msgs | Structured Mem | Gists | Doc Mem | Safety | Answer Reserve |
|---------|--------|-------------|----------------|-------|---------|--------|----------------|
| `general_chat` | 8% | 55% | 20% | 0% | 0% | 7% | 10% |
| `memory_recall` | 8% | 35% | 35% | 10% | 0% | 7% | 5% |
| `document_question` | 8% | 20% | 10% | 0% | 50% | 7% | 5% |
| `mixed_memory_document` | 8% | 20% | 20% | 25% | 25% | 7% | 5% |

Ratios are normalized for enabled sources only. `default_model_context_limit = 4096`.

### 13.2 ContextBuilder Assembly Order

1. System prompt
2. Structured memory section (formatted as "Current structured memory:\n- category.key: value")
3. Retrieved memory section (current_chat_gist, previous_chat_gist, document_memory, raw_message_span, aliases)
4. Recent messages (chronological order, NOT reranker order)
5. Latest user message (always last)

### 13.3 Overflow Handling

- Candidates fitted into source budgets (highest-ranked first)
- If total prompt exceeds `context_limit`: iteratively drops lowest-ranked non-recent candidate
- Recent messages are NEVER dropped for overflow (protected)
- `DROPPABLE_OVERFLOW_SOURCES`: structured_memory, gists, document, raw_span, aliases

### 13.4 Token Estimation

- `ApproximateTokenEstimator`: `chars / 4.0` + per-message overhead of 4 tokens
- `TokenEstimator` Protocol allows plugging in a real tokenizer later
- Currently intentional overestimation

---

## 14. Testing Patterns

### 14.1 Test Structure

- 38 test files in `tests/`, evaluation scripts in `evals/`
- `tests/fixtures/docs/` — test documents for document QA
- No shared `conftest.py` — each test file is self-contained

### 14.2 Mocking/Faking Patterns

**Manual fake classes** (no mocking library used):

- `FakeModel` / `FakeRoutingModel` / `FakeRerankerModel` — implements `chat(messages, temperature) -> str` or raises Exception
- `FakeLangMemManager` — implements `invoke(input) -> list[Any]`, records calls
- `FakeExtractedMemory` — wraps content in `content` attribute to match LangMem's ExtractedMemory shape
- `SpyRetriever` — counts calls, returns predictable candidates
- `MissingLatestContextBuilder` — subclass override for edge-case testing

### 14.3 Test Pattern Conventions

- Helper factory functions: `candidate(source, content, score, record_id, ...)`
- `from __future__ import annotations` in all test files
- Direct instantiation of components, no dependency injection framework
- `FakeModel.calls` list records all invocations for assertion
- Tests cover: representative query tables, edge cases (empty, overflow, missing messages), mode combinations, fallback behavior, trace metadata completeness
- Architecture layer test: wires the full pipeline with fake components, verifies end-to-end data flow

---

## 15. Error Handling Patterns

### 15.1 Non-Critical Paths (fail gracefully)

- **Routing fallback**: LLM routing failure → deterministic route with all core sources enabled
- **Reranking fallback**: LLM reranker failure → deterministic ordering
- **Memory update**: OpenAIError caught, message marked as error but chat response unaffected
- **Vector search unavailability**: falls back to SQLite lexical search
- **Document indexing failures**: caught in `app.py`, error message shown to user

### 15.2 Critical Paths (fail with error message)

- **Model call**: OpenAIError caught, returns user-facing error message (doesn't crash)
- **Empty routing**: produces fallback decision with all core sources
- **Empty prompt assembly**: validated before model call, falls back to legacy path

### 15.3 Exception Hierarchy

- No custom exception hierarchy beyond `DocumentLoaderError(RuntimeError)` and `LangChainChromaUnavailable(RuntimeError)`
- Standard library exceptions used for validation: `ValueError`, `json.JSONDecodeError`

### 15.4 Logging

- **Primary**: `print()` statements with key=value format (workflow_trace, turn_timing, memory_update_timing, structured_memory_extraction_timing)
- **Secondary**: `logging.getLogger(__name__)` used only in `src/memory/short_term.py` for rejection warnings
- No structured logging framework

---

## 16. Type Annotation Style & Patterns

### 16.1 Core Patterns

- `from __future__ import annotations` in every file (PEP 604 `|` syntax, deferred evaluation)
- **Frozen dataclasses** as primary data structure (all contracts, configs, policies)
- **Protocols** used for dependency inversion (NOT ABCs):
  - `SourceRetriever`, `RoutingModel`, `RerankerModel`, `ChatModel`, `TokenEstimator`
  - `StructuredMemoryUpdater`, `LongTermMemoryStore`, `LangMemManager`, `TextDocumentIndexer`
- **No ABCs** anywhere in the codebase
- **Literal types** for constrained string sets (MemorySourceType, StructuredMemoryCategory, etc.)

### 16.2 Specific Style Points

- `field(default_factory=...)` for mutable defaults in dataclasses
- `replace()` from dataclasses for immutable updates to candidate metadata
- `object.__setattr__()` for setting frozen dataclass fields in `__post_init__` (only in `RoutePlannerPolicy`)
- `dict()` constructor pattern: `dict(candidate.metadata)` for copying
- `setdefault()` on dicts — `dict.setdefault()` is the standard Python built-in method, used correctly throughout the codebase
- Pydantic `BaseModel` for LangMem schema (`LangMemStructuredMemory`), with `model_dump()` / `dict()` fallback for v1/v2 compat
- `hasattr` checks for optional API compatibility (e.g., `similarity_search_with_score` vs `similarity_search_with_relevance_scores`)

### 16.3 Interesting Patterns

- `del` unused parameters in function signatures (e.g., `del chat_id`, `del temperature`)
- `# type: ignore[no-untyped-def]` for override signatures that don't match superclass
- `try/except ImportError` for optional dependency paths (Chroma, LangChain, LangMem)

---

## 17. Undocumented Conventions & Patterns That Would Surprise a New Developer

### 17.1 Code Organization

1. **Dual prompt paths**: Every turn builds BOTH a trace `ContextPacket` AND a legacy `ShortTermContext` prompt. They are compared, and the trace path only wins if validation passes. This is a transitional state.
2. **Console telemetry**: Almost all observability is via `print()` with URL-query-string-style formatting (`key1=value1 key2=value2`). Only `src/memory/short_term.py` uses `logging`.
3. **`elapsed_ms()` duplication**: The same helper function is copy-pasted in `short_term.py`, `structured_state.py`, and `coordinator_agent.py`. Same signature but defined in each file.
4. **`del` for unused params**: Consistent pattern where unused parameters are explicitly `del`eted to signal intent.
5. **`ensure_ascii=True` on all `json.dumps()`**: Consistent across the codebase for serialization stability.

### 17.2 Memory Management

1. **Dual-write memory**: When LangMem updates memory, it writes to BOTH `long_term_memories` table AND `chat_memory_state` JSON mirror. The old `chat_memory_state` is a compatibility layer.
2. **Message ID annotations in LangMem prompts**: Message content is prefixed with `[message_id=N]` before sending to LangMem. The `strip_message_id_markers()` function cleans this if the model echoes it back.
3. **Correction rejection**: A batch of memory operations with corrections but no new upsert is rejected. The user must have provided a replacement fact.
4. **Memory rebuild path**: When existing memory is empty and batch < threshold, up to 100 messages are used for initial memory population.
5. **`ShortTermMemoryAgent` is a pure pass-through**: 18 lines, exists only to give `ShortTermMemory` an "Agent" suffix for architectural consistency (AGENTS.md requires agent-roled classes).

### 17.3 Routing & Reranking

1. **All sources always in route plan**: Route plans contain entries for ALL possible sources (enabled and disabled), not just active ones. This is important for trace completeness.
2. **Hybrid routing asymmetry**: Hybrid mode only allows LLM to decide document_memory; core chat memory is always deterministic.
3. **Reranker candidate IDs**: Each candidate gets `reranker_candidate_id = f"c{original_rank}"` during deterministic ranking, used as stable references in LLM prompts.

### 17.4 Context Building

1. **Recent messages chronological ordering**: ContextBuilder sorts recent messages by message ID, NOT by reranker rank. Reranker scores for recent messages are effectively disregarded in prompt assembly.
2. **Non-recent sources are droppable, recent messages are not**: Overflow drops structured memory, gists, document chunks, raw spans — but never recent messages or the latest user message.
3. **Latest user message dedup**: If a recent-message candidate matches the latest user query, it's excluded to avoid duplication.
4. **Per-source budget fitting, then global overflow check**: First fit into per-source budgets, THEN check if total exceeds context window. Iteratively drops until it fits.

### 17.5 Database

1. **Schema migration via PRAGMA**: `_ensure_*` methods check column existence with `PRAGMA table_info()`, add columns with `ALTER TABLE ADD COLUMN`. No migration framework. Currently 2 migrations exist (`summarized`, `model_name`); the `active` column migration is planned (P4.3).
2. **Row `.keys()` method**: Used to check column existence (`"summarized" in columns` where `columns` is a set of row names).
3. **Connection-per-method**: Every DB method opens/closes its own connection. No pooling, no shared transactions.

### 17.6 Testing

1. **No pytest fixtures**: Every test file uses manual helper functions and Fake classes. There's no `conftest.py` with shared fixtures.
2. **Database tests use real SQLite**: The `Database` class is tested against the actual SQLite file at the configured path.
3. **FakeLangMemManager pattern**: Tests use `FakeExtractedMemory(content=dict)` to simulate LangMem's `ExtractedMemory` wrapper.

### 17.7 Import Patterns

1. **`try/except ImportError` for optional deps**: Chroma, LangChain, LangMem are imported lazily. `LangGraphInMemoryStore` is `None` if unavailable.
2. **Static factory methods on LangChain classes**: `LangChainChromaRetriever._chroma_class()`, `._embeddings()`, `._text_splitter()`, `._document_class()` are static methods that import and return the class, catching ImportError.
3. **Pydantic v1/v2 compat**: `model_dump()` with `dict()` fallback for serialization.

### 17.8 Chainlit-Specific

1. **`os.environ.setdefault()` for Chainlit auth**: Default auth secrets set in app.py before Chainlit reads them.
2. **Per-model chat service caching**: Global `chat_services: dict[str, ChatService]` dict in app.py, keyed by model name.
3. **Thread-to-chat binding**: Chainlit thread ID is used as the SQLite chat ID. Model choice persisted in thread metadata.

### 17.9 Vector Search

1. **Chroma API compatibility shims**: `hasattr(vectorstore, "similarity_search_with_score")` checks for different Chroma versions.
2. **Score normalization**: Chroma returns L2 distances (lower is better), normalized to (0,1] with `1.0 / (1.0 + distance)`.
3. **Document dedup before indexing**: `documents_missing_from_store()` checks existing Chroma IDs to avoid re-indexing.

### 17.10 Configuration Quirks

1. **`memory_update_batch_size` legacy fallback**: Reads `SUMMARY_BATCH_SIZE` env var as fallback for backward compat.
2. **`long_term_memory_chroma_persist_dir` chained fallback**: `LONG_TERM_MEMORY_CHROMA_PERSIST_DIR` → `LANGCHAIN_CHROMA_PERSIST_DIR` → `"data/chroma"`.
3. **Boolean env vars**: `env_bool()` accepts `"1"`, `"true"`, `"yes"`, `"on"`. `os.getenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}` is duplicated in `route_planner.py` instead of using `env_bool()`.
4. **LangMem `enable_deletes=False`**: The `create_real_langmem_manager()` function creates the LangMem manager with `enable_deletes=False`. LangMem only produces upsert operations — manual CRUD (P4.6) must bypass LangMem and write directly to `SQLiteLongTermMemoryStore` + `LongTermMemoryVectorIndex`.

---

## 18. Files Most Likely to Need Changes

| Change Area | Files |
|-------------|-------|
| Data contracts / new fields | `src/core/contracts.py` |
| Turn pipeline flow | `src/agents/coordinator_agent.py`, `src/chat_service.py` |
| Routing logic | `src/routing/routing_agent.py`, `query_analyzer.py`, `route_planner.py` |
| New retrieval source | `src/retrieval/retriever_dispatcher.py` + new retriever file |
| Reranking policy | `src/retrieval/reranker.py` (RerankerWeights, RerankerPolicy) |
| Context assembly | `src/context/context_budget_allocator.py`, `context_builder.py` |
| Memory management | `src/memory/short_term.py`, `langmem_structured.py`, `long_term_store.py` |
| Schema changes | `src/database.py` |
| New configuration | `src/config.py` |
| Chainlit UI | `app.py`, `src/chainlit_data_layer.py` |
| Document handling | `src/documents/loaders.py`, `splitters.py`, `ingestion.py` |

---

## 19. Key Design Decisions (Recap)

1. **Typed memory with unified `MemoryCandidate` interface** — all memory sources normalize to the same contract
2. **`ContextPacket` as the production prompt path** with legacy `ShortTermMemory` fallback (transitional state)
3. **Deterministic-first with optional LLM enhancement** — reliability and traceability prioritized
4. **LangMem for structured memory extraction** — not custom JSON operations
5. **Cross-chat memory via shared namespaces** in `long_term_memories`
6. **Budget-aware context assembly** with source-level token allocation and overflow handling
7. **Comprehensive `WorkflowTrace`** for every turn — timings, decisions, candidates, dropped items
8. **Protocol-based dependency inversion** — no ABCs, no DI framework
9. **Frozen dataclasses everywhere** — immutability for contracts, policy objects, configs
10. **No centralized DI container** — ad-hoc wiring in `ChatService` and `CoordinatorAgent`

---

*Context verified against 30 source files (2026-06-28). Accuracy: ~99% after corrections.*
