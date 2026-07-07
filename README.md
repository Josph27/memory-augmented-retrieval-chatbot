# Memory-Augmented Retrieval Chatbot

This repository contains a TUM practical-course prototype of a multi-agent,
typed-memory chatbot. The system combines Chainlit, SQLite, Chroma, LangGraph,
and an OpenAI-compatible model endpoint to answer from recent conversation,
cross-chat memory, and uploaded documents.

The current application default is:

```env
ORCHESTRATION_MODE=langgraph_demo
```

In this mode, LangGraph builds the authoritative `ContextPacket` used by the
answer model. The older Native coordinator path remains as an internal fallback
if the graph fails.

## Implemented features

- ChatGPT-style Chainlit UI with Home, sidebar navigation, active chats, ended
  read-only chats, New Chat, End Chat, and Fork Chat.
- SQLite-backed chat/message persistence through the project data layer.
- Recent-message retrieval and LangMem-backed structured long-term memory.
- Previous-chat gist generation plus raw-message-span provenance expansion.
- Document upload, deterministic loading/chunking, Chroma indexing, and
  chat-scoped document retrieval.
- Same-turn document retrieval: uploaded files are indexed before the current
  answer is generated.
- Semantic Router v2, deterministic reranking, dynamic context budgeting, and
  `ContextPacket` validation.
- Read-only Answer Inspector showing route, sources, selected evidence,
  provenance, token diagnostics, and fallback status.
- Product Behavior, document QA, structured-memory, typed-memory, MAB, and
  LongMemEval evaluation tooling.

## Architecture at a glance

```text
Chainlit UI
-> ChatService
-> CoordinatorAgent
-> Native fallback preparation
-> LangGraph route/retrieve/expand/rerank/context/validate
-> authoritative ContextPacket
-> AnswerAgent / model endpoint
-> assistant message persistence
-> structured-memory update
```

All retrieved evidence is normalized into `MemoryCandidate` objects before
reranking and context selection. The final model prompt is assembled from a
validated `ContextPacket`.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the detailed current
architecture.

## Quick start

1. Create a local environment file:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` for your model endpoint:

   ```env
   OPENAI_API_KEY=dummy
   OPENAI_BASE_URL=http://localhost:11434/v1
   MODEL_NAME=qwen2.5:3b
   ORCHESTRATION_MODE=langgraph_demo
   ```

3. Install dependencies:

   ```bash
   uv sync
   ```

4. Start the app:

   ```bash
   uv run chainlit run app.py -w
   ```

5. Open the local URL printed by Chainlit, usually
   `http://localhost:8000`.

The runtime SQLite database defaults to `data/chatbot.db`, and Chroma defaults
to `data/chroma/`. Both are ignored local runtime state.

## Configuration

Required application variables:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Credential for the OpenAI-compatible endpoint. Use `dummy` for local endpoints that do not require a key. |
| `OPENAI_BASE_URL` | OpenAI-compatible chat-completions endpoint. |
| `MODEL_NAME` | Model ID sent to the endpoint. |
| `ORCHESTRATION_MODE` | `langgraph_demo` by default. `native` and `langgraph_shadow` are diagnostic alternatives. |

Important optional variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_PATH` | `data/chatbot.db` | SQLite path. |
| `DOCUMENT_RETRIEVAL_MODE` | `langchain_chroma` | Document retrieval backend. |
| `LANGCHAIN_CHROMA_PERSIST_DIR` | `data/chroma` | Chroma document index. |
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model for vector-backed paths. |
| `STRUCTURED_MEMORY_RETRIEVAL_MODE` | `sqlite` | Structured-memory retrieval mode: `sqlite`, `vector`, or `hybrid`. |
| `RERANKER_MODE` | `deterministic` | Reranking mode. |
| `DEMO_MEMORY_TRACE` | `0` | Optional message-level trace display. |

See [.env.example](.env.example) for the current runnable defaults.

## Normal usage

1. Create a chat from Home or the sidebar.
2. Ask normal questions; the app retrieves recent messages and structured
   memory when useful.
3. Upload a document and ask about it in the same turn or later. Retrieval is
   scoped to documents associated with the selected chat.
4. End a chat to make it read-only and flush final memory/gist processing.
5. Fork an ended chat when you want to continue from its history.
6. Use **Inspect answer** on an assistant response to see how the answer was
   produced without exposing hidden chain-of-thought.

## Supervisor demo flow

1. Start the app.
2. Create Chat A and state a durable preference or project fact.
3. End Chat A.
4. Create Chat B and ask the assistant to recall that fact.
5. Inspect the answer provenance.
6. Upload a document with a fact near the end.
7. Ask a same-turn question about that fact.
8. Inspect the selected document chunk.
9. Reopen the ended Chat A and verify it is readable but not writable.
10. Fork Chat A if continuation is required.

See [docs/DEMO_RUNBOOK.md](docs/DEMO_RUNBOOK.md) for a fuller runbook.

## Testing

Core local checks:

```bash
ORCHESTRATION_MODE=langgraph_demo uv run pytest -q
uv run ruff check .
uv run python -m compileall app.py src evals tests scripts
node --check public/product-navigation.js
git diff --check
```

Browser/Product Behavior checks:

```bash
ORCHESTRATION_MODE=langgraph_demo \
PRODUCT_E2E_HEADED=0 \
uv run pytest -q tests/e2e

ORCHESTRATION_MODE=langgraph_demo \
uv run python -m evals.product_behavior.runner
```

The browser checks require permission to bind a local port and launch the local
browser. Some restricted sandboxes block that setup before the app starts.

## Evaluation summary

- Product Behavior Benchmark: 50 product-level cases covering navigation,
  lifecycle, persistence, document behavior, failure handling, races, and
  idempotency. The intended current result is 48 passed, 2 documented failures.
- MAB answer-level evaluation: fixed held-out manifests exercise answer quality
  through the production-shaped memory pipeline.
- LongMemEval answer-level pilot: evaluates long-memory behavior with the
  project adapter and documents pilot limitations.
- Document QA and structured-memory evals provide smaller subsystem checks.

See [docs/EVALUATION.md](docs/EVALUATION.md) for commands, caveats, and result
interpretation.

## Repository structure

```text
app.py                         Chainlit entry point and UI callbacks
src/                           Application, agents, retrieval, memory, documents
src/orchestration/             LangGraph demo orchestration
src/context/                   Context budgets, selection, ContextPacket building
src/retrieval/                 Source retrievers and rerankers
src/documents/                 Document loading, splitting, lifecycle resolution
evals/                         Evaluation adapters and benchmark runners
tests/                         Unit, integration, and browser E2E tests
public/product-navigation.js   Product navigation and lifecycle UI behavior
docs/                          Canonical project documentation
```

## Known limitations

The prototype intentionally keeps some constraints visible:

- fixed local/single-user identity;
- no multi-user authorization isolation;
- no coordinated automatic Chroma deletion;
- process-local document upload locks;
- no general memory conflict-resolution UI;
- quality limitations on broad summarization, multi-hop reasoning, and some
  long-memory benchmark families.

See [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).

## Canonical docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/DATA_LIFECYCLE.md](docs/DATA_LIFECYCLE.md)
- [docs/EVALUATION.md](docs/EVALUATION.md)
- [docs/DEMO_RUNBOOK.md](docs/DEMO_RUNBOOK.md)
- [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)
