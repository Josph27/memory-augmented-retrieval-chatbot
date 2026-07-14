# AGENTS.md

This repository is a TUM practical-course project: a multi-agent typed-memory RAG chatbot.

## Project Direction

The system should be a **multi-agent memory-augmented chatbot**.

It is multi-agent at the responsibility and decision level:

* routing decisions
* retrieval coordination
* memory-management decisions
* context orchestration
* answer generation

It should remain deterministic where reliability and evaluation matter:

* document loading
* chunking
* embedding
* SQLite access
* Chroma retrieval
* token budgeting
* prompt assembly
* metadata updates

Do not turn every component into a free-form LLM call.

## Architecture to Preserve

The current design is a typed-memory architecture with a unified retrieval interface.

Different memory sources may use different storage backends, but all retrieved context should be normalized into:

```text
MemoryCandidate
```

and assembled through:

```text
ContextPacket
```

The core spine to preserve is:

```text
source retrievers
-> MemoryCandidate[]
-> reranking / budgeting
-> ContextPacket
-> ChatAgent / LLM
-> memory update
```

Do not casually rewrite or remove:

* `MemoryCandidate`
* `ContextPacket`
* `WorkflowTrace`
* `RetrieverDispatcher`
* LangMem structured memory path
* SQLite `chats`, `messages`, and `long_term_memories`
* LangChain-Chroma document RAG
* existing evaluation scripts

## Essential Features That Must Not Break

The following features are required for the final project:

* Chainlit chat interface
* SQLite chat history
* recent / short-term message memory
* cross-chat structured long-term memory
* document RAG over documents longer than the context window
* workflow trace / retrieval trace
* document retrieval evaluation scripts
* structured memory evaluation support

## Agent Framing

Expected agent roles:

* `CoordinatorAgent`: orchestrates a user turn
* `RoutingAgent`: decides which memory sources to use
* `DocumentIngestionAgent`: loads, chunks, embeds, and indexes documents using deterministic tools
* `LangChainChromaRetriever` (formerly DocumentRetrievalAgent): retrieves document chunks from Chroma
* `StructuredMemoryRetriever` (formerly StructuredMemoryAgent): retrieves structured long-term memories
* `ShortTermMemoryAgent` / `LangMemStructuredMemoryState`: writes, updates, or ignores candidate memories
* `MemoryReranker` (formerly RerankerAgent): ranks `MemoryCandidate` objects
* `ContextManagerAgent`: allocates context budget and builds `ContextPacket`
* `ChatAgent` (formerly AnswerAgent): generates the final response from the context packet

Some of these are currently implemented as deterministic service classes or
thin wrappers rather than concrete classes with the exact role name. That is
acceptable as long as the responsibility boundary is clear and traceable. For
example, current routing is `QueryAnalyzer` + `RoutePlanner`, current document
retrieval is `LangChainChromaRetriever`, current context management is
`ContextBudgetAllocator` + `ContextBuilder`, and current memory management is
LangMem-backed through `LangMemStructuredMemoryState`.

## Implementation Rules

1. Prefer small, reviewable changes.
2. Do not fully rewrite the architecture unless explicitly instructed.
3. Do not collapse all memory into one anonymous vector database.
4. Do not remove legacy paths unless tests confirm replacement safety.
5. Add or update tests for architectural changes.
6. Keep fallback behavior when LLM-backed routing or memory decisions fail.
7. Keep traces explicit: selected sources, retrieved candidates, ranking scores, budget decisions, prompt sections, and memory update results.
8. Do not implement full query decomposition, full gist vector retrieval, or full Mem0-style rewrite unless explicitly requested later.
9. If a change touches database schema, provide a reset or migration strategy.
10. After each implementation step, run available compile, lint, and test commands, and report failures honestly.

## Project Achievements

The system successfully implements a reliable and explainable multi-agent typed-memory system featuring:

* deterministic routing and fallback LLM routing (`RoutingAgent`, `SemanticRouter`)
* deterministic document chunking and indexing (`DocumentIngestionAgent`)
* traceable retrieval and multi-mode reranking (`MemoryReranker`)
* dynamic context budgeting and evidence-constrained prompt construction (`ContextManagerAgent`)
* scoped chat lifecycle actions and gist compaction
* comprehensive evaluation support for document retrieval and structured cross-chat memory

## Deeper Project Docs

Before major implementation work, read:

* `docs/ARCHITECTURE.md`
* `docs/DATA_LIFECYCLE.md`
* `docs/EVALUATION.md`
* `docs/DEMO_RUNBOOK.md`
* `docs/KNOWN_LIMITATIONS.md`
