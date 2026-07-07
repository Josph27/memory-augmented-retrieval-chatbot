# Architecture

This document describes the current implementation only. Historical design
notes and migration plans are intentionally not kept as canonical docs.

## System spine

```text
Chainlit UI
-> ChatService
-> CoordinatorAgent
-> Native fallback preparation
-> LangGraph route/retrieve/expand/rerank/context/validate
-> authoritative ContextPacket
-> AnswerAgent / model endpoint
-> message persistence
-> structured-memory update
```

The project is multi-agent at the responsibility boundary: routing,
retrieval coordination, memory management, context orchestration, and answer
generation are separate roles. Many roles are deterministic services or thin
wrappers rather than independent free-form LLM calls.

## Live orchestration modes

`ORCHESTRATION_MODE=langgraph_demo` is the application default.

- `langgraph_demo`: the graph-built `ContextPacket` is authoritative.
- `native`: the imperative coordinator path is authoritative.
- `langgraph_shadow`: graph runs read-only for comparison while Native remains
  authoritative.

In `langgraph_demo`, Native preparation still happens first so the app has a
safe fallback if graph execution or packet validation fails. Graph failure is
recorded in trace metadata and the Native packet is used instead.

## Typed memory sources

All retrievers return `MemoryCandidate` objects. Source semantics remain
distinct:

| Source | Meaning |
| --- | --- |
| `recent_messages` | newest same-chat raw messages |
| `structured_memory` | durable facts, preferences, decisions, corrections, tasks, constraints |
| `document_memory` | uploaded document chunks from Chroma |
| `previous_chat_gist` | lossy orientation for ended chats |
| `raw_message_span` | exact transcript evidence, including gist expansion and direct raw retrieval |
| `current_chat_span` | older exact evidence from the active chat |
| `current_chat_gist` | active-chat lossy orientation scaffold, default-off for answer retrieval |

`RetrieverDispatcher` invokes only enabled sources from the route plan. Document
retrieval is scoped with `DocumentRegistry` before the Chroma retriever runs.

## Routing

Semantic Router v2 produces typed intent, temporal scope, source plans, context
profile, query-rewrite metadata, and evidence-contract information. It remains
deterministic where reliability matters. Optional LLM routing exists behind the
routing agent but falls back to deterministic routing when unavailable or
invalid.

## Retrieval and expansion

Retrieval is source-specific:

- SQLite for recent messages, raw spans, gists, and structured-memory records;
- Chroma for document chunks;
- optional vector/hybrid lookup for structured memories.

Gists are orientation, not proof. When a gist has source-message provenance,
`GistRawSpanExpander` can derive bounded `raw_message_span` candidates so the
final context contains exact transcript evidence.

Direct raw retrieval can retrieve bounded raw spans without depending on a gist.
Candidates preserve typed provenance and retrieval-path metadata.

## Reranking and context selection

The default reranker is deterministic. CrossEncoder, LLM, and hybrid modes are
available as explicit configuration, not defaults.

`ContextManagerAgent` applies dynamic budget profiles and builds a validated
`ContextPacket`. Context selection is evidence-constrained, overlap-aware, and
records selected and dropped candidates. The latest user message is supplied
exactly once at the end of the prompt.

## Answer generation

`AnswerAgent` receives the final prompt messages derived from `ContextPacket`.
The answer prompt asks the model to answer directly when supplied context is
sufficient, abstain when evidence is insufficient, qualify partial evidence,
and report unresolved conflicts rather than guessing.

## Writes and duplicate-write safety

Graph nodes are read-only. Persistent writes happen outside the graph:

- user message persistence before retrieval;
- assistant message persistence after answer generation;
- structured-memory update after answer emission;
- chat-end finalization through lifecycle actions;
- document lifecycle metadata and chat associations during upload.

This separation avoids duplicate message, memory, gist, document, or lifecycle
writes when Native fallback preparation and LangGraph execution both run.

## Answer Inspector

The Answer Inspector is read-only. It persists compact answer-level
observability tied to an assistant message: requested/effective orchestration,
route, sources, selected evidence summaries, provenance, token diagnostics, and
fallback status. It never exposes hidden chain-of-thought and does not let users
edit memory, documents, budgets, reranking, or prompts.
