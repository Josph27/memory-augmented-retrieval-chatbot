# LangGraph Migration Plan

## Goal

Evaluate LangGraph as an optional orchestration layer around the existing
typed-memory services. The intended boundary is:

```text
LangGraph
= graph state + control flow + conditional edges + resumability/debug state

Existing project services
= typed-memory semantics + retrieval + provenance + context construction
  + lifecycle + storage
```

This is an audit and spike design, not approval to replace the production
pipeline. `ChatService` and `CoordinatorAgent` remain authoritative until an
isolated graph proves behavioral equivalence.

The graph must preserve:

- `MemoryCandidate` as the unified retrieval contract;
- typed source semantics under that contract;
- `ContextPacket` as the model-context contract;
- SQLite as structured-memory source of truth;
- Chroma as a derived document/semantic index;
- LangMem as the structured-memory extraction/update backend;
- gist as lossy orientation and raw span as exact evidence;
- `WorkflowTrace` as the project-level observability artifact.

## Current Orchestration Summary

### Main request path

Per-turn orchestration is implemented manually in
`CoordinatorAgent.run_turn()`. `ChatService.handle_user_turn()` performs title
setup and delegates to it.

The current sequence is:

| Stage | Input | Output | External mutation / I/O |
|---|---|---|---|
| Route | user query | `RoutingDecision`, `RoutePlan` | Optional model call in LLM/hybrid mode |
| Save user | chat ID, original query | SQLite message ID | SQLite write |
| Retrieve and expand | chat ID, route plan | `MemoryCandidate[]` | SQLite/Chroma reads; gist expander reads SQLite |
| Rerank | query, candidates, profile | ranked candidates + metadata | Pure in deterministic mode; optional CrossEncoder/LLM inference |
| Build context | system prompt, query, route, ranked candidates | `ContextBudget`, `ContextPacket`, metadata | Deterministic/in-memory |
| Build legacy context | chat ID, current message ID | legacy model messages | SQLite reads |
| Compare/validate prompt | legacy messages, packet, latest query | validated model messages or fallback reason | Pure/in-memory |
| Answer | model messages | answer text | Model/network call |
| Save answer | chat ID, answer | assistant message ID | SQLite write |
| Update memory | chat ID | update result + saved-memory trace rows | SQLite reads/writes, LangMem/model call; optional derived Chroma sync |
| Trace | all prior values | `WorkflowTrace`, `AgentTurnResult` | Console output only; trace is not independently persisted |

`RetrieverDispatcher.retrieve()` currently performs two logical operations:

1. dispatch enabled source retrievers;
2. call `GistRawSpanExpander` and append derived raw spans.

A spike can expose these as separate nodes by using a spike-only adapter around
the dispatcher's public `retrievers` and `gist_expander` members. Production
dispatcher behavior should not change for the spike.

### State passed manually

`CoordinatorAgent.run_turn()` carries local variables for:

- trace/timing IDs;
- routing decision and route plan;
- user/assistant message IDs;
- retrieved and ranked candidates;
- reranker metadata;
- context budget and ContextPacket;
- context-manager metadata;
- legacy prompt and comparison;
- prompt source/fallback reason;
- model messages and answer;
- errors and memory trace rows.

These variables are the natural graph-state candidates. The graph should not
copy full chat history into state. Source message IDs, bounded candidates, and
ContextPacket are sufficient.

### Pure or node-ready stages

These are already close to graph nodes:

- rule `RoutingAgent` / `RoutePlanner`;
- deterministic reranking;
- `ContextManagerAgent`;
- ContextPacket prompt validation;
- evidence-contract validation proposed by Router v2;
- project trace assembly.

These are node-ready wrappers with external reads or inference:

- retrieval/expansion;
- LLM/hybrid routing;
- CrossEncoder/LLM reranking;
- answer generation.

These mutate authoritative stores and require idempotency before graph retry:

- saving user and assistant messages;
- `ShortTermMemory.update_memory_if_needed`;
- LangMem/SQLite structured-memory writes;
- structured-memory vector synchronization;
- document ingestion, which is not part of a normal query graph.

### Lifecycle actions

`ChatEndAction` and `ChatForkAction` are not per-query nodes.

- Chat end performs bounded structured-memory flush, finalizes episodic gists,
  then marks the chat inactive only after success.
- Chat fork transactionally copies chat-local history/provenance and keeps
  structured long-term memory shared.

They should remain explicit lifecycle services. Separate lifecycle graphs may
be considered later, but they must not be inserted into the first request-graph
spike.

### Current failure paths

- Routing catches planner/model failures and returns a deterministic fallback.
- Retrieval, expansion, deterministic reranking, and context construction
  generally propagate exceptions from `CoordinatorAgent`.
- Optional neural/LLM reranking has its own deterministic fallbacks.
- Invalid ContextPacket prompt shape falls back to the legacy short-term prompt.
- Answer generation catches `OpenAIError`, returns a visible endpoint error,
  and still saves the resulting assistant message.
- Normal memory update catches `OpenAIError`; other unexpected errors can still
  propagate.
- SQLite structured-memory writes can commit before derived vector sync fails;
  the sync layer raises an explicit error rather than pretending consistency.
- Chat end preserves active state on memory/gist failure.
- Chat fork relies on a database transaction for rollback.

Conditional edges would make prompt fallback, evidence insufficiency, optional
memory update, and later route escalation explicit. They do not automatically
make mutating nodes safe to retry.

## What LangGraph Should Replace

If the spike succeeds, LangGraph may eventually replace:

- the procedural stage sequencing inside `CoordinatorAgent.run_turn()`;
- manually threaded intermediate local variables;
- nested prompt/evidence fallback `if/else` logic;
- per-stage timing/error bookkeeping boilerplate;
- future bounded retry/escalation routing;
- graph-run inspection and optional resumability.

It should wrap current services rather than reimplement them.

## What LangGraph Must Not Replace

The migration must not replace:

- `ChatService` session/UI-facing API in the first phase;
- SQLite chats, messages, gists, and long-term memories;
- Chroma document and structured-memory derived indexes;
- LangMem extraction/update;
- `MemoryCandidate`, source labels, or provenance;
- `RetrieverDispatcher` and source-specific retrievers;
- `GistRawSpanExpander`;
- `MemoryReranker`;
- `ContextManagerAgent`, budget allocator, builder, or `ContextPacket`;
- `WorkflowTrace`;
- ChatEnd/Fork lifecycle semantics.

LangGraph Store is explicitly out of scope for the first spike. Adopting it as
another long-term memory store would duplicate or conflict with existing
SQLite/Chroma/LangMem ownership.

## Proposed MemoryGraphState

Use a `TypedDict` or equivalent schema with partial node updates:

```python
class MemoryGraphState(TypedDict):
    run_id: str
    chat_id: str
    user_id: str | None
    user_query: str
    current_message_id: int | None

    query_understanding: dict[str, Any] | None
    evidence_contract: dict[str, Any] | None
    route_plan: RoutePlan | None
    routing_metadata: dict[str, Any]

    candidates: list[MemoryCandidate]
    expanded_candidates: list[MemoryCandidate]
    reranked_candidates: list[MemoryCandidate]
    reranker_metadata: dict[str, Any]

    source_budgets: dict[str, int]
    context_packet: ContextPacket | None
    context_metadata: dict[str, Any]
    prompt_messages: list[dict[str, str]]
    prompt_source: str | None

    answer: str | None
    assistant_message_id: int | None
    memory_update_enabled: bool
    insufficient_evidence: bool
    insufficient_evidence_reason: str | None

    errors: list[str]
    node_timings_ms: dict[str, float]
    trace: dict[str, Any]
```

Notes:

- The database message identifier is currently an integer, not a string.
- `user_query` always contains the original query.
- Query variants, if introduced by Router v2, belong in bounded
  `query_understanding`; they are never evidence.
- Candidate lists must be bounded by source limits. Do not put full transcripts,
  Chroma objects, model clients, database connections, or service instances in
  state.
- Services should be dependency-injected into node closures or a graph factory.
- For a checkpointed implementation, consider storing compact candidate
  snapshots/IDs instead of repeatedly checkpointing full content.
- List fields should normally be overwritten by sequential nodes. Use reducers
  only where append semantics are intentional; careless additive reducers can
  duplicate candidates on retry.

## Proposed Nodes

| Node | Reads | Writes | Existing service | Side effects | Failure behavior | First spike? |
|---|---|---|---|---|---|---|
| `understand_or_route_node` | query, optional understanding | route plan, routing metadata, evidence contract | `RoutingAgent` / future Router v2 | Optional route-model call | Preserve current rule fallback; record low confidence | Yes, deterministic fixture route or rule router |
| `save_user_node` | chat ID, query | current message ID | `Database.save_message` | SQLite write | Fail graph; requires idempotency key before retries | No |
| `retrieve_node` | chat ID, route plan | base candidates | source retrievers / dispatcher adapter | SQLite/Chroma reads | Record source error; first spike fails scenario explicitly | Yes |
| `expand_gists_node` | base candidates, original query | expanded candidates | `GistRawSpanExpander` | SQLite reads | Keep gist orientation if provenance missing; record error | Yes |
| `rerank_node` | original query, all candidates, profile | reranked candidates, metadata | `MemoryReranker` | Optional model/CrossEncoder inference | Preserve deterministic fallback | Yes, deterministic |
| `build_context_node` | route, ranked candidates, query | budgets, ContextPacket, context metadata | `ContextManagerAgent` | None | Fail scenario; no legacy fallback in isolated spike |
| `validate_evidence_contract_node` | contract, ContextPacket | insufficiency flags/reason | New small validator | None | Never treat routed/retrieved-but-dropped evidence as present | Yes |
| `insufficient_evidence_node` | insufficiency reason | bounded abstention answer | New deterministic node | None | Return explicit unsupported-evidence answer | Yes |
| `answer_or_abstain_node` | packet, prompt messages, flags | answer | `ChatAgent`/mock answer backend | Optional model call | Mock deterministic; model mode records endpoint error | Yes, mock |
| `save_answer_node` | chat ID, answer | assistant ID | `Database.save_message` | SQLite write | Fail graph; requires idempotency before retry | No |
| `update_memory_node` | chat ID, update policy | update metadata | `ShortTermMemoryAgent` / LangMem | Model + SQLite + optional Chroma | Record error without losing visible answer; do not blind-retry | No |
| `trace_node` | all bounded outputs | project trace dictionary / WorkflowTrace | Current trace assembly helpers | Optional report write | Always run for success/insufficiency; sanitize large content | Yes |

The first spike should use pre-seeded temporary SQLite data and must not save
new user/assistant messages or update memory. This avoids introducing
exactly-once problems while validating orchestration and evidence branches.

## Proposed Conditional Edges

```text
START
  → understand_or_route

understand_or_route
  ├─ route_error / unsupported → trace
  ├─ low_confidence → deterministic fallback route
  └─ accepted route → retrieve

retrieve
  → expand_gists
  → rerank
  → build_context
  → validate_evidence_contract

validate_evidence_contract
  ├─ satisfied → answer
  ├─ requires_raw_span but absent → insufficient_evidence
  ├─ requires_document_citation but absent → insufficient_evidence
  └─ no strict requirement → answer

answer
  ├─ memory_update_enabled → update_memory       # later phase only
  └─ disabled → trace

insufficient_evidence
  → trace

update_memory
  → trace

trace
  → END
```

Future bounded branches, not first-spike behavior:

- low route confidence → optional LLM route planner;
- missing raw evidence → one targeted current-span or gist-expansion retry;
- missing document evidence → one document-query rewrite/retry;
- model endpoint failure → configured answer fallback.

No retry may loop without a retry counter. A graph checkpoint does not prevent
duplicate SQLite writes if a mutating node is executed again.

## Checkpointing and WorkflowTrace Mapping

LangGraph checkpointers persist graph-state snapshots at graph steps under a
`thread_id`. They are useful for graph resumability, inspection, time-travel
debugging, interrupts, and fault recovery. They are not a replacement for the
project's domain memory.

Recommended boundary:

```text
LangGraph checkpoint
  = one bounded orchestration run and its next-node/debug state

WorkflowTrace
  = project semantic trace:
    route, sources, candidates, scores, budgets, prompt sections, fallbacks

SQLite / Chroma / LangMem
  = durable chat, typed memory, provenance, and derived retrieval indexes
```

For the first spike:

- compile without persistence by default;
- optionally use `InMemorySaver` in tests to inspect state history;
- use `run_id` as checkpointer `thread_id`, not as a replacement for `chat_id`;
- export a compact graph-state/trace JSON artifact under `/tmp` or an ignored
  reports path;
- do not enable LangGraph Store.

If durable graph checkpointing is evaluated later, the SQLite saver is a
separate package (`langgraph-checkpoint-sqlite`) and should use a separate
database/path or an explicit migration/ownership design. Do not silently add
LangGraph tables to the chatbot's source-of-truth database.

`WorkflowTrace` should remain the public project trace. The final trace node can
construct it from graph state and add supplemental metadata:

- graph run ID;
- visited nodes;
- conditional-edge choices;
- per-node timings;
- checkpoint/thread ID if enabled;
- evidence-contract result.

## Short-Term vs Long-Term Memory Boundary

LangGraph documentation uses “short-term memory” for checkpointed thread state
and “long-term memory” for cross-thread Store data. Those names must not blur
this project's established semantics.

In this project:

- recent messages/current spans remain SQLite-backed typed context;
- current gists remain project episodic records;
- structured long-term memory remains LangMem + SQLite;
- document and semantic indexes remain Chroma-derived;
- previous gists/raw spans retain project provenance;
- graph state contains only bounded orchestration data.

LangGraph Store is not adopted in the first spike. If considered later, it
requires a separate architectural decision and migration plan rather than
parallel writes to two competing memory sources.

## Default-Off Spike Plan

### Location

Proposed isolated files:

```text
src/orchestration/__init__.py
src/orchestration/langgraph_spike.py
tests/test_langgraph_spike.py
scripts/run_langgraph_spike.py
```

No import from `ChatService`, `app.py`, or the production coordinator.

### Graph factory

```python
def build_memory_graph_spike(
    *,
    routing_agent: RoutingAgent,
    dispatcher: RetrieverDispatcher,
    reranker: MemoryReranker,
    context_manager: ContextManagerAgent,
    answer_backend: SpikeAnswerBackend,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    ...
```

The spike runner constructs temporary SQLite data, existing retrievers, a
deterministic reranker, existing context manager, and a mock answer backend.

### Required scenarios

1. **Exact quote, raw span present**
   - route explicitly enables `current_chat_span` or previous gist expansion;
   - raw candidate reaches ContextPacket;
   - `requires_raw_span` is satisfied;
   - answer node runs.
2. **Exact quote, raw span missing**
   - gist-only or empty context;
   - evidence validator rejects gist-only evidence;
   - graph follows `insufficient_evidence`;
   - model answer node is not called.
3. **Previous gist → raw span**
   - existing gist is retrieved;
   - expansion node creates linked exact raw candidate;
   - parent gist provenance survives;
   - contract passes only after raw evidence reaches ContextPacket.

### Output

Each scenario returns:

- final `MemoryGraphState`;
- visited nodes and selected edges;
- source/candidate IDs and bounded snippets;
- ContextPacket source summary;
- evidence-contract result;
- mock answer or deterministic abstention;
- per-node timing/error trace.

### Default-off guarantee

- no environment flag is added in the first spike;
- no production constructor imports/builds the graph;
- only the test and explicit script invoke it;
- no live model, CrossEncoder download, or network is required;
- no LangGraph Store or durable checkpointer is configured.

## Dependency Check

Local environment:

- Python: `3.12.13`
- LangGraph installed: `1.2.4`
- `langgraph-checkpoint`: present transitively
- `langgraph` is **not** a direct `pyproject.toml` dependency;
- it is currently pulled in by `langchain` and recorded in `uv.lock`.

The installed version imports successfully under the project's Python version.
The spike could technically use it without changing the lock file, but relying
on an undeclared transitive dependency is fragile. When implementation is
explicitly approved, add a compatible direct `langgraph` requirement and let
`uv` resolve/verify it. Do not add the dependency during this documentation
audit.

Official references:

- Graph nodes and conditional edges:
  `https://docs.langchain.com/oss/python/langgraph/use-graph-api`
- Persistence, threads, checkpoints, and Store distinction:
  `https://docs.langchain.com/oss/python/langgraph/persistence`
- Checkpointer integrations:
  `https://docs.langchain.com/oss/python/integrations/checkpointers`

## Risks

1. **Duplicate side effects on retry.** Saving messages or updating LangMem is
   not automatically exactly-once because a graph is checkpointed.
2. **Two sources of conversation state.** Treating graph checkpoints as chat
   history would conflict with SQLite.
3. **State growth.** Checkpointing full candidates/ContextPackets every step can
   duplicate large text. Keep state bounded or store compact snapshots.
4. **Serialization.** Service clients, database connections, model wrappers, and
   arbitrary backend objects must remain outside graph state.
5. **Trace duplication.** LangGraph state history supplements, but must not
   replace, semantic WorkflowTrace fields.
6. **Fallback drift.** The current legacy-prompt fallback must be represented
   explicitly before any production migration.
7. **Evidence regression.** Exact quote must branch on raw evidence included in
   ContextPacket, not merely routed/retrieved.
8. **Async mismatch.** The current pipeline is synchronous. An async graph
   migration would require deliberate database/model client review.
9. **Checkpoint data sensitivity.** Candidate text and user queries can contain
   sensitive data. Persistent checkpointing needs retention, encryption, and
   redaction policy.
10. **Premature graph complexity.** A linear graph without meaningful branches
    adds indirection. The spike should specifically prove evidence-contract and
    fallback benefits.

## Tests Needed

1. State schema contains bounded values and excludes service objects/transcripts.
2. Exact quote with raw current span follows the answer edge.
3. Exact quote with gist only follows insufficient-evidence edge.
4. Previous gist expands to raw span and preserves parent provenance.
5. Raw evidence retrieved but dropped by budget does not satisfy the contract.
6. Document-citation contract rejects ContextPacket without document evidence.
7. Casual/no-contract query follows the normal answer edge.
8. Mock answer backend is not called on insufficient evidence.
9. Dispatcher/reranker/context manager are the existing implementations.
10. Deterministic reranker and mock answer require no network/download.
11. Node error is recorded with node name and bounded message.
12. In-memory checkpointer can inspect state history by run ID.
13. Re-invocation does not mutate pre-seeded SQLite in the read-only spike.
14. Existing `WorkflowTrace` fields can be reconstructed from final graph state.
15. Production `ChatService` still constructs `CoordinatorAgent`, not the graph.
16. Full existing suite remains green.

## Recommended Next Step

Implement one isolated, default-off spike commit:

```text
spike: add default-off LangGraph memory orchestration
```

Scope only:

- direct `langgraph` dependency declaration after dependency review;
- `MemoryGraphState`;
- read-only routing/retrieval/expansion/rerank/context/evidence/answer/trace nodes;
- optional `InMemorySaver`;
- three deterministic fixture scenarios;
- focused tests and a CLI script;
- no production imports, flags, database writes, memory update, Store, or UI.

After the spike, compare its final ContextPacket and trace against the current
CoordinatorAgent for identical fixtures. A production migration should proceed
only if equivalence, side-effect idempotency, and trace quality are demonstrated.
