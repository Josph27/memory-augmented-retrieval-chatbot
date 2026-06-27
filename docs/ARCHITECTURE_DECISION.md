docs/ARCHITECTURE_DECISION.md
Architecture Decision: Multi-Agent Typed-Memory RAG Chatbot
1. Decision

We choose a multi-agent typed-memory RAG architecture.

The system separates memory types by their lifecycle and storage requirements, but unifies retrieval outputs through a shared MemoryCandidate interface and assembles final model context through ContextPacket.

The intended responsibility flow is:

User query
-> CoordinatorAgent
-> RoutingAgent / QueryAnalyzer / RoutePlanner
-> source-specific retrievers
-> MemoryCandidate[]
-> MemoryReranker
-> ContextManagerAgent / ContextBudgetAllocator / ContextBuilder
-> ContextPacket
-> ModelWrapper
-> LangMem-backed memory update
2. Alternatives Considered
Option A: Simple RAG Chatbot

A simple RAG chatbot would retrieve document chunks and append them to the prompt.

This is insufficient because the project also needs:

short-term dialogue memory
cross-chat structured memory
memory writing and updating
source-specific traceability
memory lifecycle evaluation
Option B: One Unified Vector Database

A unified vector database would store documents, memories, gists, and chat chunks in the same retrieval system.

This is attractive because it simplifies retrieval.

However, it blurs important lifecycle differences:

a document chunk should not be updated like a user preference
a recent message should not automatically become durable memory
a structured memory should support update/delete semantics
a compressed gist should preserve provenance back to raw message spans
documents and personal memories require different evaluation criteria

Therefore, a single vector database is not the best source-of-truth design.

Option C: Full Mem0-Style Memory Lifecycle Rewrite

A full Mem0-style system would include rich memory lifecycle actions, memory pruning, update/delete/pass decisions, semantic long-term memory retrieval, gists, and unified retrieval across many stores.

This is a strong future direction.

However, fully switching to this design before the deadline is risky because:

the current system already has working cross-chat memory and document RAG
many proposed components are underspecified
a full rewrite would touch storage, routing, retrieval, context construction, UI, and evaluation
implementation fidelity would likely suffer if the rewrite is incomplete
Chosen Option: Hybrid Typed-Memory Multi-Agent Architecture

The chosen design keeps the working architecture spine and adopts the strongest lifecycle ideas incrementally.

Keep:

typed memory sources
SQLite as source of truth for chats and structured memories
LangMem for structured memory extraction
LangChain-Chroma for document retrieval
MemoryCandidate
ContextPacket
WorkflowTrace

Adopt:

clearer agent roles
stronger query routing
memory lifecycle terminology
use_count / last_used metadata if feasible
memory/document inspector actions if feasible
future semantic index over long-term memory

Current implementation status:

Implemented:

recent_messages retrieval
structured_memory retrieval from SQLite long_term_memories
chat_memory_state compatibility fallback
document_memory retrieval through LangChain-Chroma
ContextPacket active prompt path after validation
legacy ShortTermMemory prompt fallback
WorkflowTrace metadata
Chainlit model profiles
SQLiteChainlitDataLayer
DEMO_MEMORY_TRACE helpers
document QA retrieval evals with oracle/model answer modes
RAGAS-compatible export
optional sentence-transformers/BGE cross-encoder reranking with deterministic fallback

Partially implemented:

current_chat_gist storage and explicit summarizer service
previous_chat_gist generator and retriever, disabled by default
raw_message_span explicit lookup
document metadata/chunk SQLite compatibility path

Future / intended:

semantic vector index over long-term memories
automatic gist retrieval pipeline
hybrid or LLM-backed routing
query decomposition
full memory lifecycle benchmark
full external benchmark implementations
3. Core Design Claim

The project unifies memory at the interface level, not necessarily at the storage level.

recent_messages
structured_memory
document_memory
future gists
future raw spans
        ↓
MemoryCandidate
        ↓
ContextPacket
        ↓
LLM answer

This preserves the semantics of each memory type while allowing a common downstream retrieval, reranking, budgeting, and prompt construction pipeline.

4. Memory Types
4.1 Recent Messages

Recent messages preserve immediate conversation continuity.

They are volatile and should stay close to the current turn.

4.2 Structured Long-Term Memory

Structured memory stores durable semantic information, such as:

user preferences
project facts
decisions
constraints
corrections
long-term tasks

Current implementation:

old messages
-> LangMem structured extraction
-> SQLite long_term_memories
-> StructuredMemoryRetriever
-> MemoryCandidate(source="structured_memory")
4.3 Document Memory

Document memory stores external knowledge from uploaded files.

Current implementation:

document file
-> loader
-> chunker
-> embedding
-> LangChain-Chroma
-> LangChainChromaRetriever
-> MemoryCandidate(source="document_memory")
4.4 Gists

Gists are compressed episodic memories of conversations.

They are future or partial scope.

Possible future flow:

old chat messages
-> gist summarizer
-> chat_gists
-> gist retriever
-> MemoryCandidate(source="current_chat_gist" or "previous_chat_gist")
4.5 Raw Message Spans

Raw message spans provide provenance for compressed gists.

Implemented explicit lookup:

retrieved gist
-> raw span metadata
-> raw message span lookup
-> MemoryCandidate(source="raw_message_span")

This lookup is still a second-stage provenance tool. It is not automatically
enabled in normal routing by default.
5. Agent Design

The system is multi-agent at the responsibility level.

Not every named role below is a concrete class today. Some roles are currently
implemented by deterministic services or thin wrappers. This is deliberate:
the project should be multi-agent in responsibility and traceability without
turning deterministic infrastructure into free-form LLM calls.

LLM-backed or policy agents:

RoutingAgent / thin wrapper over current QueryAnalyzer + RoutePlanner
MemoryManagerAgent / current LangMemStructuredMemoryState
MemoryCriticAgent if implemented
AnswerAgent / current ModelWrapper

Tool/service agents:

DocumentIngestionAgent / current document loaders and LangChainChromaRetriever indexing
DocumentRetrievalAgent / current LangChainChromaRetriever
StructuredMemoryAgent / current StructuredMemoryRetriever
RerankerAgent / current MemoryReranker
ContextManagerAgent / thin wrapper over current ContextBudgetAllocator + ContextBuilder

Not every agent needs to call an LLM. This is intentional.

6. Deterministic Components

The following should remain deterministic unless there is a strong reason to change them:

chunking
embedding
Chroma retrieval
SQLite retrieval
token budgeting
prompt section ordering
metadata updates

This improves reliability, testability, and demo stability.

7. Traceability

Every turn should produce or support a trace containing:

route decision
active sources
retrieved candidates
reranking scores
token budget allocation
final context sections
memory update actions

Traceability is important for debugging, evaluation, and presentation.

8. Evaluation Implications

The architecture supports separate evaluation of:

document retrieval
generated-answer RAG quality
cross-chat structured memory
memory lifecycle
source selection
answer faithfulness

This is easier to evaluate than a system where all context is mixed into anonymous vector chunks.

9. Near-Term Scope

Before the deadline, prioritize:

improved query routing
reliable document ingestion/chunking
traceable reranking
deterministic context budgeting
deterministic prompt construction
scoped chat lifecycle
document retrieval benchmark
cross-chat structured memory benchmark
small lifecycle benchmark

Defer:

full unified memory rewrite
full gist vector retrieval
query decomposition
full LongMemEval / PerLTQA / LoCoMo implementation
10. Final Presentation Summary

The final design can be summarized as:

We built a multi-agent typed-memory RAG chatbot. Different memory sources have different storage and lifecycle semantics, but all retrieved context is normalized into MemoryCandidate and assembled through ContextPacket. This gives us source-specific memory behavior with a unified downstream context construction pipeline.
