# Initial repository audit — reconstructed historical summary

**Not a transcript.** Original report date unavailable; reconstruction dated 2026-10-27. Shared recorded baseline: branch `tmp-audit`, commit `f4fc7c265f963cf516b5b8a13ee2ea0ad4ee24f7`, with provider-related tracked modifications and untracked settings/tests. Exact original dirty bytes and a separately timestamped first-pass status are unavailable; see [provenance](provenance.md).

## 1. Assignment and verification boundary

The user requested a comprehensive read-only audit: actual architecture and lifecycle, retained capabilities, correctness/maintenance/cleanup evidence, provider/configuration compatibility, test/evaluation protection and documentation discrepancies. Required behavior included native Chainlit, SQL history, typed memory, document RAG, cross-chat structured memory and evaluations. Stashed prior deletions were explicitly not approval or evidence of unnecessary code.

The audit used static source/configuration-template inspection. It did not launch the app, import application state, install dependencies, make inference calls, run ingestion/consolidation or inspect runtime/private content. Retained audit context reports syntax-only checks of 219 Python files, nine shell files and two JavaScript files; exact command output is not preserved in this package. These counts do not establish semantic review or passing tests. Existing output and provider-work notes were historical evidence only. User-reported DeepSeek success did not verify every inference-dependent path.

## 2. Architecture established by the first pass

- `app.py` is the Chainlit composition root; callbacks and custom `register_api_routes` expose different interfaces over SQLite and `ChatService`.
- `ChatService.__init__` composes `CoordinatorAgent`, short-term/LangMem memory, routing/retrieval/ranking/context services and document ingestion.
- `src/core/contracts.py::{MemoryCandidate, ContextPacket, WorkflowTrace}` form the shared retrieval/answer boundary. Deterministic tools implement much of the agent responsibility model.
- SQLite owns chats/messages/durable memories plus caches, gists, document metadata and inspections. Chroma document storage and optional memory vectors are separate state owners.
- The React `braemon/` app and native Chainlit custom shell coexist. Custom REST lifecycle handlers and framework callbacks must not be assumed equivalent.
- Graph, native, shadow, optional reranker and legacy prompt paths have consumers or fallback responsibilities. Their presence alone does not justify removal.
- Evaluation runners mix production services with fixtures, custom prompts, oracle answers and adapters; their outputs have different meanings.

The first report supplied an architecture map and findings register, but did **not** establish exhaustive entry-point or workflow coverage. The user explicitly identified that gap and requested the challenge pass.

## 3. Findings and later corrections

The early register addressed document scope, REST lifecycle bypass, memory deletion, distance scoring, context defaults, online extraction progress, import/database effects, HTTP/upload contracts, blocking work, configuration divergence, packaging, provider gates, API exposure/evaluation claims and fork semantics. Current IDs and precise evidence are preserved in [AUD-01–AUD-20](../bug-backlog.md); this reconstruction does not invent the original wording or restore superseded assertions.

The following early interpretations **must not be reused without the second-pass corrections**:

| Early concern | Current qualification |
|---|---|
| Global document fallback is a scope defect. | Fallback is intentional; the confirmed issue is inconsistent policy/docs/Inspector visibility. Actual model context is a separate issue. |
| Canonical memory delete solves forgetting. | Namespace/cache/vector/source history and supported future extraction all matter. Stale vectors rehydrate SQL and do not alone prove deleted-text recall. |
| Chroma scores reverse final ordering. | Wrong distance contribution is confirmed; other ranking/selection features can offset it. |
| Unknown model budget proves DeepSeek over-limit behavior. | Unsafe unknown-model defaults are established; actual DeepSeek capacity/rejection was not measured. |
| Empty extraction necessarily starves all later processing. | Stable full oldest batches can starve; batch growth, changed extraction or End processing can allow progress. |
| Import-time migration demonstrates lost data. | Some imports/inspectors can initialize the configured DB and migrate; actual data loss was not observed. |
| Fixing upload request access is sufficient. | Unscoped ingestion also bypasses registry; ordinary HTTP request context and downstream visibility need separate tests. |

## 4. Coverage and cleanup conclusions

Backend workflow reading was deepest; frontend, scripts, evaluations and documentation were partially inspected, with entry-point/failure coverage uneven. Generated/vendor/cache/runtime/private contents were excluded. No wholesale directory cleanup, workflow removal, fallback removal or stashed deletion was authorized.

The later cleanup decision brief applied a stricter removal screen and recommended **no workflow removals**. That result is not a retroactive first-pass approval. Follow the current [decisions](../decisions.md) and [cleanup plan](../cleanup-plan.md), not this historical reconstruction, for next actions.
