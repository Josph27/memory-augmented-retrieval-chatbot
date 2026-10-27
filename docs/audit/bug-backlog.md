# Current findings and bug backlog

TASK11 revalidation is complete against source1cf4c55 on codex/audit-main. Use the [current revalidated document](revalidation/findings-register.md), [exact coverage](revalidation/coverage-ledger.md), [execution evidence](revalidation/execution.md) and [task ledger](cleanup-plan.md).

The [original historical document](history/tmp-audit/docs/audit/bug-backlog.md) remains unchanged for provenance. Its ui/tmp-audit line references, counts, findings and completion statements are historical. Current findings are supported/revised/superseded/unresolved as recorded; no workflow/test removal or general fix is approved.

## Stage5 executed updates

See [readiness/blockers](stage5/readiness.md), [execution](stage5/execution.md) and [latest machine results](stage5/runs/latest-summary.json). Native vec update primary-key failure (S5-APP-01) and UI login overlay (S5-APP-02) are executed findings. JS const reassignments remain static, not reached. RV004 LongMem removed config caller and synthetic mock-evaluator guard failures reproduced. RV001rebuild syntax remains. Timeout product-oracle expectation conflicts with current failed-assistant persistence; no desiredpolicy inferred. No appfix authorized/performed.

AUD17's exercised graph request now has recorded selected evidence/no fallback and omission/leak assertion negatives with realChroma/localembeddings; this does not certify all providers/modes. Native structured-vector store/namespace and deletion paths passed with real384dim vec0; update fails and fullforgetting remains unverified. TSA11constructor-only and TSA13installed-only tests strengthened; their old weakness is no deletionreason. Browser/React/live gaps remain explicit rather than counted as passes.

## MAINT-01 — Simplify the test suite and its supporting infrastructure

Requested by the user in “Braem. audit co-work”, 2026-10-27. Deferred maintenance task, not a prerequisite for completing every coverage gap or starting an independently protected cleanup batch. See TASK13 and [maintainer scope](stage5/maintainer-scope.md).

- Review overlapping assertions and fixtures by the distinct failure/behavior they protect; consolidate only demonstrated equivalence. Preserve storage, service, HTTP and UI boundaries when they detect different regressions.
- Review the custom isolation runner for simpler equivalent controls and portable configuration; retain verified filesystem, credential and network isolation.
- Keep a small, useful default suite with explicit integration/browser/live-evaluation/manual groups. Separate generated run evidence from maintained documentation and define retention without losing baseline provenance.
- Known leads: three equivalent selector parameter instances and repeated explicit MAB embedding setup. Recheck current consumers and unique coverage before changing them; historical constructor-only and Pillow weaknesses were already repaired.
- Completion: a concrete reduction proposal followed by separately authorized changes, preserved relevant outcome/negative-control checks, independently reviewed isolation, before/after size and runtime evidence, and documented exclusions. Do not remove tests merely because they fail or pass, pursue a line-count quota, or weaken assertions to obtain green results.

Backlog entry only: no test deletion, runner rewrite or evidence removal authorized by this request.

## User-reported functionality check — 2026-10-27

The user reports: “I have already done a full functionality check.” Record this as user-reported manual verification of the current application. Detailed scenarios, exact source revision and results were not supplied. It does not overwrite the recorded six automated failures, twelve browser setup errors, or deferred coverage. Reconcile those observations in the next bounded blocker batch; manual verification and automated evidence remain separate.
