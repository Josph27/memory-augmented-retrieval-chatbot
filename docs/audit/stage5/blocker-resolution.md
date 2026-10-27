# TASK14 — bounded blocker resolution

DEC015 authorizes four blocker fixes only; DEC013 remains SQL-success/logged-vector-failure. MAINT-01/TASK13 remains deferred. No purge or live inference.

## Preserved starting state

Initial source HEAD3593719 plus exactly five dirty files: React package/lock and audit backlog/ledger/decisions. Their exact bytes are preserved in /tmp/breamon-blocker-preexisting-backup (manifest + archive) and separately committed after independent review: c487db3 React18 type alignment;785ccd9 manual report/deferred maintenance. Manifest/lock agree; offline npm ls verified installed React/ReactDOM18.3.1 and type packages18.3.31/18.3.7. No install performed; this is dependency validation, not React browser verification.

Fresh initial integration run ty1ursk4:509collected/508selected,502passed6failed,0errors/skips/xfail/xpass;1real-model preload excluded. Native browser tv8j2jv5 reconfirmed the same loading-overlay interception in fresh sessions; deliberately interrupted to avoid repeating the shared setup failure. Its partial counts and incomplete cases are recorded in the machine summary; not a complete13-case baseline. Prior complete13-case baseline (1configuration pass/12setup errors) remains preserved.

## Manual versus automated UI evidence

The manual functionality report has no supplied surface/scenario matrix/exact revision. startup.py advertises the React frontend5173, whose main.jsx auto-authenticates and whose ModelLoadingScreen uses its own readiness API. It does not load native public/product-navigation.js. Native Chainlit separately injects that asset via .chainlit/config.toml. A fresh unauthenticated session is blocked by its immediate loading overlay; only an authenticated on_chat_start product-state can clear it. These observations can coexist. Native automation cannot certify React, nor invalidate the user's report.

Independent read-only review confirmed the login deadlock and later const-reassignment defects. Planned bounded fix: defer startup overlay until an authenticated composer exists, mark first state before clearing it, make reassigned state mutable, preserve End/Fork overlays. No forced interaction or test-side overlay bypass.

## Implemented fixes and classification

- a02bcfa: native vec0 INSERT OR REPLACE primary-key failure is an application defect. Both single and batch paths now delete/insert per row in the existing transaction, preserving last-write-wins for duplicates. All blobs are prepared before mutation. Existing update case checks real vector bytes/scores/count/identity, duplicate batch inputs and rollback after single/batch dimension errors; no new cases. SQL authority and DEC013 direct/combined error boundaries unchanged.
- 4dbcaa4: LongMemEval's obsolete config read is an evaluation defect; shared default500 retained. Its subsequently exposed uncached embeddings are an offline prerequisite defect: three existing tests explicitly substitute only embeddings, verify real temporary Chroma and retain every original report/retrieval/metric assertion. The default eager neighbor/backend initialization was not changed.
- 4dbcaa4: fake structured-memory extraction reaching real connectivity is an evaluation-harness defect. Inject a mock-only guard and explicit SQLite; schema-align exactly6synthetic category values (preferences→user_preferences4, demo decision→user_facts1, dependency policy→procedural1), retaining texts, keys and expected outcomes. Existing2sample tests require fake-manager invocation and reject real guard calls. Oracle answers still do not measure generated-answer quality.
- bc28550: native overlay deadlock and mutable state are application defects. Fix the production asset with authenticated-composer startup feedback and first-state handling; preserve End/Fork loading. Fresh browser tests then exposed4test prerequisite/assertion defects: missing explicit graph configuration and stale toolbar lists. The fixture requests graph mode before app import, toolbar lists include existing Consolidation Log, and **all original Inspector assertions remain**. Initial speculation about a changed field layout was rejected: the renderer has separate value spans. Cross-chat failure initially had zero selected evidence under native mode; final graph-mode provenance assertions genuinely pass.

## Independent review and execution

Read-only reviewers checked native/manual reconciliation, all consequential fixes, fixture category-only changes and the exact test repairs. Review caught bulk replacement breaking duplicate row IDs; corrected to per-row replacement and checked in the existing native case before runtime acceptance. No source/index/docs edits while tests ran. No test deletion, weakening, new cases or suite-wide simplification.

| Group / responsibilities | Collected | Passed | Failed | Errored | Skipped | Xfailed / Xpassed | Excluded | Pytest duration |
|---|---:|---:|---:|---:|---:|---|---|---:|
| offline-unit: routing, context, prompts, metrics, asset wiring | 127 | 127 | 0 | 0 | 0 | 0 / 0 | 0 within group | 16.39s |
| offline-integration: SQL/native vectors/Chroma, memory/document/lifecycle, fake evaluations | 509 | 508 | 0 | 0 | 0 | 0 / 0 | 1 cross-encoder preload | 36.20s |
| app-composition: real callbacks, trace serialization and report harness | 20 | 20 | 0 | 0 | 0 | 0 / 0 | 0 within group | 6.70s |
| subprocess-wrappers: shell/uv/config/status with fake answer/judge children | 21 | 21 | 0 | 0 | 0 | 0 / 0 | 0 within group | 2.04s |
| browser: native Chainlit fresh login and lifecycle/Inspector journeys | 13 | 13 | 0 | 0 | 0 | 0 / 0 | 0 within group | 86.16s |

Final690collected/1excluded/689selected,689passed; no collection errors, incomplete cases, skips or xfails. Same working-source snapshot across all5groups; exact hashes/index/dirty paths in each archive. Final committed application/test bytes match that tested state. Native parent/child controls support0externalrequests/tokens/cost for every run; fake-call totals unknown. Twelve native browser page-error artifacts are empty.

Fresh initial integration:502pass6fail; deliberately partial browser1pass6setup errors6unfinished (progress216.07s; launcher265.02s, exit143). First affected integration505pass3embedding failures; first affected browser9pass4call assertion failures. All retained separately in [machine summary](runs/blockers-summary.json) and compressed logs, without adding reruns to final coverage. Original complete browser baseline remains unchanged.

Focused Python AST, Ruff --no-cache, JavaScript syntax and whitespace checks pass. First local Ruff invocation hit a read-only cache path; cache-free validation then passed. Isolated React build passed (114modules); existing >500KB bundle warning retained in [build evidence](runs/blockers-react-build.tar.gz), not treated as a blocker. No package install performed.

## Readiness and first cleanup

[Current readiness](readiness.md) records remaining product-oracle disagreements, deferred live/React/default-model/forgetting policy checks, existing unrelated defects and the independently consumer-checked **single PNG removal proposal**. The file remains present. Zero workflow removals approved; no purge started; MAINT-01/TASK13 remains deferred. No current product decision blocks that artifact proposal. Spending and artifact deletion each require their own future authorization.
