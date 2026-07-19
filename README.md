# Memory-Augmented Retrieval Chatbot

This repository contains a TUM practical-course prototype of a multi-agent,
typed-memory chatbot. The system combines Chainlit, SQLite, Chroma, and
an OpenAI-compatible model endpoint to answer from recent conversation,
cross-chat memory, and uploaded documents.

The default orchestration mode is `native` with a fast cross-encoder reranker
(MiniLM). A quality mode (mxbai) is available via startup flag but is
**experimental** — it has not been optimized or fully tested due to the
heavy model weight and constrained development hardware.

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
Chainlit UI → ChatService → CoordinatorAgent (14-phase turn pipeline)
  ├── Routing: QueryAnalyzer → RoutePlanner → RoutingAgent (rule/hybrid)
  ├── Retrieval: RetrieverDispatcher → 7 source retrievers → GistRawSpanExpander
  ├── Reranking: MemoryReranker (deterministic + cross-encoder + optional LLM gate)
  ├── Context: ContextManagerAgent (budget → preflight → selection → assembly)
  ├── [optional] LangGraph 10-node read-only shadow/demo pipeline
  ├── Legacy context + comparison (always runs, diagnostic only)
  ├── Prompt validation → fallback gate
  ├── Answer generation via ModelWrapper (OpenAI-compatible endpoint)
  └── Memory update: LangMem extraction → SQLite long_term_memories → sqlite-vec sync
```

All retrieved evidence normalizes into `MemoryCandidate`. The final model prompt
assembles from a validated `ContextPacket` — if validation fails, the system falls
back to the legacy short-term memory path.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the detailed current
architecture.

## Quick start

1. Create a local environment file. If `.env.example` exists, copy it:

   ```bash
   cp .env.example .env
   ```

   Otherwise, create `.env` with the variables shown in step 2.

2. Edit `.env` for your model endpoint:

   ```env
   OPENAI_API_KEY=dummy
   OPENAI_BASE_URL=http://localhost:11434/v1
   MODEL_NAME=google/gemma-4-31B-it
   ```

3. Install dependencies:

   ```bash
   uv sync
   cd braemon && npm install && cd ..
   ```

4. Start the app (backend + frontend, default fast mode):

   ```bash
   uv run python startup.py -w
   ```

   Or use the quality mode (experimental — slower, not fully tested):

   ```bash
   uv run python startup.py --cross-encoder -w
   ```

5. Open the frontend at `http://localhost:5173` (backend runs on `http://localhost:8000`).

### Startup modes

| Flag | Reranker | CE model | CE weight | Use when |
| --- | --- | --- | --- | --- |
| `--hybrid` (default) | Per-source z-score CE + deterministic blend + optional LLM gate | MiniLM (130 MB) | 0.65 | Normal chat, demos |
| `--cross-encoder` | Pure raw cross-encoder scores, no normalization | mxbai (~2.2 GB) | 1.0 | Evaluation, precision retrieval |

The `startup.py` script sets `RERANKER_STARTUP_MODE` and launches Chainlit.
You can also set it directly as an env var:

```bash
RERANKER_STARTUP_MODE=cross_encoder uv run chainlit run app.py -w
```

## Frontend

The primary UI is a standalone React 18 SPA in `braemon/`. It uses the
`@chainlit/react-client` SDK to connect to the Python backend and provides
a multi-page workspace (chats, documents, memories, diagnostics, retrieval
logs). The app is optimized for this frontend — the bare Chainlit UI on
port 8000 is functional but lacks the full product experience.

See [braemon/.doc.md](braemon/.doc.md) for comprehensive frontend documentation.

To run it alongside the backend:

```bash
cd braemon
npm install
npm run dev
```

It proxies API and WebSocket traffic to the backend at `localhost:8000`.

The runtime SQLite database defaults to `data/chatbot.db`, and Chroma defaults
to `data/chroma/`. Both are ignored local runtime state.

## Configuration

Required application variables:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Credential for the OpenAI-compatible endpoint. Use `dummy` for local endpoints that do not require a key. |
| `OPENAI_BASE_URL` | OpenAI-compatible chat-completions endpoint. |
| `MODEL_NAME` | Model ID sent to the endpoint. |
| `ORCHESTRATION_MODE` | `native` (default). `langgraph_demo` and `compare` are diagnostic alternatives. |

Important optional variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `RERANKER_STARTUP_MODE` | `hybrid` | `hybrid` (fast MiniLM + deterministic) or `cross_encoder` (experimental mxbai quality). Set via `startup.py` flag or env. |
| `RERANKER_CROSS_ENCODER_MODEL` | `cross-encoder/ms-marco-MiniLM-L12-v2` | Cross-encoder model. Overridden by `RERANKER_STARTUP_MODE`. |
| `RERANKER_CROSS_ENCODER_WEIGHT` | `0.65` | Blending weight (1.0 = pure CE). Overridden by `RERANKER_STARTUP_MODE`. |
| `DATABASE_PATH` | `data/chatbot.db` | SQLite path. |
| `DOCUMENT_RETRIEVAL_MODE` | `langchain_chroma` | Document retrieval backend. |
| `DOCUMENT_TOP_K` | `18` | Number of document chunks in prompt after reranking. |
| `LANGCHAIN_CHROMA_PERSIST_DIR` | `data/chroma` | Chroma document index. |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-small-en-v1.5` | Embedding model for vector-backed paths. |
| `STRUCTURED_MEMORY_RETRIEVAL_MODE` | `hybrid` | Structured-memory retrieval mode: `sqlite`, `vector`, or `hybrid`. |
| `ROUTING_MODE` | `hybrid` | `rule` is canonical; `hybrid` optionally lets the LLM add typed retrieval sources while preserving deterministic sources. |
| `MEMORY_UPDATE_POLICY` | `scheduled` | `agentic_each_turn` makes LangMem evaluate each completed turn; `scheduled` batches by token threshold. |
| `PREVIOUS_CHAT_GIST_EXTRACTOR` | `llm` | Set to `deterministic` to use no-LLM previous-chat gists. |
| `RERANKER_MODE` | `cross_encoder` | Reranking mode: `deterministic`, `cross_encoder`, `hybrid`, or `llm`. Overridden by `RERANKER_STARTUP_MODE` — defaults to `hybrid` in practice. |
| `DEMO_MEMORY_TRACE` | `0` | Optional message-level trace display. |

See [.env.example](.env.example) for the current runnable defaults.

## Normal usage

1. Open the braemon frontend (`http://localhost:5173`).
2. Create a chat from Home or the sidebar.
3. Ask questions; the app retrieves recent messages and structured
   memory when useful.
4. Upload a document and ask about it in the same turn or later. Retrieval is
   scoped to documents associated with the selected chat.
5. End a chat to make it read-only and flush final memory/gist processing.
6. Fork an ended chat when you want to continue from its history.
7. Use **Inspect answer** on an assistant response to see how the answer was
   produced (route, sources, evidence, token diagnostics).

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
uv run pytest -q
uv run ruff check .
uv run python -m compileall app.py src evals tests scripts
node --check public/product-navigation.js
git diff --check
```

Browser/Product Behavior checks:

```bash
PRODUCT_E2E_HEADED=0 \
uv run pytest -q tests/e2e

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
startup.py                     CLI launcher with reranker mode flags
src/settings.py                Canonical configuration defaults (single source of truth)
src/config.py                  Frozen AppConfig dataclass (~60 fields)
src/database.py                SQLite adapter (10 tables, 7 migrations, fork logic)
src/model_wrapper.py           OpenAI-compatible chat client with ConnectionGuard
src/connection_guard.py        Server reachability cache with TTL
src/chat_service.py            Top-level agent assembly and turn orchestration
src/api_routes.py              21 FastAPI endpoints on Chainlit's server
src/chainlit_data_layer.py     Chainlit BaseDataLayer adapter
src/agents/                    6 agent wrappers (Coordinator, ContextManager, …)
src/core/                      Frozen dataclass contracts (MemoryCandidate, ContextPacket, …)
src/routing/                   QueryAnalyzer, RoutePlanner, RoutingAgent, SemanticRouter
src/retrieval/                 7 source retrievers, MemoryReranker, GistRawSpanExpander
src/context/                   Budget allocation, evidence selection, ContextPacket assembly
src/memory/                    Short-term, structured (LangMem), episodic (gist), sqlite-vec
src/documents/                 Loading, splitting, chunking, document registry, inspection
src/orchestration/             LangGraph 10-node read-only pipeline
src/lifecycle/                 Chat operation guard (process-local RLock)
src/actions/                   ChatEndAction, ChatForkAction
src/inspection/                Answer inspector for post-hoc observability
braemon/                       Custom React frontend (Vite, Tailwind, Chainlit SDK)
scripts/                       Operational and inspection scripts
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
- long-term memory vectors use sqlite-vec (in-process), not a standalone vector DB;
- quality limitations on broad summarization, multi-hop reasoning, and some
  long-memory benchmark families;
- `MEMORY_REPLAY_MAX_MESSAGES` has a known discrepancy: settings.py pushes 128,
  but the Python constant in `constants.py` is 2.

See [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).

## Canonical docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/DATA_LIFECYCLE.md](docs/DATA_LIFECYCLE.md)
- [docs/EVALUATION.md](docs/EVALUATION.md)
- [docs/DEMO_RUNBOOK.md](docs/DEMO_RUNBOOK.md)
- [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)
