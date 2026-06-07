# Architecture Status

This project is a Chainlit + SQLite chatbot with current-chat short-term memory.
The new agent classes are production-shaped wrappers around the existing behavior.
Document memory is implemented as a plain-text chunk baseline with SQLite
storage and keyword retrieval by default. Optional vector/hybrid retrieval
interfaces now exist, but app startup and tests do not require embeddings,
sqlite-vec, or external document frameworks.

## Current Pipeline

```text
Chainlit app.py
-> ChatService
-> CoordinatorAgent
-> QueryAnalyzer / RoutePlanner
-> Database.save_message(user)
-> RetrieverDispatcher
-> RecentMessagesRetriever / StructuredMemoryRetriever / DocumentRetriever
-> MemoryReranker
-> ContextBudgetAllocator
-> ContextBuilder / ContextPacket
-> ContextComparator
-> ShortTermMemoryAgent / ShortTermMemory.build_context
-> ContextBuilderAgent / ShortTermMemory.build_model_messages fallback
-> ChatAgent / ModelWrapper.chat
-> Database.save_message(assistant)
-> ShortTermMemoryAgent / ShortTermMemory.update_memory_if_needed
-> termination: response_generated_and_messages_saved
```

`ChatService.handle_user_message` still returns only the assistant text for the
Chainlit UI. `ChatService.handle_user_turn` exposes the richer
`AgentTurnResult` for future orchestration work.

## New Agent Skeleton

- `src/core/contracts.py`
  - Defines `SourcePlan`, `RoutePlan`, `MemoryCandidate`, `ContextBudget`,
    `ContextPacket`, `WorkflowTrace`, and `AgentTurnResult`.
- `src/agents/coordinator_agent.py`
  - Coordinates the existing one-turn flow and returns `AgentTurnResult`.
- `src/agents/chat_agent.py`
  - Thin wrapper around `ModelWrapper.chat`.
- `src/agents/short_term_memory_agent.py`
  - Thin wrapper around `ShortTermMemory`.
- `src/agents/context_builder_agent.py`
  - Thin wrapper around model-message construction and `ContextPacket`
    creation.
- `src/routing/query_analyzer.py`
  - Produces normalized query text, coarse intent, lightweight signals, and
    confidence for tracing and future routing.
- `src/routing/route_planner.py`
  - Produces a `RoutePlan` for every turn. The plan is included in
    `WorkflowTrace` but does not change context construction yet.
- `src/retrieval/retriever_dispatcher.py`
  - Calls enabled source retrievers from the `RoutePlan` and returns normalized
    `MemoryCandidate` objects.
- `src/retrieval/recent_messages_retriever.py`
  - Loads recent raw messages from SQLite and preserves role, content, order,
    and message metadata.
- `src/retrieval/structured_memory_retriever.py`
  - Loads active structured memory records from `chat_memory_state`.
- `src/retrieval/document_retriever.py`
  - Loads plain-text document chunks from SQLite. Default mode ranks them with
    simple keyword overlap. Optional vector and hybrid modes use an embedding
    interface plus vector store abstraction when configured and indexed.
- `src/retrieval/reranker.py`
  - Scores retrieved `MemoryCandidate` objects and returns ranked copies with
    score breakdown metadata. This is trace-only and does not affect prompts.
- `src/context/token_estimator.py`
  - Defines a model-aware replaceable token estimator interface plus a
    tokenizer-free approximate implementation. No real tokenizer dependency is
    currently declared, so budgeting uses the approximate fallback until a
    model-specific tokenizer is plugged in.
- `src/context/context_budget_allocator.py`
  - Allocates profile-based trace budgets using `RoutePlan`, ranked candidates,
    model context limit, answer reserve, and system prompt estimate.
- `src/context/context_builder.py`
  - Builds a budget-aware `ContextPacket` from ranked candidates and
    `ContextBudget`. This is now the default final prompt source after
    validation. It records section-level token accounting and overflow metadata
    for each packet.
- `src/context/context_comparator.py`
  - Compares the legacy `ShortTermMemory` prompt messages with the trace-only
    `ContextPacket`. It records compact prompt-shape metrics and warning codes
    without printing full prompts by default.
- `src/context/prompt_messages.py`
  - Converts validated `ContextPacket` messages to OpenAI-compatible chat
    messages and returns fallback reasons when validation fails.

## Current Routing

The current route plan always enables:

- `recent_messages`
- `structured_memory`

For document-like queries, it also enables:

- `document_memory`

Future sources may appear in the plan as disabled:

- `current_chat_chunks`
- `previous_chat_memory`

The dispatcher now calls retrievers for enabled sources and stores the resulting
`MemoryCandidate` objects on `WorkflowTrace.retrieved_candidates`.

`MemoryReranker` now stores scored copies on
`WorkflowTrace.ranked_candidates`. Score breakdowns include feature values,
weights, feature contributions, final score, and the `ranking_profile`.

`ContextBudgetAllocator` now stores a trace-only `ContextBudget` on
`WorkflowTrace.context_budget`. It supports profiles for `general_chat`,
`memory_recall`, `document_question`, and `mixed_memory_document`.

`ContextBuilder` now stores a `ContextPacket` on
`WorkflowTrace.context_packet`. It orders proposed context as system prompt,
structured memory, retrieved/document memory, recent raw messages, and latest
user message. Recent raw messages are chronology-preserving conversation
context, not semantic retrieval results: they are ordered by persisted message
order and the latest user query is excluded from the recent-message section so
it appears only once as the final latest user message. Retrieved/gist/document
memories may use ranked order, but recent raw messages preserve conversation
order. This packet is now the default model prompt source.

Context token budgeting is tokenizer-aware by interface but currently
approximate in practice. The active estimator is
`ApproximateTokenEstimator`; no exact tokenizer dependency is installed or
selected yet. `ContextPacket.metadata["token_estimator"]` records
`"approximate"`, and `ContextPacket.metadata["token_accounting"]` records
system tokens, structured-memory tokens, retrieved/source-memory tokens, recent
message tokens, latest-user-message tokens, total prompt tokens, answer
reserve, safety margin, context limit, and overflow status. If
`total_prompt_tokens + answer_reserve + safety_margin` exceeds the context
limit, overflow is detected and traced. The builder first drops lower-ranked
non-recent candidates when possible; it does not drop chronological recent
messages or the final latest user message. Exact token counting is future work
after selecting the target model/tokenizer. LLM summarization on overflow is
also future work and is not implemented.

`ContextComparator` now stores a compact comparison result in
`WorkflowTrace.metadata["context_comparison"]`. It compares estimated token
usage, message/section shape, structured memory presence, recent-message
presence, latest-user-message presence, and large token-count differences.

Prompt assembly validates the `ContextPacket` before calling the model. If the
packet is missing or invalid, the coordinator falls back to the legacy
`ShortTermMemory` prompt messages. `WorkflowTrace.metadata` records
`prompt_source` as `context_packet` or `legacy_short_term_memory_fallback` plus
`fallback_reason` when fallback is used. It also records prompt token estimates,
context limit, answer reserve, safety margin, overflow status, overflow tokens,
and dropped candidate IDs/reasons for compact debugging.

Stub retrievers exist for disabled future sources:

- `current_chat_chunks`
- `previous_chat_memory`

## Current Document Memory

Document memory is a first baseline implementation:

- plain text is ingested through `DocumentIngestionService`
- documents are split into paragraph-preserving chunks of roughly 500-1000
  characters
- chunks are stored in SQLite tables `documents` and `document_chunks`
- `DocumentRetriever` performs simple lowercase keyword overlap by default
- matching chunks become `MemoryCandidate(source="document_memory", ...)`
- document candidates flow through `RetrieverDispatcher`, `MemoryReranker`,
  `ContextBudgetAllocator`, `ContextBuilder`, and `ContextPacket`

Document chunks appear in the retrieved/document memory section of the prompt,
not as recent messages.

Optional semantic retrieval components:

- `src/embeddings/base.py` defines the embedding interface
- `src/embeddings/sentence_transformer_embedder.py` is the intended real backend
  using `sentence-transformers/all-MiniLM-L6-v2`
- `src/embeddings/fake_embedder.py` supports offline deterministic tests
- `src/vectorstores/base.py` defines vector store search/upsert contracts
- `src/vectorstores/sqlite_json_store.py` stores vectors as JSON in normal SQLite
  for fallback/testing
- `src/vectorstores/sqlite_vec_store.py` checks for sqlite-vec availability and
  fails clearly if unavailable
- `src/documents/embedding_indexer.py` indexes stored chunks separately from
  ingestion

Configuration:

- `DOCUMENT_RETRIEVAL_MODE=keyword|vector|hybrid`
- `EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2`
- `DOCUMENT_TOP_K=4`
- `VECTOR_BACKEND=sqlite_json|sqlite_vec|in_memory`

Keyword remains the default and fallback path.

Still missing:

- production sqlite-vec virtual table wiring
- semantic reranking
- PDF or document-file parsing
- RAGAS dependency and full generated-answer evaluation

## Termination

Every current turn ends with:

```text
response_generated_and_messages_saved
```

The termination reason is stored in both `WorkflowTrace` and
`AgentTurnResult`. A compact trace is currently printed to stdout; there is no
trace persistence table yet.

## Current Memory Behavior

Short-term memory remains unchanged:

- raw messages are stored in SQLite `messages`
- recent raw messages are included directly in the prompt
- older processed messages update structured memory in `chat_memory_state`
- structured memory is generated through `StructuredMemoryState` operations:
  `upsert`, `supersede`, and `delete`

## Missing Future Components

- `LongTermMemoryAgent`
- implemented chunk/document/previous-chat retrieval
- persistent workflow trace storage
- explicit graph runtime or LangGraph-style execution
