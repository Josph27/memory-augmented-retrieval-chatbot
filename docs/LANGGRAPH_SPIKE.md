# LangGraph Read-Only Memory Pipeline Spike

## Goal

Validate LangGraph as a control-flow wrapper around the existing typed-memory
read path without replacing production orchestration or memory services.

This spike is not production orchestration. It is invoked only through its
explicit helper from focused tests or future diagnostic scripts.

## What This Spike Includes

The graph wraps existing services:

```text
route
→ retrieve source candidates
→ expand gists to raw spans
→ rerank
→ build ContextPacket
→ validate evidence contract
→ mock answer or insufficient-evidence response
→ bounded trace
```

It preserves:

- `MemoryCandidate` objects and typed source labels;
- source message IDs and parent gist provenance;
- `GistRawSpanExpander`;
- `MemoryReranker`;
- `ContextManagerAgent` and normal `ContextPacket`;
- gist as orientation and span as exact evidence.

## What This Spike Excludes

- production `ChatService` and `CoordinatorAgent` integration;
- UI and production configuration;
- real answer-model calls;
- saving user or assistant messages;
- ShortTermMemory/LangMem updates;
- SQLite/Chroma writes and vector synchronization;
- ChatEndAction and ChatForkAction;
- retry loops;
- LangGraph Store;
- durable checkpointing.

The installed LangGraph package is currently available transitively through
LangChain. The spike does not change dependency declarations.

## Graph Nodes

| Node | Existing component |
|---|---|
| `route` | `RoutingAgent` |
| `retrieve` | registered retrievers from `RetrieverDispatcher` |
| `expand_gists` | dispatcher's `GistRawSpanExpander` |
| `rerank` | `MemoryReranker` |
| `build_context` | `ContextManagerAgent` |
| `validate_evidence` | spike-only `EvidenceContract` validator |
| `mock_answer` | deterministic mock output |
| `insufficient_evidence` | deterministic abstention |
| `trace` | bounded source/ID/snippet summary |

The retrieve and expansion stages are separated in the graph even though the
production dispatcher combines them. No production dispatcher behavior changed.

## Graph State

`MemoryGraphState` holds:

- run/chat/user identity and original query;
- `RoutePlan` and evidence contract;
- bounded base, expanded, and reranked candidates;
- source budgets and ContextPacket;
- evidence-validation result and mock answer;
- errors, visited nodes, node timings, and bounded trace.

It does not hold database/model clients or full chat transcripts. Trace snippets
are capped at 160 characters, candidate summaries at 20 entries, base candidates
at 32, and expanded candidates at 16.

## Evidence Contract Validation

`EvidenceContract(requires_raw_span=True)` passes only when the final
ContextPacket includes `raw_message_span` or `current_chat_span`.

A `previous_chat_gist` or `current_chat_gist` candidate is orientation only and
does not satisfy an exact quote request. Validation happens after context
budgeting, so evidence retrieved but dropped from ContextPacket also fails.

## Why Memory Update Is Excluded

LangGraph may retry or resume nodes. Retrying a SQLite/LangMem/Chroma mutation
without an idempotency key could duplicate or partially apply memory writes.

The first spike is deliberately read-only. Memory-update nodes require a
separate design for idempotency, transaction boundaries, and checkpoint/write
ordering.

## Test Scenarios

Focused tests cover:

1. exact current-chat quote with raw span present;
2. exact quote with gist-only evidence and deterministic insufficiency;
3. previous-chat gist expansion into linked raw transcript evidence;
4. absence of LangGraph integration in ChatService/CoordinatorAgent;
5. bounded trace fields and unchanged SQLite messages, gists, and memory state.

All answer text is explicitly prefixed `MOCK`.

## How To Run

```bash
uv run pytest -q tests/test_langgraph_memory_pipeline.py
```

The graph is built directly by tests with temporary SQLite fixtures. There is
no production feature flag because no production module imports the spike.

## Next Steps

Before production migration:

1. compare graph and Coordinator ContextPackets for identical fixtures;
2. add optional `InMemorySaver` state-history tests;
3. design idempotency keys for message and memory writes;
4. preserve legacy prompt fallback behavior;
5. add Router v2 evidence contracts;
6. evaluate a separate default-off model-answer node;
7. explicitly declare LangGraph as a direct dependency if the spike is retained.

LangGraph Store remains out of scope; SQLite/Chroma/LangMem stay authoritative.
