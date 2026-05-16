# memory-augmented-retrieval-chatbot

First runnable MVP for a memory-enabled chatbot prototype.

The app uses Chainlit for the browser chat UI, Python for backend logic, SQLite for persistent chat/message storage, and an OpenAI-compatible chat completions wrapper. It is intentionally small so vector memory with `sqlite-vec` or another SQLite vector extension can be added later.

## Features

- Browser chat UI with Chainlit
- OpenAI-compatible model wrapper with one `chat(messages)` method
- Local/free model defaults for Ollama-compatible endpoints
- SQLite tables for `chats` and `messages`
- Short-term memory from recent messages in the current chat
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
  -e MODEL_NAME=llama3.2:1b \
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
src/chat_service.py     Chat orchestration and short-term memory
data/chatbot.db         Runtime SQLite database, created automatically
```

## Notes

No API keys are committed. Put local secrets in `.env`, which is ignored by git.
