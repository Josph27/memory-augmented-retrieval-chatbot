# Codebase Reconnaissance: memory-augmented-retrieval-chatbot

## 1. Project Overview

This is a **TUM practical-course project**: a **multi-agent typed-memory RAG chatbot** with a Chainlit browser UI. The system combines:

- **SQLite-backed chat/message persistence**
- **Structured typed long-term memory** (LangMem-backed, stored in `long_term_memories` + compatibility `chat_memory_state`)
- **Document RAG** via LangChain-Chroma vector retrieval
- **Deterministic routing, reranking, context budgeting, and prompt assembly**
- **Multi-agent architecture** at the responsibility/decision level, with deterministic components for reliability

## 2. Tech Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.10+ (`.python-version` = 3.12) |
| **Package Manager** | `uv` + `pyproject.toml` (authoritative); `requirements.txt` (fallback) |
| **Chat UI** | Chainlit 2.x (`app.py` entrypoint) |
| **LLM Client** | OpenAI-compatible (`openai` library) → any `/v1/chat/completions` endpoint |
| **Structured Memory** | LangMem (`langmem>=0.0.30`) for typed semantic memory extraction |
| **Document Retrieval** | LangChain-Chroma (`langchain-chroma`) + HuggingFace embeddings |
| **Database** | SQLite (single file `data/chatbot.db`) |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` |
| **Testing** | pytest 8.x |
| **Linting** | ruff 0.8.x (line-length=100, target py310) |
| **Containerization** | Docker (`python:3.12-slim`) |

## 3. Project Directory Structure

```text
/workspace/
├── app.py                          # Chainlit entrypoint (auth, chat profiles, uploads, UI hooks)
├── pyproject.toml                  # Project metadata + dependencies (uv)
├── requirements.txt                # Minimal pip fallback
├── Dockerfile                      # Container deployment
├── .chainlit/config.toml           # Chainlit UI configuration
├── .env / .env.example             # Environment variables (ignored by git)
│
├── src/                            # Main application source (51 Python files)
│   ├── config.py                   # AppConfig dataclass (all env-var loading)
│   ├── database.py                 # SQLite adapter (chats, messages, documents, chat_gists, long_term_memories)
│   ├── model_wrapper.py            # ModelWrapper: thin OpenAI-compatible client
│   ├── chat_service.py             # ChatService: top-level orchestration factory
│   ├── chainlit_data_layer.py      # SQLiteChainlitDataLayer: Chainlit history adapter
│   │
│   ├── core/
│   │   └── contracts.py            # Core data contracts (MemoryCandidate, ContextPacket, RoutePlan, WorkflowTrace, etc.)
│   │
│   ├── agents/                     # Agent wrappers (responsibility boundaries)
│   │   ├── coordinator_agent.py    # CoordinatorAgent: main turn pipeline
│   │   ├── chat_agent.py           # ChatAgent: thin ModelWrapper adapter
│   │   ├── short_term_memory_agent.py  # ShortTermMemoryAgent adapter
│   │   ├── context_builder_agent.py    # ContextBuilderAgent: legacy prompt assembly adapter
│   │   ├── context_manager_agent.py    # ContextManagerAgent: budget + ContextPacket builder
│   │   └── document_ingestion_agent.py # DocumentIngestionAgent: file loading/indexing
│   │
│   ├── routing/                    # Query analysis and route planning
│   │   ├── query_analyzer.py       # QueryAnalyzer: lexical signal detection (deterministic)
│   │   ├── route_planner.py        # RoutePlanner: deterministic source-plan building
│   │   └── routing_agent.py        # RoutingAgent: rule/llm/hybrid modes with fallback
│   │
│   ├── retrieval/                  # Retrieval dispatcher + per-source retrievers
│   │   ├── retriever_dispatcher.py # RetrieverDispatcher: dispatch to enabled sources
│   │   ├── recent_messages_retriever.py     # Recent raw messages from current chat
│   │   ├── structured_memory_retriever.py   # Structured memories (sqlite/vector/hybrid)
│   │   ├── langchain_chroma_retriever.py    # LangChain-Chroma document retrieval
│   │   ├── current_chat_gist_retriever.py   # Current-chat gist stub (lexical only)
│   │   ├── previous_chat_gist_retriever.py  # Previous-chat gist stub (lexical only)
│   │   ├── raw_message_span_retriever.py    # Raw message span drill-down
│   │   └── reranker.py                     # MemoryReranker: deterministic/llm/hybrid
│   │
│   ├── context/                    # Context budgeting and prompt assembly
│   │   ├── context_budget_allocator.py  # Profile-based token budget allocation
│   │   ├── context_builder.py           # ContextBuilder: ContextPacket construction
│   │   ├── context_comparator.py        # ContextComparator: legacy vs. trace prompt diff
│   │   ├── prompt_messages.py           # ContextPacket→model messages validation
│   │   └── token_estimator.py           # ApproximateTokenEstimator (chars/4)
│   │
│   ├── memory/                     # Memory management
│   │   ├── short_term.py           # ShortTermMemory: build context + trigger updates
│   │   ├── structured_state.py     # Memory operations, validation, compat layer
│   │   ├── langmem_structured.py   # LangMem backend (primary structured memory path)
│   │   ├── long_term_store.py      # SQLiteLongTermMemoryStore: namespace/key store
│   │   ├── long_term_vector_index.py  # Chroma-based vector index for long-term memory
│   │   ├── chat_gist_summarizer.py    # Chat gist generation
│   │   ├── previous_chat_gist.py       # Previous-chat gist generation orchestration
│   │   ├── memory_trace.py            # Demo memory trace formatting (debug UI)
│   │   └── constants.py               # Raw message limit, batch sizes, gist limits
│   │
│   └── documents/                  # Document loading & ingestion
│       ├── loaders.py              # File loaders (.txt, .md, .pdf)
│       ├── splitters.py            # Custom paragraph splitter + LangChain adapter
│       ├── ingestion.py            # DocumentIngestionService (SQLite chunks)
│       └── inspection.py           # Document inspection utilities
│
├── tests/                          # Unit + integration tests (60+ test files)
│   ├── test_architecture_layers.py
│   ├── test_context_builder.py
│   ├── test_context_manager_agent.py
│   ├── test_document_*.py          # Document QA, loaders, memory, inspection
│   ├── test_langmem_structured_memory.py
│   ├── test_long_term_memory_vector_retrieval.py
│   ├── test_memory_reranker.py
│   ├── test_routing_agent.py
│   ├── test_structured_memory_eval.py
│   └── ... (many more)
│
├── evals/                          # Evaluation scripts
│   ├── document_qa/                # Document retrieval + answer quality + RAGAS evals
│   ├── structured_memory/          # Cross-chat structured memory evaluations
│   ├── e2e_scenarios/              # End-to-end scenario evaluations
│   ├── generated_answer/           # Generated answer quality evaluations
│   └── multi_source_retrieval/     # Multi-source retrieval evaluations
│
├── scripts/                        # Operational scripts
│   ├── index_document_file.py      # CLI to index a document into Chroma
│   ├── inspect_long_term_memory.py # Inspect long-term memory store
│   ├── rebuild_long_term_memory_index.py
│   ├── verify_natural_long_term_memory_flow.py  # Cross-chat memory verification
│   └── ...
│
├── docs/                           # Design docs
│   ├── AGENT_CONTRACTS.md
│   ├── ARCHITECTURE_DECISION.md
│   ├── PROJECT_CONTEXT.md
│   ├── IMPLEMENTATION_PLAN_2W.md
│   └── EVALUATION_PLAN.md
│
├── data/                           # Runtime data (gitignored)
│   ├── chatbot.db                  # SQLite database
│   └── chroma/                     # Chroma vector store persist dir
│
└── chainlit/                       # Chainlit framework source (vendored? or submodule)
```

## 4. Core Architecture

### 4.1 Turn Pipeline (CoordinatorAgent.run_turn)

```text
User message
  → RoutingAgent.route(query)           → RoutePlan (which sources enabled)
  → database.save_message(user)         → user_message_id
  → RetrieverDispatcher.retrieve()      → MemoryCandidate[] (from enabled sources)
  → MemoryReranker.rank_with_trace()    → Ranked MemoryCandidate[]
  → ContextManagerAgent.build_context_packet()  → ContextBudget + ContextPacket
  → ShortTermMemoryAgent.build_context() → legacy prompt messages (fallback)
  → ContextComparator.compare()         → diff legacy vs. trace packet
  → prompt_messages validation          → validated model messages
  → ChatAgent.generate()                → assistant response
  → database.save_message(assistant)    → assistant_message_id
  → ShortTermMemoryAgent.update_memory_if_needed()  → structured memory update
  → AgentTurnResult (with WorkflowTrace)
```

### 4.2 Data Contracts (src/core/contracts.py)

Key types that define the entire system:

- **`MemoryCandidate`**: One candidate memory item (`source`, `content`, `score`, `record_id`, `chat_id`, `source_message_ids`, `metadata`)
- **`SourcePlan`**: Per-source routing instruction (`source`, `enabled`, `reason`, `query`, `limit`, `filters`)
- **`RoutePlan`**: Routing decision (`query`, `sources: list[SourcePlan]`, `intent`, `confidence`, `requires_retrieval`, `ranking_profile`, `context_profile`, `fallback_policy`, `update_policy`, `termination_policy`, `metadata`)
- **`ContextBudget`**: Token allocation across sources (`max_tokens`, `system_tokens`, `memory_tokens`, `recent_message_tokens`, `retrieval_tokens`, `reserved_response_tokens`, `source_token_budgets: dict[str, int]`, `metadata`)
- **`ContextPacket`**: Assembled context for a model call (`chat_id`, `system_prompt`, `structured_memory`, `recent_message_ids`, `candidates`, `budget`, `model_messages`, `metadata`)
- **`WorkflowTrace`**: Full trace of a turn (`trace_id`, `chat_id`, `route_plan`, `retrieved_candidates`, `ranked_candidates`, `context_budget`, `context_packet`, `termination_reason`, `errors`, `metadata`)
- **`AgentTurnResult`**: Final result (`answer`, `chat_id`, `trace_id`, `termination_reason`, `trace: WorkflowTrace`, `assistant_message_id`, `metadata`)

### 4.3 Memory Architecture

Three tiers of memory:

1. **Short-term / Recent Messages**: Latest N raw messages (default `RAW_MESSAGE_LIMIT=8`) stored in `messages` table
2. **Structured Long-Term Memory**: Typed memories via LangMem, stored in `long_term_memories` namespace/key store + `chat_memory_state` compatibility mirror. Categories: `user_facts`, `project_facts`, `decisions`, `corrections`, `open_tasks`, `preferences`, `constraints`, `procedural`
3. **Document Memory**: LangChain-Chroma vector store for uploaded documents

Memory update policy: When unsummarized messages outside the raw window reach `MEMORY_UPDATE_BATCH_SIZE=6`, LangMem extracts structured operations (upsert/supersede/delete). Messages are marked `summarized=1`. Memory is cross-chat via shared namespaces `("user", "default", "semantic_memory")` and `("project", "default", "semantic_memory")`.

### 4.4 Routing Modes

- **`rule`** (default): `QueryAnalyzer` detects lexical signals → `RoutePlanner` builds `RoutePlan`
- **`llm`**: LLM decides which sources to enable; falls back to `rule` on invalid/uncertain output
- **`hybrid`**: LLM decides document memory; rule decides core chat memory

### 4.5 Reranking Modes

- **`deterministic`** (default): Weighted feature scoring (lexical overlap, source priority, recency, confidence, redundancy)
- **`llm`**: LLM ranks candidates via structured JSON
- **`hybrid`**: Top-K deterministic + LLM reordering

Both LLM-based routing and reranking have fallback to deterministic behavior on failure.

### 4.6 Context Budgeting

Profile-based token allocation via `ContextBudgetAllocator`:

- **`general_chat`**: 55% recent messages, 20% structured memory, 8% system
- **`memory_recall`**: 35% each recent + structured memory
- **`document_question`**: 50% document memory, 20% recent messages
- **`mixed_memory_document`**: balanced across sources

`ContextBuilder` fits candidates into source budgets and handles overflow by dropping lowest-ranked non-recent candidates.

### 4.7 Retrieval Sources

| Source | Default | Retriever | Backend |
|--------|---------|-----------|---------|
| `recent_messages` | ENABLED | `RecentMessagesRetriever` | SQLite `messages` |
| `structured_memory` | ENABLED | `StructuredMemoryRetriever` | `long_term_memories` + `chat_memory_state` fallback |
| `document_memory` | DISABLED* | `LangChainChromaRetriever` | Chroma vector store |
| `current_chat_gist` | DISABLED | `CurrentChatGistRetriever` | SQLite `chat_gists` (lexical stub) |
| `previous_chat_gist` | DISABLED | `PreviousChatGistRetriever` | SQLite `chat_gists` (lexical stub) |
| `raw_message_span` | DISABLED | `RawMessageSpanRetriever` | SQLite `messages` by span |

\* `document_memory` auto-enabled when query signals detect document-like terms.

## 5. Database Schema (SQLite)

Tables: `chats`, `messages`, `chat_memory_state`, `documents`, `document_chunks`, `document_chunk_embeddings`, `chat_gists`, `long_term_memories`

Key relationships:

- `chats` 1→N `messages` (cascading delete). Messages have `role`, `content`, `summarized` flag, `created_at`
- `chats` 1→1 `chat_memory_state` (structured memory JSON cache with `memory_json`, `updated_at`)
- `documents` 1→N `document_chunks` → `document_chunk_embeddings` (SQLite fallback path; chunks have `chunk_index`, `text`; embeddings store `embedding_model`, `dimension`, `vector_json`)
- `chats` 1→N `chat_gists` (typed by `source_type`). Gists carry `gist_text`, `topics_json`, `decisions_json`, `open_tasks_json`, `start_message_id`, `end_message_id`, `updated_at`
- `long_term_memories`: cross-chat namespace/key store with fields `namespace_json`, `namespace_path`, `memory_id`, `category`, `key`, `value`, `confidence`, `status`, `source_chat_id`, `source_message_ids_json`, `source_gist_id`, `created_at`, `updated_at`
- Indices: `idx_messages_chat_created`, `idx_messages_chat_summarized`, `idx_document_chunks_document`, `idx_chat_gists_chat_source`, `idx_chat_gists_source`, `idx_long_term_memories_namespace`, `idx_long_term_memories_category`

## 6. Entry Points

1. **`app.py`** - Chainlit chat UI (primary entry point): `chainlit run app.py -w`
2. **`scripts/index_document_file.py`** - CLI document indexing
3. **`scripts/verify_natural_long_term_memory_flow.py`** - Cross-chat memory verification
4. **`evals/`** - Evaluation scripts for document QA, structured memory, e2e, etc.
5. **Docker**: `docker run ... memory-chatbot` (exposes port 8000)

## 7. Key Configuration (Environment Variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | `dummy` | LLM API key |
| `OPENAI_BASE_URL` | `http://localhost:11434/v1` | LLM endpoint |
| `MODEL_NAME` | `google/gemma-4-31B-it` | Default chat model |
| `DATABASE_PATH` | `data/chatbot.db` | SQLite database location |
| `RAW_MESSAGE_LIMIT` | `8` | Recent messages kept raw |
| `MEMORY_UPDATE_BATCH_SIZE` | `6` | Messages needed to trigger memory update (also reads legacy `SUMMARY_BATCH_SIZE`) |
| `ROUTING_MODE` | `rule` | Routing strategy (`rule`/`llm`/`hybrid`) |
| `RERANKER_MODE` | `deterministic` | Reranking strategy |
| `RERANKER_LLM_TOP_K` | `10` | Top-K candidates passed to LLM reranker |
| `RERANKER_LLM_MIN_CONFIDENCE` | `0.55` | Min confidence threshold for LLM reranker output |
| `DOCUMENT_RETRIEVAL_MODE` | `langchain_chroma` | Document backend |
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `DOCUMENT_TOP_K` | `4` | Documents to retrieve |
| `DOCUMENT_CHUNKER` | `custom` | Chunker strategy (`custom`/`langchain`) |
| `DOCUMENT_CHUNK_SIZE` | `1000` | Custom chunker chunk size |
| `DOCUMENT_CHUNK_OVERLAP` | `150` | Custom chunker overlap |
| `LANGCHAIN_CHROMA_PERSIST_DIR` | `data/chroma` | Chroma persist directory |
| `LANGCHAIN_CHUNK_SIZE` | `1000` | LangChain chunker chunk size |
| `LANGCHAIN_CHUNK_OVERLAP` | `150` | LangChain chunker overlap |
| `STRUCTURED_MEMORY_RETRIEVAL_MODE` | `sqlite` | Structured memory retrieval mode (`sqlite`/`vector`/`hybrid`) |
| `LONG_TERM_MEMORY_CHROMA_PERSIST_DIR` | `data/chroma` | Chroma persist dir for long-term memory vector index |
| `LONG_TERM_MEMORY_COLLECTION` | `long_term_memory` | Chroma collection for long-term memory |
| `PREVIOUS_CHAT_GIST_GENERATION_ENABLED` | `false` | Enable previous-chat gist generation |
| `PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED` | `false` | Enable previous-chat gist retrieval |
| `DEMO_MEMORY_TRACE` | disabled | Enable memory trace in UI |

Chainlit auth: `CHAINLIT_AUTH_SECRET`, `CHAINLIT_LOCAL_USERNAME`, `CHAINLIT_LOCAL_PASSWORD`

## 8. Agent Roles (per AGENTS.md)

| Agent | Implementation | Status |
|-------|---------------|--------|
| `CoordinatorAgent` | `src/agents/coordinator_agent.py` | **Implemented** |
| `RoutingAgent` | `src/routing/routing_agent.py` | **Implemented** (rule/llm/hybrid) |
| `DocumentIngestionAgent` | `src/agents/document_ingestion_agent.py` | **Implemented** |
| `DocumentRetrievalAgent` | `src/retrieval/langchain_chroma_retriever.py` | **Implemented** (via `LangChainChromaRetriever`) |
| `StructuredMemoryAgent` | `src/retrieval/structured_memory_retriever.py` | **Implemented** (via `StructuredMemoryRetriever`) |
| `MemoryManagerAgent` | `src/memory/langmem_structured.py` + `short_term.py` | **Implemented** (LangMem-backed) |
| `RerankerAgent` | `src/retrieval/reranker.py` | **Implemented** (deterministic/llm/hybrid) |
| `ContextManagerAgent` | `src/agents/context_manager_agent.py` | **Implemented** |
| `AnswerAgent` | `src/agents/chat_agent.py` | **Implemented** (via `ChatAgent`) |

## 9. Deterministic vs. LLM Components

**Deterministic** (no LLM calls):

- `QueryAnalyzer` - lexical signal detection
- `RoutePlanner` - source plan construction
- `MemoryReranker` (deterministic mode) - weighted feature scoring
- `ContextBudgetAllocator` - profile-based token allocation
- `ContextBuilder` - budget-fitting ContextPacket construction
- `ApproximateTokenEstimator` - chars/4 token estimation
- `ContextComparator` - prompt shape comparison
- `prompt_messages` validation
- All retrievers (except LLM-backed modes)
- Document loading, chunking, embedding, SQLite access, Chroma access

**LLM-backed** (with deterministic fallback):

- `RoutingAgent` (llm/hybrid modes) → falls back to `rule`
- `MemoryReranker` (llm/hybrid modes) → falls back to `deterministic`
- `ChatAgent.generate()` - final answer generation
- `StructuredMemoryState` / `LangMemStructuredMemoryState` - memory extraction

## 10. Evaluation Infrastructure

- **Document QA**: SQuAD/NQ subsets, retrieval metrics, RAGAS export, top-K curves
- **Structured Memory**: Cross-chat memory extraction quality metrics
- **E2E Scenarios**: Full pipeline scenario tests
- **Generated Answer**: Answer quality evaluation
- **Multi-source Retrieval**: Combined retrieval evaluation
- **60+ test files**: Unit + integration tests covering architecture layers, retrievers, memory, context, routing, reranking

## 11. Key Design Decisions

1. **Typed memory with unified `MemoryCandidate` interface**: All memory sources normalize to the same contract
2. **`ContextPacket` as the production prompt path** with legacy `ShortTermMemory` fallback
3. **Deterministic-first with optional LLM enhancement**: Reliability and traceability prioritized
4. **LangMem for structured memory extraction** (not custom JSON operations)
5. **Cross-chat memory via shared namespaces** in `long_term_memories`
6. **Budget-aware context assembly** with source-level token allocation
7. **Comprehensive `WorkflowTrace`** for every turn (timings, decisions, candidates)

## 12. Files Most Likely to Need Changes

For most feature work or bug fixes, these are the key touch points:

1. **`src/core/contracts.py`** - If data structures need to change
2. **`src/agents/coordinator_agent.py`** - If the turn pipeline needs adjustment
3. **`src/routing/routing_agent.py`** + **`route_planner.py`** + **`query_analyzer.py`** - Routing logic
4. **`src/retrieval/retriever_dispatcher.py`** - Adding/removing retrieval sources
5. **`src/retrieval/reranker.py`** - Reranking policy changes
6. **`src/context/context_budget_allocator.py`** + **`context_builder.py`** - Context assembly changes
7. **`src/memory/short_term.py`** + **`langmem_structured.py`** - Memory management changes
8. **`src/database.py`** - Schema changes
9. **`src/config.py`** - New configuration options
