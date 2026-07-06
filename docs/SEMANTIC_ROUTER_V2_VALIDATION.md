# Semantic Router v2 Validation

## Goal

Validate that default-off Semantic Router v2 improves English exact
quote/provenance handling through the complete read-only LangGraph path:

```text
Semantic Router v2
→ typed source retrieval
→ optional gist-to-raw-span expansion
→ deterministic reranking
→ ContextManagerAgent
→ ContextPacket
→ evidence-contract validation
→ mock answer or insufficient evidence
```

This validation tests evidence reaching `ContextPacket`, not only intent
classification.

## Environment

- Branch: `integration/playground-demo`
- Base commit: `ef26b89`
- Semantic router status: default-off and explicitly enabled by tests
- Graph path: read-only LangGraph spike
- Answer mode: deterministic mock
- Storage: isolated temporary SQLite databases
- Model/API calls: none
- Production `ChatService`/`CoordinatorAgent`: unchanged and unused

## Scenario Results

### Same-Chat Router Principle

- Query: `What exact phrase did I use about router principle?`
- Expected intent: `EXACT_QUOTE`
- Observed intent: `EXACT_QUOTE`
- Enabled sources: recent messages, current-chat span, previous-chat gist,
  raw-message span
- Evidence contract: raw span required; gist-only evidence prohibited
- ContextPacket evidence: exact persisted user sentence from
  `current_chat_span`
- Raw span present: yes
- Generated variants excluded from evidence: yes
- `insufficient_evidence`: false
- Result: **PASS**

The target message is older than the configured eight-message recent window.
The test confirms it is absent from recent-message candidates and reaches the
packet through current-chat raw-span retrieval.

### Same-Chat Quote Paraphrases

| Query | Observed intent | Raw evidence in packet | Result |
|---|---|---:|---|
| `How did I phrase the memory rule?` | `EXACT_QUOTE` | Yes | PASS |
| `What were my exact words about gist and span?` | `EXACT_QUOTE` | Yes | PASS |
| `Can you quote my earlier message about context budget?` | `EXACT_QUOTE` | Yes | PASS |

Each case preserves the original stored sentence, chat ID, and source message
IDs. Generated retrieval hints are not present as candidates or evidence.

### Previous-Chat Gist to Raw Span

- Query: `What exact phrase did I use about my previous router principle?`
- Setup: `ChatEndAction` finalizes an extractive previous-chat gist with
  message provenance
- Observed intent: `EXACT_QUOTE`
- Retrieved orientation: `previous_chat_gist`
- Expanded evidence: `raw_message_span`
- ContextPacket evidence: exact original previous-chat sentence
- Parent provenance: gist ID, parent source, chat ID, and source message IDs
- `insufficient_evidence`: false
- Result: **PASS**

### Gist-Only Exact Quote

- Query: `Can you quote my earlier message about context budget?`
- Observed intent: `EXACT_QUOTE`
- Retrieved context: gist orientation without usable raw-span provenance
- Raw span present: no
- Evidence contract result: failed closed
- `insufficient_evidence`: true
- Response: mock insufficient-raw-evidence response
- Result: **PASS**

The graph does not treat compressed gist text as exact quotation evidence.

### Casual Chat

- Query: `How are you?`
- Expected/observed intent: `CASUAL_CHAT`
- Enabled sources: `recent_messages` only
- Current/raw span enabled: no
- Document memory enabled: no
- Graph completed: yes
- Result: **PASS**

## Summary

Compared with the production rule router, Semantic Router v2 recognizes more
English exact-quote paraphrases and activates sources capable of producing raw
transcript evidence. More importantly, graph-level evidence validation checks
what survived into `ContextPacket`: a route or retrieved gist alone is not
enough.

Semantic Router v2 remains default-off. Tests instantiate it directly and pass
`use_semantic_router=True`; no production entry point imports or enables it.

## Remaining Limitations

- There is no production `ChatService` or `CoordinatorAgent` integration.
- Mock answers do not validate live-model grounding or exact quotation quality.
- The router is a deterministic pattern/example baseline, not an embedding or
  LLM semantic classifier.
- Retrieval has no retry edge after evidence validation; missing raw evidence
  goes directly to insufficient evidence.
- The LangGraph spike has no memory update nodes.
- Generated retrieval variants are typed and traced but are not yet fanned out
  as multiple dispatcher calls.
- The validation covers controlled SQLite fixtures, not benchmark performance.
