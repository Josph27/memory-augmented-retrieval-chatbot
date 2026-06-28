# Assessment Q&A

## Architecture

### 1. What exactly did you implement?

We implemented a typed-memory chatbot pipeline: source routing, multiple memory
retrievers, a unified `MemoryCandidate` contract, cross-source reranking,
budgeted `ContextPacket` construction, model answering, structured memory
updates, tracing, and several focused evaluation suites. Mature libraries back
document RAG, semantic embeddings, reranking, and memory extraction.

### 2. What is different from ordinary document RAG?

Document RAG retrieves file chunks. This system also handles recent dialogue,
durable preferences and decisions, compressed earlier chats, and exact
conversation evidence. It must choose among these sources and preserve their
different semantics.

### 3. Is this really multi-agent?

It is multi-agent at the responsibility and decision level: routing,
ingestion, retrieval coordination, reranking, context management, answering,
and memory management are explicit roles. Not every role is a free-form LLM
agent; several are deterministic wrappers because that is more reliable.

### 4. What is the role of `CoordinatorAgent`?

It owns the order of one turn: route, save the user message, retrieve, rerank,
budget/build context, validate, call the answer model, save the answer, update
memory, and produce a trace.

### 5. What is the role of `RoutingAgent`?

It selects which source families should be queried. Rule mode is the default;
optional LLM/hybrid modes return structured decisions and fall back to rules on
invalid or unavailable model output.

### 6. Why is routing separate from reranking?

Routing is pre-retrieval cost and scope control: which stores should run.
Reranking is post-retrieval relevance ordering: which returned candidates are
most useful. Combining them would obscure failures and force unnecessary
retrieval.

### 7. What is `MemoryCandidate`?

It is the common output contract for every retriever. It carries content,
source identity, score, and metadata. This lets shared ranking and context code
operate over heterogeneous stores without erasing source semantics.

### 8. What is `ContextPacket`?

It is the typed representation of the context selected for the answer model.
It separates source sections and recent conversation, supports validation, and
makes prompt construction traceable.

### 9. What happens if `ContextPacket` validation fails?

The coordinator records the reason and falls back to the legacy
`ShortTermMemory` prompt path. The system does not silently send a known-invalid
packet.

## Storage and Memory

### 10. Why not put every memory into Chroma?

Vector stores are good semantic indexes but weak as the only source of truth
for ordered messages, stable update keys, statuses, and exact provenance.
SQLite stores authoritative records; Chroma is used where semantic lookup adds
value.

### 11. Why use SQLite and Chroma together?

SQLite provides transactions, stable IDs, filtering, and inspectable records.
Chroma provides similarity search over documents and optional structured-memory
representations. The stores serve complementary roles.

### 12. What does LangMem do?

LangMem is the primary semantic extraction/consolidation backend for durable
structured memory. Project code still validates categories and source IDs,
normalizes records, stores them in SQLite, retrieves them as
`MemoryCandidate`, and controls when messages are marked processed.

### 13. What is stored as structured memory?

Durable user/project facts, preferences, decisions, corrections, constraints,
and open tasks. Temporary filler and unsupported inferences should be ignored.

### 14. How is structured memory different from chat history?

Chat history is the raw source of truth. Structured memory is a compact,
updateable semantic representation intended to survive across chats.

### 15. How do previous-chat gists differ from structured memory?

Gists summarize an episode or message range. Structured memories represent
durable facts or state that can be updated independently of one conversation.

### 16. How do gists differ from raw message spans?

A gist is compact and lossy. A raw span contains the original role-labelled
messages referenced by the gist, so it is useful for exact wording and
provenance.

### 17. Is gist-to-raw-message expansion automatic?

Not generally. Raw span retrieval is currently an explicit, configuration-safe
drill-down capability. Full iterative coarse-to-fine retrieval is future work.

### 18. Why not send the full chat history?

It eventually exceeds the model context, increases latency, and dilutes
relevant information. Recent raw context plus durable memory and episodic
compression is more scalable.

## Retrieval and Reranking

### 19. How is structured memory retrieved semantically?

SQLite `long_term_memories` remains authoritative. A secondary Chroma index
stores compact text representations. `StructuredMemoryRetriever` supports
SQLite, vector, and hybrid modes and deduplicates by memory ID.

### 20. What happens if the structured-memory vector index is unavailable?

Retrieval falls back to the existing SQLite path. The semantic index is an
optional accelerator, not a requirement for preserving memory.

### 21. Why use CrossEncoder/BGE reranking?

A CrossEncoder jointly reads the query and each candidate and usually estimates
semantic relevance better than lexical overlap or independent embeddings. We
use the mature `sentence-transformers` implementation rather than building a
neural reranker.

### 22. Why keep deterministic source-aware scoring?

Semantic relevance alone does not encode application policy. Exact quote
questions should favor raw evidence, document questions should favor document
chunks, and preference questions should favor structured memory. Deterministic
features also provide a fast offline fallback.

### 23. Is the deterministic reranker state of the art?

No. It is a project-specific feature scorer for typed candidates. The BGE
CrossEncoder is the mature semantic component; the deterministic layer supplies
source semantics and safe fallback.

### 24. How does hybrid reranking avoid unnecessary LLM calls?

It ranks deterministically, optionally applies CrossEncoder scoring to top-k,
then checks ambiguity, source conflict, and provenance signals. The LLM is
skipped when the margin is decisive or candidates are homogeneous.

### 25. What happens if the LLM reranker returns invalid JSON?

The response is strictly validated. Unknown IDs, duplicates, malformed output,
low confidence, empty output, timeout, or model failure cause fallback to the
last valid deterministic or CrossEncoder ranking.

### 26. What happens if the CrossEncoder fails to load?

The backend is lazy-loaded only when selected. Missing packages, download/load
failures, invalid scores, and inference errors are traced and fall back to
deterministic ranking.

### 27. How do you prevent irrelevant memories entering the answer?

Routing limits source families, retrievers rank within stores, the reranker
compares candidates across stores, source budgets limit dominance, and
`ContextPacket` includes only selected candidates. This reduces risk but does
not guarantee that a generation model will never misuse context.

### 28. How does the system decide how much context to include?

`ContextBudgetAllocator` applies deterministic profile and source budgets.
`ContextBuilder` includes ranked candidates that fit, records dropped items,
preserves recent chronology, and constructs `ContextPacket`.

## Implementation Choices

### 29. What did you implement yourself versus use libraries for?

Project-specific work includes typed contracts, source routing, dispatcher
integration, source-aware reranking/cascade policy, context budgeting,
orchestration, SQLite schemas, traces, and evaluations. LangChain/Chroma handle
document vector RAG, sentence-transformers handles embeddings/CrossEncoder,
LangMem handles semantic memory extraction, and Chainlit provides the UI.

### 30. Why not use LangGraph?

The current turn is mostly linear and already explicit. LangGraph becomes more
valuable with iterative retrieval, retries, parallel branches, or durable
workflow checkpoints. Adding it now would increase complexity without removing
the need for the typed-memory contracts.

### 31. Is this full multi-hop retrieval?

No. It supports several sources and explicit gist/raw provenance lookup, but it
does not yet run a general loop that repeatedly plans, retrieves, expands, and
decides when enough evidence has been found.

### 32. What is the main architectural tradeoff?

Typed sources improve explainability and control but require more adapters,
configuration, and evaluation than one generic vector store. The project chose
that complexity because memory update and provenance semantics matter.

## Evaluation

### 33. How do you evaluate structured memory?

Controlled cases test memory writes, cross-chat retrieval, and lifecycle
actions: `ADD`, `NOOP`, `UPDATE`, `RETRIEVE`, and `ABSTAIN`. Mock mode verifies
the contract without model nondeterminism.

### 34. How do you evaluate source selection?

The multi-source retrieval suite defines expected and forbidden sources,
retrieved content, and abstention cases. It reports source-selection accuracy,
hit@k, forbidden-source violations, and exports traces.

### 35. How do you evaluate generated answers?

Controlled cases check expected answer content, forbidden claims, abstention,
expected-source use, and whether retrieved context was used. Model mode is
optional; mock and replay modes support reproducible testing.

### 36. What does the end-to-end scenario evaluation prove?

It proves that routing, retrieval, reranking, context construction, fake answer
generation, and trace export integrate correctly over isolated fixtures.

### 37. What does the end-to-end evaluation not prove?

Mock mode does not prove real-model answer quality, real embedding quality,
production latency, or robustness on a large public dataset. Those require
recorded model-mode and benchmark runs.

### 38. Why do normal tests avoid API calls and model downloads?

Network/model dependencies make tests slow, expensive, flaky, and difficult to
reproduce. Unit tests inject fake managers and mocked reranker backends; live
integration runs are separate and explicit.

### 39. How do document QA metrics differ from answer metrics?

Document hit@k asks whether an evidence-bearing chunk was retrieved. Answer
metrics ask whether the generated response used evidence correctly and avoided
unsupported claims. Good retrieval is necessary but not sufficient.

### 40. What are the biggest limitations?

Small controlled evaluations, no completed user study, limited public
long-memory benchmark coverage, no general multi-hop loop, and dependence on
model quality for memory extraction and final generation.

### 41. What would you improve with more time?

Run larger LongMemEval/LoCoMo/PerLTQA-compatible subsets, add provenance and
document-neighbor expansion, improve contradiction consolidation, record
model-mode reports, measure latency/cost, and add a user study. LangGraph would
be reconsidered only if those workflows require real loops and retries.

### 42. How should you discuss AI coding assistance honestly?

State that coding assistance accelerated implementation, test creation, and
documentation. Then demonstrate ownership through architectural rationale,
code-level understanding, reproducible tests, failure analysis, and an honest
account of what is library-backed, custom, optional, and not yet implemented.
