# PURGE1 maintained-area and removal ledger

TASK16 / DEC017. In progress; baseline3a3ad03e5fb33b23c56aa5f36e49c1f2e413bf67. Existing audit/workflow/test maps supply area coverage; this is cleanup disposition work, not a general audit restart. One implementation writer; independent read-only challenge of consequential removals.

## Areas

Backend source assessment complete at responsibility/consumer depth; dependency/evaluation/script and frontend/docs/assets/configuration assessments in progress. Baseline tracked-tree metadata accounts for root17, .chainlit1, .dev2, braemon31, data3, docs126, evals91, public1, scripts20, src85, tests86entries. Existing audit/history and runtime/data are protected. Final area dispositions and before/after counts follow completed checks.

## Candidate ledger

| ID | Candidate / bounded scope | Evidence and disposition | Verification / dependency |
|---|---|---|---|
| P1-A01 | docs/mermaid-diagram-2026-07-15-021559.png | Removed752065d under DEC016; no active consumer; retained Mermaid hash unchanged. | References/assets/packaging/source/diff/link checks; [recovery](purge1-batch1.md). |
| P1-C01 | structured_state.py deprecated JSON-operation updater and exclusive helpers | Safe-removal recommendation: no maintained runtime/config/dynamic/CLI/eval/frontend/package selector; active ShortTermMemory chooses LangMem. Retain shared validators/contracts/JSON migration unchanged. | Independent challenge accepted; retained19structured-state declarations byte-identical, plus15short-term and7guard declarations unchanged. Affected isolated integration:508passed/1real-model preload excluded,0fail/error/skip; source stable. Existing LangMem, scheduling, store, vector, eval and context/request tests. |
| P1-C02 | short_term.py unused ChatEndMemoryProcessingError declaration | Safe-removal recommendation: no raises/catches/imports; keep current partial-result and real exception behavior. | Independent challenge accepted; existing End/failure/scheduling protection. |
| P1-C03 | connection_guard.py unused connection_guard_from_env factory | Safe-removal recommendation: actual provider-aware model/LangMem constructors instantiate guard; no factory consumers. Keep guard/cache/timeout/env helpers. | Independent challenge accepted; unused urljoin import also removed after focused static check, preserving actual URL construction. Existing provider/guard/LangMem tests. |
| P1-D01 | braemon direct puppeteer-core declaration | Candidate: both Node probes import puppeteer, whose exact transitive core dependency stays. No installed package/browser capability removal. | Dependency/lock/operational consumer review pending; offline resolution/build and final groups. |
| P1-R01 | FAISS/community/langchain dependencies and eval backends | Retain: documented optional FAISS baseline is selected by default; community wrappers and langchain compatibility splitter fallback have real consumers. | Existing eval baseline tests; no dependency removal. |
| P1-R02 | LangMem unwired expiry helper/table | Retain this phase: advertised expiration intent remains unresolved; removing an unwired helper would not establish obsolete responsibility. No expiry implementation/policy change. | Existing backlog; no decision needed for retention. |
| P1-R03 | data/chatbot.db.old and other data/runtime/recovery material | Protected, retain. Filenames/stat metadata only; no data inspection or deletion. | User data-preservation boundary. |

## Backend batch verification

P1-C01–03 implemented without test changes. Independent review confirmed exact removal closure and all retained declarations source-identical (19structured-state,15short-term,7guard). Direct JSON migration/shared validators and current LangMem/provider/End policy remain. Existing isolated integration collected509/selected508:508passed,1actual cross-encoder preload excluded,0failed/errored/skipped/xfail/xpass; source stable, native isolation passed,0externalrequests/tokens/cost. Full logs/JUnit/source/proofs: purge1-runs/backend.tar.gz. Focused Ruff/AST/diff checks pass. Initial static check found an already-unused urljoin import, removed in the touched guard; trailing blank lines introduced by deletion were corrected.

## Frontend/dependency/artifact batch

Implemented after independent pre/post-diff challenge: removed ChainlitChat.jsx.orig/.rej (234lines,7203bytes) whose rejected cleanup is already in unchanged actual JSX; removed unused fetchChatMessages/uploadDocumentFile exports only (18remaining export bodies byte-identical, SDK history/uploads and backend endpoints unchanged); removed unread Vite-plugin bindings only; removed unreferenced template favicon.svg/icons.svg (14553bytes). Product inline/Material Symbols icons remain. Core's root declaration is removed from both manifests; Puppeteer25.3.0 still resolves identical Core25.3.0 transitively, all package-lock nodes unchanged. No installed dependency removed or reclassified.

Corrected dynamic-consumer evidence: Tailwind's automatic scanner did consume the old backup/SVG tokens. The build loses exactly610bytes of generated CSS:4utilities unused by retained renderers plus5unused rotation/skew property registrations/initializers. Current disabled-state/rotation/border classes remain. Independent comparison reconstructs the new CSS byte-for-byte from just those removals; do not claim no build consumer.

Offline isolated verification passed dependency-root consistency, actual Puppeteer→Core resolution/npm tree, retained API imports, actual dev-console hook/log write, Node syntax and production build114modules. Initial auxiliary hook check read its asynchronous output prematurely; corrected check awaits the actual write promise, with initial failed evidence preserved. No production fix or retry loop. Existing >500KB bundle warning remains. [Frontend evidence](purge1-runs/frontend-summary.json); full React browser probes remain separately unexecuted, not inferred from native cases.
