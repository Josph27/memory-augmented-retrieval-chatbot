# Demo Q&A cheatsheet

This cheatsheet is for project demos, supervisor questions, and oral-exam style
discussion. It describes the current implementation on `integration/playground-demo`.
For deeper implementation details, especially gist derivation and storage, see
`docs/SYSTEM_DETAILS.md`.

## One-sentence project pitch

This project is a Chainlit chatbot with typed memory and document RAG. A routing
agent decides which memory sources to consult, typed retrievers normalize results
into `MemoryCandidate` objects, a reranker/context manager builds a
`ContextPacket`, an answer agent responds from that packet, and the memory layer
updates durable user/project memories after the answer is saved.

## Short demo script

1. Start the app.

   ```bash
   ORCHESTRATION_MODE=langgraph_demo uv run chainlit run app.py -w
   ```

2. Create a new chat and give it a durable fact.

   ```text
   Remember that my preferred demo database is SQLite.
   ```

3. End the chat. Point out that the chat stays visible, becomes read-only, and
   is forkable.
4. Create another chat and ask:

   ```text
   What database did I prefer for the demo?
   ```

5. Use **Inspect answer** to show route, selected evidence, token accounting,
   and provenance.
6. Upload a small document and ask a same-turn question about it. Show that the
   document source is chat-scoped and appears in the Inspector.

## Current canonical configuration

| Setting | Current default | Demo answer |
| --- | ---: | --- |
| `ORCHESTRATION_MODE` | `langgraph_demo` | Live app mode. LangGraph builds the authoritative context packet; Native remains an internal fallback. |
| `ROUTING_MODE` | `rule` | Deterministic typed router. `semantic_full` exists as an experimental opt-in mode, not the default. |
| `RERANKER_MODE` | `deterministic` | Canonical reranker. CrossEncoder/LLM modes are ablation paths, not defaults. |
| `RECENT_MESSAGES_MAX_COUNT` | `32` | Maximum recent-message candidate pool for the current chat. |
| `RAW_MESSAGE_LIMIT` | `8` | Legacy fallback limit; it does not override `RECENT_MESSAGES_MAX_COUNT`. |
| `MEMORY_RECALL_BUDGET_TOKENS` | `8192` | Default retrieved-memory budget for focused memory recall. |
| `GLOBAL_SUMMARY_BUDGET_TOKENS` | `65536` | Larger budget for broad “summarize previous content” requests. |
| `GLOBAL_SUMMARY_MAX_BUDGET_TOKENS` | `131072` | Upper bound for global summary memory budget before model/window safety calculations. |
| `DOCUMENT_CHUNK_SIZE` | `1000` chars | Deterministic document chunk size. |
| `DOCUMENT_CHUNK_OVERLAP` | `150` chars | Deterministic document chunk overlap. |
| `DOCUMENT_TOP_K` | `4` | Default document retrieval candidate count. |
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace embedding model for Chroma-backed vector paths. |
| `STRUCTURED_MEMORY_RETRIEVAL_MODE` | `sqlite` | Canonical structured-memory retrieval. `vector` and `hybrid` are advanced paths. |
| `PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED` | `true` | Previous-chat gist retrieval is available when route planning enables it. |
| `PREVIOUS_CHAT_GIST_GENERATION_ENABLED` | `false` | Automatic startup-time generation for existing chats is off by default. End Chat still finalizes the selected chat through `ChatEndAction`. |

## Memory sources in plain English

| Source | What it stores | Storage | How it is retrieved | Typical use |
| --- | --- | --- | --- | --- |
| `recent_messages` | Latest raw messages in the selected active chat | SQLite `messages` | Latest-message candidate pool, then budgeted newest suffix | “What did I just say?” |
| `current_chat_span` | Raw windows from the current chat | SQLite `messages` | Lexical/raw span retrieval | Same-chat recall beyond the immediate suffix |
| `structured_memory` | Typed durable memories, such as user facts, preferences, project facts, constraints | SQLite `long_term_memories`; optional Chroma derived index in advanced modes | SQLite lexical/list retrieval by default | “What do you remember about my preferences?” |
| `previous_chat_gist` | Compact summaries of ended chats, with pointers back to message ids | SQLite `chat_gists` | Lexical gist retrieval; can expand to raw spans | “What did we discuss last time?” |
| `raw_message_span` | Raw evidence windows from previous chats | SQLite `messages` | Direct raw retrieval and gist-expanded windows | Precise cross-chat evidence |
| `document_memory` | Uploaded document chunks | Chroma vector index plus SQLite document lifecycle metadata | LangChain-Chroma similarity search scoped to the chat’s associated documents | “What does the uploaded report say?” |

## “Recent messages” Q&A

### How many messages are considered recent?

By default, up to `RECENT_MESSAGES_MAX_COUNT=32` latest messages from the
current chat can be returned by the `recent_messages` retriever.

### Are all 32 recent messages pushed into the final prompt?

No. The 32 messages are a candidate pool, not a guaranteed prompt section.
The context manager applies source budgets and selects the newest chronological
suffix that fits. It also excludes the current user query from the retrieved
recent-message section because the current query is appended separately as the
latest user message.

### Why do we keep recent messages if we also have structured memory?

They solve different problems:

- recent messages preserve exact local conversational context;
- structured memory stores durable facts extracted from older turns;
- raw spans and gists provide traceable evidence across ended chats.

### Does recent-message retrieval control structured-memory formation?

No. Answer-time recent retrieval is separate from structured-memory ingestion.
Structured-memory formation uses token-aware batches, not `RECENT_MESSAGES_MAX_COUNT`.

## Structured-memory update Q&A

### When does structured memory update?

In live chat, the intended order is:

```text
persist user message and attachments
→ route/retrieve/rerank/build ContextPacket
→ generate answer
→ persist one assistant message
→ emit answer
→ run structured-memory update synchronously
```

The online structured-memory scheduler uses:

- `MEMORY_UPDATE_TRIGGER_TOKENS=1000`
- `MEMORY_UPDATE_MAX_INPUT_TOKENS=4000`
- `MEMORY_UPDATE_MAX_MESSAGES=64`
- `MEMORY_RECENT_PROTECTION_TOKENS=1500`

That means the newest raw suffix is protected, and older eligible
conversation units are processed only after enough token volume accumulates.

### Does the memory updater process one message at a time?

No. It uses token-aware conversational units. A user message and its immediately
following assistant response are kept together where possible, and batches are
formed from the oldest eligible units.

### What happens on End Chat?

`ChatEndAction` runs the lifecycle finalization:

```text
ShortTermMemory.process_all_for_chat_end()
→ PreviousChatGistGenerator.finalize_chat()
→ mark messages summarized / gist_processed
→ mark chat inactive
```

After this, the ended chat is readable but not writable. It can be forked.

### Does the system memorize everything?

No. The structured-memory updater is supposed to extract durable facts,
preferences, project facts, constraints, decisions, and similar useful memory.
Raw messages remain in SQLite for provenance and span retrieval, but not every
message becomes a structured long-term memory row.

## Gists Q&A

### What is a gist?

A gist is a compact summary record for a chat segment. It stores:

- `gist_text`
- topics / decisions / open tasks
- source message id range
- metadata including source message ids

Gists live in SQLite `chat_gists`.

### What embedding model is used for gisting?

Gisting itself is not embedding-based.

Current-chat gist infrastructure supports an LLM JSON summarizer, but it is
disabled by default. Previous-chat finalization uses the
`PreviousChatGistGenerator`; the app’s default `ChatEndAction` finalizer uses a
deterministic extractive gist extractor unless a model-backed finalizer is
configured/injected.

Retrieving previous-chat gists is currently lexical/filtering over stored gist
text, not Chroma embedding retrieval. When a gist is relevant, the system can
expand it into raw message spans so the final answer has traceable source text.

### Then where are embeddings used?

Embeddings are used for Chroma-backed vector retrieval paths:

- uploaded document chunks through LangChain-Chroma;
- optional vector/hybrid structured long-term-memory retrieval.

The default embedding model is:

```text
sentence-transformers/all-MiniLM-L6-v2
```

## Long-term vs short-term memory

### How do we store short-term memory?

Short-term conversational memory is the raw chat transcript:

- table: SQLite `messages`;
- linked to SQLite `chats`;
- roles: `user`, `assistant`, `system`;
- flags: `summarized`, `gist_processed`;
- used for recent-message retrieval and raw span retrieval.

Short-term memory is exact and provenance-rich, but it can be too verbose to
always include fully in the prompt.

### How do we store long-term memory?

Long-term structured memory is stored separately:

- table: SQLite `long_term_memories`;
- fields include namespace, category, key, value, confidence, status, source chat
  id, and source message ids;
- default retrieval mode: `sqlite`;
- optional advanced modes: `vector` and `hybrid`, using a derived Chroma index.

Long-term memory is typed and compact. It is meant for durable facts rather than
full transcripts.

### What is `chat_memory_state`?

`chat_memory_state` is per-chat serialized structured-memory state used during
the update process. Committed durable records are also persisted in
`long_term_memories`.

### How are previous chats remembered?

Ended chats remain as raw messages. In addition, End Chat creates previous-chat
gists and marks messages as gist-processed. For a later question, the route can
enable `previous_chat_gist` and `raw_message_span`, so the answer can use both a
compact summary and exact raw evidence.

## Document RAG Q&A

### How are documents stored?

The document lifecycle is split:

- SQLite `document_records`: document id, file name, status, chunk count, errors;
- SQLite `chat_documents`: association between a chat and its documents;
- Chroma: actual chunk embeddings and chunk metadata.

Chunks are scoped through the current chat’s associated document ids before
retrieval.

### Can the system answer about an uploaded document in the same turn?

Yes. The live path persists the user message and attachments, indexes the
document once, associates it with the chat, and then routes/retrieves with the
document scope available for the answer.

### Is this a full document benchmark system?

It supports document RAG and has document QA evaluation scaffolding, but the
main MAB and LongMemEval results are conversational-memory benchmarks, not
uploaded-document RAG benchmarks.

## Routing and orchestration Q&A

### What does the router do?

The canonical router is deterministic and typed. It decides:

- intent;
- temporal scope;
- enabled sources;
- evidence requirements;
- query simplification metadata.

It is not primarily an embedding-similarity router.

### What is `semantic_full`?

`ROUTING_MODE=semantic_full` is an experimental opt-in source-expansion mode. It
does not replace the rule router by default. The default remains:

```text
ROUTING_MODE=rule
```

### What does `langgraph_demo` mean?

`ORCHESTRATION_MODE=langgraph_demo` means the LangGraph memory pipeline is the
authoritative live orchestration mode. The graph performs routing, retrieval,
reranking, context construction, and answer generation. Native remains an
internal fallback if the graph path fails.

### Does navigation or switching chats call the model?

No. Opening a persisted chat, going Home, or switching threads should only load
persisted state and render UI. Model calls happen on user message submission.

## Reranking and context Q&A

### Are retrieved candidates directly sent to the model?

No. The flow is:

```text
route
→ retrieve typed candidates
→ rerank
→ select within source/global token budgets
→ build ContextPacket
→ answer
```

### What is a `ContextPacket`?

It is the normalized final context object used by the answer path and Inspector.
It records selected candidates, dropped candidates, token accounting, section
ordering, source usage, route metadata, and model-shaped messages.

### What happens if there is too much evidence?

The context selector respects per-source budgets and the model/application
context limit. Recent messages are selected as a newest suffix. Non-recent
candidate overflow can be dropped with trace metadata explaining why.

### Why is CrossEncoder not the default?

The deterministic reranker is the canonical default because it is fast,
reproducible, and sufficient for the demo. CrossEncoder exists as an ablation
path, but it is slower and not enabled by default.

## Product/evaluation Q&A

### What should I say if asked whether the system is evaluated?

Use the layers:

- unit and integration tests for services;
- browser E2E tests for the Chainlit UI;
- Product Behavior Benchmark for end-to-end local product invariants;
- routing evaluation for route decisions only;
- document QA evaluation scaffolding;
- structured-memory evaluation support;
- MAB and LongMemEval answer-level memory evaluations.

### What are MAB and LongMemEval testing?

They mainly test conversational memory behavior: recall, cross-session memory,
fact consolidation, knowledge updates, temporal cases, and long-context memory
pressure. They are not uploaded-document RAG benchmarks.

### What does the project still struggle with?

Be honest:

- global whole-document/book summarization is not a hierarchical summarizer;
- complex multi-hop reasoning may fail even when evidence is retrieved;
- benchmark-specific output formats are handled in evaluation code, not product
  behavior;
- `semantic_full` routing remains experimental;
- optional vector/hybrid structured-memory retrieval is advanced, not canonical;
- MAB/LongMemEval are harder and noisier than the local Product Behavior suite.

## Demo-safe answers to likely supervisor questions

### “Is this really multi-agent?”

Yes, at the responsibility level. The implementation has distinct agents or
service boundaries for routing, document ingestion, retrieval dispatch, memory
retrieval, reranking, context management, answer generation, and memory update.
Some are deterministic service classes instead of free-form LLM agents because
reliability and evaluation matter.

### “Why not just put everything in one vector database?”

Because memory has different semantics. Recent raw turns, durable structured
facts, previous-chat gists, raw spans, and document chunks need different
storage, scope, lifecycle, and provenance. They are normalized only after
retrieval as `MemoryCandidate` objects.

### “How do you prevent irrelevant memory from polluting answers?”

The router chooses sources, retrievers are scoped, the reranker assigns utility,
the context selector budgets evidence, and the answer prompt instructs the model
to answer only from sufficient supplied context or say what is missing.

### “Can users inspect why an answer happened?”

Yes. The answer Inspector is read-only and shows orchestration mode, effective
context source, route/profile, selected evidence, dropped evidence diagnostics,
token accounting, document provenance, and memory update summary. It does not
show hidden chain-of-thought or allow memory edits.

### “Can ended chats still affect future answers?”

Yes. They remain readable raw transcripts, and End Chat finalizes structured
memory plus previous-chat gists. Later routes can retrieve structured memory,
previous-chat gist candidates, or raw spans from those ended chats.

### “What happens if the model says something unsupported?”

The product cannot guarantee perfect model behavior. But the pipeline preserves
route/retrieval/context traces so we can inspect whether the issue was memory
formation, retrieval, context selection, or answer use.

### “What is the most important engineering decision?”

Keeping typed memory sources separate until retrieval, then normalizing them
into `MemoryCandidate` and assembling an explicit `ContextPacket`. That makes
the system explainable and testable without collapsing everything into a black
box.
