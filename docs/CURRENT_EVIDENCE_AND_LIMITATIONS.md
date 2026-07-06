# Current Evidence and Limitations

## Purpose

This report states what the typed-memory chatbot currently demonstrates, what
is default production behavior, and what remains an isolated experiment. It is
an engineering evidence summary, not a benchmark or deployment claim.

## Current Architecture Status

The project preserves source-specific memory semantics behind a shared
retrieval and context interface:

```text
typed source retrievers
→ MemoryCandidate[]
→ optional gist-to-raw-span expansion
→ MemoryReranker
→ ContextBudgetAllocator / ContextManagerAgent
→ ContextPacket
→ answer model
→ memory update
```

SQLite remains authoritative for chats, messages, episodic provenance, and
structured long-term memory. Chroma indexes are derived retrieval indexes.
LangMem performs structured-memory extraction and maintenance.

The central distinction remains:

```text
gist = lossy orientation
span = exact transcript evidence
gist tells where to look
span proves exact content
```

## Native Path vs Selectable Read-Only Graph Path

### Production path

```text
ChatService
→ CoordinatorAgent
→ production RoutingAgent / RoutePlanner
→ RetrieverDispatcher
→ MemoryReranker
→ ContextManagerAgent
→ ContextPacket
→ ModelWrapper
→ ShortTermMemory / LangMem update
```

LangGraph Demo is the live application default, with Native retained as the
internal fallback. The Native router is conservative and does not
automatically activate every span/gist source.

### Explicit Shadow/Demo path

```text
Semantic Router v2
→ read-only LangGraph pipeline
→ retrieval
→ gist expansion
→ reranking
→ ContextPacket
→ evidence-contract validation
→ existing answer agent or insufficient evidence
```

The graph itself remains read-only. In Shadow mode native context remains
authoritative. In Demo mode the graph-built ContextPacket is passed to the
existing answer agent. User/assistant persistence and memory update remain
outside graph nodes in the Coordinator.

## What Is Implemented

### Typed-memory sources

| Source | Status | Main role |
|---|---|---|
| `recent_messages` | Production | Immediate chat continuity; newest fitting suffix is retained |
| `structured_memory` | Production, SQLite default | Durable facts, preferences, decisions, and constraints |
| `document_memory` | Production when documents are configured | Uploaded external knowledge through LangChain/Chroma |
| `previous_chat_gist` | Implemented, conservatively routed/configured | Ended-chat episodic orientation |
| `raw_message_span` | Implemented, explicit/derived | Exact previous-chat transcript evidence |
| `current_chat_span` | Implemented, explicitly routed | Exact older same-chat transcript evidence |
| `current_chat_gist` | Default-off scaffold | Rolling same-chat orientation; not production-ready |

`MemoryCandidate` unifies downstream handling while preserving source labels,
record IDs, chat IDs, source message IDs, and source-specific metadata.

### Memory lifecycle

- `messages.summarized` tracks structured/LangMem semantic processing.
- `messages.gist_processed` independently tracks episodic gist processing.
- `ChatEndAction` performs bounded structured-memory flushing, finalizes pending
  previous-chat gist segments, and marks a chat inactive only after success or
  valid no-op processing.
- `ChatForkAction` copies chat-local history with remapped message/gist
  provenance and prevents inherited messages from being treated as fresh
  semantic extraction input.
- Structured long-term memory remains shared rather than duplicated per fork.

Chat end and fork remain explicit lifecycle services, not LangGraph nodes.

### Retrieval and context

- Previous/current gist provenance can expand into bounded
  `raw_message_span` candidates.
- `current_chat_span` performs deterministic SQLite lexical retrieval and
  preserves chronological raw role/content text.
- Routed sources with candidates receive bounded nonzero source budgets;
  enabled sources are still subject to the total context limit.
- `ContextPacket` retains included candidates and provenance, while tracing
  records source budgets and inclusion/drop decisions.
- Recent-message selection keeps the newest fitting suffix, restores
  chronological order, and avoids duplicating the separately supplied current
  user query.
- Raw-span character bounding is anchor-preserving:
  - current-chat matched message IDs are anchors;
  - gist expansion selects a query-best message inside the provenance range;
  - surrounding context is omitted before anchor text;
  - omission markers make truncation visible;
  - overlong anchors retain a query-relevant internal window.

The anchor-preserving change affects raw transcript evidence only. Document,
structured, gist, and recent-message formatting are unchanged.

### LangGraph and Semantic Router

- The LangGraph spike wraps existing read-side services as graph nodes.
- Graph state and trace fields are bounded.
- Semantic Router v2 is a deterministic English typed baseline, but it
  is default-off and currently used only by the spike/tests.
- Router v2 emits intent, temporal scope, source plans, retrieval hints, and an
  evidence contract.
- Exact-quote contracts require `raw_message_span` or `current_chat_span` to
  survive into the final `ContextPacket`.
- Gist-only context fails closed for exact quotation.
- Generated retrieval variants remain typed hints and are not inserted as user
  evidence.
- Both success and insufficient-evidence branches produce clearly marked mock
  output.

### Evaluation

Current evidence comes from several layers:

- component tests for every main memory source and lifecycle action;
- production-style route/retrieval-to-`ContextPacket` acceptance tests;
- deterministic structured-memory lifecycle evaluation;
- multi-source retrieval and source-selection evaluation;
- controlled generated-answer and E2E scaffolds;
- demo trace validation with temporary SQLite/Chroma state;
- LongMemEval pilot adapter and message-span representation;
- MemoryAgentBench adapter with incremental replay;
- a three-row real `Conflict_Resolution` mock dry run and stage-level miss
  analysis;
- graph-level English exact-quote tests;
- raw-span anchor-truncation regressions.

Several of these are fixture-assisted. Mock-answer evaluations validate
pipeline wiring, evidence presence, provenance, and failure behavior; they do
not validate live-model grounding.

## What Can Be Claimed

- The system implements a typed-memory retrieval/context layer with
  source-specific provenance.
- Recent, structured, document, gist, and raw-span evidence use a shared
  `MemoryCandidate` to `ContextPacket` path without flattening source semantics.
- Gists are treated as orientation and can expand to exact transcript spans
  when usable provenance exists.
- Exact quote/provenance queries work in the selectable LangGraph demo for
  controlled English paraphrases when raw evidence is available.
- The spike rejects gist-only evidence for exact quotation.
- Anchor-preserving raw-span truncation retains the selected evidential message
  under tested tight character/context limits.
- SQLite is the structured-memory source of truth and can synchronize stable
  records into a derived vector index in vector/hybrid mode.
- Chat end/fork lifecycle invariants and semantic/gist processing-state
  separation are covered by offline tests.

## What Cannot Be Claimed Yet

- LangGraph Demo is the default live orchestration path.
- Semantic Router v2 is used only in explicitly selected graph modes.
- Mock answers do not prove final-answer correctness, faithfulness, or
  quotation behavior.
- Live-model grounding and citation use have not been validated end to end.
- The three-row MemoryAgentBench run is diagnostic, not benchmark accuracy.
- MemoryAgentBench `Conflict_Resolution` is not solved. The analyzed cases need
  conflict handling and distant multi-hop relation assembly.
- Multi-hop evidence retrieval and noncontiguous evidence-chain assembly are
  not implemented.
- The LangGraph spike has no message-saving or memory-update nodes.
- Exactly-once/idempotent side-effect behavior under graph retry/resume is not
  designed or tested.
- LangGraph Store is not used and is not a long-term-memory source of truth.
- The graph has no targeted retrieval retry beyond failing closed as
  insufficient evidence.
- `current_chat_gist` is not production-ready.
- Live-model grounding remains unvalidated despite the demo selector.

## Recommended Next Steps

1. Commit the anchor-preserving raw-span fix as a separate scoped commit.
2. Run a targeted exact-quote/provenance evaluation and a small
   MemoryAgentBench `Accurate_Retrieval` or `Test_Time_Learning` subset.
3. Add one bounded missing-evidence retry edge to the graph, with a
   retry counter and no write side effects.
4. Add an opt-in live-model answer-grounding smoke test that records the exact
   ContextPacket and generated answer separately.
5. Design idempotency keys, transaction boundaries, and checkpoint/write
   ordering before adding any graph memory-update node.
6. Compare graph and production Coordinator outputs on identical fixtures.
7. Consider changing the default only after parity, observability, and
   failure-mode tests pass.

## Suggested Demo Claims

Safe:

> The selectable read-only LangGraph demo demonstrates evidence-contract-aware routing
> and context construction for exact quote queries.

> The typed-memory layer preserves provenance from episodic gists to exact raw
> transcript spans.

> Under tested tight limits, raw-span formatting retains the matched evidence
> message before trimming surrounding context.

Unsafe:

> The production chatbot now fully solves quote recall.

> LangGraph now owns the chatbot's production memory lifecycle.

> The model's final answers are proven grounded.

> The system solves MemoryAgentBench conflict resolution.

## Verification Snapshot

Latest local verification reported on this branch after the raw-span change:

- compileall: passed;
- Ruff: passed;
- pytest: `332 passed, 1 skipped`;
- `git diff --check`: passed.

This snapshot is local test evidence, not CI, benchmark, or live-model
validation. The generated MemoryAgentBench JSONL files remain local untracked
artifacts and are not evidence committed by this report.
