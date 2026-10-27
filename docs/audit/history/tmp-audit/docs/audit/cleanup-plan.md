# Cleanup plan and task ledger

Package v1.2 · 2026-10-27. DEC-006/007 authorize the completed documentation-only test-suite assessment before selecting implementation batches or expanding protection. Later cleanup stages remain **not execution approval**. Bugs remain in [their backlog](bug-backlog.md); do not convert cleanup into general bug fixing.

## Current execution sequence — DEC-008

Stable TASK IDs below are ledger identities, not stage numbers. The latest user plan governs stage order:

| Stage | Objective / current status | Ledger mapping |
|---|---|---|
| 1 — Restore inference | Provider connectivity restored/user-reported; not full application verification. | Historical provider work; TASK-01 provenance |
| 2 — Read-only audit and durable handoff | Static audit/handoff completed with documented limits; package uncommitted. | TASK-01 |
| 3 — Scope decisions | No justified workflow-removal candidates; zero is valid. Retained constraints recorded; relevant ambiguities remain open until needed. | TASK-02/03, DEC-001/101–107 |
| 4 — Audit existing tests | **Completed static assessment and independent review**: existing protection, misleading assertions, isolation risks and gaps; no runtime baseline. | TASK-09 |
| 5 — Establish protection | Future bounded test repairs/additions, independent coverage review and baseline failures. | TASK-04 |
| 6 — PURGE1 | Approved unnecessary code/artifacts; check runtime/config/CLI/eval/asset/operational consumers and verify each batch. | TASK-05 with TASK-03 approval |
| 7 — PURGE2 | Consolidate equivalent responsibilities, preserving differences/fallbacks. | TASK-06 |
| 8 — PURGE3 | Restructure resulting responsibilities; update imports, entry points, packaging and docs. | TASK-07 |
| 9 — Final acceptance/backlog | Setup/startup and retained workflows; user functionality confirmation; docs reconciliation and bug prioritization. | TASK-08 |

Documentation updates and blocker triage run throughout. Coordinator handles bounded implementation, verification and review at an authorized tier; user decides capability changes and validates the product. Stage 4 does not authorize Stage 5+ changes. Relevant scope decisions can be revisited after test assessment without reopening unrestricted auditing.

## Task ledger

| ID / stage | Status and dependency | Completion criterion / smallest next action |
|---|---|---|
| TASK-01 — Baseline and handoff | Historical static baseline completed with provenance gaps; documentation consolidation completed in this package. | Incoming worker reads README/decisions, records current commit **and dirty state**, and checks relevant symbol/fingerprint drift before relying on old evidence. Never reset the checkout or apply stashes to recreate an assumed baseline. |
| TASK-09 — Existing test-suite audit | **Completed, coordinator accepted bounded static assessment**, authorized DEC-006/007; depends on TASK-01. Main: “Audit Breamon repository”; two independent internal reviewers; coordinator owns ledger. | [Assessment](test-suite-audit.md), [inventory](test-suite-inventory.md), [symbols](test-suite-symbols.md), reports 03–05. 80 Python sources / 602 lexical test functions; evaluation support, JS/manual/shell/config consumers inventoried with depth limits. All 80 test/probe source roles assessed; consequential recommendations and retained sample independently challenged. No collection/execution or test/app changes. |
| TASK-02 — Workflow/product decisions | Initial Stage 3 removal screen completed with **zero justified candidates**; outstanding choices deferred until relevant batch after TASK-09. | Resolve only choices needed for proposed cleanup (`DEC-101`–`DEC-107`). Keep required behavior and fallback boundaries explicit. No qualifying workflow removal is currently proposed. Do not require all open product decisions before static test assessment. |
| TASK-03 — Concrete cleanup proposal | **Proposed, not authorized for execution**; depends on TASK-02. | For each workflow/file candidate record consumers, dynamic/CLI/config/eval selectors, replacement responsibility coverage, concrete benefit, invalidators, relevant protection and exact proposed removal. User approval must distinguish planning from execution. “No direct import” is insufficient. |
| TASK-04 — Protection tests | **Deferred; no tests run or written here**; depends on TASK-09, defined behavior and authorization. | Use reviewed test-audit evidence to scope protection. Isolate SQL, vector paths, namespace, environment and inference before any import. Add minimal outcome tests for the affected boundary; see prerequisite table below. Record commands/results and unsupported environments honestly. |
| TASK-05 — Approved workflow/file removal | **Not approved**; depends on TASK-03 approval and TASK-04 passing. | Remove only explicitly approved scope with tested replacement/fallback preservation, rollback strategy and updated consumer documentation. No stashed deletion is approved. |
| TASK-06 — Consolidation | **Proposed**; after removal decisions and protection, or an expressly approved no-removal route. | Merge only equivalent responsibilities; retain meaningful differences and deterministic operations. Deprecated updater/helper separation is a lead, not an authorized deletion. Avoid flag-heavy generalizations. |
| TASK-07 — Restructuring | **Deferred**; depends on stabilized responsibility boundaries and TASK-06. | Make targeted navigation/ownership improvements, update all import/CLI/asset paths and verify launch/eval consumers. Moving files is not workflow removal. No wholesale folder redesign is approved. |
| TASK-08 — Final verification/documentation | **Future**; depends on authorized implementation stages. | Run agreed deterministic, isolated integration and frontend checks; separately identify any live provider evaluations. Reconcile setup/docs, inspect actual prompt/trace parity, update WF/AUD/DEC/TASK records and report remaining risks. No implied permission to run production inference or touch real data. |

## Bugs that may block trustworthy protection or cleanup

These remain parked unless the selected work actually depends on them; each requires separate implementation scope.

| Dependency | Minimal proposed protection / expected invariant | Isolation and starting test |
|---|---|---|
| AUD-07/20 — testing must not mutate real stores | Import/source-inspection subprocess plus structured-eval vector/hybrid case; all writes stay inside temporary storage and namespaces. | Export isolated paths before import, fake embedding transport, sentinel index. Start `tests/test_structured_memory_eval.py`, `tests/test_structured_memory_vector_sync.py`; add import-boundary test. |
| AUD-17 — selection is not proof of answer context | Real builder plus recording model with document/span evidence; actual sent prompt contains selected evidence and trace matches it. | Synthetic SQLite/candidates, no inference. Extend `tests/test_orchestration_demo_modes.py`. |
| AUD-02/06 — lifecycle/memory cleanup needs reliable outcomes | Same pending turns through native/REST End; empty first online batch does not permanently starve later valid memory. | Fake updater, temporary SQL/index, deterministic batch settings. Extend `tests/test_chat_end_action.py`, `tests/test_short_term_memory_scheduling.py`. |
| AUD-01/03/16/19 — ambiguous behavior must not be frozen accidentally | Scope, deletion, fork and edit tests match an explicit product decision, including caches/provenance and later extraction. | Resolve DEC-101–104 first; synthetic data only. Start document lifecycle, long-term store, chat lifecycle and fork tests. |

## Removal screen and current result

No workflow removals are justified by the current evidence. The last decision brief recommended none; the user has not subsequently approved one. Optional modes, evaluations, operational tools, advertised-but-unwired features and broken paths are not disposable by default.

The deprecated `StructuredMemoryState` in `src/memory/structured_state.py` is a possible **implementation-consolidation** subject: its operation helpers had no checked consumers outside that class, but active `LangMemStructuredMemoryState` imports shared validators from the same module. A module deletion would remove retained behavior. Patch rejects/backups and generated artifacts require their own consumer/provenance checks; they are not approved workflow candidates.

## Authorized next action

TASK-09 is complete at its documented static depth. Stage 5 / TASK-04 is next and has not started; the assessment itself does not authorize test/app modifications or remove the isolation gate. Start its bounded scope with pre-import isolation and a baseline run of existing sensitive tests before adding duplicates. Collection/execution require verified and documented isolation of SQL, document and structured-memory vectors, namespaces, environment, credentials/transports, tokenizer/model loaders, filesystem/caches and network effects. Resolve only behavior choices actually needed by that batch.

### TASK-09 assignment and review gates

- **Objective / scope:** existing tests and test-like scripts, assertion quality and unique coverage; documentation only.
- **Ownership:** main auditor owns `test-suite-audit.md`, `test-suite-inventory.md` and related `test-suite-*` supporting evidence; coordinator owns this ledger, README and decisions; internal reviewer is read-only and reports to coordinator. One documentation writer per owned file.
- **Behavior to preserve:** DEC-001 and existing required capabilities/fallbacks. Product intent comes from explicit requirements/decisions; source behavior and test assertions are separate evidence.
- **Verification:** static inventory and source/caller checks initially; independent review of consequential replace/removal recommendations and a diverse retained-test sample. Inventory counts are static counts, not collection/pass results.
- **Completion:** reviewed classifications, exact coverage/consumer evidence, isolation limitations and subsequent verification proposals, with no test/app modifications. Record partial/uninspected areas honestly.
- **Escalation:** only material behavior ambiguities blocking the assessment, unauthorized scope expansion, private-state risk, or unresolved consequential reviewer disagreement. Park unrelated bugs.
- **Baseline observed by coordinator:** branch `tmp-audit`, HEAD `c3ffee2`; existing provider modifications and untracked handoff/provider files preserved. Earlier handoff check matched 53/53 source fingerprints; this is static drift evidence, not a runtime baseline.

### TASK-09 completion record

- Main assessor delivered v1.2 on 2026-10-27; coordinator accepted the bounded static assessment after reconciling independent reviews. This is assessment completion, not product acceptance, passing-test evidence or approval to execute recommendations.
- Inspection provenance: 49 Python sources with main setup/assertion slices, 31 additional files with independent setup/assertion review; 12-item initial sample plus consequential cross-challenge. Every helper/branch/plugin/CLI combination was not exhaustively inspected.
- Primary file dispositions: 42 retain, 34 strengthen, 2 replace, 2 unresolved; mixed per-symbol caveats remain. No whole-file removal. Narrow reduction candidates are one constructor-only test and three equivalent selector parameter instances; replacement/preservation conditions are explicit in TSA-11/12.
- Review corrected untagged-score overclaims, cache-versus-durable-memory claims, missing-actual-request coverage claims, literal fixture-equivalence wording and source-string network assertions. No material disagreement or user ambiguity blocks assessment completion.
- Coordinator checks: inventory paths/counts reconciled by AST without imports; local Markdown links valid; 284 recorded application/test/supporting source files unchanged. No tests, app, inference, ingestion, migration, install or Git mutation executed by this phase.
- Stage 5 priorities: verified isolation (TSA-01/02/10), execute existing real-composition request/lifecycle/memory tests and record baseline failures, then bounded oracle/assertion repairs with negative controls and independent review. Park application bugs unless they block that authorized batch.
