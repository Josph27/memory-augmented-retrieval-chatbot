# Known limitations

This project is a practical-course prototype. The following limitations are
current and intentional unless otherwise noted.

## Product and identity

- The app uses a fixed local user identity.
- Multi-user authorization isolation is not implemented.
- Ended chats are retained and readable, but there is no user-facing archive or
  deletion workflow.
- There is no general memory conflict-resolution UI.

## Operations and consistency

- Upload idempotency is guarded, but there is no unified operation key across
  every possible write path.
- Document upload locks are process-local.
- There is no background reconciliation job for stale document states.
- There is no coordinated automatic deletion of Chroma chunks when document
  metadata is removed or superseded.
- `LONG_TERM_MEMORY_CHROMA_PERSIST_DIR` defaults to the same path as
  `LANGCHAIN_CHROMA_PERSIST_DIR`. If a single Chroma directory holds both
  document chunks and long-term memory vectors, collection collision is
  possible.
- Memory update is LLM-backed (LangMem). When the model call fails, the error
  is caught silently — the user receives a successful answer but no new
  structured memories are extracted that turn. Unprocessed messages remain
  queued for the next successful turn.

## Orchestration

- In `langgraph_demo`, Native fallback preparation performs duplicate
  read-only retrieval work before the graph result becomes authoritative.
- Native remains necessary as a fallback and diagnostic path.

## Retrieval and answer quality

- Broad whole-document summarization is limited by single-pass retrieval and
  context selection; there is no map-reduce or hierarchical summarizer.
- Multi-hop reasoning and temporal event reasoning are not fully solved.
- MAB and LongMemEval runs show quality weaknesses in retrieval, context
  selection, and answer use on hard held-out cases.
- LongMemEval support is a pilot adapter, not an official leaderboard scorer.
- The `--cross-encoder` startup mode (mxbai DeBERTa model, ~142 MB) is
  **experimental**.  It loads a substantially heavier model than the default
  MiniLM path and has not been optimized or fully tested.  Development was
  constrained by a weak laptop; retrieval quality, latency, and correctness
  in `--cross-encoder` mode are not yet characterised.  Prefer `--hybrid`
  (the default) for reproducible evaluations and demos.
- Cross-encoder and LLM reranking are the supported reranker modes until "cross_encoder"
  is properly validated. `RERANKER_MODE` defaults to `cross_encoder` but changes
  to `hybrid` when `RERANKER_STARTUP_MODE=hybrid`.
- Token counting relies on a Gemma-specific tokenizer loaded from Hugging
  Face. On any load or tokenization error, the estimator silently falls back
  to approximate character-based counting (4 chars/token), which can cause
  significant over- or under-estimation of context usage.

## Configuration and defaults

- Only one model profile is registered: `gemma-4-31B-it`. Unknown models get a
  conservative profile with a 4096-token safe fallback and no sliding window,
  which reduces context budget accuracy for other models.
- `CURRENT_CHAT_GIST_GENERATION_ENABLED` defaults to `False`;
  `PREVIOUS_CHAT_GIST_GENERATION_ENABLED` defaults to `True`. Gists are
  orientation summaries that enable longer-context orientation without
  carrying raw evidence. Without current-chat gists, the system loses
  low-token orientation for long chats.
- The richer deterministic `SemanticRouter` (592 lines) is not wired into the
  native production path. It runs only within LangGraph orchestration modes.
  The native path uses the simpler `QueryAnalyzer` + `RoutePlanner` pipeline.

## Prompt and model compatibility

- For Qwen 3.5: structured memory is merged into the system message and
  retrieved context is prepended to the latest user message. This is a
  workaround because Qwen's chat template rejects multiple system messages.
  If the model changes to one with different template constraints, prompt
  assembly may need revisiting.

## Frontend

- Workflow traces are embedded as HTML comments (`<!--breamon-trace:...-->`)
  inside assistant message output strings. Any post-processing that strips
  HTML comments would lose trace data.
- The Documents and Memories page search inputs are present in the DOM but
  have no `onChange` handlers — they are decorative only. Filtering is not
  implemented.
- `fetchChats()` in the REST client ignores the `limit` parameter. Callers
  that pass `{ limit: 20 }` or `{ limit: 50 }` receive all chats regardless.
- `uploadDocumentFile()` in `api.js` is exported but never imported by any
  component — dead code. File upload goes through Chainlit SDK hooks instead.
- The Diagnostics page shows hardcoded "v2.4.1" as the version fallback and
  "Daemon: Running" as a static string — neither reflects actual system state.
- The auto-login flow (`POST /login` with `local`/`local`) shows
  "Authenticating..." forever on failure with no retry or error message.
- The `text-code` typography token uses Inter (not a monospace font), so
  code blocks do not visually distinguish from body text.
- `puppeteer` and `puppeteer-core` are in `dependencies` rather than
  `devDependencies` in `braemon/package.json`.

## Evaluation

- Product Behavior has two documented remaining failures:
  `PB-PERSIST-005` and `PB-FAIL-010`.
- Browser E2E validation requires local browser and localhost port access.
  Restricted sandboxes can block those tests before application startup.
