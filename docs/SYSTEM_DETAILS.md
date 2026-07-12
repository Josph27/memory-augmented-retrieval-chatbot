# System details: demo and technical Q&A reference

This document is the implementation-level reference for demos, supervisor
questions, and oral-exam style discussion. It is intentionally more detailed
than the README and runbook. It describes the current implementation on
`integration/playground-demo` and distinguishes canonical/default behavior from
advanced or experimental paths.

## 1. System in one minute

The project is a multi-agent typed-memory RAG chatbot. “Multi-agent” here means
separate responsibility boundaries, not that every step is a free-form LLM
call. Routing, retrieval coordination, document ingestion, reranking, context
management, answer generation, lifecycle actions, and memory updates are
separate roles.

The central spine is:

```text
source retrievers
→ MemoryCandidate[]
→ reranking / evidence selection / budgeting
→ ContextPacket
→ AnswerAgent / model endpoint
→ persistence and memory update
```

The project keeps memory types separate until retrieval. It does not put all
state into one vector database. Recent chat messages, structured long-term
memory, previous-chat gists, raw message spans, and uploaded document chunks
have different storage, scope, lifecycle, and provenance.

## 2. End-to-end live pipeline

The canonical live app mode is:

```text
ORCHESTRATION_MODE=langgraph_demo
```

In this mode, LangGraph builds the authoritative `ContextPacket`. The Native
coordinator path remains available as a fallback if graph execution or packet
validation fails.

The intended live turn is:

```text
user submits message and optional attachments
→ user message is persisted in SQLite
→ attachments are persisted/indexed/associated with the selected chat
→ router creates a RoutePlan
→ retrievers load typed MemoryCandidate objects
→ gist candidates may expand into raw message spans
→ reranker ranks candidates
→ context manager selects evidence under a shared budget
→ ContextPacket is built and validated
→ answer model receives model messages derived from the ContextPacket
→ one assistant message is persisted
→ read-only answer inspection payload is persisted
→ structured-memory update runs after answer emission
```

Important write boundaries:

- user messages are persisted before retrieval;
- assistant messages are persisted once after answer generation;
- graph nodes are read-only with respect to durable memory/document writes;
- structured-memory extraction happens after the answer is saved/emitted;
- End Chat uses `ChatEndAction`, not ordinary answer-turn logic.

Main files:

- `app.py`
- `src/chat_service.py`
- `src/agents/coordinator_agent.py`
- `src/orchestration/langgraph_memory_pipeline.py`
- `src/core/contracts.py`

## 3. Core data contracts

### `MemoryCandidate`

All retrievers normalize their outputs into `MemoryCandidate`.

Typical fields include:

- `source`: typed source name such as `document_memory` or `raw_message_span`;
- `content`: text available for context selection;
- `score`: retrieval/reranking score when available;
- `record_id`: stable row/chunk/span identifier;
- `chat_id`;
- `source_message_ids`;
- `metadata`: provenance, retrieval path, document ids, span bounds, etc.

This lets heterogeneous stores feed a single reranking and context-selection
pipeline.

### `RoutePlan`

The router emits a `RoutePlan` describing:

- original query;
- intent;
- confidence;
- context profile;
- enabled/disabled source plans;
- source-specific query/filter/limit metadata;
- evidence requirements.

### `ContextPacket`

The context manager builds the final `ContextPacket`. It records:

- selected candidates;
- dropped candidates and reasons;
- source token usage;
- final prompt/model messages;
- route/context profile;
- token accounting;
- evidence-selection metadata;
- fallback and context-window diagnostics.

The answer model receives messages derived from this packet. The Answer
Inspector reads compact observability from the same traceable packet/result
data and does not expose hidden chain-of-thought.

## 4. Router

### Canonical router

The default router mode is:

```text
ROUTING_MODE=rule
```

This uses the deterministic `QueryAnalyzer` + `RoutePlanner` path. It is a
typed policy router: it detects signals such as document references,
previous-chat recall, current-chat recall, decisions, tasks, exact quotes, and
global summaries, then enables the corresponding memory sources.

It is not an embedding-similarity router. It is deterministic because routing is
a reliability-sensitive part of the evaluated pipeline.

Main files:

- `src/routing/query_analyzer.py`
- `src/routing/route_planner.py`
- `src/routing/routing_agent.py`

### Routing modes

| Mode | Default? | Calls model? | Description |
| --- | --- | --- | --- |
| `rule` | Yes | No | Canonical deterministic planner. |
| `semantic_full` | No | No | Experimental keyword/semantic source-expansion layer over the rule plan. |
| `semantic` | No | No | Deterministic Semantic Router v2 adapted into the existing `RoutePlan` schema. |
| `hybrid_semantic` | No | No | Experimental semantic-router entry point with fallback behavior. |
| `llm` | No | Yes | Structured-output LLM routing diagnostic. |
| `hybrid` | No | Sometimes | Hybrid diagnostic path that can use LLM routing with fallback. |

Invalid, unavailable, or low-confidence non-rule outputs fall back to the
deterministic rule planner.

### What `semantic_full` does

`semantic_full` is intentionally conservative. It:

1. builds the deterministic rule `RoutePlan`;
2. applies a deterministic semantic expansion backend;
3. may add sources such as `document_memory`, `previous_chat_gist`,
   `raw_message_span`, or `current_chat_span`;
4. does not remove sources selected by the rule planner;
5. records routing metadata including expansion reason/confidence.

The current implementation uses deterministic pattern matching in
`KeywordSemanticFullBackend`; it does not call embeddings or an LLM.

### Why `rule` remains default

Routing benchmark evidence shows that `semantic_full` is promising but not yet
canonical:

| Mode | Strict exact | Relaxed | Required recall | Over-retrieval |
| --- | ---: | ---: | ---: | ---: |
| `rule` | 18/120 | 75/120 | 0.667 | 0.100 |
| `semantic` | 32/120 | 48/120 | 0.600 | 0.317 |
| `semantic_full` | 18/120 | 94/120 | 0.850 | 0.125 |

`semantic_full` improved relaxed routing and required-source recall, especially
for document paraphrases and some current-chat cases. However, it still has
extra over-retrieval and weaknesses in previous/current-chat classification.
Product Behavior did not regress in the recorded A/B, but the evidence supports
keeping it experimental rather than promoting it.

Routing report:

- `artifacts/routing_eval/semantic_full_canonical_assessment_20260709T0009Z.md`

## 5. Retrieval sources

The dispatcher only invokes sources enabled by the route plan. It returns all
candidate types as `MemoryCandidate` objects.

Main file:

- `src/retrieval/retriever_dispatcher.py`

### Source summary

| Source | Canonical storage | Retrieval mechanism | When enabled | Provenance | Main limitation |
| --- | --- | --- | --- | --- | --- |
| `recent_messages` | SQLite `messages` | latest same-chat messages | always in rule route plans | message ids, role, timestamp | candidate pool; not all are included |
| `structured_memory` | SQLite `long_term_memories`; `chat_memory_state` as state/cache | SQLite lexical/list retrieval by default | default active source | memory id, category, key, source message ids | extraction quality depends on LangMem update |
| `document_memory` | Chroma chunks plus SQLite document metadata | LangChain-Chroma similarity search | document-like queries | document id, chunk index, file metadata | not a full hierarchical document summarizer |
| `previous_chat_gist` | SQLite `chat_gists` | lexical gist matching | previous-chat recall when enabled | gist id, message range, source ids | gist is lossy orientation |
| `raw_message_span` | SQLite `messages` | direct lexical raw spans or gist expansion | previous-chat recall / exact evidence | exact message ids and span bounds | lexical first-stage retrieval is limited |
| `current_chat_span` | SQLite `messages` | deterministic same-chat lexical windows | same/current-chat recall | exact message ids and span bounds | only same chat |
| `current_chat_gist` | SQLite `chat_gists` if rows exist | lexical stored-gist matching | infrastructure path, default-off for answer retrieval | gist id and message range | current-chat gist generation is disabled by default |

### `recent_messages`

Default candidate pool:

```text
RECENT_MESSAGES_MAX_COUNT=32
```

The retriever loads up to the latest 32 messages from the current chat and
normalizes each into a candidate. These are not blindly inserted into the final
prompt. The context selector includes the newest chronological suffix that fits
the active budget and excludes the current user query because it is appended
separately as the latest message.

Relevant file:

- `src/retrieval/recent_messages_retriever.py`

### `structured_memory`

Default mode:

```text
STRUCTURED_MEMORY_RETRIEVAL_MODE=sqlite
```

The SQLite path searches/list active long-term memory records across structured
namespaces:

- user namespace;
- project namespace;
- chat-local structured namespace.

Advanced modes:

```text
STRUCTURED_MEMORY_RETRIEVAL_MODE=vector
STRUCTURED_MEMORY_RETRIEVAL_MODE=hybrid
```

These use a derived Chroma index for semantic lookup, then load committed
records from SQLite. SQLite remains the durable source of truth.

Relevant files:

- `src/retrieval/structured_memory_retriever.py`
- `src/memory/long_term_store.py`
- `src/memory/long_term_vector_index.py`

### `document_memory`

Documents are retrieved by LangChain-Chroma using the configured embedding
model:

```text
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
```

Before retrieval, `DocumentRegistry` scopes the query to documents associated
with the current chat. It handles explicit filenames, single ready documents,
multiple ready documents, pending documents, and failed documents.

Relevant files:

- `src/retrieval/langchain_chroma_retriever.py`
- `src/documents/registry.py`

### `previous_chat_gist`

Previous-chat gists are stored SQLite rows. Retrieval is lexical over gist
text/topics and returns gist candidates. In a `global_summary` context, the
retriever can return gists chronologically.

Relevant file:

- `src/retrieval/previous_chat_gist_retriever.py`

### `raw_message_span`

Raw spans provide exact transcript evidence from SQLite `messages`.

They can be produced by:

- explicit message-id span lookup;
- direct lexical retrieval over inactive previous chats;
- gist-to-raw-span expansion.

Raw spans include source message ids, span bounds, anchor message ids,
retrieval path, truncation metadata, and omission markers when needed.

Relevant file:

- `src/retrieval/raw_message_span_retriever.py`

### `current_chat_span`

This source retrieves exact same-chat transcript windows around lexical hits.
It excludes the current query and returns bounded windows with message ids,
matched ids, and truncation metadata.

Relevant file:

- `src/retrieval/current_chat_span_retriever.py`

### `current_chat_gist`

This is infrastructure for stored current-chat gists. It reads existing
`current_chat_gist` rows if present. It does not generate gists and does not use
vector search. Current-chat gist generation is disabled by default.

Relevant file:

- `src/retrieval/current_chat_gist_retriever.py`

## 6. Gisting

### Short answer

Gists are not embeddings. Gists are compact text rows derived from raw chat
messages and stored in SQLite `chat_gists`.

Current default End Chat gisting is deterministic and extractive. The codebase
also supports an optional model-backed JSON gist extractor, but the visible
default End Chat path does not inject that model-backed finalizer.

### Default End Chat gist extractor

The Chainlit End Chat callback calls:

```python
ChatEndAction(database=database, memory=chat_service.memory).execute(chat_id)
```

Because no custom gist finalizer is passed, `ChatEndAction` constructs:

```python
PreviousChatGistGenerator(
    database=database,
    extractor=DeterministicPreviousChatGistExtractor(),
)
```

`DeterministicPreviousChatGistExtractor`:

1. reads a batch of raw messages;
2. finds the first user message;
3. finds the last user message;
4. creates compact text such as `Earlier user request: ... Later user request: ...`;
5. extracts a small stable keyword list;
6. returns a `ChatGistSummary`.

It does not call an embedding model, a reranker, or the answer model.

Relevant files:

- `app.py`
- `src/actions/chat_end.py`
- `src/memory/previous_chat_gist.py`

### Optional LLM gist extractor

`LLMChatGistExtractor` exists for model-backed gist creation. It calls the
configured chat model with:

- a gist-specific system prompt;
- formatted source messages with message ids;
- temperature `0.0`;
- strict JSON output requirements.

Expected JSON shape:

```json
{
  "summary": "concise paragraph",
  "topics": ["short topic"],
  "decisions": ["decision made"],
  "open_tasks": ["unfinished task"],
  "important_facts": ["fact likely to matter later"],
  "corrections": ["correction made by the user"]
}
```

Invalid, empty, or transcript-like output is rejected.

Relevant file:

- `src/memory/chat_gist_summarizer.py`

### Gist storage

SQLite table:

```text
chat_gists
```

Important columns:

- `chat_id`
- `source_type`
- `gist_text`
- `topics_json`
- `decisions_json`
- `open_tasks_json`
- `start_message_id`
- `end_message_id`
- `metadata_json`

Source raw messages are not deleted. They remain in SQLite `messages`.

### Finalization flow

At End Chat:

```text
ChatEndAction.execute(chat_id)
→ ShortTermMemory.process_all_for_chat_end(chat_id)
→ PreviousChatGistGenerator.finalize_chat(chat_id)
→ Database.mark_chat_inactive(chat_id)
```

The gist finalizer:

1. loads messages where `gist_processed = 0`;
2. processes bounded batches;
3. marks assistant-only batches processed as no-op;
4. creates gists for batches containing user messages;
5. inserts rows in `chat_gists`;
6. marks source messages `gist_processed = 1`.

If finalization fails, the chat is not marked inactive as if it succeeded.

### Gist retrieval and expansion

Gist retrieval is lexical. A selected gist can then be expanded back into raw
message spans through `GistRawSpanExpander`, using the gist’s chat id and source
message range/source ids.

This is why gists are orientation, not final proof. The answer path can use the
gist to find the right episode, then use raw transcript spans as exact evidence.

Relevant files:

- `src/retrieval/previous_chat_gist_retriever.py`
- `src/retrieval/gist_raw_span_expander.py`

## 7. Structured memory

### What structured memory stores

Structured memory stores durable facts as typed records, not full transcript
summaries.

Allowed categories include:

- `user_facts`
- `project_facts`
- `decisions`
- `corrections`
- `open_tasks`
- `preferences`
- `constraints`
- `procedural`

Each record has a category, key, value, confidence, status, and source message
ids.

SQLite table:

```text
long_term_memories
```

Compatibility/state table:

```text
chat_memory_state
```

### How structured memory is formed

`ShortTermMemory` selects unsummarized raw messages in chronological
conversation units. A user message and its immediately following assistant
response stay together where possible. The selected batch is sent to
`LangMemStructuredMemoryState`, which normalizes LangMem outputs into project
memory records and persists them through `SQLiteLongTermMemoryStore`.

Canonical online scheduler defaults:

```text
MEMORY_UPDATE_TRIGGER_TOKENS=1000
MEMORY_UPDATE_MAX_INPUT_TOKENS=4000
MEMORY_UPDATE_MAX_MESSAGES=64
MEMORY_RECENT_PROTECTION_TOKENS=1500
```

Offline replay/chat-end defaults:

```text
MEMORY_REPLAY_TRIGGER_TOKENS=4000
MEMORY_REPLAY_MAX_INPUT_TOKENS=8000
MEMORY_REPLAY_MAX_MESSAGES=128
```

Main files:

- `src/memory/short_term.py`
- `src/memory/langmem_structured.py`
- `src/memory/long_term_store.py`

### Why SQLite is canonical

`STRUCTURED_MEMORY_RETRIEVAL_MODE=sqlite` is the default because:

- SQLite is the durable source of truth;
- retrieval is deterministic and easy to inspect;
- tests and demo behavior are stable;
- vector/hybrid retrieval adds optional derived-index complexity.

Vector and hybrid modes are advanced paths. They index active long-term-memory
records into Chroma and fall back to SQLite behavior if the vector backend is
unavailable or returns no useful active records.

### Limitations

- Memory extraction depends on model/LangMem quality.
- Not every raw message becomes a structured memory.
- Role-less benchmark histories are not personal conversations; the MAB
  adapter marks structured memory as not applicable for those histories.
- There is no user-facing memory conflict-resolution UI.

## 8. Document RAG

### Upload lifecycle

Document upload does:

```text
claim upload operation
→ create document_records row
→ associate document with chat in chat_documents
→ mark Indexing
→ load file text
→ split and index chunks into Chroma
→ mark Ready or Failed
```

Same-turn uploads are indexed before the answer is generated, so the current
question can retrieve the just-uploaded document.

Relevant files:

- `src/chat_service.py`
- `src/agents/document_ingestion_agent.py`
- `src/documents/loaders.py`
- `src/documents/registry.py`
- `src/retrieval/langchain_chroma_retriever.py`

### Supported loading

Supported file types:

- `.txt`
- `.md`
- `.pdf`

PDF loading uses `pypdf` when available, then PyMuPDF as fallback.

### Chunking and indexing

Config defaults:

```text
DOCUMENT_CHUNKER=custom
DOCUMENT_CHUNK_SIZE=1000
DOCUMENT_CHUNK_OVERLAP=150
DOCUMENT_TOP_K=4
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
LANGCHAIN_CHROMA_PERSIST_DIR=data/chroma
```

The document loader creates plain text. The Chroma retriever uses
LangChain/Chroma and HuggingFace embeddings. SQLite stores document lifecycle
metadata and chat associations; Chroma stores embedded chunks.

Important distinction:

- SQLite says which documents exist, their status, and which chat can use them.
- Chroma stores the vectorized chunks used for retrieval.

### Document scope

Document retrieval is chat-scoped. `DocumentRegistry` resolves the current
query against documents associated with the selected chat:

- explicit filename → that document;
- one ready associated document → that document;
- multiple ready documents with implicit reference → ambiguity error;
- pending document → not-ready error;
- failed document → failure message.

This prevents an answer in one chat from accidentally retrieving another chat’s
uploaded document.

### Document RAG limitations

- There is no map-reduce or hierarchical summarizer.
- Whole-document summarization is single-pass context selection.
- The current document QA evaluation is a subsystem regression signal, not a
  broad leaderboard-style RAG benchmark.
- Chroma chunk deletion/suppression is not exposed as a user-facing workflow.

## 9. Reranking and context selection

### Default reranker

Default:

```text
RERANKER_MODE=deterministic
```

The deterministic reranker uses explainable features:

- lexical overlap;
- source boost;
- existing semantic/similarity scores from retrievers;
- importance/confidence;
- recency;
- usage count;
- source priority;
- status/redundancy penalties.

Relevant file:

- `src/retrieval/reranker.py`

### Advanced reranker modes

| Mode | Status |
| --- | --- |
| `cross_encoder` | Advanced ablation. Loads sentence-transformers CrossEncoder only when selected. |
| `llm` | Diagnostic model-backed reranking. |
| `hybrid` | Diagnostic hybrid path. |

CrossEncoder default model setting:

```text
RERANKER_CROSS_ENCODER_MODEL=BAAI/bge-reranker-v2-m3
```

CrossEncoder ablation summary from project docs:

- first-stage candidate recall did not change;
- final context inclusion improved by two cases in the relevant ablation;
- runtime was much higher;
- therefore it is not recommended as the default.

### Context selection

The context manager:

1. resolves model/context window;
2. computes fixed prompt overhead;
3. computes available memory budget;
4. preflights required evidence;
5. resolves route-specific working budget;
6. selects evidence with `EvidenceConstrainedContextSelector`;
7. builds the final `ContextPacket`;
8. verifies hard input budget.

Canonical budgets:

```text
BASE_MEMORY_BUDGET=4096
MEMORY_RECALL_BUDGET_TOKENS=8192
CHAT_MEMORY_CAP=8192
DOCUMENT_MEMORY_CAP=16384
MULTI_SCOPE_MEMORY_CAP=16384
LONG_DOCUMENT_MEMORY_CAP=32768
GLOBAL_SUMMARY_BUDGET_TOKENS=65536
GLOBAL_SUMMARY_MAX_BUDGET_TOKENS=131072
GLOBAL_SUMMARY_RESERVED_TOKENS=4096
RAW_SPAN_OVERLAP_THRESHOLD=0.7
```

The latest user message is included exactly once at the end of the prompt.
Recent-message candidates matching the current query are excluded from the
retrieved recent-message section.

### Candidate vs selected context

Retrieved candidates are not automatically selected. A source can retrieve
several candidates and the selector may drop some because of:

- disabled source;
- duplicate content;
- overlapping raw span;
- insufficient relevance;
- budget limit;
- hard input overflow;
- latest user message duplicate.

The Inspector and trace metadata expose selected and dropped candidates.

### Global summary behavior

For `context_profile=global_summary`, the selector uses larger budgets and a
chronological coverage strategy. If all gists/raw spans fit, it keeps them
chronologically. If not, it prioritizes beginning, end, and middle coverage
before filling remaining regions.

This improves broad coverage but is still not a hierarchical summarization
system.

## 10. Config surface

### Required runtime variables

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Credential for the OpenAI-compatible model endpoint; can be `dummy` for local endpoints. |
| `OPENAI_BASE_URL` | OpenAI-compatible chat completions base URL. |
| `MODEL_NAME` | Model id passed to the endpoint. |

### Canonical defaults

| Variable | Default | Role |
| --- | --- | --- |
| `ORCHESTRATION_MODE` | `langgraph_demo` | Live app orchestration. |
| `ROUTING_MODE` | `rule` | Canonical deterministic route planner. |
| `RERANKER_MODE` | `deterministic` | Canonical candidate reranker. |
| `STRUCTURED_MEMORY_RETRIEVAL_MODE` | `sqlite` | Canonical structured-memory retrieval. |
| `DATABASE_PATH` | `data/chatbot.db` | SQLite state. |
| `LANGCHAIN_CHROMA_PERSIST_DIR` | `data/chroma` | Chroma document/vector state. |
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | Chroma-backed embedding model. |

### Advanced and diagnostic options

| Variable | Status |
| --- | --- |
| `ROUTING_MODE=semantic_full` | Experimental deterministic source expansion. |
| `ROUTING_MODE=semantic` / `hybrid_semantic` | Experimental Semantic Router v2 entry points. |
| `ROUTING_MODE=llm` / `hybrid` | Model-backed routing diagnostics. |
| `RERANKER_MODE=cross_encoder` / `llm` / `hybrid` | Ablation/diagnostic rerankers. |
| `STRUCTURED_MEMORY_RETRIEVAL_MODE=vector` / `hybrid` | Advanced structured-memory vector retrieval. |
| `DEMO_MEMORY_TRACE=1` | Debug/demo tracing. |

### Compatibility seams and aliases

| Variable | Current interpretation |
| --- | --- |
| `DOCUMENT_RETRIEVAL_MODE` | Compatibility seam. The real product backend is `langchain_chroma`; unsupported values fall back. |
| `SUMMARY_BATCH_SIZE` | Older alias/fallback for memory batch sizing. |
| `LANGCHAIN_CHUNK_SIZE` / `LANGCHAIN_CHUNK_OVERLAP` | Older LangChain retriever chunk controls; canonical public names are `DOCUMENT_CHUNK_SIZE` and `DOCUMENT_CHUNK_OVERLAP`. |

Do not present compatibility seams as normal demo tuning knobs.

## 11. Evaluation layers

### Repository validation

Purpose: unit/integration coverage for services, agents, retrieval, memory,
documents, UI helpers, and evaluation utilities.

Typical command:

```bash
uv run pytest -q
```

### Browser E2E

Purpose: real Chainlit browser behavior: Home, sidebar, active/ended chats,
lifecycle controls, uploads, and Inspector UI.

Typical command:

```bash
ORCHESTRATION_MODE=langgraph_demo PRODUCT_E2E_HEADED=0 uv run pytest -q tests/e2e
```

### Product Behavior

Purpose: 50 product-level oracle cases for navigation, lifecycle, persistence,
documents, failure handling, races, and idempotency.

Expected current result:

```text
48 passed
2 documented failures
0 errors
0 not executed
```

Known remaining failures:

- `PB-PERSIST-005`: multi-user isolation is outside the fixed-local-user demo
  scope.
- `PB-FAIL-010`: cross-operation idempotency beyond upload remains future work.

### Routing evaluation

Purpose: evaluate routing only, without retrieval, reranking, answer generation,
judging, MAB, or LongMemEval.

Dataset:

```text
evals/routing/datasets/routing_curated_v1.jsonl
```

It has 120 curated cases across:

- document retrieval;
- document paraphrases;
- previous-chat recall;
- structured-memory recall;
- current-chat recall;
- general/no specialized retrieval.

Metrics include strict exact accuracy, relaxed accuracy, required-source recall,
over-retrieval rate, per-source precision/recall/F1, category accuracy, and
case-level improvements/regressions.

### MAB answer-level evaluation

MemoryAgentBench mainly tests conversational memory, not uploaded-document RAG.
Task families include RULER QA2, EventQA, FactConsolidation, TTL/Banking77,
DetectiveQA, and InfBench summarization.

Current held-out summary from docs:

```text
semantic valid:        10 / 27
semantic conservative: 10 / 33
official metric:       12 / 33
```

MAB is useful for diagnosing memory formation, retrieval, context selection,
answer use, and output-format issues. It is not proof that uploaded-document
RAG is strong or weak.

### LongMemEval pilot

LongMemEval tests long-session conversational memory. The local adapter is a
project pilot, not an official leaderboard scorer.

Current pilot summary from docs:

```text
semantic valid:        12 / 16
semantic conservative: 12 / 19
official pilot metric: 10 / 19
```

It covers single-session recall, multi-session recall, temporal cases,
knowledge updates, preferences, and insufficient-evidence behavior.

### Document QA

Document QA is a smaller document retrieval/grounding subsystem check over
local fixtures/subsets. It is valuable for regressions, but it is not yet a full
RAG benchmark.

### Structured-memory and typed-memory evals

These are controlled internal checks for memory extraction, retrieval,
source-selection, and answer-grounding behavior. They complement MAB/LongMemEval
but do not replace answer-level evaluation.

## 12. Likely supervisor questions and precise answers

### Why not one vector store?

Because the memory types have different semantics. Recent messages are exact
transcript; structured memory is typed durable facts; gists are compact
episode orientation; raw spans are exact provenance; documents are chunked
external content. They need different lifecycle and scope rules. The system
normalizes them only after retrieval as `MemoryCandidate` objects.

### What is the document chunk size?

Default public document chunking is:

```text
DOCUMENT_CHUNK_SIZE=1000
DOCUMENT_CHUNK_OVERLAP=150
DOCUMENT_TOP_K=4
```

The default embedding model for Chroma-backed vector paths is:

```text
sentence-transformers/all-MiniLM-L6-v2
```

### How many recent messages are considered?

The recent-message candidate pool is:

```text
RECENT_MESSAGES_MAX_COUNT=32
```

Those 32 messages are candidates, not guaranteed prompt content. The context
selector includes the newest suffix that fits the current budget.

### Are gists embeddings?

No. Gists are text summaries/extracts stored in SQLite `chat_gists`. Current
previous-chat gist retrieval is lexical, and gist expansion uses SQLite message
ids to recover raw spans.

### Which model summarizes gists?

In the default visible End Chat path, no model summarizes previous-chat gists.
The system uses `DeterministicPreviousChatGistExtractor`. The optional
`LLMChatGistExtractor` can use the configured chat model to produce strict JSON
gists, but that is not the default End Chat finalizer.

### How do you avoid duplicate writes?

Writes are separated from graph read steps. User message persistence,
assistant message persistence, document upload claims, structured-memory
updates, and End Chat finalization happen in explicit service/lifecycle paths.
Graph retrieval/context nodes are read-only. Document upload also uses
operation records for idempotent upload handling.

### How do you know memory is grounded?

Every durable memory candidate and raw evidence candidate carries provenance:
source message ids, source chat id, document id/chunk metadata, gist id, or span
bounds. The Answer Inspector shows selected evidence and dropped evidence. The
system keeps raw messages instead of trusting only summaries.

### What is the reranker?

The canonical reranker is deterministic. It scores candidates using lexical
overlap, source match, retriever scores, confidence/importance/recency,
usage/status features, and source priorities. CrossEncoder and LLM rerankers
exist only as advanced ablations.

### Why not CrossEncoder by default?

Project ablation evidence showed no first-stage candidate recall improvement,
only two extra context-inclusion successes, and much higher runtime. For a
reliable demo, deterministic reranking remains the better default.

### What does the router do?

It creates the `RoutePlan`: intent, context profile, enabled sources, source
filters/limits, and evidence requirements. The default router is deterministic
and typed, not an embedding router.

### Why is `semantic_full` not default?

It improves relaxed routing from 75/120 to 94/120 and required-source recall
from 0.667 to 0.850 in the routing benchmark, with no recorded Product Behavior
regression. But it still adds some over-retrieval and has remaining
current/previous-chat weaknesses. The evidence says promising but experimental.

### Does MAB test document RAG?

No. MAB mainly tests conversational memory over replayed histories. It is not an
uploaded-document RAG benchmark.

### What does Product Behavior test?

It tests product invariants: Home/sidebar behavior, New Chat, End Chat, Fork
Chat, active/ended chat state, persistence, document upload behavior, failure
handling, race behavior, and idempotency cases.

### What are the two known Product Behavior failures?

- `PB-PERSIST-005`: multi-user isolation is outside the current fixed-local-user
  scope.
- `PB-FAIL-010`: cross-operation idempotency beyond upload is future work.

### What are current limitations?

- fixed local/single-user identity;
- no user-facing memory conflict-resolution UI;
- no map-reduce/hierarchical summarization;
- multi-hop and temporal reasoning remain hard;
- MAB/LongMemEval quality is mixed on hard held-out cases;
- LongMemEval support is pilot-level;
- document QA is not yet a broad RAG benchmark;
- advanced vector/hybrid and semantic routing modes are not canonical defaults.

### What is the strongest engineering point?

The project keeps memory sources typed and inspectable, then normalizes them
into `MemoryCandidate` and `ContextPacket`. That makes the chatbot easier to
debug, evaluate, and explain than a single opaque retrieval bucket.

## 13. Files to cite during Q&A

Architecture and docs:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_LIFECYCLE.md`
- `docs/EVALUATION.md`
- `docs/KNOWN_LIMITATIONS.md`
- `docs/DEMO_RUNBOOK.md`

Runtime config:

- `.env.example`
- `src/config.py`

Routing:

- `src/routing/query_analyzer.py`
- `src/routing/route_planner.py`
- `src/routing/routing_agent.py`
- `src/routing/semantic_router.py`

Retrieval:

- `src/retrieval/retriever_dispatcher.py`
- `src/retrieval/recent_messages_retriever.py`
- `src/retrieval/structured_memory_retriever.py`
- `src/retrieval/langchain_chroma_retriever.py`
- `src/retrieval/previous_chat_gist_retriever.py`
- `src/retrieval/raw_message_span_retriever.py`
- `src/retrieval/current_chat_span_retriever.py`
- `src/retrieval/gist_raw_span_expander.py`
- `src/retrieval/reranker.py`

Memory:

- `src/memory/short_term.py`
- `src/memory/langmem_structured.py`
- `src/memory/long_term_store.py`
- `src/memory/previous_chat_gist.py`
- `src/memory/chat_gist_summarizer.py`

Documents:

- `src/documents/loaders.py`
- `src/documents/splitters.py`
- `src/documents/registry.py`
- `src/agents/document_ingestion_agent.py`

Context:

- `src/context/dynamic_budget.py`
- `src/context/evidence_selector.py`
- `src/context/context_builder.py`
- `src/agents/context_manager_agent.py`

Lifecycle:

- `src/actions/chat_end.py`
- `src/actions/chat_fork.py`

Evaluation:

- `docs/EVALUATION.md`
- `evals/product_behavior/`
- `evals/routing/`
- `evals/document_qa/`
- `evals/mab_answer_eval/`
- `evals/longmemeval_answer_eval.py`
- `evals/structured_memory/`
