# Workflow coverage and finding challenge — reconstructed historical summary

**Not a transcript.** Original continuation date unavailable; reconstruction dated 2026-10-27. Retained baseline information points to branch `tmp-audit`, commit `f4fc7c265f963cf516b5b8a13ee2ea0ad4ee24f7`, with the same recorded provider working-copy changes. A distinct original second-pass status and byte snapshot are not recoverable. See [provenance](provenance.md).

## 1. Assignment and boundary

The user asked to deepen the first map, enumerate entry points in both caller directions, make inspection depth explicit, challenge AUD-01–07/09 and close high-impact lifecycle/configuration/evaluation gaps. The instruction was to treat prior findings as claims to challenge, not defend. Boundaries remained static/read-only: no app/tests/inference/ingestion, runtime/private data, dependency installation or stash changes. Reproductions were specified for later isolated testing, not executed.

## 2. What the continuation established

The pass reconciled Chainlit auth/data-layer/start/resume/message/window callbacks and lifecycle actions with custom API routes and React callers; native custom navigation/Inspector events differ from React consumption. It mapped CLI/development/container/evaluation selectors and important graph/native/fallback differences. The maintained [workflow map](../workflow-map.md) is the compact consolidation of that work, including unrecovered/mapped-only areas; it is not a new claim of exhaustive semantic coverage.

State boundaries mattered: user-message persistence, vector indexing, SQL registry status, memory upsert/cache/progress flags, assistant persistence and inspection emission are separate operations. Process-local guards and transactional SQL forks do not make the whole turn/index/model workflow transactional. Isolated tests must cover representations and callers rather than one helper alone.

## 3. Revised findings

| ID | Challenge result and counterevidence retained |
|---|---|
| AUD-01 | **Reclassified/narrowed.** `DocumentRegistry.resolve` intentionally supplies global Ready docs for an empty chat. Retriever postfilters resolved IDs; Inspector requires explicit associations. Policy/visibility mismatch remains; actual answer exposure is not established by candidate presence. |
| AUD-02 | **Retained.** REST End bypasses `ChatEndAction.execute`; no later callback guarantees memory/gist flush. Native flush/no-op/failure guards matter. |
| AUD-03 | **Narrowed.** REST physical deletion differs from namespaced soft-delete/vector synchronization. Vector hits rehydrate active SQL. Compatibility caches and source history/future extraction mean canonical delete alone does not implement forgetting. |
| AUD-04 | **Narrowed.** Selected Chroma API returns lower-is-better distances; normalization contributes incorrectly. Final ordering still depends on weighted features, optional rerankers and context utility/cost. Existing score test encodes the current conversion. |
| AUD-05 | **Narrowed.** Unknown-model cap/default is unsafe; pruning exists. No live DeepSeek limit or endpoint failure was established. Output reservation and sent output cap differ. |
| AUD-06 | **Conditional.** Two full fixed batches with repeated empty extraction can demonstrate progress starvation. Incomplete batch growth, changed output/config or valid End no-op can permit progress; tests intentionally leave online flags unsummarized on empty. |
| AUD-07 | **Narrowed.** Specific early test imports and source-inspection oracles can reach real DB initialization; browser fixture pre-exports temp path and provider tests avoid import. Destructive migration capability is not observed data loss. |
| AUD-09 | **Strengthened.** Ordinary route has no usable Chainlit request context; access precedes try. Complete unscoped downstream path indexes without SQL registry; success/failure cleanup and listing/scoping require separate protection. |

Other retained findings remain parked in the backlog. Evidence overlaps were consolidated: app-import mutation belongs to AUD-07, not a second evaluation finding; selected-versus-sent context belongs to AUD-17, not a second document-scope finding.

## 4. Additional distinct findings from the deeper pass

- **AUD-17:** `ContextBuilder` augments final user content, while prompt validation/comparison demands unchanged original content; coordinator can fall back to legacy context. Trace/inspection may still show selected evidence. Static contradiction is confirmed; runtime reproduction remains pending.
- **AUD-18:** native product state/error/inspection handling has no equivalent React consumer. UI lifecycle parity needs a real frontend contract test; no specific reconnect defect was proven.
- **AUD-19:** native edit can invoke `on_message` while data-layer update/delete hooks do not reconcile durable/derived history. Actual edit/reload needs isolated browser reproduction.
- **AUD-20:** temporary SQLite evaluation does not isolate independently configured memory vectors. Vector/hybrid environment can reach persistent index; no actual contamination was observed.

## 5. Verification and product decisions left open

Highest-value protection scenarios: isolate before importing app; isolate SQL **and** vectors; record actual model prompt with real context builder; compare native/REST End; prove oldest-empty batch behavior deterministically; compare document selection/Inspector/prompt; test deletion across cache/SQL/vector/source/future extraction; test fork/edit/resume and frontend events.

Product choices remain document-library scope, deletion semantics, fork inheritance, edit invalidation, deployment boundary and retained frontend/mode combinations. Recommendations are not approvals. No workflow removal met the later decision brief's threshold; neither bugs nor default-off/evaluation-only status justify removal.

Unfinished coverage includes all CLI flags/metric implementations, real browser reconnect/concurrency, cross-process guards, crash/index recovery, clean container/dependency execution, live provider/model/judge combinations and genuine inference quality. Static evidence is sufficient to design targeted protection, not to claim passing tests or exhaustive correctness.
