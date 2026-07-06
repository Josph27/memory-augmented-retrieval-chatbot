# Architecture Status

This project is a Chainlit + SQLite chatbot with current-chat short-term memory.
The new agent classes are production-shaped wrappers around the existing behavior.
Document memory now uses a LangChain-Chroma retrieval backend while keeping
the project-specific memory architecture unchanged. SQLite still stores chats,
raw messages, structured memory, and chat gists. Chroma is the sole persistent
document store. `MemoryCandidate`, `ContextPacket`, and `WorkflowTrace` remain
custom.

## Current Pipeline

```text
Chainlit app.py
-> ChatService
-> CoordinatorAgent
-> RoutingAgent / QueryAnalyzer / RoutePlanner
-> Database.save_message(user)
-> RetrieverDispatcher
-> source retrievers
-> MemoryCandidate[]
-> optional gist-to-raw-span expansion
-> MemoryReranker
-> ContextBudgetAllocator / ContextManagerAgent
-> ContextBuilder / ContextPacket
-> ContextComparator
-> ShortTermMemoryAgent / ShortTermMemory.build_context
-> ContextBuilderAgent / ShortTermMemory.build_model_messages fallback
-> ChatAgent / ModelWrapper.chat
-> Database.save_message(assistant)
-> ShortTermMemoryAgent / ShortTermMemory.update_memory_if_needed
-> termination: response_generated_and_messages_saved
```

The Chainlit demo has three explicit orchestration modes. `native` retains this
imperative path. `langgraph_shadow` runs a read-only graph comparison while
native context remains authoritative. `langgraph_demo` uses Semantic Router v2
and the graph-built ContextPacket for the existing answer agent. Message
persistence and memory updates remain outside graph nodes.

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
  - Produces a `RoutePlan` for every turn. Current routing is mostly
    rule/keyword based: recent and structured memory are enabled by default,
    and document memory is enabled for document-like queries.
- `src/retrieval/retriever_dispatcher.py`
  - Calls enabled source retrievers from the `RoutePlan` and returns normalized
    `MemoryCandidate` objects.
- `src/retrieval/recent_messages_retriever.py`
  - Loads recent raw messages from SQLite and preserves role, content, order,
    and message metadata.
- `src/retrieval/structured_memory_retriever.py`
  - Loads active structured memory records from SQLite `long_term_memories`
    first, then falls back to `chat_memory_state` only when no active
    long-term records are available.
- `src/memory/langmem_structured.py`
  - Primary structured-memory extraction backend. Uses LangMem
    `create_memory_manager` with a project Pydantic schema, then normalizes
    outputs into SQLite `long_term_memories` and mirrors them into the
    existing `chat_memory_state` compatibility record format.
- `src/retrieval/langchain_chroma_retriever.py`
  - Preferred document-memory retriever. Indexes document text/chunks into
    Chroma with LangChain, retrieves top-k LangChain documents, and converts
    them into `MemoryCandidate(source="document_memory", ...)`.
- `src/retrieval/reranker.py`
  - Scores retrieved `MemoryCandidate` objects and returns ranked copies with
    score breakdown metadata. Deterministic query-aware scoring is the default;
    optional cross-encoder and adaptive hybrid/LLM reranking are fallback-safe.
- `src/context/token_estimator.py`
  - Defines a model-aware replaceable token estimator interface plus a
    tokenizer-free approximate implementation. No real tokenizer dependency is
    currently declared, so budgeting uses the approximate fallback until a
    model-specific tokenizer is plugged in.
- `src/context/context_budget_allocator.py`
  - Allocates profile-based budgets using `RoutePlan`, ranked candidates,
    model context limit, answer reserve, and system prompt estimate.
- `src/context/context_builder.py`
  - Builds a budget-aware `ContextPacket` from ranked candidates and
    `ContextBudget`. This is now the default final prompt source after
    validation. It records section-level token accounting and overflow metadata
    for each packet.
- `src/context/context_comparator.py`
  - Compares the legacy `ShortTermMemory` prompt messages with the active
    `ContextPacket` prompt path. It records compact prompt-shape metrics and
    warning codes without printing full prompts by default.
- `src/context/prompt_messages.py`
  - Converts validated `ContextPacket` messages to OpenAI-compatible chat
    messages and returns fallback reasons when validation fails.

## Current Routing

The current route plan always enables:

- `recent_messages`
- `structured_memory`

For document-like queries, it also enables:

- `document_memory`

Implemented optional sources appear in the plan as disabled unless explicitly
configured or routed:

- `current_chat_gist`
- `current_chat_span`
- `previous_chat_gist`
- `raw_message_span`
- `current_chat_chunks`
- `previous_chat_memory`

`current_chat_chunks` and `previous_chat_memory` are legacy placeholder names.
New gist-memory work should prefer `current_chat_gist` and
`previous_chat_gist`.

The dispatcher now calls retrievers for enabled sources and stores the resulting
`MemoryCandidate` objects on `WorkflowTrace.retrieved_candidates`.

`RoutingAgent` selects which sources are active. Source retrievers normalize
their results as `MemoryCandidate` objects. `MemoryReranker` orders those
candidates before `ContextManagerAgent` applies source budgets and builds the
`ContextPacket`.

`MemoryReranker` stores scored copies on `WorkflowTrace.ranked_candidates`.
Deterministic mode is the default and requires no model call. It uses lexical
overlap, source priors, query/source intent boosts, retrieval/vector scores,
recency, confidence, status, usage, and duplicate penalties. Optional `hybrid`
mode is an adaptive cascade: deterministic scoring, optional cross-encoder
top-k reranking, and gated LLM candidate-ID reranking only when the top margin
is small, sources conflict, or a gist/raw-span provenance question requires
extra disambiguation. `RERANKER_HYBRID_BACKEND` can select `auto`,
`cross_encoder`, or `llm`. Optional direct `llm` mode still considers the full
candidate set. Failed optional stages preserve the last valid ordering.

Optional `cross_encoder` mode uses the existing `sentence-transformers`
dependency and lazy-loads `BAAI/bge-reranker-v2-m3` only when selected. It
scores deterministic top-k query/candidate pairs, combines normalized neural
scores with deterministic/source-aware scores, and appends candidates outside
top-k in deterministic order. It falls back on missing dependencies, model-load
errors, inference errors, empty output, invalid values, or score-count
mismatches. Cross-encoder reranking is generally more stable and cheaper than
LLM listwise reranking, while typed-memory source boosts remain useful for
provenance and lifecycle semantics.

Reranker trace metadata records mode, fallback status/reason, deterministic
scores and feature contributions, original/final ranks, candidate source, and
LLM IDs/confidence or cross-encoder/combined scores when used. Hybrid traces
also record whether LLM reranking was considered/used, skip reason, score
margins, and top candidate sources.

Configuration:

- `RERANKER_MODE=deterministic|cross_encoder|hybrid|llm`
- `RERANKER_LLM_TOP_K=10`
- `RERANKER_LLM_MIN_CONFIDENCE=0.55`
- `RERANKER_CROSS_ENCODER_MODEL=BAAI/bge-reranker-v2-m3`
- `RERANKER_CROSS_ENCODER_TOP_K=10`
- `RERANKER_CROSS_ENCODER_WEIGHT=0.65`
- `RERANKER_HYBRID_BACKEND=auto|cross_encoder|llm`
- `RERANKER_LLM_AMBIGUITY_MARGIN=0.15`
- `RERANKER_LLM_REQUIRE_CROSS_SOURCE_CONFLICT=1`
- `RERANKER_LLM_PROVENANCE_QUERIES=1`

`deterministic` remains the safest default. `cross_encoder` provides mature
semantic scoring without an API call. `hybrid` with backend `auto` is the
recommended demo mode when the BGE model and configured chat model are
available; the LLM stage is reserved for difficult heterogeneous cases.

`ContextBudgetAllocator` stores a `ContextBudget` on
`WorkflowTrace.context_budget`. It supports profiles for `general_chat`,
`memory_recall`, `document_question`, and `mixed_memory_document`.
Candidate-bearing enabled sources receive a bounded minimum reservation, so a
routed source such as `previous_chat_gist` cannot silently receive zero budget.
Raw spans derived from an enabled gist inherit budget eligibility without
making direct raw-span routing default-on.

`ContextBuilder` stores a `ContextPacket` on
`WorkflowTrace.context_packet`. It orders proposed context as system prompt,
structured memory, retrieved/document memory, recent raw messages, and latest
user message. Recent raw messages are chronology-preserving conversation
context, not semantic retrieval results: the newest fitting suffix is selected
under budget, chronological order is restored, and the latest user query is
excluded so it appears once as the final latest user message. Retrieved/gist/document
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

Retrievers exist for disabled-by-default optional sources:

- `current_chat_gist`
- `current_chat_span`
- `previous_chat_gist`
- `raw_message_span`
- `current_chat_chunks`
- `previous_chat_memory`

## Gist Memory Infrastructure

Raw chat messages remain the source of truth. Gists are lossy orientation and
retrieval pointers, not quotation evidence. Spans are exact transcript
evidence: gist tells where to look; span proves exact content.

The current gist infrastructure is present:

- `chat_gists` stores gist rows with `source_type`, `gist_text`,
  optional topic/decision/task JSON, and `start_message_id` /
  `end_message_id` pointers back to raw messages.
- `CurrentChatGistSummarizer` explicitly compacts one bounded batch of
  `gist_processed = 0` messages. It is disabled by default.
- `PreviousChatGistGenerator` can generate `previous_chat_gist` rows for
  existing chats, either through a deterministic offline extractor or an
  optional model-backed extractor.
- `ChatEndAction` flushes structured memory, finalizes pending bounded
  previous-chat gist segments, and then marks the chat inactive.
- `current_chat_gist` is the orientation source for older active-chat content,
  but remains outside the normal answer path by default.
- `previous_chat_gist` is the canonical source for summaries of older chats.
- `GistRawSpanExpander` expands retrieved provenance-bearing gists into bounded
  exact `raw_message_span` candidates before reranking.
- `current_chat_span` performs deterministic lexical retrieval over exact
  messages from the current chat only and remains explicitly routed.

Current limitations:

- startup scanning for previous-chat gists remains config-controlled, while
  explicit chat-end finalization is implemented
- no vector retrieval over gists
- no background compaction job
- gist retrievers are disabled by default in routing; previous-chat gist
  retrieval can be enabled with `PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED=1`
- `CURRENT_CHAT_GIST_GENERATION_ENABLED=0` remains the generation default
- current-chat span routing remains an explicit decision

`messages.summarized` means processed for semantic/LangMem memory.
`messages.gist_processed` independently means included in episodic gist
processing. Gist insertion and state advancement are transactional.

## Structured Memory Index Consistency

SQLite `long_term_memories` is authoritative and SQLite retrieval remains the
default. In `STRUCTURED_MEMORY_RETRIEVAL_MODE=vector|hybrid`, committed SQLite
writes synchronize to the dedicated long-term-memory vector index. Stable
`namespace::memory_id` IDs make updates idempotent; inactive/deleted records
remove their derived entries. Failures are explicit, and `sync_all()` provides
repair/backfill for existing rows.

Useful commands:

```bash
uv run python scripts/rebuild_previous_chat_gists.py --mode deterministic
uv run python scripts/inspect_raw_message_span.py --gist-id 1
PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED=1 uv run chainlit run app.py
```

## Current Document Memory

Document memory uses the LangChain-Chroma path:

- runtime file uploads are loaded through `src/documents/loaders.py` and indexed
  directly into the LangChain-Chroma backend
- local `.txt` and `.md` files can be loaded through `src/documents/loaders.py`
  and indexed into the LangChain-Chroma backend; `.pdf` loading is optional when
  `pypdf` or PyMuPDF is installed
- documents are split through `src/documents/splitters.py`
- `DOCUMENT_CHUNKER=custom` uses the stable paragraph-preserving splitter
- `DOCUMENT_CHUNKER=langchain_recursive` uses LangChain's
  `RecursiveCharacterTextSplitter` when available and falls back to the custom
  splitter if unavailable
- chunk metadata records `splitter_name`, `chunk_size`, `chunk_overlap`,
  `fallback_used`, and character offsets when available
- Chroma `document_memory` is the sole persistent document store
- `LangChainChromaRetriever` indexes document text/chunks into Chroma and uses
  LangChain retrieval for `document_memory`
- document memory is global across chats and is not converted into structured
  user memory
- document deletion and suppression are not implemented
- `scripts/index_document_file.py` is a small development utility for indexing
  local files into the LangChain-Chroma document backend without the Chainlit UI
- retrieved LangChain `Document` objects are converted into
  `MemoryCandidate(source="document_memory", ...)`
- document candidates flow through `RetrieverDispatcher`, `MemoryReranker`,
  `ContextBudgetAllocator`, `ContextBuilder`, and `ContextPacket`

Document chunks appear in the retrieved/document memory section of the prompt,
not as recent messages.

Configuration:

- `DOCUMENT_CHUNKER=custom|langchain_recursive`
- `DOCUMENT_CHUNK_SIZE=1000`
- `DOCUMENT_CHUNK_OVERLAP=150`
- `DOCUMENT_RETRIEVAL_MODE=langchain_chroma`
- `LANGCHAIN_CHROMA_PERSIST_DIR=data/chroma`
- `LANGCHAIN_CHUNK_SIZE=1000`
- `LANGCHAIN_CHUNK_OVERLAP=150`
- `EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2`
- `DOCUMENT_TOP_K=4`

`langchain_chroma` is the document RAG mode. If `DOCUMENT_RETRIEVAL_MODE` is set
to another value, the dispatcher logs a warning and uses LangChain-Chroma.

Still missing or legacy:

- richer file loading/parsing beyond `.txt`, `.md`, and optional `.pdf`
- semantic reranking
- PDF or document-file parsing
- Markdown/header-aware chunking
- token-aware chunking
- page-aware and parent-child chunks
- required RAGAS dependency and full required RAGAS evaluator pipeline
- generated-answer document QA exists, but deterministic retrieval metrics are
  still the primary reliable benchmark

## Chainlit Runtime Integration

Implemented runtime integration includes:

- Chainlit chat interface in `app.py`
- selectable Chainlit model profiles
- `SQLiteChainlitDataLayer` for SQLite-backed thread history
- uploaded-file indexing before a chat turn
- `DEMO_MEMORY_TRACE=1` trace helpers through `src/memory/memory_trace.py`
- `scripts/inspect_long_term_memory.py` for inspecting stored long-term
  memories
- `scripts/verify_natural_long_term_memory_flow.py` for cross-chat memory demo
  verification

Dependency management should use `pyproject.toml` with `uv sync` as the
primary workflow. `requirements.txt` is minimal and should not be treated as the
authoritative dependency list.

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
- older processed messages update structured memory in `long_term_memories` and
  mirror compatible records into `chat_memory_state`
- structured memory extraction/consolidation is LangMem-backed through
  `LangMemStructuredMemoryState`
- the long-term store is namespaced and can be reused across chats, while
  `chat_memory_state` remains the compatibility mirror for the current runtime
- SQLite `long_term_memories` is read first by `StructuredMemoryRetriever`;
  `chat_memory_state` remains a compatibility fallback/mirror
- the older custom JSON-operation updater in `structured_state.py` is
  deprecated compatibility code; project-specific validators and storage
  helpers remain in use

## Missing Future Components

- `LongTermMemoryAgent`
- implemented chunk/document/previous-chat retrieval
- persistent workflow trace storage
- explicit graph runtime or LangGraph-style execution
