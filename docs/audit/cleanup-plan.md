# Cleanup plan and task ledger

Updated 2026-10-27. Governing sequence DEC-008: inference → audit/handoff → scope → test audit → protection → PURGE1 → PURGE2 → PURGE3 → final acceptance. Documentation/blocker triage throughout. [Historical full ledger](history/tmp-audit/docs/audit/cleanup-plan.md) retains TASK-01–09 details.

| Task | Ownership / dependency | Current state / completion gate |
|---|---|---|
| TASK-10 — Recover onto main (DEC-009) | Coordinator sole writer; independent migration reviewer | Complete: verified backup, separate main worktree, provider port, 23 focused offline checks, independent review and coherent commits. Original-state checks recorded in migration.md. |
| TASK-01 — Baseline/handoff | Coordinator; TASK-10 | Main baseline pinned; prior provenance retained. Migration evidence supersedes old current-checkout wording. |
| TASK-09 — Existing-test audit | Audit assessment plus independent reviews; TASK-10 | Old assessment completed historically; reopened for bounded delta revalidation. Re-inventory changed/new tests, then reassess affected assertions/coverage. No deletion authorized. |
| TASK-02/03 — Scope and concrete proposals | Coordinator + user for capability choices; current evidence | Zero workflow removals approved; DEC-101–107 only when relevant. |
| TASK-04 — Protection | Depends on revalidated TASK-09 and bounded scope | Not started generally. Isolation must include canonical settings, SQL/sqlite-vec, document Chroma, download caches, cwd logs, inference and app import preload. |
| TASK-05/06/07 — Purge/consolidate/restructure | Dependencies and batch approval as historical ledger | Not started; migration is not approval. |
| TASK-08 — Acceptance | Implementation tiers and user functionality confirmation | Not started; no full application verification claimed. |

## Immediate follow-up after transfer

1. Reconcile test inventory against main: new coordinator/consolidation tests, React E2E, removed upload probes, changed scheduling/end/timeout semantics. Static first; classify intended/implemented/asserted behavior separately.
2. Establish full-suite isolation using current settings and new side-effect map; migration tests exercise only their bounded provider seams.
3. Run existing request-composition/lifecycle/memory protection only after isolation is verified; record baseline failures before proposing test/app changes. AUD-17/20 original arguments are superseded, not runtime-fixed conclusions.
