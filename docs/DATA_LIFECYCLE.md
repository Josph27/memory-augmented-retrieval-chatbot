# Data lifecycle

## Chat lifecycle

```text
New Chat
-> active chat
-> ordered user/assistant messages
-> online structured-memory updates
-> End Chat
-> remaining memory/gist flush
-> inactive read-only chat
-> optional Fork Chat
```

Chats and messages are stored in SQLite. Ended chats remain visible and
readable; they are retained history, not garbage. New messages are rejected for
ended chats. Forking creates a new active chat with copied history and remapped
chat-local provenance so future messages remain independent.

`ChatEndAction` is the authoritative end-chat path. It flushes remaining
structured-memory work, finalizes previous-chat gists, updates processing
flags, and marks the chat inactive only after finalization succeeds.

## Message and memory lifecycle

Raw messages are the source of truth. Derived memory is separate:

- `long_term_memories`: durable structured memory records;
- `chat_memory_state`: compatibility state/cache;
- `chat_gists`: current/previous chat gist rows with source-message ranges;
- message flags `summarized` and `gist_processed`: processing state.

Online structured-memory updates use token-aware batches and protect a newest
raw suffix. Chat End flushes remaining eligible messages regardless of the
online trigger threshold.

## Document lifecycle

```text
upload
-> document_records row
-> chat_documents association
-> indexing (256-token chunks, hybrid retrieval)
-> summary generation (LLM, stored in summary_text)
-> Ready or Failed
-> scoped retrieval (with sticky scope + pre-computed summaries)
```

SQLite stores document lifecycle metadata and chat-document associations:

- `document_records`: file name, status, chunk count, error, summary_text, metadata;
- `chat_documents`: which chat may retrieve which document;
- `operation_results`: idempotent upload operation records.

Chroma stores document chunks and embeddings. Document text chunks are not
stored in SQLite. Legacy SQLite tables named `documents`, `document_chunks`,
and `document_chunk_embeddings` are abandoned and dropped by database
initialization migration code while preserving live chat/memory rows.

Same-turn attachments are indexed before the answer turn is generated, so a
question sent with an uploaded file can retrieve that file in the same turn.

Document retrieval is chat-scoped. `DocumentRegistry` resolves explicit
filenames and implicit English document references to documents associated with
the selected chat, then the Chroma retriever filters by allowed document IDs.

## Answer Inspector lifecycle

For each completed assistant answer, the app can persist an
`answer_inspections` row keyed by assistant message ID. The payload is
read-only observability: route, context profile, selected sources, compact
evidence summaries, provenance, token counts, and fallback state. It is not a
memory source and cannot change application state.
