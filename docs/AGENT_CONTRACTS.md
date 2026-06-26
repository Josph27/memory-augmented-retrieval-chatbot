docs/AGENT_CONTRACTS.md
Agent Contracts

This document defines the intended agent responsibilities and input/output contracts.

Status labels:

Implemented = backed by current runtime code.
Partially implemented = storage, helpers, or stubs exist, but the full runtime
behavior is not enabled.
Future / intended = design target, not current behavior.

The word "agent" means a responsibility boundary. Several responsibilities are
currently implemented as deterministic services or thin wrapper classes rather
than independent LLM-calling agents.

1. CoordinatorAgent
Responsibility

Orchestrates one user turn.

Input
chat_id
user query
uploaded files if any
model/profile config
runtime settings
Output
assistant response
workflow trace
memory update result if applicable
Main Steps
save user message
route query
retrieve candidates
rank candidates
build context packet
generate answer
save assistant message
update memory if needed
return trace
Notes

The current CoordinatorAgent may still be broad. Refactoring should reduce confusion without breaking the working pipeline.

2. RoutingAgent
Responsibility

Decides which memory sources should be active for a query.

Current status

Implemented as a thin RoutingAgent responsibility wrapper over QueryAnalyzer +
RoutePlanner. Routing is mostly rule/keyword based:

recent_messages = enabled by default
structured_memory = enabled by default
document_memory = enabled for document-like terms
current_chat_gist / previous_chat_gist / raw_message_span = disabled by default

Input
user query
chat metadata
available memory sources
optional recent context summary
optional document availability metadata
Output
{
  "use_recent_messages": true,
  "use_structured_memory": true,
  "use_document_memory": false,
  "reason": "The query asks about a durable user/project preference.",
  "confidence": 0.85,
  "fallback_mode": false
}
Failure Behavior

If routing fails, returns invalid output, or confidence is too low, use safe broad retrieval:

recent_messages = true
structured_memory = true
document_memory = true if documents are indexed
Implementation Notes

The router may be:

rule-based
LLM-backed with structured output
hybrid rule + LLM

A hybrid or fully LLM-backed router is future / intended. The current
implementation is the safer rule-based path and records its structured decision
in WorkflowTrace metadata. Representative deterministic routing cases are
covered in tests before any LLM or hybrid routing is introduced.

3. DocumentIngestionAgent
Responsibility

Indexes uploaded documents.

Current status

Implemented as deterministic services, not a separate concrete agent class.
Runtime file upload uses document loaders plus LangChainChromaRetriever
indexing. SQLite document chunk/embedding tables remain compatibility,
metadata, or legacy paths rather than the primary runtime vector index.

Input
file path
file metadata
chat_id or document owner metadata
Tools / Services
document loader
deterministic chunker
embedding model
Chroma vector store
SQLite document metadata store if available
Output
{
  "document_id": "doc_...",
  "chunk_count": 24,
  "indexed": true,
  "errors": []
}
Design Rule

This agent should not normally use an LLM for chunking or embedding.

Chunking and embedding should be reproducible.

4. DocumentRetrievalAgent
Responsibility

Retrieves document chunks relevant to the query.

Current status

Implemented through LangChainChromaRetriever. LangChain-Chroma is the primary
runtime document RAG backend.

Input
query
top_k
optional document filters
optional route plan
Output

A list of MemoryCandidate objects:

MemoryCandidate(source="document_memory")
Required Metadata

Each candidate should preserve:

document_id
chunk_id
source filename
retrieval score
chunk index or location if available
5. StructuredMemoryAgent
Responsibility

Retrieves durable structured long-term memories.

Current status

Implemented through StructuredMemoryRetriever. It reads SQLite
long_term_memories first and falls back to chat_memory_state only when no
active long-term records are available.

Input
query
chat/user context
top_k
optional memory type filters
Output

A list of MemoryCandidate objects:

MemoryCandidate(source="structured_memory")
Source of Truth

SQLite long_term_memories remains the source of truth.

Future Extension

A vector index over long-term memories may be added later:

SQLite long_term_memories = source of truth
Chroma / sqlite-vec LT memory index = retrieval index
6. MemoryManagerAgent
Responsibility

Decides whether conversation content should create, update, delete, or ignore structured memories.

Current status

Partially implemented through ShortTermMemory.update_memory_if_needed and
LangMemStructuredMemoryState. LangMem extracts typed memories and project code
validates, normalizes, writes to long_term_memories, and mirrors to
chat_memory_state. A full explicit ADD / UPDATE / DELETE / NOOP lifecycle
classifier is future / intended.

Input
old unsummarized messages
existing relevant memories
memory policy
chat metadata
Output
{
  "actions": [
    {
      "type": "ADD",
      "memory_type": "preference",
      "content": "The user prefers mature open-source libraries over custom infrastructure.",
      "confidence": 0.91
    }
  ]
}
Supported Actions
ADD
UPDATE
DELETE
NOOP
Current Implementation

The current implementation may use LangMem for extraction/update and project-side validation before writing to SQLite.

7. MemoryCriticAgent
Responsibility

Validates proposed memory updates.

Current status

Future / intended as a separate component. Current validation is embedded in
LangMemStructuredMemoryState and structured-memory validation helpers.

Input
proposed memory actions
source messages
existing memories
Output
{
  "accepted": true,
  "reason": "The preference is durable and useful for future conversations."
}
Scope

Optional before the deadline.

If not implemented as a separate component, validation can be included inside MemoryManagerAgent.

8. RerankerAgent
Responsibility

Ranks MemoryCandidate objects before context construction.

Current status

Implemented as MemoryReranker. It is deterministic and metadata-aware, with
score breakdowns. It is not a cross-encoder or semantic reranker.

Input
query
candidates
route plan
source metadata
Output
ranked candidates
score breakdowns
Initial Implementation

Use deterministic or metadata-aware scoring:

retrieval score
source priority
recency
memory confidence
use_count / last_used if available
Future Implementation

Optional:

encoder-based reranking
cross-encoder reranking
LLM-based reranking for small candidate sets
9. ContextManagerAgent
Responsibility

Controls context budgeting and prompt construction.

Current status

Implemented as a thin ContextManagerAgent wrapper over
ContextBudgetAllocator, ContextBuilder, and prompt_messages. ContextPacket is
the active prompt path after validation. If validation fails, the coordinator
falls back to the legacy ShortTermMemory prompt.

Input
ranked MemoryCandidate objects
recent messages
token budget
route plan
system prompt config
Output
ContextPacket
Design Rule

Implementation should be deterministic before the deadline.

Context construction should be stable and testable.

10. AnswerAgent
Responsibility

Generates the assistant response from the final ContextPacket.

Current status

Implemented as ChatAgent + ModelWrapper. ModelWrapper uses an
OpenAI-compatible chat completions endpoint and the selected Chainlit model
profile.

Input
system prompt
context packet
user query
Output
assistant response
Requirements

The answer should:

use retrieved context faithfully
avoid inventing unsupported memories
distinguish document evidence from remembered user/project preferences where relevant
11. WorkflowTrace

Every turn should expose enough trace information to inspect:

routing decision
active sources
retrieved candidates
reranking scores
context budget allocation
final prompt sections
memory update actions

Traceability is part of the design, not only a debugging feature.
