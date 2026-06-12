# memory-augmented-retrieval-chatbot

First runnable MVP for a memory-enabled chatbot prototype.

The app uses Chainlit for the browser chat UI, Python for backend logic, SQLite for persistent chat/message storage, LangChain-Chroma for document retrieval, and an OpenAI-compatible chat completions wrapper.

## Features

- Browser chat UI with Chainlit
- OpenAI-compatible model wrapper with one `chat(messages)` method
- Local/free model defaults for Ollama-compatible endpoints
- SQLite tables for `chats`, `messages`, and `chat_memory_state`
- Short-term memory: structured JSON memory state plus recent raw messages
- Document memory through LangChain-Chroma
- Production-shaped prompt assembly through `ContextPacket`, with legacy
  `ShortTermMemory` prompt fallback
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

```bash
cp .env.example .env
uv sync
uv run chainlit run app.py -w
```

Open the local URL printed by Chainlit, usually `http://localhost:8000`.

The SQLite database is created at `data/chatbot.db` by default. The database file is ignored by git because it is runtime state.

## Short-Term Memory

Current chat memory is built from two parts:

- Structured JSON memory derived from older messages and stored in `chat_memory_state`
- The most recent raw messages from `messages`

Raw messages remain the source of truth. The JSON memory state is a derived cache that can be regenerated later from `messages` if needed.

Structured memory extraction/consolidation is LangMem-backed. LangMem produces
typed semantic memories, and the app normalizes them into the existing
`chat_memory_state.memory_json` record format so `StructuredMemoryRetriever`,
`MemoryCandidate`, and `ContextPacket` stay stable.

Structured memory also writes into a namespace/key long-term store in the same
SQLite database. The default namespace is stable until real user/project IDs are
available, so memory can be reused across chats while still mirroring into
`chat_memory_state` for compatibility.

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

The older custom JSON-operation updater is deprecated. The current primary path
uses LangMem's `create_memory_manager` with a project schema, then applies
project-specific validation such as category checks, source-message ID checks,
transcript-like output rejection, vague-memory rejection, and lexical source
support before writing both the long-term store and the compatibility mirror.

Supported memory categories are `user_facts`, `project_facts`, `decisions`, `corrections`, `open_tasks`, `preferences`, and `constraints`.

The MVP policy keeps the latest `RAW_MESSAGE_LIMIT` messages raw. Older unprocessed messages update structured memory only when at least `MEMORY_UPDATE_BATCH_SIZE` eligible messages exist. After a batch is processed, those message rows are marked with `summarized = 1`, so they are not processed again. The column name is historical; it now means "processed into the derived memory cache."

This is intentionally based on fixed message counts for now. The memory module accepts a future `token_budget` parameter so the selector can later be replaced or extended with token-budget-based context selection.

## Document Memory

Document memory currently supports plain text only:

- `DocumentIngestionService.ingest_text_document(...)`
- local file loading for `.txt` and `.md`, with optional `.pdf` support when a
  PDF library is installed
- splitter abstraction with custom paragraph-preserving chunking by default
- SQLite `documents` and `document_chunks` tables
- LangChain-Chroma document retrieval

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

Optional semantic retrieval is available behind abstractions:

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

## Local Setup With pip

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
src/memory/short_term.py  Structured-memory plus recent-message context selection
src/memory/structured_state.py  JSON memory update and validation
data/chatbot.db         Runtime SQLite database, created automatically
```

## Notes

No API keys are committed. Put local secrets in `.env`, which is ignored by git.
