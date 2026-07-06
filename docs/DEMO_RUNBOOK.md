# Demo Runbook

## 1. Setup Checklist

1. Confirm the branch and worktree:

   ```bash
   git status --short
   git branch --show-current
   ```

2. Install the locked project dependencies:

   ```bash
   uv sync
   ```

3. Configure a local `.env` without committing it. At minimum, model mode
   needs:

   ```env
   OPENAI_API_KEY=...
   OPENAI_BASE_URL=...
   MODEL_NAME=...
   ```

4. Check storage paths in `.env` or `.env.example`:

   - `DATABASE_PATH`
   - `LANGCHAIN_CHROMA_PERSIST_DIR`
   - `LONG_TERM_MEMORY_CHROMA_PERSIST_DIR`

5. Confirm safe defaults before a demo:

   ```env
   ROUTING_MODE=rule
   STRUCTURED_MEMORY_RETRIEVAL_MODE=sqlite
   RERANKER_MODE=deterministic
   ```

6. If showing memory traces:

   ```env
   DEMO_MEMORY_TRACE=1
   ```

7. Start Chainlit:

   ```bash
   set -a
   source .env
   set +a
   uv run chainlit run app.py
   ```

Use `-w` only during development; reloads can make a timed demo less
predictable.

## 2. Useful Commands

### Static checks

```bash
uv run python -m compileall app.py src scripts evals tests
uv run pytest -q
uv run ruff check .
```

### Structured memory and lifecycle

```bash
uv run python evals/structured_memory/run_structured_memory_eval.py --mode mock

uv run python evals/structured_memory/run_structured_memory_eval.py \
  --dataset evals/structured_memory/datasets/lifecycle_sample.jsonl \
  --mode mock
```

### Multi-source retrieval

```bash
uv run python \
  evals/multi_source_retrieval/run_multi_source_retrieval_eval.py \
  --mode mock \
  --output reports/multi_source_retrieval_eval.json
```

### Generated answers

```bash
uv run python evals/generated_answer/run_generated_answer_eval.py \
  --mode mock \
  --output reports/generated_answer_eval.json
```

Optional configured model run:

```bash
uv run python evals/generated_answer/run_generated_answer_eval.py --mode model
```

### End-to-end scenarios

```bash
uv run python evals/e2e_scenarios/run_e2e_scenarios.py \
  --mode mock \
  --output reports/e2e_scenario_report.json
```

Optional configured model run:

```bash
uv run python evals/e2e_scenarios/run_e2e_scenarios.py \
  --mode model \
  --limit 2
```

### Inspectors and maintenance

```bash
uv run python scripts/inspect_long_term_memory.py --limit 20
uv run python scripts/inspect_document_memory.py
uv run python scripts/inspect_raw_message_span.py --gist-id 1
uv run python scripts/rebuild_long_term_memory_index.py
uv run python scripts/rebuild_previous_chat_gists.py --mode deterministic
```

The document inspector reads the persistent Chroma `document_memory`
collection. Uploaded documents are globally scoped document memory; they are
not copied into SQLite structured memory. Document deletion and suppression
are not implemented.

Index a local document:

```bash
uv run python scripts/index_document_file.py README.md
```

The exact optional arguments are available with `--help`.

## 3. Demo Configurations

### Safe baseline

```env
ORCHESTRATION_MODE=langgraph_demo
ROUTING_MODE=rule
STRUCTURED_MEMORY_RETRIEVAL_MODE=sqlite
RERANKER_MODE=deterministic
PREVIOUS_CHAT_GIST_GENERATION_ENABLED=0
PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED=1
```

### Orchestration mode

The live UI does not expose orchestration selection. `LangGraph Demo` is
authoritative by default, with Native retained as the internal fallback.
Shadow compares sources, selected
candidate IDs, token use, provenance, and latency without affecting the answer.
Demo uses the graph-built ContextPacket and visibly falls back to native if the
graph fails. Graph nodes do not save messages, update memories, index
documents, or invoke lifecycle actions.

The expandable LangGraph trace shows intent, enabled sources, evidence
contract, candidate/selected/dropped counts, source budgets, estimated context
tokens, provenance validation, node timings, and fallback status. It does not
show system prompts, raw router prompts, secrets, or full database contents.

Use this to demonstrate predictable routing, existing cross-chat memory, and
document RAG without optional neural reranking. Previous-chat gist retrieval
is available by default but remains router-controlled: previous-chat queries
enable gist orientation, exact-wording requests retain a raw-span evidence
path, and casual queries do not retrieve gists.

### CrossEncoder semantic reranking

```env
RERANKER_MODE=cross_encoder
RERANKER_CROSS_ENCODER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_CROSS_ENCODER_TOP_K=10
RERANKER_CROSS_ENCODER_WEIGHT=0.65
```

Preload the model before the presentation. The first run may download weights
and take significantly longer.

### Hybrid adaptive cascade

```env
RERANKER_MODE=hybrid
RERANKER_HYBRID_BACKEND=auto
RERANKER_LLM_AMBIGUITY_MARGIN=0.15
RERANKER_LLM_REQUIRE_CROSS_SOURCE_CONFLICT=1
RERANKER_LLM_PROVENANCE_QUERIES=1
```

This can use CrossEncoder scoring and reserve LLM reranking for ambiguous
heterogeneous candidates. It requires both local reranker availability and
valid model endpoint configuration for the complete path. Fallback remains
deterministic.

### Routing

Use `ROUTING_MODE=rule` for the safest presentation. `llm` or `hybrid` routing
is optional and fallback-protected, but introduces endpoint latency and another
source of nondeterminism.

### Structured semantic retrieval

```env
STRUCTURED_MEMORY_RETRIEVAL_MODE=hybrid
```

Use only after rebuilding/checking the long-term memory vector index. SQLite
remains the source of truth and fallback.

## 4. What to Show

Every completed assistant answer has a small **Inspect answer** action. Its
read-only panel shows the authoritative orchestration mode, route, context
profile, bounded evidence counts, selected source excerpts, and recorded
provenance. Opening it never reruns retrieval or generation, and the persisted
record remains available after ending or reloading a chat.

### A. Document question

1. Index a small `.txt` or `.md` document with a distinctive fact.
2. Ask a question whose answer exists only in that file.
3. Show the document source in trace output.
4. Optionally run the document inspector.

Do not claim this proves answer faithfulness; it demonstrates the document
retrieval and integration path.

### B. Structured cross-chat memory

1. In Chat 1, state a durable explicit preference.
2. Continue until the configured memory-update eligibility threshold is met.
3. With `DEMO_MEMORY_TRACE=1`, show the saved memory record.
4. Open Chat 2 and ask for the preference.
5. Show that the retrieved candidate has `source_chat_id` from Chat 1.

Use the existing natural-flow verifier before recording:

```bash
uv run python scripts/verify_natural_long_term_memory_flow.py \
  --scenario demo-dialogue \
  --mode natural \
  --filler-turns 6
```

### C. Previous-chat gist

End Chat finalizes previous-chat gists. Retrieval is available by default and
remains intent-aware; set the capability flag to `0` for an emergency disable.
For pre-existing chats, run the deterministic rebuild and inspect its output:

```env
PREVIOUS_CHAT_GIST_GENERATION_ENABLED=1
PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED=1
```

Ask what was discussed or decided in an earlier chat. Describe the gist as
compressed episodic memory, not as exact evidence.

### D. Raw span/provenance

Use a gist with a valid source message range. Ask for exact wording or evidence,
then inspect the linked raw span. State clearly that this is an explicit
provenance drill-down, not a general automatic multi-hop loop.

### E. Fallback and trace

Show one trace that includes:

- routing mode and selected sources;
- candidate source counts;
- reranker mode and scores;
- context inclusion/dropping;
- fallback or LLM skip reason.

A useful defense point is that optional model components fail toward
deterministic behavior rather than breaking the turn.

### F. Evaluation report

Run the E2E mock report and one focused evaluation before the presentation.
Explain that mock mode proves deterministic contracts and integration, while
real model quality requires separately recorded model-mode results.

## 5. Troubleshooting

### Missing or invalid API key

Symptoms include HTTP 401, connection errors, or a clear model-configuration
message.

1. Confirm `.env` exists and is not committed.
2. Load it in the terminal:

   ```bash
   set -a
   source .env
   set +a
   ```

3. Verify the model name and base URL match the endpoint.
4. Use mock eval mode while the endpoint is unavailable.

### CrossEncoder download or cache problem

- Return to `RERANKER_MODE=deterministic` for a safe demo.
- Preload the configured model before the presentation.
- Check disk space, Hugging Face connectivity, and cache permissions.
- Do not clear working caches immediately before the demo.

### Chroma path issue

- Confirm the configured path is writable.
- Avoid pointing document and structured-memory indexes at the same collection.
- Run the appropriate inspector/rebuild script.
- If the index was built with a different embedding model, rebuild it
  consistently.

### SQLite path issue

- Confirm `DATABASE_PATH` points to the intended demo database.
- Ensure its parent directory exists and is writable.
- Inspect records before deleting/resetting anything.
- Keep a clean demo database separate from important manual-test data.

### Slow LLM reranking

- Use `RERANKER_MODE=deterministic` or `cross_encoder`.
- Reduce `RERANKER_LLM_TOP_K`.
- Keep hybrid gating enabled so decisive cases skip the LLM.
- Do not demonstrate live LLM routing and live LLM reranking simultaneously
  unless latency has been measured.

### Evaluation failure

1. Run the failing command without model mode.
2. Run its focused pytest file if available.
3. Inspect the exported JSON trace.
4. Distinguish a fixture/contract failure from missing optional dependencies.
5. Do not present old numbers as current results without rerunning them.

### No memories retrieved

- Confirm a durable record exists with `inspect_long_term_memory.py`.
- Confirm it is active and in the expected namespace.
- Check `STRUCTURED_MEMORY_RETRIEVAL_MODE`.
- Rebuild the vector index if using vector/hybrid retrieval.
- Inspect routing to ensure `structured_memory` was enabled.

### No documents indexed

- Run `scripts/index_document_file.py` directly and inspect the result.
- Confirm the extension is supported (`.txt`, `.md`, optional `.pdf`).
- Check Chroma and embedding model availability.
- Ask a document-specific question so routing activates document memory.

## 6. Safety Notes

- Never commit `.env`, API keys, tokens, or endpoint credentials.
- Do not commit local SQLite databases unless the repository explicitly treats
  one as a fixture.
- Do not commit `.DS_Store`, caches, Chroma indexes, downloaded model weights,
  or generated reports unintentionally.
- Review evaluation reports and traces for conversation or document content
  before committing them.
- Use isolated demo data. Do not delete or reset the primary database without a
  verified backup and an explicit reason.
- Before committing:

  ```bash
  git status --short
  git diff --stat
  git diff --cached --name-only
  ```
