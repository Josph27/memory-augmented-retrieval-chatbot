# Reference

> Information-oriented. Configuration defaults match `src/settings.py` (canonical source of truth). Links to explanation in `ARCHITECTURE.md`.

## Core Types

All types from `src/core/contracts.py`. Frozen dataclasses — immutable by design.

### `MemorySourceType`

Literal union of known memory-source identifiers:

| Value | Meaning | Storage |
|---|---|---|
| `recent_messages` | newest same-chat raw messages | SQLite `messages` |
| `structured_memory` | durable facts, preferences, decisions, corrections, tasks, constraints — 10 categories with TTL | SQLite `long_term_memories` + sqlite-vec vector index (`vec_memories` table) |
| `document_memory` | uploaded document chunks | Chroma |
| `current_chat_gist` | active-chat lossy orientation scaffold | SQLite `chat_gists` |
| `current_chat_span` | older exact evidence from the active chat | SQLite `messages` (via span extraction) |
| `previous_chat_gist` | lossy orientation for ended chats | SQLite `chat_gists` |
| `raw_message_span` | exact transcript evidence — gist expansion or direct retrieval | SQLite `messages` |
| `current_chat_chunks` | legacy alias for `current_chat_gist` | — |
| `previous_chat_memory` | legacy alias for `previous_chat_gist` | — |
| `short_term` | legacy alias | — |
| `long_term` | legacy alias | — |
| `document` | legacy alias for `document_memory` | — |
| `raw_messages` | legacy alias | — |
| `unknown` | unrecognized source | — |

### `SourcePlan`

Planned source for context retrieval.

| Field | Type | Description |
|---|---|---|
| `source` | `MemorySourceType` | Which memory source |
| `enabled` | `bool` | Whether this source should be queried (default `True`) |
| `reason` | `str \| None` | Why enabled/disabled |
| `query` | `str \| None` | Retrieval query for this source |
| `limit` | `int \| None` | Max candidates from this source |
| `filters` | `dict` | Source-specific filters |

### `RoutePlan`

Routing decision for one user turn. Produced by `RoutingAgent.route()` (returns `RoutingDecision`). See `RoutingDecision.to_trace_dict()` for the trace payload.

| Field | Type | Description |
|---|---|---|
| `query` | `str` | User's original query |
| `sources` | `list[SourcePlan]` | Which sources to query, in priority order |
| `intent` | `str \| None` | Classified intent |
| `confidence` | `float \| None` | Routing confidence |
| `requires_retrieval` | `bool \| None` | Whether retrieval is needed at all |
| `ranking_profile` | `str \| None` | Which ranking profile to use |
| `context_profile` | `str \| None` | Which context/budget profile: `general_chat`, `memory_recall`, `document_question`, `global_summary` |
| `fallback_policy` | `str \| None` | Fallback behavior |
| `update_policy` | `str \| None` | Memory update policy |
| `termination_policy` | `str \| None` | When to stop |
| `metadata` | `dict` | Extra routing metadata |

### `MemoryCandidate`

One candidate memory/context item — the universal normalization shape. All retrievers produce this.

| Field | Type | Description |
|---|---|---|
| `source` | `MemorySourceType` | Which source produced this candidate |
| `content` | `str` | The actual text |
| `score` | `float \| None` | Relevance/quality score |
| `record_id` | `str \| int \| None` | Source-specific record identifier |
| `chat_id` | `str \| None` | Which chat the candidate came from |
| `source_message_ids` | `list[int]` | Provenance — which SQLite message IDs |
| `metadata` | `dict` | Extra source-specific data |

### `ContextBudget`

Token budget allocation for context construction. Produced by `ContextBudgetAllocator`.

| Field | Type | Description |
|---|---|---|
| `max_tokens` | `int \| None` | Total token budget |
| `system_tokens` | `int \| None` | Budget for system prompt |
| `memory_tokens` | `int \| None` | Budget for structured memory |
| `recent_message_tokens` | `int \| None` | Budget for recent messages |
| `retrieval_tokens` | `int \| None` | Budget for retrieved candidates |
| `reserved_response_tokens` | `int \| None` | Budget reserved for model response |
| `source_token_budgets` | `dict[str, int]` | Per-source breakdown |
| `metadata` | `dict` | Allocation metadata |

### `ContextPacket`

Single authoritative context assembly for one model call. Produced by `ContextManagerAgent`.

| Field | Type | Description |
|---|---|---|
| `chat_id` | `str` | Which chat |
| `system_prompt` | `str \| None` | Base system prompt |
| `structured_memory` | `str \| None` | Formatted active structured memories (merged into system message) |
| `recent_message_ids` | `list[int]` | Selected recent message IDs |
| `candidates` | `list[MemoryCandidate]` | All selected memory candidates |
| `budget` | `ContextBudget \| None` | Budget used for this packet |
| `model_messages` | `list[dict]` | Ready-to-use chat-completions messages |
| `metadata` | `dict` | Token accounting, drops, source usage |

### `WorkflowTrace`

Full turn trace for observability. Captures every stage of the pipeline.

| Field | Type | Description |
|---|---|---|
| `trace_id` | `str` | Unique trace identifier |
| `chat_id` | `str` | Which chat |
| `route_plan` | `RoutePlan \| None` | Routing decision |
| `retrieved_candidates` | `list[MemoryCandidate]` | Pre-reranking candidates |
| `ranked_candidates` | `list[MemoryCandidate]` | Post-reranking candidates |
| `context_budget` | `ContextBudget \| None` | Budget allocation |
| `context_packet` | `ContextPacket \| None` | Final context |
| `termination_reason` | `str \| None` | Why the turn ended |
| `errors` | `list[str]` | Collected error messages |
| `metadata` | `dict` | Timing, candidate counts, comparison data |

### `OrchestrationResult`

Context and trace from one orchestration implementation (Native or LangGraph).

| Field | Type | Description |
|---|---|---|
| `context_packet` | `ContextPacket` | The assembled context |
| `trace` | `WorkflowTrace` | Full trace |
| `mode` | `str` | `"native"`, `"langgraph_shadow"`, or `"langgraph_demo"` |
| `fallback_used` | `bool` | Whether fallback was activated |
| `error` | `str \| None` | Orchestration error if any |

### `AgentTurnResult`

Final result for one user turn. Produced by `CoordinatorAgent.run_turn()`.

| Field | Type | Description |
|---|---|---|
| `answer` | `str` | The model's response text |
| `chat_id` | `str` | Which chat |
| `trace_id` | `str` | Trace identifier |
| `termination_reason` | `str` | Why the turn finished |
| `trace` | `WorkflowTrace` | Full pipeline trace |
| `assistant_message_id` | `int \| None` | Persisted message ID |
| `metadata` | `dict` | Timing, error flags, answer_failed |

---

## Agent Interfaces

All agents in `src/agents/`.

| Agent | Key method | Returns |
|---|---|---|
| `CoordinatorAgent` | `run_turn(chat_id, content, ...)` | `AgentTurnResult` |
| `ContextManagerAgent` | `build_context_packet(system_prompt, latest_user_message, ranked_candidates, route_plan)` | `ContextManagerResult` |
| `ContextBuilderAgent` | `build(chat_id, system_prompt, context, latest_user_message)` | `tuple[list[dict], ContextPacket]` |
| `ChatAgent` | `generate(messages, temperature?)` | `str` |
| `ShortTermMemoryAgent` | `build_context(chat_id, latest_user_message_id?)` | `ShortTermContext` |
| `ShortTermMemoryAgent` | `update_memory_if_needed(chat_id)` | `bool` |
| `DocumentIngestionAgent` | `index_file(path, display_name?, document_id?)` | `DocumentIngestionResult` |

---

## Configuration Variables

All variables from `src/settings.py` (single source of truth), loaded into `AppConfig` in `src/config.py`. Defaults as of current code.

### Model

| Env var | Default | Controls |
|---|---|---|
| `OPENAI_API_KEY` | `dummy` | API key for the chat model |
| `OPENAI_BASE_URL` | `http://localhost:11434/v1` | Base URL for OpenAI-compatible API |
| `MODEL_NAME` | `google/gemma-4-31B-it` | Model identifier |
| `ENDPOINT_CONTEXT_WINDOW` | (auto-detected) | Override context window from endpoint metadata |
| `MODEL_CONTEXT_WINDOW` | (none) | Override context window |
| `CONTEXT_LENGTH` | (none) | Legacy alias for context window |
| `MAX_MODEL_LEN` | (none) | Alternative context window env |
| `MAX_INPUT_TOKENS` | (none) | Alternative context window env |
| `APPLICATION_CONTEXT_CAP` | 262144 | Hard cap on context window |

### Memory Budgets

| Env var | Default | Controls |
|---|---|---|
| `BASE_MEMORY_BUDGET` | 4096 | Base working memory budget for general chat |
| `MEMORY_RECALL_BUDGET_TOKENS` | 8192 | Budget for memory-recall profile |
| `CHAT_MEMORY_CAP` | 8192 | Max tokens for chat-context profile |
| `DOCUMENT_MEMORY_CAP` | 49152 | Max tokens for document-only profile |
| `MULTI_SCOPE_MEMORY_CAP` | 16384 | Max tokens for mixed memory+document |
| `LONG_DOCUMENT_MEMORY_CAP` | 32768 | Max tokens for long-document profile |
| `GLOBAL_SUMMARY_BUDGET_TOKENS` | 65536 | Base budget for global summary |
| `GLOBAL_SUMMARY_MAX_BUDGET_TOKENS` | 131072 | Max budget for global summary |
| `GLOBAL_SUMMARY_RESERVED_TOKENS` | 4096 | Reserved tokens in global summary mode |
| `REQUIRED_EVIDENCE_HEADROOM_RATIO` | 0.25 | Extra budget margin for required evidence |
| `MINIMUM_OPTIONAL_CANDIDATE_UTILITY` | 0.15 | Minimum utility score for optional candidates |

### Memory Processing

| Env var | Default | Controls |
|---|---|---|
| `RAW_MESSAGE_LIMIT` | 8 | Max raw messages per batch |
| `MEMORY_UPDATE_BATCH_SIZE` | 6 | Messages per memory-update batch |
| `MEMORY_UPDATE_POLICY` | `scheduled` | `scheduled`, `agentic_each_turn`, or `chat_end_only` |
| `RECENT_MESSAGES_MAX_COUNT` | 8 | Max recent messages in context |
| `MEMORY_UPDATE_TRIGGER_TOKENS` | 1000 | Unsummarized tokens before triggering update |
| `MEMORY_UPDATE_MAX_INPUT_TOKENS` | 4000 | Max tokens per update batch |
| `MEMORY_UPDATE_MAX_MESSAGES` | 64 | Max messages per update batch |
| `MEMORY_RECENT_PROTECTION_TOKENS` | 1500 | Recent tokens protected from summarization |
| `MEMORY_REPLAY_TRIGGER_TOKENS` | 4000 | Unsummarized tokens before replay trigger |
| `MEMORY_REPLAY_MAX_INPUT_TOKENS` | 8000 | Max tokens per replay batch |
| `MEMORY_REPLAY_MAX_MESSAGES` | 128 ⚠ | Max messages per replay batch. ⚠ Discrepancy: `settings.py` pushes `128` into env; `src/memory/constants.py` hardcodes `2` as Python fallback. Runtime uses env value (128 from settings.py). |
| `PREVIOUS_CHAT_GIST_EXTRACTOR` | `llm` | `deterministic` or `llm`; LLM mode falls back deterministically |
| `PREVIOUS_CHAT_GIST_MAX_MESSAGES_PER_GIST` | 5 | Max messages per previous-chat gist batch |

### Routing

| Env var | Default | Controls |
|---|---|---|
| `ROUTING_MODE` | `hybrid` | `rule`, `llm`, or `hybrid` |
| `ENABLE_RETRIEVAL_QUERY_SIMPLIFICATION` | `true` | Whether to simplify retrieval queries |

### Reranking

| Env var | Default | Controls |
|---|---|---|
| `RERANKER_STARTUP_MODE` | `hybrid` | `hybrid` (fast MiniLM CE + deterministic blend) or `cross_encoder` (pure mxbai CE). Set via `startup.py --hybrid`/`--cross-encoder` flag, or directly. Overrides `RERANKER_MODE` and `RERANKER_CROSS_ENCODER_MODEL`. |
| `RERANKER_MODE` | `cross_encoder` (base) | `deterministic`, `cross_encoder`, `hybrid`, or `llm`. Startup mode overrides: `hybrid`→`hybrid`, `cross_encoder`→`cross_encoder`. |
| `RERANKER_LLM_TOP_K` | 10 | Candidates sent to LLM reranker |
| `RERANKER_LLM_MIN_CONFIDENCE` | 0.55 | Minimum LLM reranker confidence |
| `RERANKER_CROSS_ENCODER_MODEL` | `cross-encoder/ms-marco-MiniLM-L12-v2` | Cross-encoder model. `--cross-encoder` startup → `mixedbread-ai/mxbai-rerank-xsmall-v1`. |
| `RERANKER_CROSS_ENCODER_WEIGHT` | 0.65 | Cross-encoder weight vs deterministic. `--cross-encoder` → 1.0. |
| `RERANKER_HYBRID_BACKEND` | `cross_encoder` (after startup) | `auto` or `cross_encoder`. Startup `hybrid` → `cross_encoder` (skips LLM gate). |
| `RERANKER_LLM_AMBIGUITY_MARGIN` | 0.15 | Score margin triggering LLM gate |
| `RERANKER_LLM_REQUIRE_CROSS_SOURCE_CONFLICT` | `true` | Require multi-source conflict for LLM gate |
| `RERANKER_LLM_PROVENANCE_QUERIES` | `true` | Trigger LLM reranking on provenance queries |

> **Note:** `RERANKER_CROSS_ENCODER_TOP_K` is NOT an env var. It is a Python constant (`500`) in `src/retrieval/reranker.py` — the number of candidates submitted to the cross-encoder before per-source normalization.

### Documents

| Env var | Default | Controls |
|---|---|---|
| `DOCUMENT_RETRIEVAL_MODE` | `langchain_chroma` | Document retrieval backend |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-small-en-v1.5` | Embedding model (384-dim, ~130 MB) |
| `DOCUMENT_TOP_K` | 18 | Chunks in prompt after reranking |
| `DOCUMENT_RETRIEVAL_FETCH_LIMIT` | 42 | Chunks fetched from Chroma before reranking |
| `DOCUMENT_CHUNKER` | `custom` | `custom` or `langchain_recursive` |
| `DOCUMENT_CHUNK_SIZE` | 1024 | Target characters per chunk |
| `DOCUMENT_CHUNK_OVERLAP` | 164 | Chunk overlap (16% of chunk_size) |
| `LANGCHAIN_CHROMA_PERSIST_DIR` | `data/chroma` | Chroma storage directory |
| `LANGCHAIN_CHUNK_SIZE` | 1024 | LangChain splitter chunk size |
| `LANGCHAIN_CHUNK_OVERLAP` | 164 | LangChain splitter overlap |

### Structured Memory Retrieval

| Env var | Default | Controls |
|---|---|---|
| `STRUCTURED_MEMORY_RETRIEVAL_MODE` | `hybrid` | `sqlite`, `vector`, or `hybrid` |
| `LONG_TERM_MEMORY_CHROMA_PERSIST_DIR` | (same as `LANGCHAIN_CHROMA_PERSIST_DIR`) | Chroma directory for long-term memory vectors |
| `LONG_TERM_MEMORY_COLLECTION` | `long_term_memory` | Chroma collection name |

### Gists

| Env var | Default | Controls |
|---|---|---|
| `CURRENT_CHAT_GIST_GENERATION_ENABLED` | `false` | Enable current-chat gist compaction |
| `PREVIOUS_CHAT_GIST_GENERATION_ENABLED` | `true` | Enable previous-chat gist generation |
| `PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED` | `true` | Retrieve previous-chat gists in context |
| `GIST_RETRIEVAL_CANDIDATES` | 8 | Max gist candidates |
| `DIRECT_RAW_RETRIEVAL_CANDIDATES` | 12 | Max direct raw retrieval candidates |
| `RAW_SPAN_OVERLAP_THRESHOLD` | 0.7 | Overlap threshold for span folding |

### LangGraph Pipeline

| Env var | Default | Controls |
|---|---|---|
| `LANGGRAPH_MAX_DIRECT_RETRIEVAL_CANDIDATES` | 160 | Max candidates from direct retrieval nodes |
| `LANGGRAPH_MAX_GIST_EXPANSION_CANDIDATES` | 80 | Max candidates from gist expansion nodes |

### Orchestration

| Env var | Default | Controls |
|---|---|---|
| `ORCHESTRATION_MODE` | `native` | `native`, `langgraph_shadow`, or `langgraph_demo` |

### Debug

| Env var | Default | Controls |
|---|---|---|
| `DEMO_MEMORY_TRACE` | `false` | Print memory trace blocks per turn |
| `RETRIEVAL_LOG_ENABLED` | `true` | Write per-turn retrieval logs to disk |
| `CHAT_DOCUMENT_SCOPE_STICKY` | `true` | Chat-scoped document visibility |

### Database

| Env var | Default | Controls |
|---|---|---|
| `DATABASE_PATH` | `data/chatbot.db` | SQLite database path |

---

## Database Schema

10 tables in `src/database.py`.

| Table | Purpose | Key columns |
|---|---|---|
| `chats` | Chat threads | `id TEXT PK`, `title`, `created_at`, `updated_at`, `model_name`, `active INTEGER` |
| `messages` | Raw user/assistant/system messages | `id INTEGER PK AUTO`, `chat_id FK`, `role CHECK`, `content`, `summarized`, `gist_processed` |
| `chat_memory_state` | Per-chat structured memory cache | `chat_id PK FK(chat)`, `memory_json` |
| `chat_gists` | Gist summaries with source-message ranges | `id PK`, `chat_id FK`, `source_type`, `gist_text`, `topics_json`, `decisions_json`, `open_tasks_json`, `start_message_id`, `end_message_id` |
| `long_term_memories` | Durable cross-chat structured memory | `id PK`, `namespace_json`, `namespace_path`, `memory_id`, `category`, `key`, `value`, `confidence`, `status`, `source_chat_id`, UNIQUE on `(namespace_path, memory_id)` |
| `document_records` | Document lifecycle metadata | `id TEXT PK`, `file_name`, `status CHECK(Uploading/Indexing/Ready/Failed/deleted)`, `chunk_count`, `error`, `summary_text` |
| `document_summaries` | LLM-generated document summaries | Populated by `DocumentIngestionAgent` during indexing |
| `chat_documents` | Chat-document association | `(chat_id, document_id) PK`, `selected`, FK to chats + document_records |
| `operation_results` | Idempotent operation keys (upload dedup) | `operation_id PK`, `operation_type`, `scope_id`, `result_ref` |
| `answer_inspections` | Per-answer observability | `assistant_message_id PK FK(messages)`, `chat_id`, `trace_id`, `payload_json` |

---

## API Routes

All routes registered in `src/api_routes.py` on Chainlit's FastAPI app.

### Chats

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/chats` | List chats with optional `cursor`, `search`, `limit` |
| `GET` | `/api/chats/{chat_id}/messages` | Get message history for a chat |
| `POST` | `/api/chats` | Create a new chat |
| `POST` | `/api/chats/{chat_id}/fork` | Fork a chat (copy messages to new chat) |
| `POST` | `/api/chats/{chat_id}/end` | End a chat (mark inactive) |
| `POST` | `/api/chats/{chat_id}/reactivate` | Reactivate an ended chat |
| `POST` | `/api/chats/{chat_id}/consolidate` | Trigger memory consolidation (30s timeout) |
| `GET` | `/api/chats/{chat_id}/consolidation-log` | Get consolidation log text |
| `DELETE` | `/api/chats/{chat_id}` | Hard delete a chat |

### Documents

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/documents` | List documents with optional `status` filter |
| `POST` | `/api/documents/upload` | Upload a file (multipart/form-data) |
| `POST` | `/api/documents/{doc_id}/deactivate` | Soft-delete document |
| `POST` | `/api/documents/{doc_id}/activate` | Restore a soft-deleted document |
| `DELETE` | `/api/documents/{doc_id}` | Hard delete (includes Chroma cleanup) |

### Memories

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/memories` | List long-term memories with optional `status` filter |
| `POST` | `/api/memories/{memory_id}/deactivate` | Soft-delete memory |
| `POST` | `/api/memories/{memory_id}/activate` | Restore memory |
| `DELETE` | `/api/memories/{memory_id}` | Hard delete memory |

### System

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/models/status` | Returns `{ready: bool}` — model reachability |
| `GET` | `/api/retrieval-logs/{chat_id}/{turn_index}` | Get per-turn retrieval debug log |
| `GET` | `/api/stats` | System stats: active chats, memory count, document count, version `v2.4.1` |

---

## Retrieval Pipeline

Seven retrievers in `src/retrieval/`, all implementing the same interface: `retrieve(chat_id, source_plan) -> list[MemoryCandidate]`.

| Retriever | Source type | Backend | Default status |
|---|---|---|---|
| `RecentMessagesRetriever` | `recent_messages` | SQLite | Always enabled |
| `StructuredMemoryRetriever` | `structured_memory` | SQLite / Vector / Hybrid | Always enabled |
| `LangChainChromaRetriever` | `document_memory` | Chroma | Enabled when document signals detected |
| `CurrentChatGistRetriever` | `current_chat_gist` | SQLite + lexical | Disabled by default |
| `CurrentChatSpanRetriever` | `current_chat_span` | SQLite + lexical | Enabled for same-chat recall |
| `PreviousChatGistRetriever` | `previous_chat_gist` | SQLite + lexical | Enabled via `PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED` |
| `RawMessageSpanRetriever` | `raw_message_span` | SQLite | Explicit span / direct / global summary modes |

**Post-retrieval**: `GistRawSpanExpander` expands gist candidates into bounded raw evidence from SQLite. `MemoryReranker` scores and reorders all candidates (deterministic, cross-encoder, hybrid, or LLM mode).
