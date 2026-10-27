# PURGE1 completion and tier acceptance

2026-10-27 · TASK16 / DEC017 · branch `codex/audit-main` at `/home/josph/.codex/worktrees/audit-main/repo`.

Engineering complete; the user confirmed application functionality on 2026-10-27 (DEC018). Every justified safe removal from the recorded review is executed and independently reviewed. All 463 baseline tracked paths have a disposition in 11 areas; ignored/runtime areas have preservation boundaries, with recursive contents and sizes intentionally unknown. No unresolved PURGE1 product/data/value decision remains. This is bounded consumer/responsibility review using the existing audit, not a claim that every branch is covered or all possible dead code has been proven absent. PURGE2 had not started at that checkpoint; subsequent work is recorded in the [PURGE2 ledger](purge2-ledger.md).

## 1. Changes and recovery

Starting state: clean `3a3ad03e5fb33b23c56aa5f36e49c1f2e413bf67`. Four recoverable logical commits:

| Commit | Removal / practical benefit |
|---|---|
| `752065d` | Approved unreferenced 3,063,514-byte PNG; retained Mermaid source unchanged. Exact rendering equivalence was not claimed. |
| `3399a2b` | Unused custom JSON-operation updater and exclusive helpers, unused End exception and guard factory/import. Shared contracts, JSON migration and active LangMem policy remain source-identical. Reduces a misleading alternative implementation. |
| `858d4f2` | Two unused REST wrappers, unread plugin bindings, two superseded `.orig`/`.rej` files and two unused template SVGs. Direct `puppeteer-core` declaration removed; identical Core25.3.0 stays installed/locked through Puppeteer25.3.0. Actual React chat component, SDK history/uploads and backend endpoints unchanged. |
| `3fa357c` | Four Python import aliases plus three unused Home named imports. Retained callable/component bodies and API exports unchanged. |

Consumer checks include source references and attributes, configuration/dynamic selectors, CLI/evaluation entrypoints, frontend callers/assets, manifest/lock/package exports and operational scripts. No live-responsibility consolidation was included. Independent before/after review challenged removal closures, retained declarations, dependency resolution, CSS effects and final evidence. See [area/candidate ledger](purge1-ledger.md).

Tailwind implicitly scanned the removed patch/SVG files. Output CSS decreases by 610 bytes: exactly four unused utilities plus five unused property registrations/initializers; retained active selectors, including disabled variants, are unchanged. The files were not literally invisible to the build. Removing the SVGs also removes their otherwise-unreferenced Vite static URLs.

Recovery uses Git without rewriting history. For any removed file:

```bash
git restore --source=3a3ad03e5fb33b23c56aa5f36e49c1f2e413bf67 -- <repository-relative-path>
```

Then review and commit the restoration if desired. [PNG-specific recovery and hashes](purge1-batch1.md). Original `tmp-audit` checkout, 28 historical dirty files, stashes and recovery backup remain intact. No credentials, private settings, uploads or database contents were opened for cleanup; tracked data comparisons use Git metadata only.

## 2. Before / after

Basis: tracked starting tree versus maintained final working files. Logical lines use `splitlines`; application/evaluation/operations includes Python, JS/JSX, shell, CSS and HTML, and excludes tests and patch artifacts. Generated evidence is separated from reduction totals. [Machine census](purge1-runs/census.json) lists paths and categories.

| Category | Before | After | Difference |
|---|---:|---:|---:|
| Application/evaluation/operations code files | 174 | 174 | No module moves/deletions |
| Same code, logical lines | 43,788 | 43,330 | −458 |
| Same code, bytes | 1,570,453 | 1,554,729 | −15,724 |
| Diagram/template/patch artifacts, files | 6 | 1 | −5 |
| Same artifacts, bytes | 8,541,840 | 5,456,570 | −3,085,270 |
| Verification code, files / lines / bytes | 89 / 22,606 / 775,754 | Same | No tests changed |
| Frontend direct runtime declarations | 10 | 9 | Transitive Core unchanged |
| Python runtime / dev declarations | 17 / 3 | Same | All retained |
| Protected tracked data, files / bytes | 3 / 1,417,216 | Same | Metadata only |

Audit documentation and allowlisted run archives grew as evidence, separately from the code/artifact reductions. Final audit-record counts and bytes are in the census; generated test evidence is not application code. Ignored caches, installed dependencies, output directories and runtime/user data are preserved, with total sizes unknown. No disk-space reduction from dependency installation is claimed.

## 3. Final verification

Final five groups ran once on identical frozen source: `858d4f2` plus the recorded four Python import edits and dirty current documentation. Each archive stores exact HEAD, index/working-file hashes, before/after equality, commands, logs, JUnit and isolation proofs. Python/source bytes match committed `3fa357c`; the only later executable change was Home's three import bindings, independently accepted and verified by the final frontend run. Final frontend input hashes match committed frontend bytes. Documentation finalized after execution is not retroactively part of the run snapshots.

| Group / responsibilities | Collected | Passed | Excluded | Pytest duration |
|---|---:|---:|---:|---:|
| Offline unit: routing, budgeting, context, trace/contracts | 127 | 127 | 0 | 16.48s |
| Offline integration: synthetic stores/vectors, LangMem, document/evaluation/request composition | 509 | 508 | 1 | 37.04s |
| App composition: actual callbacks/lifecycle and product-oracle harness | 20 | 20 | 0 | 7.00s |
| Subprocess wrappers: CLI/environment/output contracts | 21 | 21 | 0 | 2.06s |
| Native browser: 12 local journeys plus one configuration check | 13 | 13 | 0 | 87.84s |
| **Distinct total** | **690** | **689** | **1** | **150.42s summed** |

All groups: zero failed, errored, skipped, xfailed, xpassed, collection errors or incomplete cases. Selected node IDs are disjoint; intermediate/affected reruns are not added to the total. The excluded actual cross-encoder preload requires real model assets and is not passing protection.

Filesystem/network namespaces, synthetic stores/config/caches, hidden real settings/home, subprocess inheritance and negative canaries passed before imports. Native browser traffic was confined to controlled private loopback; all 12 page-error artifacts are empty. These controls support zero external inference requests/tokens/cost; no provider metering occurred. Fake model calls were not counted and are not external requests.

Final offline frontend verification: root manifest/lock consistency, Puppeteer→Core resolution and dependency tree, 18 retained API imports, actual dev-console hook/log write, Vite build (114 modules), and lint all exit0. Lint has three retained warnings (error/catch bindings and Fast Refresh), and the preexisting >500KB bundle warning remains. Earlier auxiliary logger check failed because it read before the async append completed; the corrected check awaits the actual write promise. Initial failed evidence remains; no application fix, polling/retry loop or assertion weakening.

Changed-file syntax, shell wrapper syntax, startup `--help`, retained Mermaid hash, active references/entrypoints, current Markdown path links and `git diff --check` were checked. Python manifests/uv.lock, evaluation and wrapper callers, native config/assets and all test identities are unchanged. Global Ruff remains nonzero: 31→25 existing diagnostics, no new identities. Syntax-only parsing covers 233 Python files; the sole known RV001 rebuild-script syntax defect remains. No application launch using real credentials/data, clean dependency installation or live startup/model readiness was attempted.

Evidence: [final summary](purge1-runs/final-summary.json), [initial/corrected frontend checks](purge1-runs/frontend-summary.json), [backend batch](purge1-runs/backend-summary.json), [static/current-link checks](purge1-runs/final-static.json). Historical Stage5 initial/final evidence remains unchanged.

## 4. Limits, retained and deferred work

The non-browser product oracle remains **42 rows: 39 passed / 3 failed**, independently of passing pytest harness cases. PB-PERSIST-005 (multiuser), PB-FAIL-010 (broader idempotency), and PB-FAIL-003 (timeout oracle versus typed assistant failure) remain recorded gaps/mismatches. No product expectation was changed to make cleanup green. RV001 rebuild syntax/API and other existing backlog findings are not fixed by PURGE1; none blocks these specific removals.

Live-provider/extraction/judge checks, paid/repeated evaluations, actual embedding/reranker assets, and React/Node browser probes remain unexecuted; counts are unknown in this phase, with reasons/commands in the existing [group register](stage5/groups.json), [exclusion commands/reasons](stage5/exclusions.md) and [unexecuted checks](revalidation/unexecuted-checks.json). Native browser results do not substitute for React journeys. The [live proposal](stage5/live-proposal.md) remains subject to spending authorization.

Explicitly retained: active native/React/graph/shadow/fallback paths; all evaluations/manual diagnostics; FAISS/community and other optional Python dependencies; persisted JSON migration; advertised but incomplete expiry support; the other larger diagram render without a verified equivalent replacement; all data, history and recovery material. Unused-name lint alone did not justify removing diagnostic calculations or changing function signatures.

Deferred: equivalent **live** responsibilities to PURGE2, filesystem changes to PURGE3, and test-suite/fixture/framework/evidence-retention simplification to MAINT-01/TASK13. No further PURGE1 decision is requested.

## 5. Tier-end manual acceptance

Using the existing local setup, confirm:

1. Open React and native Chainlit; login/loading completes, Home and an existing chat render correctly, and icons/controls look normal.
2. Create/send/end/resume/fork a chat; confirm history and cross-chat memory still work as expected.
3. Upload a small document, ask a grounded question, inspect retrieval provenance; in development, check that browser console forwarding still writes its log.

The user subsequently confirmed application functionality without specifying individual scenarios or runtime configuration. This confirmation does not convert these items into completed automated live checks.
