docs/PROJECT_CONTEXT.md
1. Project

This project is a TUM practical-course project: a memory-augmented chatbot.

The system should support:

short-term conversational memory
structured long-term memory across chats
document retrieval over uploaded files
multi-agent orchestration
traceable context construction
evaluation of retrieval and memory behavior

The final goal is not only to produce a live demo. The project should present a defensible system design and an implementation that realizes that design.

2. Current Implementation Summary

The current system is a hybrid memory architecture with a central retrieval contract.

Runtime flow:

Chainlit UI
-> ChatService
-> CoordinatorAgent
-> RoutingAgent / QueryAnalyzer / RoutePlanner
-> RetrieverDispatcher
-> source retrievers
-> MemoryCandidate[]
-> optional gist-to-raw-span expansion
-> MemoryReranker
-> ContextBudgetAllocator / ContextManagerAgent
-> ContextBuilder
-> ContextPacket
-> ModelWrapper
-> memory update

The role names used in the architecture, such as RoutingAgent,
RerankerAgent, ContextManagerAgent, AnswerAgent, and MemoryManagerAgent, are
responsibility boundaries. They are not all concrete classes today. Current
code uses concrete classes such as QueryAnalyzer, RoutePlanner,
MemoryReranker, ContextBudgetAllocator, ContextBuilder, ModelWrapper, and
LangMemStructuredMemoryState.

Current storage:

SQLite
├── chats
├── messages
├── long_term_memories
├── chat_memory_state
├── documents
├── document_chunks
├── document_chunk_embeddings
└── chat_gists

LangChain-Chroma
├── document chunk vector retrieval
└── optional derived structured-memory vector index

LangMem
└── structured memory extraction and update

Chainlit integration:

SQLiteChainlitDataLayer
└── exposes SQLite chats/messages to Chainlit thread history

Model profiles:

app.py
└── exposes selectable Chainlit chat profiles for configured model IDs
3. Implementation Status

Implemented:

Chainlit chat interface
SQLite chat and message history
SQLiteChainlitDataLayer for Chainlit thread history
Chainlit model profiles
recent message retrieval
newest-fitting recent-message suffix with chronological restoration
LangMem-backed structured memory extraction
SQLite long_term_memories
StructuredMemoryRetriever reading long_term_memories first
chat_memory_state compatibility fallback
cross-chat structured memory retrieval
automatic structured-memory vector synchronization in vector/hybrid mode
LangChain-Chroma document retrieval
document upload / indexing path for .txt / .md and optional .pdf
MemoryCandidate
ContextPacket as the active prompt path after validation
ContextPacket fallback to legacy ShortTermMemory prompt when validation fails
WorkflowTrace
active/inactive chat lifecycle
safe ChatEndAction structured-memory flush and previous-chat gist finalization
safe ChatForkAction with provenance remapping and duplicate-extraction prevention
previous_chat_gist generation/retrieval
raw_message_span retrieval and automatic gist provenance expansion
current_chat_span exact SQLite transcript retrieval
default-off bounded current_chat_gist scaffold
DEMO_MEMORY_TRACE=1 helpers in src/memory/memory_trace.py
scripts/inspect_long_term_memory.py
scripts/verify_natural_long_term_memory_flow.py
document retrieval benchmark scripts
oracle/model answer modes for document QA eval
RAGAS-compatible JSONL export and optional run_ragas_eval.py

Implemented but default-off or explicitly routed:

current_chat_gist bounded generation scaffold
current_chat_span retrieval
direct raw_message_span lookup
previous_chat_gist retrieval
structured-memory vector/hybrid retrieval

Partially validated:

memory trace display in UI/terminal for demo mode
document metadata in SQLite alongside Chroma indexing

Future / intended:

production routing policy for current_chat_span
production answer-path enablement policy for current_chat_gist
current_chat_state / active-task decision ledger
live-model grounding and provenance evaluation
query decomposition
larger external LongMemEval / PerLTQA / LoCoMo runs

4. Essential Current Features

The following are essential and must remain working:

Chainlit chat interface
SQLite chat and message history
recent message retrieval
LangMem-backed structured memory extraction
SQLite long_term_memories
cross-chat structured memory retrieval
LangChain-Chroma document retrieval
document upload / indexing path
MemoryCandidate
ContextPacket
WorkflowTrace
document retrieval benchmark scripts

5. Current Memory Sources

Implemented sources:

recent_messages
structured_memory
document_memory
current_chat_gist
previous_chat_gist
raw_message_span
current_chat_span

Implementation does not imply default activation. `current_chat_gist` and
`current_chat_span` remain disabled in normal production routing. Previous-chat
gist retrieval and structured vector/hybrid retrieval are config-controlled.

The source contract is unified through `MemoryCandidate`, while source
semantics remain distinct. In particular:

gist = lossy orientation
span = exact transcript evidence
gist tells where to look
span proves exact content

6. Design Philosophy

The project uses a typed-memory architecture.

Different memory types have different lifecycle semantics:

recent messages are volatile dialogue context
structured memories are durable facts, preferences, decisions, and constraints
documents are external knowledge sources
gists are compressed episodic memory
raw message spans provide provenance

These memory types should not necessarily share the same physical storage or update logic.

Instead, they are unified at the retrieval-interface level through:

MemoryCandidate

and assembled into the model prompt through:

ContextPacket
7. Multi-Agent Framing

The system is multi-agent because different components own different decisions:

routing decides which memory sources are needed
retrieval agents interact with source-specific stores
memory-management agents decide what to write, update, delete, or ignore
reranking agents prioritize retrieved memory candidates
context-management agents control prompt construction
answer agents generate the final response

These are responsibility-level agents. Some are implemented as deterministic
service classes rather than separate LLM-calling agents. This is intentional
for reliability and evaluation.

However, low-level infrastructure should remain deterministic where possible:

chunking
embedding
vector search
SQLite writes
token budgeting
prompt layout

This makes the system reliable, debuggable, and evaluable.

8. Current Reliability Boundary

Reliable/default paths:

recent-message continuity
SQLite structured-memory recall
document retrieval when configured
deterministic reranking and context construction
chat-end/fork lifecycle invariants

Implemented but opt-in:

current-chat exact span retrieval
rolling current-chat gist generation
previous-chat gist retrieval
structured vector/hybrid recall

Some production-style acceptance tests use real routing, SQLite retrievers,
budgeting, and ContextPacket construction. Other evals still use fixture route
plans, fake retrievers, or mock answers and must not be presented as proof of
live-model grounding.

9. Future Work

Future extensions may include:

real model/routing/context demo runs with trace inspection
production routing policy for current_chat_span
production retrieval policy for current_chat_gist
current_chat_state
query decomposition
stress tests for real Chroma structured-memory synchronization
model-grounded citation/provenance evaluation
larger LongMemEval runs
PerLTQA-style personalized memory QA benchmark
LoCoMo-style long conversation evaluation

Known risks and decisions still required:

manual review of WorkflowTrace for several realistic recall scenarios
whether current_chat_span should activate automatically for same-chat recall
whether current_chat_gist should ever enter the production answer path
real-model validation that generated answers use cited evidence faithfully
the fork tradeoff: inherited messages are marked semantically processed in the
fork, so extraction ownership remains with the original branch if it was not
already processed
