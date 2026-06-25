# memory-augmented-retrieval-chatbot

First runnable MVP for a memory-enabled chatbot prototype.

The app uses Chainlit for the browser chat UI, Python for backend logic, SQLite for persistent chat/message storage, LangChain-Chroma for document retrieval, and an OpenAI-compatible chat completions wrapper.

## Features

- Browser chat UI with Chainlit
- Chainlit model profiles for selecting a model before a new chat
- SQLite-backed Chainlit thread history through `SQLiteChainlitDataLayer`
- OpenAI-compatible model wrapper with one `chat(messages)` method
- Local/free model defaults for Ollama-compatible endpoints
- SQLite tables for chats, messages, long-term memories, compatibility memory
  state, document metadata/chunks, and chat gists
- Recent-message memory plus LangMem-backed structured long-term memory
- Document memory through LangChain-Chroma
- Production-shaped prompt assembly through `ContextPacket`, with legacy
  `ShortTermMemory` prompt fallback
- Demo/debug memory tracing with `DEMO_MEMORY_TRACE=1`
- Dockerfile with persistent `data/` mount support

## Local Model Defaults

The default environment targets Ollama's OpenAI-compatible API:

```env
OPENAI_API_KEY=dummy
OPENAI_BASE_URL=http://localhost:11434/v1
MODEL_NAME=qwen2.5:3b
```

Example Ollama setup:

```bash
ollama pull qwen2.5:3b
ollama serve
```

## Local Setup With uv

`pyproject.toml` with `uv` is the main dependency workflow for this project.
`requirements.txt` is a minimal fallback and is not the authoritative list of
optional RAG/evaluation dependencies.

```bash
cp .env.example .env
uv sync
uv run chainlit run app.py -w
```

Open the local URL printed by Chainlit, usually `http://localhost:8000`.

The SQLite database is created at `data/chatbot.db` by default. The database file is ignored by git because it is runtime state.

## Short-Term Memory

Current chat memory is built from three related parts:

- The most recent raw messages from `messages`
- Structured long-term memories stored in `long_term_memories`
- A compatibility mirror in `chat_memory_state`

Raw messages remain the source of truth. The JSON memory state is a derived cache that can be regenerated later from `messages` if needed.

Structured memory extraction/consolidation is LangMem-backed. LangMem produces
typed semantic memories, and the app normalizes them into SQLite
`long_term_memories` plus the existing `chat_memory_state.memory_json`
compatibility format.

`StructuredMemoryRetriever` reads the namespace/key long-term store first. If
no active long-term records are available, it falls back to `chat_memory_state`.
The default namespace is stable until real user/project IDs are available, so
memory can be reused across chats.

Final chat prompts are assembled through the production-shaped `ContextPacket`
path. The current active sources are `recent_messages`, `structured_memory`, and
`document_memory` for document-like queries. Current-chat chunks and
previous-chat memory are still disabled/stubbed. If the `ContextPacket` is
invalid, the coordinator falls back to the legacy `ShortTermMemory` prompt
messages.

The current schema for `chat_memory_state.memory_json` stores typed memory records:

```json
{
  "memories": [
    {
      "id": "user_facts:name",
      "category": "user_facts",
      "key": "name",
      "value": "Keming",
      "source_message_ids": [12],
      "confidence": 0.95,
      "status": "active"
    }
  ]
}
```

The older custom JSON-operation updater is deprecated compatibility code. The current primary path
uses LangMem's `create_memory_manager` with a project schema, then applies
project-specific validation such as category checks, source-message ID checks,
transcript-like output rejection, vague-memory rejection, and lexical source
support before writing both the long-term store and the compatibility mirror.

Supported memory categories are `user_facts`, `project_facts`, `decisions`, `corrections`, `open_tasks`, `preferences`, and `constraints`.

The MVP policy keeps the latest `RAW_MESSAGE_LIMIT` messages raw. Older unprocessed messages update structured memory only when at least `MEMORY_UPDATE_BATCH_SIZE` eligible messages exist. After a batch is processed, those message rows are marked with `summarized = 1`, so they are not processed again. The column name is historical; it now means "processed into the derived memory cache."

This is intentionally based on fixed message counts for now. The memory module accepts a future `token_budget` parameter so the selector can later be replaced or extended with token-budget-based context selection.

## Document Memory

Document memory currently supports:

- local file loading for `.txt` and `.md`, with optional `.pdf` support when a
  PDF library is installed
- LangChain recursive splitting in the primary Chroma indexing path
- LangChain-Chroma document retrieval as the primary runtime backend
- legacy/compatibility SQLite `documents`, `document_chunks`, and
  `document_chunk_embeddings` paths
- `DocumentIngestionService.ingest_text_document(...)` for the SQLite
  compatibility path

Document-like questions enable `document_memory` and retrieved chunks flow
through:

```text
LangChainChromaRetriever
-> RetrieverDispatcher
-> MemoryReranker
-> ContextBudgetAllocator
-> ContextBuilder
-> ContextPacket
```

Document RAG configuration:

- `DOCUMENT_CHUNKER=custom|langchain_recursive`
- `DOCUMENT_CHUNK_SIZE=1000`
- `DOCUMENT_CHUNK_OVERLAP=150`
- `DOCUMENT_RETRIEVAL_MODE=langchain_chroma`
- `LANGCHAIN_CHROMA_PERSIST_DIR=data/chroma`
- `LANGCHAIN_CHUNK_SIZE=1000`
- `LANGCHAIN_CHUNK_OVERLAP=150`
- `EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2`
- `DOCUMENT_TOP_K=4`

Defaults keep `DOCUMENT_RETRIEVAL_MODE=langchain_chroma` so document RAG uses
LangChain's Chroma integration when dependencies and the embedding model are
available. If `DOCUMENT_RETRIEVAL_MODE` is set to another value, the dispatcher
logs a warning and uses LangChain-Chroma. `DOCUMENT_CHUNKER=custom` remains
available for SQLite chunk storage. `DOCUMENT_CHUNKER=langchain_recursive` uses
LangChain's `RecursiveCharacterTextSplitter` when `langchain-text-splitters`
or LangChain is installed; if unavailable, ingestion falls back to the custom
paragraph splitter and records fallback metadata on chunks.

Index a local file into the LangChain-Chroma document backend without starting
the Chainlit UI:

```bash
uv run python scripts/index_document_file.py tests/fixtures/docs/sample_report.txt
```

Supported loader formats are `.txt`, `.md`, and `.pdf` when either `pypdf` or
PyMuPDF is installed. Loaded-file metadata preserves file path, file name,
extension, loader name, and PDF page count when available.

## Manual Memory Verification

Start the app and send messages like:

- `my name is Keming`
- `my project uses Chainlit and SQLite`
- `no, Keming is my name, not the assistant's name`

Send enough turns to create at least 6 older messages outside the latest 8-message raw window. Then inspect SQLite:

```bash
sqlite3 data/chatbot.db
```

Inside SQLite:

```sql
SELECT * FROM chat_memory_state;
SELECT id, role, summarized, content FROM messages ORDER BY id;
```

Expected result:

- A row exists in `chat_memory_state` after the memory update threshold is reached
- `memory_json` contains active records such as `user_facts.name`, not copied `user:` / `assistant:` transcript text
- Older messages included in the memory update have `summarized = 1`
- The newest `RAW_MESSAGE_LIMIT` messages remain available as raw messages
- Already processed rows are not processed again on later turns

Exit SQLite with:

```sql
.quit
```

## Running Short-Term Memory Evals

The eval script runs controlled current-chat conversations against a temporary SQLite database. It verifies that target facts leave the recent raw-message window and are still available through structured memory.

Start your local model server first:

```bash
ollama serve
```

Then run:

```bash
uv run python evals/test_short_term_memory.py
```

The script prints each test name, expected answer, actual answer, whether the fact appeared in structured memory, whether it was outside the recent raw window, and a final `Passed X/Y tests` summary.

## Verifying Natural Cross-Chat Memory

Use this script to verify the real wiring for the demo flow:

1. Chat 1 receives a memory-bearing message.
2. Additional turns push that message outside the recent raw window.
3. Normal turn processing runs `update_memory_if_needed`.
4. LangMem-backed structured memory writes to `long_term_memories`.
5. Chat 2 retrieves structured memory from shared namespaces.

Fast wiring check (simulated Chat 1 fillers, real memory update/retrieval):

```bash
uv run python scripts/verify_natural_long_term_memory_flow.py --mode staged --filler-turns 6 --skip-chat2-answer
```

Full natural-turn demo check (real ChatService turns):

```bash
uv run python scripts/verify_natural_long_term_memory_flow.py --mode natural --filler-turns 6
```

To show saved/retrieved memory in the Chainlit UI during a screen recording,
enable demo trace mode before starting the app:

```bash
set -a
source .env
set +a
export DEMO_MEMORY_TRACE=1
uv run chainlit run app.py -w
```

Demo flow:

1. Chat 1: say a durable preference, for example that you prefer mature,
   stable open-source libraries over custom infrastructure.
2. Continue about 6 turns so the first message leaves the recent raw window.
3. Observe `🧠 Long-term memory saved` in the UI after the memory update.
4. Start Chat 2 and ask: `What preferences do I have for this memory chatbot project?`
5. Observe `🔎 Long-term memory retrieved`, including the source chat ID and
   source message IDs, then the assistant answer using that memory.

Inspect the long-term memory store directly:

```bash
uv run python scripts/inspect_long_term_memory.py
uv run python scripts/inspect_long_term_memory.py --chat-id demo-chat-1 --limit 20
```

Expected success signals in output:

- `long_term_memories_count` greater than `0`
- `chat2_structured_candidates_count` greater than `0`
- `verification_summary extraction_ran=True long_term_written=True chat2_retrieved=True`

If it fails, check `OPENAI_BASE_URL`, `MODEL_NAME`, and endpoint availability.

## Local Setup With pip

The `pip` path is a minimal fallback. Prefer the `uv` workflow above because
`pyproject.toml` includes the current LangChain, LangMem, Chroma, and
evaluation dependencies.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
chainlit run app.py -w
```

## Docker

Build the image:

```bash
docker build -t memory-chatbot .
```

Run it with a persistent database directory:

```bash
docker run --rm -p 8000:8000 \
  -v "$PWD/data:/app/data" \
  -e OPENAI_API_KEY=dummy \
  -e OPENAI_BASE_URL=http://host.docker.internal:11434/v1 \
  -e MODEL_NAME=qwen2.5:3b \
  memory-chatbot
```

Open `http://localhost:8000`.

On Linux, `host.docker.internal` may need extra Docker networking configuration, or you can point `OPENAI_BASE_URL` at a reachable model server URL.

## Project Structure

```text
app.py                  Chainlit entrypoint
src/config.py           Environment configuration
src/database.py         SQLite schema and persistence helpers
src/model_wrapper.py    OpenAI-compatible model client
src/chat_service.py     Chat orchestration and memory integration
src/chainlit_data_layer.py  SQLite-backed Chainlit thread history
src/memory/short_term.py  Recent-message selection and memory update trigger
src/memory/langmem_structured.py  LangMem-backed structured memory extraction
src/memory/long_term_store.py  SQLite namespace/key long-term memory store
src/retrieval/langchain_chroma_retriever.py  Primary document RAG backend
src/context/context_builder.py  ContextPacket prompt assembly
evals/document_qa/      Document QA retrieval/model-answer/RAGAS export evals
data/chatbot.db         Runtime SQLite database, created automatically
```

## Notes

No API keys are committed. Put local secrets in `.env`, which is ignored by git.
