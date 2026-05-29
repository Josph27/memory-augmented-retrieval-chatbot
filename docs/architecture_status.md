# Architecture Status

This project is a Chainlit + SQLite chatbot with current-chat short-term memory.
The new agent classes are production-shaped wrappers around the existing behavior;
they do not add embeddings, documents, vector storage, or new memory algorithms.

## Current Pipeline

```text
Chainlit app.py
-> ChatService
-> CoordinatorAgent
-> QueryAnalyzer / RoutePlanner
-> Database.save_message(user)
-> RetrieverDispatcher
-> RecentMessagesRetriever / StructuredMemoryRetriever
-> MemoryReranker
-> ContextBudgetAllocator
-> trace-only ContextBuilder
-> trace-only ContextComparator
-> ShortTermMemoryAgent / ShortTermMemory.build_context
-> ContextBuilderAgent / ShortTermMemory.build_model_messages
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
- `src/retrieval/reranker.py`
  - Scores retrieved `MemoryCandidate` objects and returns ranked copies with
    score breakdown metadata. This is trace-only and does not affect prompts.
- `src/context/token_estimator.py`
  - Defines a replaceable token estimator interface plus a tokenizer-free
    approximate implementation.
- `src/context/context_budget_allocator.py`
  - Allocates profile-based trace budgets using `RoutePlan`, ranked candidates,
    model context limit, answer reserve, and system prompt estimate.
- `src/context/context_builder.py`
  - Builds a budget-aware trace-only `ContextPacket` from ranked candidates and
    `ContextBudget`. It records selected candidates, dropped candidates, section
    ordering, and estimated token usage.
- `src/context/context_comparator.py`
  - Compares the legacy `ShortTermMemory` prompt messages with the trace-only
    `ContextPacket`. It records compact prompt-shape metrics and warning codes
    without printing full prompts by default.

## Current Routing

The current route plan actively enables only:

- `recent_messages`
- `structured_memory`

Future sources may appear in the plan as disabled:

- `current_chat_chunks`
- `previous_chat_memory`
- `document_memory`

The dispatcher now calls retrievers for enabled sources and stores the resulting
`MemoryCandidate` objects on `WorkflowTrace.retrieved_candidates`. These
candidates are trace/normalization output only; prompt construction still uses
the existing `ShortTermMemory` path.

`MemoryReranker` now stores scored copies on
`WorkflowTrace.ranked_candidates`. Score breakdowns include feature values,
weights, feature contributions, final score, and the `ranking_profile`.
Ranked candidates are not consumed by prompt construction yet.

`ContextBudgetAllocator` now stores a trace-only `ContextBudget` on
`WorkflowTrace.context_budget`. It supports profiles for `general_chat`,
`memory_recall`, `document_question`, and `mixed_memory_document`, but final
prompt construction still uses the existing `ShortTermMemory` path.

`ContextBuilder` now stores a trace-only `ContextPacket` on
`WorkflowTrace.context_packet`. It orders proposed context as system prompt,
structured memory, retrieved/document memory, recent raw messages, and latest
user message. Recent raw messages are chronology-preserving conversation
context, not semantic retrieval results: they are ordered by persisted message
order and the latest user query is excluded from the recent-message section so
it appears only once as the final latest user message. Retrieved/gist/document
memories may use ranked order, but recent raw messages preserve conversation
order. This packet is not sent to the model yet.

`ContextComparator` now stores a compact comparison result in
`WorkflowTrace.metadata["context_comparison"]`. It compares estimated token
usage, message/section shape, structured memory presence, recent-message
presence, latest-user-message presence, and large token-count differences. This
is trace/debug output only; the model call still uses the legacy
`ShortTermMemory` messages. The next step is switching the final model call to
the validated `ContextPacket` after comparison output looks safe.

Stub retrievers exist for disabled future sources:

- `current_chat_chunks`
- `previous_chat_memory`
- `document_memory`

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
- switching the model call from legacy `ShortTermMemory` messages to the
  validated trace `ContextPacket`
- persistent workflow trace storage
- explicit graph runtime or LangGraph-style execution
