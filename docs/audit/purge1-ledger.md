# PURGE1 maintained-area and removal ledger

TASK16 / DEC017. Engineering complete; user confirmed application functionality under DEC018; baseline3a3ad03e5fb33b23c56aa5f36e49c1f2e413bf67. Existing audit/workflow/test maps supply area coverage; this is cleanup disposition work, not a general audit restart. One implementation writer; independent read-only challenge of consequential removals.

## Reviewed maintained areas

All463baseline tracked paths are accounted for by the areas below, using the existing per-file/workflow audit plus bounded current consumer checks. This is responsibility/consumer disposition, not exhaustive branch or test coverage. New current audit records/evidence are retained as outputs of this phase.

| Baseline area / paths | Disposition and checked responsibilities |
|---|---|
| Root17 | Retain entrypoints app.py/startup.py/run.sh, provider/config examples, pyproject/uv lock/runtime selector, root conftest, policy/license/README/Chainlit/planning records. Check startup/script references and package selectors; no root backup/patch files found. |
| .chainlit1 / .dev2 | Retain actual native custom-JS configuration and paired developer start/stop scripts. Different process-management responsibility is not obsolete startup duplication. |
| src85 | Retain all modules: agents/contracts/context, documents/inspection, DB/API/data-layer/lifecycle, config/provider/model, routing/retrieval/native/demo/shadow, LangMem/storage/vectors/gists. Remove only P1-C01–03 declarations and P1-C04 unused import aliases. Thin wrappers, fallbacks, optional modes and legacy persisted-JSON migration remain. |
| braemon31 | Retain bootstrap,7routes/pages, all active components/SDK paths, styles, config and toolchain; Home only loses3unused named import bindings. Remove2unused API wrappers, dead plugin bindings,2patch artifacts and2template SVGs; duplicate direct Core declaration only. |
| public1 | Retain explicitly configured native navigation/Inspector/lifecycle asset. Native is separate from React. |
| scripts20 | Retain12Python,7shell and maintained doc: index/rebuild/inspect/backfill/forensics, memory/live diagnostics, final-answer/judge/targeted wrappers, shared env/path helpers and isolated runner. Broken RV001 has unique repair capability; no deletion. |
| evals91 | Retain59Python sources incl21CLI entrypoints plus fixture/manifest/doc support across all evaluation families: retrieval, memory, replay/selection, judge/resume/report/product diagnostics. Optional/expensive/manual paths have distinct roles. |
| tests86 | Retain all tests, synthetic fixtures, support/bootstrap/canaries and native/Node/socket probes. No test identities or assertions changed; MAINT-01/TASK13 and fixture dedup deferred. |
| docs126 (includes audit) | Remove only approved PNG. Retain other rendered diagram (no verified equivalent replacement), Mermaid sources, architecture/lifecycle/evaluation/runbooks/reference/limitations/proposals and sidecar docs. Update only current affected descriptions. Historical audits/inventories/source snapshots/run archives stay byte-identical. |
| data3 | Preserve all tracked databases, including chatbot.db.old and document-vector DB. Git names/sizes metadata only, no contents inspected. |

Ignored/runtime boundary: .env/local_settings.py, data, logs/uploads/runtime outputs, .venv, braemon/node_modules, build/cache directories and Git/stashes/recovery backups are preserved. Only existence/type or Git metadata inspected for accounting; no recursive private-content/size scan, cleanup or user-data deletion. Installed dependencies are read-only inputs inside isolated verification. Runtime total sizes remain unknown.

Python manifests: retain17runtime+3dev declarations; all have core/optional/compatibility/evaluation/tool consumers. uv.lock254records/248names conservatively reachable through runtime/optional/dev dependency graph; no proven orphan. Frontend:10→9direct runtime declarations,5dev unchanged; identical transitive Core package retained.

## Candidate ledger

| ID | Candidate / bounded scope | Evidence and disposition | Verification / dependency |
|---|---|---|---|
| P1-A01 | docs/mermaid-diagram-2026-07-15-021559.png | Removed752065d under DEC016; no active consumer; retained Mermaid hash unchanged. | References/assets/packaging/source/diff/link checks; [recovery](purge1-batch1.md). |
| P1-C01 | structured_state.py deprecated JSON-operation updater and exclusive helpers | Removed in3399a2b: no maintained runtime/config/dynamic/CLI/eval/frontend/package selector; active ShortTermMemory chooses LangMem. Retain shared validators/contracts/JSON migration unchanged. | Independent challenge accepted; retained19structured-state declarations byte-identical, plus15short-term and7guard declarations unchanged. Affected isolated integration:508passed/1real-model preload excluded,0fail/error/skip; source stable. Existing LangMem, scheduling, store, vector, eval and context/request tests. |
| P1-C02 | short_term.py unused ChatEndMemoryProcessingError declaration | Removed in3399a2b: no raises/catches/imports; keep current partial-result and real exception behavior. | Independent challenge accepted; existing End/failure/scheduling protection. |
| P1-C03 | connection_guard.py unused connection_guard_from_env factory | Removed in3399a2b: actual provider-aware model/LangMem constructors instantiate guard; no factory consumers. Keep guard/cache/timeout/env helpers. | Independent challenge accepted; unused urljoin import also removed after focused static check, preserving actual URL construction. Existing provider/guard/LangMem tests. |
| P1-D01 | braemon direct puppeteer-core declaration | Removed root declaration in858d4f2: both Node probes import puppeteer, whose exact transitive core dependency stays. No installed package/browser capability removal. | Independent review and offline resolution/build passed; final groups passed; see final handoff. |
| P1-R01 | FAISS/community/langchain dependencies and eval backends | Retain: documented optional FAISS baseline is selected by default; community wrappers and langchain compatibility splitter fallback have real consumers. | Existing eval baseline tests; no dependency removal. |
| P1-R02 | LangMem unwired expiry helper/table | Retain this phase: advertised expiration intent remains unresolved; removing an unwired helper would not establish obsolete responsibility. No expiry implementation/policy change. This is an explicit retention disposition, not an outstanding PURGE1 removal decision. | Existing backlog; no decision needed for retention. |
| P1-R03 | data/chatbot.db.old and other data/runtime/recovery material | Protected, retain. Filenames/stat metadata only; no data inspection or deletion. | User data-preservation boundary. |

## Backend batch verification

P1-C01–03 implemented without test changes. Independent review confirmed exact removal closure and all retained declarations source-identical (19structured-state,15short-term,7guard). Direct JSON migration/shared validators and current LangMem/provider/End policy remain. Existing isolated integration collected509/selected508:508passed,1actual cross-encoder preload excluded,0failed/errored/skipped/xfail/xpass; source stable, native isolation passed,0externalrequests/tokens/cost. Full logs/JUnit/source/proofs: purge1-runs/backend.tar.gz. Focused Ruff/AST/diff checks pass. Initial static check found an already-unused urljoin import, removed in the touched guard; trailing blank lines introduced by deletion were corrected.

## Frontend/dependency/artifact batch

Implemented after independent pre/post-diff challenge: removed ChainlitChat.jsx.orig/.rej (234lines,7203bytes) whose rejected cleanup is already in unchanged actual JSX; removed unused fetchChatMessages/uploadDocumentFile exports only (18remaining export bodies byte-identical, SDK history/uploads and backend endpoints unchanged); removed unread Vite-plugin bindings only; removed unreferenced template favicon.svg/icons.svg (14553bytes). Product inline/Material Symbols icons remain. Core's root declaration is removed from both manifests; Puppeteer25.3.0 still resolves identical Core25.3.0 transitively, all package-lock nodes unchanged. No installed dependency removed or reclassified.

Corrected dynamic-consumer evidence: Tailwind's automatic scanner did consume the old backup/SVG tokens. The build loses exactly610bytes of generated CSS:4utilities unused by retained renderers plus5unused rotation/skew property registrations/initializers. Current disabled-state/rotation/border classes remain. Independent comparison reconstructs the new CSS byte-for-byte from just those removals; do not claim no build consumer.

Offline isolated verification passed dependency-root consistency, actual Puppeteer→Core resolution/npm tree, retained API imports, actual dev-console hook/log write, Node syntax and production build114modules. Initial auxiliary hook check read its asynchronous output prematurely; corrected check awaits the actual write promise, with initial failed evidence preserved. No production fix or retry loop. Existing >500KB bundle warning remains. [Frontend evidence](purge1-runs/frontend-summary.json); full React browser probes remain separately unexecuted, not inferred from native cases.

## Remaining/deferred dispositions

- Retain FAISS/community/datasets/model/PDF/vector dependencies and all evaluation/manual/optional/fallback workflows for checked consumers; no blanket deletion.
- Retain the larger rendered PNG because its ready-rendered reference role has no verified replacement; do not infer dispensability solely from absent links. Preserve data/recovery artifacts regardless of .old suffix.
- PURGE2: consider duplicate live document loading in scripts/index_document_file.py, native/demo retrieval preparation, and equivalent helper responsibilities only in separately authorized bounded proposals. Their live consumers and meaningful differences stay intact now.
- PURGE3: filesystem/module moves deferred. MAINT-01/TASK13 suite/fixture/framework simplification remains deferred.
- Existing RV001 CLI syntax/API, native trace presentation, incomplete expiry and product-oracle policy issues remain backlog; none blocks these removals. No unresolved PURGE1 capability/data/value decision remains. No additional justified safe-removal candidate remains from the recorded areas.

## Final verification gate

All safe code/dependency/artifact batches are implemented and independently reviewed. Final accumulated-state core/app/wrapper/native-browser groups passed689selected cases,1real-model exclusion. Final frontend checks/build/lint passed after the last import-only change. Current source/link/entrypoint checks and size-accounting handoff are recorded in the [completion report](purge1-completion.md) and [machine results](purge1-runs/final-summary.json). Four coherent removal commits preserve recovery history. No unresolved PURGE1 removal decision; no PURGE2 work had begun at that checkpoint. User confirmed application functionality on 2026-10-27 (DEC018).

## Final known-static-findings closure

P1-C04 removes4additional unused import aliases from the existing Ruff record: app.NATIVE, token_monitor.os, evidence_selector.field, and vector-sync's top-level LongTermMemoryVectorIndex alias. Actual normalization/dataclass/vector module imports remain; vector factory's active local import remains. Independent challenge found no module-attribute/export/dynamic/config/CLI consumer. All retained callable bodies source-identical (42/16/31/3respectively); no test changes.

Global lint31→25diagnostics (exit1 retained, no new diagnostic identities): unused source imports and one resulting duplicate-import warning removed. Existing RV001 syntax, Any annotation, formatting-only F541, manual-diagnostic F841 calculations and test-only unused import are explicitly retained/backlogged, not hidden or weakened. Manual calculations can perform dictionary access or helper calls; their safe simplification is not established by an unused-name warning alone. MAINT-01/test cleanup and general bug/style fixing remain outside this tier.

A first accumulated-state run passed689selected cases at858d4f2; it is not added to coverage. After the four Python import edits, the five agreed groups again passed689selected cases on stable frozen working bytes (label final-purge1-import-closure). Subsequent Home.jsx edit removes only3unused imported aliases endChat/reactivateChat/deleteChat; module import and all component/API bodies unchanged. Independent review accepted both exact changes. Final offline frontend checks/dependency-tree/build/lint passed at /tmp/breamon-purge1-frontend-7vo6bnaj; lint6→3warnings/0errors. Retain the unused error/catch parameter bindings and Fast Refresh warning: changing function arity, exception syntax or component boundaries is not a necessary safe-responsibility removal. Build outputs are byte-identical to the preceding passing build. No native-suite rerun needed for that frontend-only binding change.
