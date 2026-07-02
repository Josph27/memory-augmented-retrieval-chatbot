docs/IMPLEMENTATION_PLAN_2W.md
Two-Week Implementation Plan
1. Goal

Improve the current system into a reliable and explainable multi-agent typed-memory RAG chatbot.

The goal is not a full rewrite.

The goal is to strengthen the current architecture, improve implementation fidelity, and support a strong real-time demo and final explanation.

2. Non-Negotiable Features

Do not break:

Chainlit chat
SQLite chat history
recent / short-term memory
cross-chat structured long-term memory
LangMem structured memory update path
LangChain-Chroma document RAG
document retrieval evaluation scripts
MemoryCandidate
ContextPacket
WorkflowTrace

3. Current Status Categories

Implemented:

Chainlit chat interface
SQLite chat/message history through SQLiteChainlitDataLayer
Chainlit model profiles
recent_messages retrieval
newest-fitting recent suffix and latest-user deduplication
LangMem structured extraction/update
SQLite long_term_memories
automatic structured-memory vector sync in vector/hybrid mode
StructuredMemoryRetriever long_term_memories-first retrieval
chat_memory_state compatibility fallback
LangChain-Chroma document RAG
ContextPacket active prompt path with legacy ShortTermMemory fallback
WorkflowTrace metadata
bounded source minimum budgets
active/inactive chat lifecycle
safe ChatEndAction and ChatForkAction
previous-chat gist finalization/retrieval
gist-to-raw-span expansion
current_chat_span exact retrieval
default-off bounded current_chat_gist scaffold
DEMO_MEMORY_TRACE helpers
document QA retrieval evals
oracle/model answer mode for document QA
RAGAS-compatible export

Implemented but default-off or explicitly routed:

current_chat_gist generation/retrieval
current_chat_span routing
previous_chat_gist retrieval
direct raw_message_span routing
structured-memory vector/hybrid retrieval

Partially validated:

memory trace UI/terminal display

Future / intended:

production activation policy for current_chat_span/current_chat_gist
real-model grounding/provenance reports
current_chat_state
query decomposition
larger external benchmark runs

4. Implementation Strategy

Work in small PR-sized phases.

Each phase should:

make one architectural improvement
keep existing behavior working
add or update tests
update trace output if relevant
run compile/lint/tests where available
5. Phase 0 — Documentation and Architecture Lock
Deliverables
AGENTS.md
docs/PROJECT_CONTEXT.md
docs/ARCHITECTURE_DECISION.md
docs/AGENT_CONTRACTS.md
docs/IMPLEMENTATION_PLAN_2W.md
docs/EVALUATION_PLAN.md
Purpose

Prevent implementation drift.

Make Codex and human contributors follow the same architecture.

6. Phase 1 — Trace and Contract Stabilization
Goal

Make the current pipeline observable.

Tasks
Ensure every turn can expose:
route decision
active sources
retrieved candidates
reranking scores
context budget allocation
final context sections
memory update result
Standardize trace field names.
Avoid changing retrieval behavior unless necessary.
Success Criteria

A developer can inspect why the assistant used a given memory or document chunk.

7. Phase 2 — RoutingAgent
Goal

Improve query routing without losing fallback safety.

Tasks
Clarify RoutingAgent as a responsibility boundary over the current
QueryAnalyzer + RoutePlanner implementation.
Prefer hybrid routing:
rules for obvious cases
optional LLM structured output for ambiguous cases
Output structured route plan:
recent messages on/off
structured memory on/off
document memory on/off
reason
confidence
Add fallback broad retrieval.
Success Criteria

The system can explain which memory sources were selected and why.

Do not implement LLM-backed routing until trace and demo reliability are stable.

8. Phase 3 — DocumentIngestionAgent and Chunker
Goal

Make document ingestion clean and reproducible.

Tasks
Clarify document ingestion flow.
Use deterministic chunking.
Preserve document metadata:
filename
document_id
chunk_id
chunk index
source
Ensure documents longer than the context window can be indexed and retrieved.
Avoid LLM-based chunking before the deadline.
Success Criteria

Uploaded .txt / .md documents are reliably chunked, embedded, indexed, and retrieved.

9. Phase 4 — RerankerAgent
Goal

Make ranking traceable and defensible.

Tasks
Keep or improve deterministic ranking.
Add score breakdowns if missing:
retrieval score
source priority
recency
memory confidence
metadata signals
Avoid LLM reranking unless everything else is stable.
Success Criteria

The trace shows why candidates were ranked in a given order.

10. Phase 5 — ContextManagerAgent
Goal

Make context budgeting and prompt construction stable.

Tasks
Keep token budgeting deterministic.
Keep prompt section ordering deterministic.
Clearly separate:
system instructions
recent messages
structured memories
document evidence
user query
Add tests for overflow / budget behavior if feasible.
Success Criteria

The final prompt is predictable and explainable.

11. Phase 6 — Chat Lifecycle
Goal

Adopt useful lifecycle ideas without a full rewrite.

Tasks

Implement scoped lifecycle actions if feasible:

NEW_CHAT
END_CHAT
ARCHIVE_CHAT / INACTIVE_CHAT
DELETE_CHAT

On chat end:

flush bounded structured-memory batches
finalize pending bounded previous-chat gist segments
mark inactive only after successful processing or valid NOOP
Success Criteria

The system can explain when memory is written and how chat state affects memory.

12. Phase 7 — Evaluation
Goal

Produce evidence that the system works.

Tasks
Keep document hit@k benchmark.
Save exact benchmark outputs.
Add or formalize structured cross-chat memory benchmark.
Add small lifecycle benchmark:
ADD
NOOP
UPDATE
RETRIEVE
ABSTAIN
Optionally add generated-answer RAG evaluation.
Success Criteria

The final report can honestly say what is evaluated and what is future work.

13. Completed Optional Phase — Long-Term Memory Vector Index
Goal

Adopt part of the teammate-style memory design.

Design
SQLite long_term_memories = source of truth
Chroma / sqlite-vec index = semantic retrieval index
Rule

SQLite remains authoritative. Vector/hybrid mode now synchronizes committed
inserts, updates, deactivations, and deletes through stable derived IDs.

Success Criteria

Structured memories can be retrieved semantically while SQLite remains authoritative.

14. Explicitly Deferred

Do not implement before the deadline unless explicitly approved:

full unified memory rewrite
full Mem0-style memory architecture
full query decomposition
full gist vector retrieval
full multi-page frontend rewrite
large-scale LongMemEval / PerLTQA / LoCoMo claims without saved reports
production enablement of current_chat_gist
current_chat_state
15. Daily Working Rule

At the end of each implementation session, record:

what changed
what still works
what broke
tests run
next step
16. Final Project Story

The final system should be presented as:

A multi-agent typed-memory RAG chatbot that separates memory sources by lifecycle, unifies retrieved context through MemoryCandidate, builds traceable prompts through ContextPacket, and evaluates document retrieval plus structured long-term memory behavior.
