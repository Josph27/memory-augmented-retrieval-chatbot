# Troubleshooting

> How-to guide. Task-oriented, practical steps.

## Chroma collection schema mismatch

**Symptoms:** `RuntimeError` or `ValueError` about dimension mismatch when starting the app. Retrieval returns zero results or crashes.

**Diagnosis:** Chroma persists collections on disk. When embedding model changes (or when switching branches that changed `EMBEDDING_MODEL_NAME`), the existing collection has embeddings with different dimensionality than the new model produces.

**Fix:**

```bash
# Remove the Chroma directory and restart — data will be re-indexed from source
rm -rf data/chroma
# Then restart the app. Re-upload documents if needed.
```

If only long-term memory vectors are affected:

```bash
rm -rf data/chroma/long_term_memory*
# Then run the rebuild script:
python scripts/rebuild_long_term_memory_index.py
```

---

## Token budget exhaustion

**Symptoms:** Answers are vague ("I don't have enough context"), retrieval trace shows many candidates but few selected, or model returns `context_length_exceeded` errors.

**Diagnosis:** Check the workflow trace for the assistant message. Look at `context_budget` and `metadata.token_accounting` in the trace.

**Fix — increase budgets:**

```bash
# Increase working memory budgets (in .env or exported):
BASE_MEMORY_BUDGET=8192          # from 4096
DOCUMENT_MEMORY_CAP=32768        # from 16384
CHAT_MEMORY_CAP=16384            # from 8192
```

**Fix — increase context window cap:**

```bash
APPLICATION_CONTEXT_CAP=262144   # matches gemma native window
```

---

## LangMem memory extraction not working

**Symptoms:** Conversations don't produce durable memories. The Memories page shows no new entries. Expected facts from a conversation are absent.

**Diagnosis:** Memory update errors are silently caught. Check the database for unprocessed messages:

```sql
-- Check how many messages are pending summarization
SELECT COUNT(*) FROM messages WHERE summarized = 0;

-- Check if any memories were actually extracted
SELECT COUNT(*) FROM long_term_memories WHERE status = 'active';
```

**Common causes & fixes:**

| Cause | Fix |
|---|---|
| Token trigger not yet met | Have a longer conversation. Memory update fires when `MEMORY_UPDATE_TRIGGER_TOKENS` (default 1000) of unsummarized text accumulates. |
| Chat model unreachable | Check `OPENAI_BASE_URL` and `OPENAI_API_KEY`. LangMem extraction uses the same model API as chat. |
| LangMem rejected all extractions | Check server logs for "langmem_no_valid_memories" — the model may have produced vague or transcript-like output. |
| Recent messages are protected | Messages within `MEMORY_RECENT_PROTECTION_TOKENS` (1500) of the latest message are never summarized. Scroll back in the chat. |
| Chat was never ended | Run "Consolidate" from the frontend, or `POST /api/chats/{chat_id}/consolidate` to force processing. |

---

## Chat not loading in browser

**Symptoms:** "Authenticating..." spinner stays forever. Chat page is blank. Messages don't load.

**Diagnosis — check the browser console:**

```javascript
// Common errors:
// 1. WebSocket connection refused
// 2. CORS errors
// 3. /login endpoint returns 401
```

**Fix — Connection:**

```bash
# Ensure the Python backend is running on port 8000
python app.py
# Should show "Your app is available at http://localhost:8000"

# Ensure the frontend dev server is running
cd braemon && npm run dev
# Should proxy to localhost:8000
```

**Fix — Auth:**

```bash
# The frontend auto-logs in with:
#   username: local
#   password: local
# Check .env:
CHAINLIT_LOCAL_USERNAME=local
CHAINLIT_LOCAL_PASSWORD=local
```

**Fix — WebSocket:** The Vite proxy must forward WebSocket to the Python backend. Check `vite.config.js`:

```js
proxy: {
  "/ws": { target: "http://localhost:8000", ws: true }
}
```

---

## Document upload stuck in "Indexing"

**Symptoms:** Upload progress bar completes, but the document never appears in the "Active" section. Status shows "Indexing" indefinitely.

**Diagnosis:**

```bash
# Check document status in SQLite
sqlite3 data/chatbot.db "SELECT id, file_name, status, error FROM document_records;"
```

| Status | Meaning |
|---|---|
| `Uploading` | File received, not yet indexed |
| `Indexing` | Indexing in progress or failed silently |
| `Ready` | Successfully indexed |
| `Failed` | Indexing error — check the `error` column |

**Fix:**

```bash
# If stuck in Uploading/Indexing — the indexing process may have crashed.
# Check server logs for traceback.
# Re-upload the file.

# If status=Failed — check the error message:
sqlite3 data/chatbot.db "SELECT error FROM document_records WHERE status='Failed';"

# Common errors:
# - "scanned PDF with no extractable text" → the PDF is image-only
# - embedding model errors → check EMBEDDING_MODEL_NAME is valid
# - Chroma write errors → check disk space and permissions
```

---

## Empty retrieval results

**Symptoms:** No `document_memory` or `structured_memory` candidates appear in traces. Answers don't reference uploaded documents.

**Diagnosis — verify Chroma has data:**

```bash
python scripts/inspect_document_memory.py
```

**Diagnosis — verify structured memories exist:**

```bash
python scripts/inspect_long_term_memory.py
```

**Fix — rebuild indexes:**

```bash
# Rebuild long-term memory vector index from SQLite records:
python scripts/rebuild_long_term_memory_index.py

# Rebuild previous-chat gists:
python scripts/rebuild_previous_chat_gists.py
```

**Fix — check routing is enabling the correct sources:**

```bash
# Set routing to verbose mode for debugging
# Check the trace's route_plan.sources to see which sources were enabled
# If document_memory is not enabled, check ROUTING_MODE and routing signals
```

---

## Model API errors

**Symptoms:** "I'm sorry, something went wrong" responses. Server logs show `OpenAIError`, `TimeoutError`, or context-window errors.

**Diagnosis — check server logs:**

```bash
# Look for errors from model_wrapper or the chat agent
grep -i "error\|timeout\|context_length" logs/*.log
```

**Fix — common model errors:**

| Error | Fix |
|---|---|
| `context_length_exceeded` | Reduce memory budgets or increase `APPLICATION_CONTEXT_CAP`. Check the trace for actual token counts. |
| `timeout` | Increase model server timeout. Check that the model server is responsive. |
| `auth_error` / `401` | Verify `OPENAI_API_KEY` and `OPENAI_BASE_URL` in `.env`. |
| `model not found` | Verify `MODEL_NAME` matches what the API server has. |

---

## LangGraph demo returns insufficient-evidence message

**Symptoms:** In `langgraph_demo` mode, the assistant returns an insufficient-evidence message (e.g. "MOCK INSUFFICIENT EVIDENCE") instead of a real answer.

**Diagnosis:** `langgraph_demo` is the default production mode and normally produces real answers via `ChatAgent` using the LangGraph-assembled context. The mock strings only appear when the LangGraph pipeline's `validate_evidence` node detects an unsatisfied evidence contract — meaning required raw spans, document citations, or structured memories are absent.

**Fix:** Check the workflow trace for which evidence requirement failed. Consider:

- The query may not have triggered the right sources — check routing.
- Required evidence may have been dropped due to token budget constraints — increase `APPLICATION_CONTEXT_CAP` or memory budgets.
- If you want to bypass evidence enforcement, switch to `ORCHESTRATION_MODE=native`.

---

## Frontend shows stale data

**Symptoms:** After creating/deleting a chat, the list doesn't update. Documents page shows old statuses. Memory vault doesn't refresh.

**Diagnosis:** The frontend fetches data on mount, not via WebSocket push. A page refresh or navigation back may be needed.

**Fix:**

1. Navigate to another page and back (triggers re-mount and re-fetch).
2. If using the Chat page, click a different chat in the sidebar, then back.
3. Hard refresh the browser (`Ctrl+Shift+R`).
4. Check Vite proxy is forwarding correctly — browser DevTools Network tab should show `/api/*` calls returning correct data.

**Known issue:** The Chainlit chat sidebar and the custom Chats page maintain separate state. Ending a chat from one may not instantly reflect in the other without navigation.

---

## Database locked / concurrent access errors

**Symptoms:** `sqlite3.OperationalError: database is locked` in server logs.

**Diagnosis:** SQLite allows only one writer at a time. If multiple processes or threads try to write simultaneously, one will block.

**Fix:**

```bash
# Check if another app.py process is running
ps aux | grep app.py

# Kill stale processes
pkill -f app.py

# Restart
python app.py
```

The database uses WAL mode by default, which allows concurrent readers while one writer is active. If you're running eval scripts simultaneously with the app, run them sequentially.
