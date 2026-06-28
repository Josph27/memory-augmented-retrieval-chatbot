# Implementation Defense Guide

## 1. Project Summary

This project is a memory-augmented chatbot that can use recent conversation,
durable user/project memories, earlier conversations, and uploaded documents.
The central problem is not only generating an answer. It is selecting the right
evidence from several memory types, fitting that evidence into a bounded prompt,
and preserving enough provenance to explain the result.

A simple chatbot normally sees only the current prompt or a recent transcript.
A simple document RAG system retrieves document chunks but does not manage
cross-chat preferences, corrections, decisions, or episodic conversation
history. This project combines both concerns while keeping their storage and
retrieval semantics distinct.

The design is multi-agent at the responsibility level. Some roles are
deterministic services or thin agent wrappers rather than autonomous LLM calls.
This is deliberate: loading files, querying SQLite, budgeting context, and
assembling prompts should be predictable and testable.

## 2. High-Level Architecture

```text
Chainlit UI
    |
    v
ChatService
    |
    v
CoordinatorAgent
    |
    +--> RoutingAgent
    |      `--> QueryAnalyzer + RoutePlanner (rule default)
    |
    +--> RetrieverDispatcher
    |      +--> RecentMessagesRetriever
    |      +--> StructuredMemoryRetriever
    |      |      +--> SQLite long_term_memories
    |      |      `--> optional semantic Chroma index
    |      +--> LangChainChromaRetriever (documents)
    |      +--> PreviousChatGistRetriever
    |      `--> RawMessageSpanRetriever
    |
    +--> MemoryCandidate[]
    |
    +--> MemoryReranker
    |      +--> deterministic source-aware scoring
    |      +--> optional CrossEncoder/BGE scoring
    |      `--> optional gated LLM listwise reranking
    |
    +--> ContextManagerAgent
    |      `--> ContextBudgetAllocator + ContextBuilder
    |
    +--> ContextPacket validation
    |      `--> legacy prompt fallback on validation failure
    |
    +--> ChatAgent / ModelWrapper
    |
    +--> save messages
    `--> ShortTermMemory -> LangMem memory update
                                |
                                v
                      SQLite long_term_memories

WorkflowTrace records decisions and intermediate results across the turn.
```

The common contract is:

```text
source-specific retrieval -> MemoryCandidate[] -> ranking/budgeting
-> ContextPacket -> answer generation -> memory update
```

## 3. Component Walkthrough

### ChatService

- **Responsibility:** Constructs and exposes the application services used by
  Chainlit and scripts.
- **Input:** Chat IDs, user messages, and uploaded file paths.
- **Output:** Turn results and structured document-ingestion results.
- **Why it exists:** Keeps UI callbacks separate from orchestration and storage.
- **Without it:** `app.py` would own construction, persistence, retrieval, and
  model details, making tests and non-UI scripts harder.

### CoordinatorAgent

- **Responsibility:** Runs one complete user turn.
- **Input:** Chat ID and user message.
- **Output:** Answer plus `WorkflowTrace` and metadata.
- **Why it exists:** Defines one ordered orchestration path for routing,
  persistence, retrieval, reranking, context construction, generation, and
  memory update.
- **Without it:** Lifecycle ordering and failure handling would be duplicated
  across frontends.

### RoutingAgent

- **Responsibility:** Produces a structured source-selection decision.
- **Input:** User query and runtime availability information.
- **Output:** Source flags, active/disabled sources, reason, confidence, mode,
  and fallback information.
- **Why it exists:** Avoids querying every store for every question and makes
  source selection traceable.
- **Without it:** Retrieval would be unnecessarily expensive and irrelevant
  source types would enter the candidate pool more often.

### RoutePlanner and QueryAnalyzer

- **Responsibility:** Implement the deterministic routing policy used by
  default.
- **Input:** Query text.
- **Output:** Query features and a `RoutePlan`.
- **Why they exist:** Keyword/rule routing is fast, explainable, and available
  without a model endpoint.
- **Without them:** LLM routing failures would have no reliable fallback.

### RetrieverDispatcher

- **Responsibility:** Calls only the retrievers enabled by the route.
- **Input:** Query, chat ID, and route plan.
- **Output:** A unified list of `MemoryCandidate` objects.
- **Why it exists:** Isolates source-specific APIs and storage backends.
- **Without it:** The coordinator would need to know how each memory source is
  stored and queried.

### StructuredMemoryRetriever

- **Responsibility:** Retrieves durable structured memories and normalizes them
  as `MemoryCandidate(source="structured_memory")`.
- **Input:** Query and current chat context.
- **Output:** Structured-memory candidates with category and provenance
  metadata.
- **Why it exists:** Durable preferences, facts, constraints, tasks, decisions,
  and corrections have different semantics from raw chat or documents.
- **Current behavior:** Supports `sqlite`, `vector`, and `hybrid` retrieval.
  SQLite `long_term_memories` remains the source of truth. The legacy
  `chat_memory_state` path is a compatibility fallback.

### LongTermMemoryVectorIndex

- **Responsibility:** Maintains a semantic Chroma index over structured memory
  records.
- **Input:** Normalized records from SQLite.
- **Output:** Semantically similar memory IDs and scores.
- **Why it exists:** Exact/lexical matching may miss paraphrases across chats.
- **Without it:** Questions using different wording from the stored memory
  would be harder to retrieve.
- **Boundary:** It is a secondary index, not the authoritative memory store.

### DocumentIngestionAgent

- **Responsibility:** Wraps deterministic file loading and LangChain-Chroma
  indexing.
- **Input:** File path and optional display name.
- **Output:** Document ID when available, file metadata, chunk count, indexed
  status, and errors.
- **Why it exists:** Gives document ingestion an explicit responsibility
  boundary without replacing proven loader, splitter, embedding, or Chroma
  components.
- **Without it:** UI and scripts would need to understand all ingestion stages.

### LangChainChromaRetriever

- **Responsibility:** Indexes split document text and retrieves relevant chunks
  from Chroma.
- **Input:** Documents for indexing or a query for retrieval.
- **Output:** Document-memory candidates with source metadata.
- **Why it exists:** Uses mature LangChain/Chroma infrastructure instead of
  maintaining a custom document vector engine.

### PreviousChatGistRetriever

- **Responsibility:** Retrieves compact summaries of earlier chats.
- **Input:** Query and current chat ID.
- **Output:** `previous_chat_gist` candidates linked to source message ranges.
- **Why it exists:** Episodic summaries reduce context cost while retaining the
  topic and outcome of an earlier conversation.
- **Current limitation:** Gist generation and retrieval are configuration
  controlled and disabled by default. Retrieval is not a full multi-hop
  semantic expansion pipeline.

### RawMessageSpanRetriever

- **Responsibility:** Fetches the original message interval referenced by a
  gist.
- **Input:** Chat ID and stable message start/end IDs.
- **Output:** A compact role-labelled `raw_message_span` candidate.
- **Why it exists:** Gists are compressed and can omit exact wording. Raw spans
  provide evidence and provenance when exact details are needed.
- **Current limitation:** It is an explicit drill-down source and is not
  automatically expanded on every gist retrieval.

### MemoryReranker

- **Responsibility:** Orders heterogeneous candidates before context budgeting.
- **Input:** Query and `MemoryCandidate[]`.
- **Output:** Ranked candidates and explainable scoring metadata.
- **Why it exists:** Retrieval scores from different stores are not directly
  comparable, and source semantics matter.
- **Without it:** A weak document match could outrank a direct preference or a
  gist could outrank the raw evidence requested by the user.

### CrossEncoder Reranker Backend

- **Responsibility:** Supplies mature pairwise semantic relevance scores.
- **Input:** Query/candidate text pairs.
- **Output:** Numeric relevance scores.
- **Implementation:** Lazily uses `sentence-transformers.CrossEncoder`; the
  configured default model is `BAAI/bge-reranker-v2-m3`.
- **Why it exists:** It improves semantic ranking beyond lexical overlap.
- **Failure behavior:** Missing dependencies, model-load errors, or inference
  errors fall back to deterministic ranking.

### ContextManagerAgent

- **Responsibility:** Wraps context budgeting and packet construction.
- **Input:** Ranked candidates, route/profile information, and current query.
- **Output:** `ContextPacket` plus inclusion, dropping, and budget metadata.
- **Why it exists:** Makes context orchestration an explicit, testable role.
- **Without it:** Ranking and prompt construction would be tightly coupled.

### ContextBuilder and ContextPacket

- **Responsibility:** Build the typed final context representation.
- **Input:** Budgeted candidates and recent conversation.
- **Output:** A validated `ContextPacket` and rendered prompt sections.
- **Why they exist:** They preserve source boundaries and enforce prompt
  invariants, including safe handling of the latest user message.
- **Current behavior:** `ContextPacket` is the active prompt path after
  validation. If validation fails, the coordinator uses the legacy
  `ShortTermMemory` prompt path as a safety fallback.

### LangMem Memory Update

- **Responsibility:** Extracts and consolidates durable structured memories from
  older eligible messages.
- **Input:** Unsummarized message batches and existing memory state.
- **Output:** Validated memory records such as preferences, facts, decisions,
  constraints, corrections, and open tasks.
- **Why it exists:** It replaces a large amount of custom semantic extraction
  logic while preserving project-specific validation and storage contracts.
- **Safety:** Recent messages remain raw. Messages are marked summarized only
  after an accepted update is stored.

### WorkflowTrace

- **Responsibility:** Captures the major decisions and artifacts of a turn.
- **Input:** Data produced by each orchestration stage.
- **Output:** A trace containing route, candidates, ranking, context, fallback,
  timing, and memory-update metadata.
- **Why it exists:** Multi-source behavior is otherwise difficult to explain,
  debug, or assess.

## 4. Memory Model

| Memory type | Purpose | Primary storage/retrieval |
|---|---|---|
| Recent messages | Immediate conversational continuity | SQLite messages, chronological retrieval |
| Structured long-term memory | Durable facts, preferences, decisions, constraints, tasks, corrections | SQLite `long_term_memories` |
| Semantic structured retrieval | Paraphrase-aware access to structured memory | Secondary Chroma index |
| Document memory | Evidence from uploaded/indexed files | LangChain-Chroma |
| Previous-chat gists | Compressed episodic summaries | SQLite `chat_gists` |
| Raw message spans | Exact evidence behind a gist | SQLite messages by stable ID range |

The system does not flatten all memory into one vector store because the
sources have different ownership, update, ranking, and provenance semantics.
For example, a preference can be updated, a document chunk belongs to a file,
and a raw message span must preserve exact roles and order.

The unification happens at the retrieval boundary: every retriever emits
`MemoryCandidate`. Source semantics remain available in `source` and metadata,
so routing, reranking, budgeting, and tracing can act on them.

## 5. Routing Design

`RoutingAgent` selects which source families may be queried. It does not rank
individual candidates.

- `rule` mode is the deterministic default. It delegates to `QueryAnalyzer`
  and `RoutePlanner`.
- `llm` mode requests a structured source decision from the configured model.
- `hybrid` mode combines deterministic safety with optional model-based source
  selection.
- Invalid JSON, low confidence, missing configuration, or model errors fall
  back to the rule decision.

Routing and reranking are separate because they solve different problems:

```text
routing:   Which stores should we query?
reranking: Which returned candidates are most useful?
```

Current routing is pre-retrieval source selection. It is not full query
decomposition, iterative search, or multi-hop planning.

## 6. Reranker Design

### Deterministic scoring

The default reranker is source-aware and offline. Depending on available
metadata, its score considers:

- lexical query/content overlap;
- stable source priors;
- query-specific boosts for documents, durable memories, gists, or provenance;
- vector/retrieval scores;
- memory confidence and active status;
- recency/update information where available;
- usage and duplicate penalties where available;
- stable original-rank tie-breaking.

This logic is project-specific because a score must compare typed candidates
from different stores. It should not be described as a state-of-the-art
semantic reranker.

### Cross-encoder mode

The CrossEncoder/BGE backend scores query-candidate pairs semantically. It
reranks only a configured top-k set and combines its score with deterministic
source-aware scoring. The backend is lazy-loaded, so default startup and tests
do not download the model.

### LLM mode

The optional LLM reranker receives candidate IDs, source labels, short content,
and selected metadata. It must return validated JSON containing ranked IDs and
confidence. Unknown IDs, duplicates, malformed JSON, low confidence, missing
configuration, or model errors trigger fallback.

### Adaptive hybrid cascade

Hybrid mode follows this sequence:

```text
deterministic ranking
    -> optional CrossEncoder top-k ranking
    -> gated LLM reranking for ambiguous heterogeneous cases
    -> last valid deterministic/CrossEncoder result on failure
```

The gate can skip the LLM when the top margin is decisive, candidates share
one source, or there is no provenance/old-decision ambiguity. This controls
latency and cost while retaining the LLM option for difficult cross-source
comparisons.

Trace metadata records deterministic features, CrossEncoder scores, combined
scores, whether LLM reranking was considered or used, skip/fallback reasons,
top margins, original ranks, and final ranks.

## 7. Context Management

Retrieval can return more content than the model context should receive.
`ContextManagerAgent` delegates to `ContextBudgetAllocator` and
`ContextBuilder` to:

1. choose the applicable context profile;
2. allocate source-specific budgets;
3. include high-ranked candidates within those budgets;
4. record dropped candidates;
5. preserve recent-message chronology and prompt invariants;
6. build and validate `ContextPacket`.

Source budgets prevent one large source, especially documents or raw spans,
from consuming all context. They are deterministic approximations rather than
model-controlled prompt writing.

## 8. Memory Writing and Updating

`ShortTermMemory.update_memory_if_needed()` protects the recent window and
passes older unsummarized message batches to the LangMem-backed structured
memory updater. LangMem proposes durable memories; project-specific validation
normalizes and filters them before writing to SQLite.

Suitable records include:

- stable user preferences;
- durable user/project facts;
- decisions and constraints;
- corrections to prior memories;
- open tasks that should survive the current turn.

Temporary filler, assistant prose, unsupported inferences, vague transcript
summaries, and short-lived details should not become durable semantic memory.
Raw messages remain the source of truth for conversation history, while
structured memory is a compact, updateable representation.

The lifecycle evaluation checks `ADD`, `NOOP`, `UPDATE`, `RETRIEVE`, and
`ABSTAIN` behavior. It validates the integration contract but does not by
itself prove extraction quality for arbitrary real conversations.

## 9. Tracing and Observability

`WorkflowTrace` makes the pipeline inspectable. Depending on mode and available
components, it records:

- routing mode, decision, confidence, and fallback reason;
- active and disabled sources;
- retrieved candidate counts and metadata;
- deterministic feature contributions and scores;
- CrossEncoder model use and scores;
- LLM reranker use, confidence, skip reason, and fallback;
- source budgets and candidate inclusion/dropping;
- final context sections and prompt source;
- prompt-validation fallback reason;
- stage timings and memory-update outcome.

This matters because a wrong answer can originate from source selection,
retrieval, ranking, context truncation, generation, or memory extraction.
Tracing localizes the failure instead of treating the system as one opaque LLM
call.

## 10. Evaluation Strategy

### Structured memory evaluation

Tests deterministic cross-chat write/retrieval behavior and normalized memory
records. It supports mock mode for repeatable local/CI checks. It does not
prove real-model extraction quality.

### Memory lifecycle evaluation

Exercises `ADD`, `NOOP`, `UPDATE`, `RETRIEVE`, and `ABSTAIN` cases. Metrics
cover action correctness, retrieval hits, correct-memory use, and avoidance of
false memory. Controlled cases are regression tests, not a replacement for a
large public benchmark.

### Multi-source retrieval evaluation

Measures source selection and retrieval across recent messages, structured
memory, documents, gists, raw spans, and abstention. It exports routing and
candidate traces. It evaluates context discovery, not final prose quality.

### Generated-answer evaluation

Checks whether an answer contains expected facts, avoids forbidden claims,
uses expected sources, and abstains when required. Mock/oracle mode is
deterministic; model and replay modes are optional. It is a small controlled
end-to-end answer check, not a complete faithfulness study.

### End-to-end scenario evaluation

Exercises the orchestration sequence from routing through context construction
and answer generation using isolated fixtures and a fake model in mock mode.
It verifies component integration and trace export. Mock adapters do not prove
the latency, retrieval quality, or answer quality of production models and
stores.

### Document QA evaluation

Separately measures document hit@k over SQuAD/NQ-style subsets, supports corpus
retrieval, oracle/model answer modes, RAGAS-compatible export, and an optional
RAGAS adapter. Retrieval hit rates prove that evidence was found, not that the
final chatbot answer is faithful or useful.

Offline modes exist so normal tests do not depend on network access, API keys,
model availability, or model nondeterminism. Optional model runs provide
additional evidence but should be recorded with exact configuration.

## 11. Deterministic and Model-Based Components

| Component | Type | Default | Fallback | Offline tested? |
|---|---|---|---|---|
| QueryAnalyzer/RoutePlanner | Deterministic | Active | N/A | Yes |
| Optional LLM routing | Model-based | Off | Rule routing | Yes, mocked |
| SQLite retrieval | Deterministic | Active | Legacy state where applicable | Yes |
| Structured vector retrieval | Embedding/model-backed | Off by default | SQLite retrieval | Yes, mocked/local fixtures |
| Document retrieval | Embedding/model-backed | Preferred document path | Clear unavailable error/legacy paths where configured | Yes without downloads via fakes |
| Gist generation | Deterministic or model-backed | Disabled | No gist generated | Yes |
| Raw span lookup | Deterministic | Disabled/explicit | Empty result | Yes |
| Deterministic reranker | Deterministic | Active | Original stable ordering | Yes |
| CrossEncoder reranker | Local neural model | Off | Deterministic ranking | Yes, mocked |
| LLM reranker | Model-based | Off | Last valid ranking | Yes, mocked |
| Context budgeting/building | Deterministic | Active | Legacy prompt if packet validation fails | Yes |
| Answer generation | Model-based | Active in app | User-visible model error | Faked in evals/tests |
| LangMem extraction | Model-based | Active when update threshold is met | Reject update; do not mark messages summarized | Yes, mocked |

## 12. Configuration Guide

The exact defaults live in `src/config.py` and examples in `.env.example`.

| Variable | Purpose and current safe default |
|---|---|
| `OPENAI_API_KEY` | Credential for the configured OpenAI-compatible endpoint. |
| `OPENAI_BASE_URL` | OpenAI-compatible model endpoint. |
| `MODEL_NAME` | Default answer/model profile name. |
| `DATABASE_PATH` | SQLite database for chats, messages, memories, and metadata. |
| `ROUTING_MODE` | `rule` (default), `llm`, or `hybrid`. |
| `STRUCTURED_MEMORY_RETRIEVAL_MODE` | `sqlite` (default), `vector`, or `hybrid`. |
| `PREVIOUS_CHAT_GIST_GENERATION_ENABLED` | Disabled by default; enables automatic previous-chat gist creation. |
| `PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED` | Disabled by default; allows previous-chat gist source routing/retrieval. |
| `RAW_MESSAGE_LIMIT` | Number of recent message rows protected from memory compaction. |
| `MEMORY_UPDATE_BATCH_SIZE` | Minimum eligible batch used for structured memory updates. |
| `RAW_MESSAGE_SPAN_MAX_CHARS` | Output cap for raw-span context. |
| `RERANKER_MODE` | `deterministic` (default), `cross_encoder`, `hybrid`, or `llm`. |
| `RERANKER_CROSS_ENCODER_MODEL` | CrossEncoder model, default `BAAI/bge-reranker-v2-m3`. |
| `RERANKER_CROSS_ENCODER_TOP_K` | Number of deterministic leaders sent to CrossEncoder. |
| `RERANKER_CROSS_ENCODER_WEIGHT` | CrossEncoder contribution to combined scoring. |
| `RERANKER_HYBRID_BACKEND` | `auto`, `cross_encoder`, or `llm`; controls the hybrid cascade. |
| `RERANKER_LLM_TOP_K` | Maximum candidates sent to LLM listwise reranking. |
| `RERANKER_LLM_MIN_CONFIDENCE` | Minimum accepted LLM reranking confidence. |
| `RERANKER_LLM_AMBIGUITY_MARGIN` | Margin below which top candidates may be considered ambiguous. |
| `RERANKER_LLM_REQUIRE_CROSS_SOURCE_CONFLICT` | Requires heterogeneous top sources before ordinary LLM escalation. |
| `RERANKER_LLM_PROVENANCE_QUERIES` | Allows provenance-sensitive queries to trigger LLM consideration. |
| `LANGCHAIN_CHROMA_PERSIST_DIR` | Persistent document Chroma directory. |
| `LANGCHAIN_CHUNK_SIZE` / `LANGCHAIN_CHUNK_OVERLAP` | Document splitting configuration. |
| `EMBEDDING_MODEL_NAME` | Local embedding model used by vector-backed paths. |
| `LONG_TERM_MEMORY_CHROMA_PERSIST_DIR` | Secondary semantic index path for structured memories. |
| `DEMO_MEMORY_TRACE` | Enables demo-visible saved/retrieved memory traces; off by default. |

## 13. Design Tradeoffs

### Why not just use full chat history?

Long histories exceed context limits, increase latency and cost, and bury
relevant facts. Recent raw context, durable structured memory, and episodic
gists serve different retention needs.

### Why not just use one vector store?

One store would erase update and provenance semantics. Structured memories need
stable keys/status; raw spans need ordered message IDs; documents need file and
chunk metadata. Vector search is useful as an index, not as the only database.

### Why use typed memory?

Types let routing avoid unnecessary stores, reranking apply source-aware
features, context budgeting reserve space by source, and traces explain where
information came from.

### Why keep deterministic scoring after adding CrossEncoder/BGE?

CrossEncoders estimate semantic relevance but do not inherently understand that
an exact quote should favor raw evidence or that a durable preference should
favor structured memory. Deterministic features preserve these application
semantics and provide a no-download fallback.

### Why not use LangGraph yet?

The current flow is mostly linear and already explicit in `CoordinatorAgent`.
LangGraph would add value when the workflow needs repeated retrieval,
conditional retries, parallel branches, or durable workflow checkpoints. Adding
it now would increase dependency and debugging cost without replacing the
typed-memory contracts.

### Why not full coarse-to-fine or multi-hop retrieval now?

The current project first establishes reliable source selection, retrieval,
ranking, and context construction. Multi-hop expansion needs stopping rules,
loop controls, stronger evaluation, and more latency. The current raw-span
lookup is a useful building block but not a complete multi-hop planner.

### Why use mock evaluations in normal tests?

They make tests fast, deterministic, inexpensive, and independent of API/model
availability. They prove contracts and orchestration. Separate model-mode runs
are still required to measure real extraction and generation quality.

## 14. Limitations and Future Work

- Full coarse-to-fine and multi-hop retrieval is not implemented.
- Gist-to-raw-span expansion is explicit rather than an automatic iterative
  retrieval policy.
- Structured-memory provenance could expand source messages on demand.
- Document retrieval does not yet perform general neighbor/parent expansion.
- Current controlled datasets are small relative to LongMemEval, LoCoMo,
  PerLTQA, or large document QA benchmarks.
- There is no completed real-user study.
- Model-mode evaluation reports must be generated and versioned with exact
  endpoint/model settings.
- LangGraph may become appropriate if orchestration gains real loops, retries,
  or parallel branches.
- Memory consolidation, contradiction handling, and duplicate resolution can
  be strengthened.
- First-use local embedding and CrossEncoder models may require downloads and
  introduce startup latency.

## 15. Short Defense Scripts

### 30 seconds

This is a typed-memory RAG chatbot. It routes each query to relevant sources
such as recent messages, durable structured memory, previous-chat gists, raw
evidence, or documents. Every source returns the same `MemoryCandidate`
contract, then a source-aware reranker and context manager build a validated
`ContextPacket` for the answer model. SQLite remains the source of truth for
chat and structured memory, while Chroma provides semantic indexes. The system
is traceable and has offline evaluation for memory lifecycle, source selection,
generated answers, and end-to-end scenarios.

### 2 minutes

The project solves two related problems: document RAG and long-term
conversation memory. Instead of placing all data in one vector database, it
preserves typed sources. Recent messages give local continuity, structured
memory stores durable preferences and decisions, gists compress earlier
episodes, raw spans preserve evidence, and LangChain-Chroma retrieves document
chunks.

`RoutingAgent` selects source families before retrieval. `RetrieverDispatcher`
normalizes results into `MemoryCandidate`. `MemoryReranker` uses deterministic
source-aware features by default, with optional CrossEncoder semantic scoring
and gated LLM reranking for ambiguous cross-source cases. `ContextManagerAgent`
then allocates source budgets and builds a validated `ContextPacket`.

LangMem handles semantic extraction for structured memory, but project-specific
validation, SQLite storage, retrieval contracts, context construction, and
tracing remain under our control. The design is deliberately deterministic
where reliability matters and model-based only where semantic judgment helps.
The evaluations separate memory lifecycle, retrieval/source selection, answer
checks, and integration, so their claims remain scoped.

### 5 minutes

Start with the problem: a chat model cannot safely carry an unlimited
transcript, and document RAG alone does not maintain cross-chat preferences,
corrections, or decisions. The solution is a typed-memory architecture with a
unified candidate interface.

Walk through one turn. Chainlit calls `ChatService`, which invokes
`CoordinatorAgent`. `RoutingAgent` uses deterministic rules by default and can
optionally use a fallback-safe model policy. `RetrieverDispatcher` queries only
enabled sources. SQLite stores authoritative messages and structured memories;
Chroma provides semantic indexes for documents and optionally long-term memory.
Previous-chat gists compress episodes, while raw spans can recover exact
evidence.

All results become `MemoryCandidate` objects. A deterministic reranker compares
them using lexical relevance, source semantics, confidence, recency, and
available retrieval scores. An optional BGE CrossEncoder adds mature semantic
scoring. Hybrid mode escalates to an LLM only when top candidates are ambiguous
and heterogeneous, then validates the JSON response and falls back safely.

`ContextManagerAgent` gives each source a bounded share of context and builds
`ContextPacket`. Validation protects prompt invariants; a legacy prompt path is
retained as fallback. The answer is generated, messages are saved, and older
eligible messages can be processed by LangMem into validated durable records.

Finally, show `WorkflowTrace`: route, candidate sources, ranking features,
CrossEncoder/LLM decisions, included and dropped context, and fallback reasons.
Explain the evaluation boundaries. Offline controlled suites prove lifecycle
and integration behavior without API dependence. Document hit@k and optional
model runs add retrieval and answer evidence, but we do not claim full
multi-hop reasoning, public-benchmark coverage, or production-scale user
validation.
