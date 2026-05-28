# Architecture Status

This project is a Chainlit + SQLite chatbot with current-chat short-term memory.
The new agent classes are production-shaped wrappers around the existing behavior;
they do not add routing, retrieval, embeddings, documents, or new memory algorithms.

## Current Pipeline

```text
Chainlit app.py
-> ChatService
-> CoordinatorAgent
-> Database.save_message(user)
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

- `QueryAnalyzer`
- `RoutePlanner`
- `RetrieverDispatcher`
- source-specific retrievers
- `MemoryReranker`
- `ContextBudgetAllocator`
- `DocumentRetriever`
- `LongTermMemoryAgent`
- persistent workflow trace storage
- explicit graph runtime or LangGraph-style execution
