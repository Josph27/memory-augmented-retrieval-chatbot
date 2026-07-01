# Demo Trace Validation

Validation date: 2026-07-01

## Environment

- Branch: `integration/playground-demo`
- Commit tested: `2c531e0`
- Worktree before validation: clean
- Routing: default deterministic `rule` mode
- Reranker: default deterministic mode
- Structured-memory retrieval: default SQLite; vector/hybrid tested explicitly
- Previous-chat gist retrieval: enabled only inside the isolated validation run
- Current-chat gist: default-off and not used
- Current-chat span: explicitly enabled only for its scenario
- Embeddings: locally cached `all-MiniLM-L6-v2`
- Vector backend: real temporary local Chroma collections
- Document backend: real temporary LangChain-Chroma collection
- Answer model: deterministic fake for the Coordinator trace; no live answer
  model was called
- State: temporary SQLite databases and temporary Chroma directories; no local
  application data was modified

The component scenarios exercised production `RoutePlanner`,
`RetrieverDispatcher`, `MemoryReranker`, `ContextManagerAgent`,
`ContextBudgetAllocator`, `ContextBuilder`, and `ContextPacket`. The recent
scenario was additionally run through `ChatService` and `CoordinatorAgent`,
producing a real `WorkflowTrace`. Explicit source activation and fake answers
are identified below.

## Scenario Results

### 1. Recent-Message Recall

- Setup: active chat with five large older filler messages, then
  `The recent marker is SILVER-19.`, an assistant acknowledgement, and the
  current query.
- Query: `What is the recent marker?`
- Expected evidence: the exact recent marker message.
- Observed route: `recent_messages`, `structured_memory`.
- Retrieved candidates: eight `recent_messages`, including the separately
  stored current query.
- Tight-budget result:
  - recent-message budget: 318 estimated tokens
  - included persisted message IDs: `[4, 5, 6, 7]`
  - older IDs `[1, 2, 3]` were dropped before newer messages
  - marker message ID `6` was retained
  - current query ID `8` was excluded from recent evidence
  - current query appeared exactly once as the final user message
  - overflow: false
- Actual Coordinator trace:
  - `prompt_source=context_packet`
  - `fallback_reason=None`
  - trace errors: none
  - marker evidence reached `ContextPacket`
- Provenance: recent candidates retained current chat ID and individual source
  message IDs.
- Result: **PASS**
- Demo readiness: **Ready for retrieval/context demonstration**
- Notes: the generated answer was mocked and does not establish model
  grounding. Extremely small context limits can still report overflow because
  the builder protects recent conversation and the final user turn.

### 2. Old Same-Chat Fact via `current_chat_span`

- Setup: an old message said `The ancient codename is VIOLET-73.`, followed by
  twelve later messages and the current query.
- Query: `What was the ancient codename?`
- Expected evidence: exact old user message plus local assistant context.
- Observed route: production plan plus explicit `current_chat_span` activation.
- Recent-window check: the old fact was absent from the latest eight messages.
- Retrieved candidates: one `current_chat_span`.
- Reranked order: `current_chat_span`.
- Budget:
  - `current_chat_span`: 64
  - recent and structured budgets remained allocated by the existing profile
- ContextPacket evidence:

  ```text
  user: The ancient codename is VIOLET-73.
  assistant: Recorded.
  ```

- Provenance:
  - chat ID: current chat
  - start message ID: `1`
  - end message ID: `2`
  - source message IDs: `[1, 2]`
- Result: **PASS**
- Demo readiness: **Fixture-assisted**
- Notes: retrieval and context construction are real, but production routing
  does not enable `current_chat_span` automatically yet.

### 3. Previous Chat via Gist to Raw Span

- Setup: an ended chat contained
  `Measure twice, deploy once, preserve every rollback path.` followed by an
  assistant acknowledgement.
- Lifecycle observation:
  - `ChatEndAction` created one previous-chat gist
  - the chat became inactive after finalization
- Query: `What did we discuss last time about rollback?`
- Observed route: `previous_chat_gist` was enabled by the existing environment
  flag and previous-memory query detection.
- Retrieved/post-expansion sources:
  - `previous_chat_gist`
  - `raw_message_span`
- Context budgets:
  - `previous_chat_gist`: 64
  - derived `raw_message_span`: 64
- ContextPacket contained both lossy orientation and exact transcript evidence.
- Raw provenance:
  - parent gist ID: `1`
  - parent source: `previous_chat_gist`
  - source chat ID: ended chat
  - source message IDs: `[1, 2]`
  - retrieval mode: `gist_provenance_expansion`
- Result: **PASS**
- Demo readiness: **Fixture-assisted**
- Notes: ChatEndAction, retrieval, expansion, reranking, and context building
  are real. The lifecycle action was invoked directly because no UI action was
  part of this validation.

### 4. Exact Quote Recall

- Exact source sentence:
  `Measure twice, deploy once, preserve rollback.`
- Requested wording:
  `What exact phrase did I use about rollback?`
- Observed candidates:
  - gist orientation
  - exact `raw_message_span`
- Exact role/content text reached `ContextPacket`; gist text was not the only
  evidence.
- Reranker observation:
  - for `What exact phrase ...`, gist ranked before raw span
  - for `Quote exactly what I said ...`, raw span ranked before gist
- ContextBuilder still groups sections by source order, so gist orientation
  appears before raw evidence in the packet even when the reranker ranks raw
  first.
- Result: **PARTIAL**
- Demo readiness: **Ready only with controlled wording**
- Notes: use `Quote exactly what I said about rollback.` in the demo. The
  deterministic raw-span trigger recognizes `exactly`, `exact words`, `quote`,
  `evidence`, `provenance`, and `did I say`, but not the standalone word
  `exact`.

### 5. Structured Preference Recall

#### SQLite Mode

- Stored memory:
  - memory ID: `preferences:libraries`
  - value: `User prefers mature open-source libraries.`
  - source chat: `memory-chat`
  - source message IDs: `[41]`
- Query: `Which libraries do I prefer?`
- Observed route: `recent_messages`, `structured_memory`.
- Retrieved and included source: `structured_memory`.
- ContextPacket preserved memory ID, namespace, category, key, confidence,
  source chat, and source message IDs.
- Result: **PASS**
- Demo readiness: **Ready**

#### Hybrid Mode

- Backend: real temporary local Chroma using the locally cached embedding
  model.
- Hybrid retrieval returned one deduplicated structured-memory candidate.
- Vector metadata mapped back to the current SQLite record.
- Observed vector score was present in candidate metadata.
- After the SQLite memory was deleted/deactivated and synchronized, vector
  retrieval returned zero candidates.
- Result: **PASS**
- Demo readiness: **Configuration-dependent**
- Notes: this validates a local smoke path, not vector retrieval benchmark
  quality. SQLite remains the source of truth.

### 6. Document RAG Recall

- Fixture: `tests/fixtures/docs/sample_report.txt`
- Indexed evidence:
  `The sample report says the unique planning code is ALPHA-47.`
- Query:
  `According to the uploaded report, what is the unique planning code?`
- Backend: real temporary LangChain-Chroma collection and local embedding
  model.
- Index result: one document chunk.
- Observed route: `recent_messages`, `structured_memory`, `document_memory`.
- Retrieved/reranked/included source: `document_memory`.
- Document budget: 2080 estimated tokens.
- ContextPacket evidence contained `ALPHA-47`.
- Provenance preserved:
  - document ID
  - source fixture path
  - file name and extension
  - chunk index
  - splitter and retrieval backend
- No structured, gist, or span source was mixed into the document candidate.
- Result: **PASS**
- Demo readiness: **Ready when local embedding/Chroma dependencies are available**
- Notes: no live answer model was called.

## Summary Matrix

| Scenario | Sources exercised | Evidence reached ContextPacket? | Exact provenance? | Model answer grounded? | Demo-ready? | Caveats |
|---|---|---:|---:|---:|---|---|
| Recent recall | `recent_messages` | Yes | Yes | No, fake model | Ready for context trace | Avoid pathological context limits |
| Old same-chat fact | `current_chat_span` | Yes | Yes | Not tested | Fixture-assisted | Source must be explicitly routed |
| Previous-chat recall | `previous_chat_gist`, `raw_message_span` | Yes | Yes | Not tested | Fixture-assisted | Requires gist retrieval config and explicit chat-end lifecycle |
| Exact quote | gist + expanded raw span | Yes | Yes | Not tested | Controlled wording only | `exact phrase` does not currently trigger raw-first ranking |
| Structured preference | SQLite and hybrid structured memory | Yes | Yes | Not tested | SQLite ready; hybrid config-dependent | Local smoke test, not benchmark evidence |
| Document RAG | `document_memory` | Yes | Yes | Not tested | Ready with local dependencies | Retrieval only; no answer-grounding claim |

## Remaining Issues

1. Production routing does not automatically activate `current_chat_span`.
2. `current_chat_gist` remains default-off and was correctly excluded.
3. Exact-query intent detection does not treat standalone `exact` as a
   raw-span boost; use `quote exactly` for the current demo.
4. ContextBuilder source ordering places gist orientation before raw evidence
   even when deterministic reranking puts raw evidence first.
5. No live answer-model call was made, so final-answer grounding and
   faithfulness remain unvalidated.
6. Previous-chat lifecycle was invoked directly rather than through a UI flow.
7. Very small total context limits may remain overflowed because recent
   messages and the final user turn are protected.
8. The local Chroma checks are smoke tests, not retrieval-quality benchmarks.

## Recommended Demo Script

Safest demo subset:

1. **Recent recall**
   - State a distinctive marker.
   - Ask for it in the next turn.
   - Show `WorkflowTrace`, `ContextPacket`, and the single latest-user entry.
2. **Structured cross-chat preference**
   - Use SQLite mode for the most reliable demonstration.
   - Show memory ID, source chat, source message IDs, and ContextPacket entry.
3. **Previous-chat gist plus raw evidence**
   - End/finalize the first chat before the demo query.
   - Enable `PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED=1`.
   - Ask `What did we discuss last time about rollback?`
   - Show both orientation and parent-linked exact raw span.
4. **Exact quote**
   - Ask `Quote exactly what I said about rollback.`
   - Show the reranker placing `raw_message_span` first.
5. **Document RAG**
   - Index the small sample report.
   - Ask for `ALPHA-47`.
   - Show document-only provenance.

Treat `current_chat_span` as an engineering trace demonstration until routing
policy is enabled. Do not present `current_chat_gist`, mock generated answers,
the LongMemEval fixture, or these smoke checks as production-quality benchmark
evidence.
