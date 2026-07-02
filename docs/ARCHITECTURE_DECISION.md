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
-> optional gist-to-raw-span expansion
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

Integration constraints remain:

- `demo_mid_term`/the current integration line is the stable base;
  `origin/playground-j` is reference material, not a wholesale merge target.
- Keep the existing adaptive `MemoryReranker`,
  `ContextManagerAgent`/`ContextPacket`, and `previous_chat_gist` provenance
  wrapper.
- Use mature tools as bounded backends: LangMem for durable structured memory,
  LangChain/Chroma for document and derived vector components, and
  sentence-transformers CrossEncoder for neural reranking.
- Do not add LlamaIndex solely for summarization.
- Do not migrate to LangGraph checkpoint orchestration unless the whole
  coordinator/state ownership model is intentionally migrated.

Current implementation status:

Implemented:

recent_messages retrieval
newest fitting recent-message suffix under budget
structured_memory retrieval from SQLite long_term_memories
optional vector/hybrid structured retrieval with automatic SQLite-to-vector sync
chat_memory_state compatibility fallback
document_memory retrieval through LangChain-Chroma
previous_chat_gist generation/retrieval and chat-end finalization
raw_message_span explicit retrieval and automatic gist expansion
current_chat_span exact same-chat SQLite retrieval
default-off bounded current_chat_gist scaffold
active/inactive chat lifecycle, safe chat end, and safe chat fork
ContextPacket active prompt path after validation
legacy ShortTermMemory prompt fallback
WorkflowTrace metadata
Chainlit model profiles
SQLiteChainlitDataLayer
DEMO_MEMORY_TRACE helpers
document QA retrieval evals with oracle/model answer modes
RAGAS-compatible export
optional sentence-transformers/BGE cross-encoder reranking with deterministic fallback

Implemented but default-off or explicitly enabled:

current_chat_gist generation and retrieval
current_chat_span routing
previous_chat_gist retrieval
direct raw_message_span routing
structured-memory vector/hybrid mode

Partially validated:

live-model document grounding and provenance display

Future / intended:

production activation policy for current_chat_span/current_chat_gist
live-model provenance and grounding evaluation
query decomposition
current_chat_state
larger external benchmark runs
3. Core Design Claim

The project unifies memory at the interface level, not necessarily at the storage level.

recent_messages
structured_memory
document_memory
current_chat_gist / previous_chat_gist
current_chat_span / raw_message_span
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

They are volatile and should stay close to the current turn. Under a tight
budget the builder retains the newest fitting suffix, restores chronological
order, and excludes the separately supplied latest user turn.

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

SQLite is authoritative. `STRUCTURED_MEMORY_RETRIEVAL_MODE=vector|hybrid`
enables a derived semantic index with stable IDs and automatic synchronization
for insert, update, deactivate, and delete operations. SQLite mode does not
require the vector backend.
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

They are implemented episodic orientation, but production activation is
conservative:

old chat messages
-> gist summarizer
-> chat_gists
-> gist retriever
-> MemoryCandidate(source="current_chat_gist" or "previous_chat_gist")

`ChatEndAction` finalizes pending previous-chat gist segments before marking a
chat inactive. Rolling `current_chat_gist` generation exists behind
`CURRENT_CHAT_GIST_GENERATION_ENABLED=0` and is not part of the normal answer
path by default.
4.5 Raw Message Spans

Raw message spans provide provenance for compressed gists.

Implemented lookup and expansion:

retrieved gist
-> raw span metadata
-> raw message span lookup
-> MemoryCandidate(source="raw_message_span")

Retrieved gists with valid provenance are expanded after dispatch into bounded
exact raw spans before reranking. Missing provenance is a graceful no-op.
`current_chat_span` separately performs deterministic lexical retrieval over
exact messages from only the active chat and remains explicitly routed.

The governing rule is:

```text
gist = lossy orientation
span = exact transcript evidence
gist tells where to look
span proves exact content
```
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

Current next priorities:

real-model end-to-end demo runs with actual routing and trace inspection
production activation decisions for current_chat_span and current_chat_gist
model-grounded citation/provenance evaluation
real Chroma stress testing for structured vector/hybrid mode
current_chat_state if time permits

Defer:

full unified memory rewrite
full gist vector retrieval
query decomposition
large-scale LongMemEval / PerLTQA / LoCoMo claims without saved model reports
10. Final Presentation Summary

The final design can be summarized as:

We built a multi-agent typed-memory RAG chatbot. Different memory sources have different storage and lifecycle semantics, but all retrieved context is normalized into MemoryCandidate and assembled through ContextPacket. This gives us source-specific memory behavior with a unified downstream context construction pipeline.
