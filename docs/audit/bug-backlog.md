# Current findings and bug backlog

TASK11 revalidation is complete against source1cf4c55 on codex/audit-main. Use the [current revalidated document](revalidation/findings-register.md), [exact coverage](revalidation/coverage-ledger.md), [execution evidence](revalidation/execution.md) and [task ledger](cleanup-plan.md).

The [original historical document](history/tmp-audit/docs/audit/bug-backlog.md) remains unchanged for provenance. Its ui/tmp-audit line references, counts, findings and completion statements are historical. Current findings are supported/revised/superseded/unresolved as recorded; no workflow/test removal or general fix is approved.

## Stage5 executed updates

See [readiness/blockers](stage5/readiness.md), [execution](stage5/execution.md) and [latest machine results](stage5/runs/latest-summary.json). Native vec update primary-key failure (S5-APP-01) and UI login overlay (S5-APP-02) are executed findings. JS const reassignments remain static, not reached. RV004 LongMem removed config caller and synthetic mock-evaluator guard failures reproduced. RV001rebuild syntax remains. Timeout product-oracle expectation conflicts with current failed-assistant persistence; no desiredpolicy inferred. No appfix authorized/performed.

AUD17's exercised graph request now has recorded selected evidence/no fallback and omission/leak assertion negatives with realChroma/localembeddings; this does not certify all providers/modes. Native structured-vector store/namespace and deletion paths passed with real384dim vec0; update fails and fullforgetting remains unverified. TSA11constructor-only and TSA13installed-only tests strengthened; their old weakness is no deletionreason. Browser/React/live gaps remain explicit rather than counted as passes.
