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
-> QueryAnalyzer / RoutePlanner
-> RetrieverDispatcher
-> source retrievers
-> MemoryCandidate[]
-> MemoryReranker
-> ContextBudgetAllocator
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
└── document chunk vector retrieval

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
LangMem-backed structured memory extraction
SQLite long_term_memories
StructuredMemoryRetriever reading long_term_memories first
chat_memory_state compatibility fallback
cross-chat structured memory retrieval
LangChain-Chroma document retrieval
document upload / indexing path for .txt / .md and optional .pdf
MemoryCandidate
ContextPacket as the active prompt path after validation
ContextPacket fallback to legacy ShortTermMemory prompt when validation fails
WorkflowTrace
DEMO_MEMORY_TRACE=1 helpers in src/memory/memory_trace.py
scripts/inspect_long_term_memory.py
scripts/verify_natural_long_term_memory_flow.py
document retrieval benchmark scripts
oracle/model answer modes for document QA eval
RAGAS-compatible JSONL export and optional run_ragas_eval.py

Partially implemented:

current_chat_gist storage and explicit summarizer service
previous_chat_gist storage/retriever stubs
raw_message_span explicit lookup
memory trace display in UI/terminal for demo mode
document metadata in SQLite alongside Chroma indexing

Future / intended:

semantic vector index over long-term memories
automatic current-chat gist generation in normal runtime
previous-chat gist generation
automatic raw-message span drill-down
hybrid or LLM-backed routing
query decomposition
cross-encoder or LLM reranking
full memory lifecycle benchmark
full LongMemEval / PerLTQA / LoCoMo benchmark

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

Implemented core sources:

recent_messages
structured_memory
document_memory

Partially implemented or future sources:

current_chat_gist
previous_chat_gist
raw_message_span

The final implementation should clearly distinguish between implemented sources and future extensions.

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

8. Near-Term Goal

The near-term goal is not a full rewrite.

The near-term goal is to improve the current system into a clear multi-agent typed-memory architecture by:

clarifying agent contracts
improving query routing
improving document ingestion and chunking
making reranking traceable
keeping token budgeting and prompt construction deterministic
adding scoped chat lifecycle actions
strengthening evaluation for document retrieval and structured memory
9. Future Work

Future extensions may include:

semantic vector index over long-term memories
current-chat gist generation
previous-chat gist generation
raw-message span drill-down
query decomposition
cross-encoder reranking
LLM-based reranking
full memory lifecycle evaluation
LongMemEval-style benchmark
PerLTQA-style personalized memory QA benchmark
LoCoMo-style long conversation evaluation
