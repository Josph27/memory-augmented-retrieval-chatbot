# PURGE2 consolidation ledger

TASK17 / DEC018. Baseline `ae35188`, clean `codex/audit-main` worktree. User confirmed application functionality after PURGE1; precise manual scenarios and runtime configuration were not specified. Prior [PURGE1 evidence](purge1-completion.md) remains the automated baseline. One implementation writer, independent challenge of consequential batches. No live inference or production data.

| Responsibility / area | Implementations and callers | Meaningful differences / proposed boundary | Protection | Disposition / outcome |
|---|---|---|---|---|
| Document loading / indexing | Existing CLI and application ingestion | Under assessment; compare loader ordering, return/error contracts, state and consumers. | Existing loader, ingestion, indexing and lifecycle cases. | Pending assessment. |
| Native / demo retrieval preparation | Native and graph/demo paths | Under assessment; compare traces, fallback, scope, async and budgeting. | Existing request/composition, graph and retrieval cases. | Pending assessment. |
| Other application, frontend, CLI and evaluations | Existing workflow map and PURGE1 area dispositions | Bounded lead assessment; retain distinct policies. | Existing unit, integration, app, wrapper, browser and frontend groups. | Pending assessment. |

MAINT-01/TASK13 test-suite simplification and PURGE3 broad restructuring remain deferred.
