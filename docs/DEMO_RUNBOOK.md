# Demo runbook

This runbook is supervisor-facing. It avoids historical development notes and
uses only current application behavior.

## Before the demo

1. Configure `.env`:

   ```env
   OPENAI_API_KEY=dummy
   OPENAI_BASE_URL=http://localhost:11434/v1
   MODEL_NAME=qwen2.5:3b
   ORCHESTRATION_MODE=langgraph_demo
   ROUTING_MODE=hybrid
   MEMORY_UPDATE_POLICY=agentic_each_turn
   PREVIOUS_CHAT_GIST_EXTRACTOR=llm
   PREVIOUS_CHAT_GIST_MAX_MESSAGES_PER_GIST=30
   PREVIOUS_CHAT_GIST_GENERATION_ENABLED=1
   STRUCTURED_MEMORY_RETRIEVAL_MODE=sqlite
   RERANKER_MODE=deterministic
   DOCUMENT_TOP_K=8
   ```

2. Start the app:

   ```bash
   uv run chainlit run app.py -w
   ```

3. Open the local Chainlit URL.

## Demo sequence

### 1. Create Chat A and store a durable fact

Create a new chat and send a fact such as:

```text
For this project, remember that my preferred demo database is SQLite.
```

Ask a normal follow-up to show the chat is active.

### 2. End Chat A

Use the lifecycle toolbar to end the chat. Confirm:

- Chat A stays visible in the sidebar.
- Chat A is readable.
- The composer is disabled for Chat A.
- Fork Chat and New Chat remain available.

### 3. Create Chat B and recall the fact

Create a new chat and ask:

```text
What database did I prefer for this project demo?
```

Expected behavior: the assistant retrieves structured or cross-chat memory and
answers from stored evidence.

### 4. Inspect provenance

Use **Inspect answer** on the assistant message. Point out:

- requested mode: `langgraph_demo`;
- authoritative context: LangGraph unless fallback occurred;
- route and selected sources;
- selected evidence/provenance;
- token diagnostics;
- no hidden chain-of-thought.

### 5. Upload a document

Upload a `.txt`, `.md`, or supported `.pdf` file containing a specific marker
fact near the end. Ask about that fact in the same message or immediately after.

Expected behavior: indexing completes before answer generation, and
`document_memory` is scoped to the current chat.

### 6. Inspect document evidence

Open **Inspect answer** and show the selected document chunk, file name,
document ID, and context source.

### 7. Reopen and fork an ended chat

Return to ended Chat A. Confirm it is read-only. Use Fork Chat, then ask a new
question in the fork. Confirm the fork is active and independent.

## Recovery notes

- If model calls fail, verify `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and
  `MODEL_NAME`.
- If document retrieval returns no chunks, check that the upload reached
  `Ready` status and that the question refers to the associated document.
- If browser tests fail in a restricted environment before app startup, check
  whether localhost port binding is allowed.
