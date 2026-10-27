# Current findings and bug backlog

TASK11 revalidation is complete against source1cf4c55 on codex/audit-main. Use the [current revalidated document](revalidation/findings-register.md), [exact coverage](revalidation/coverage-ledger.md), [execution evidence](revalidation/execution.md) and [task ledger](cleanup-plan.md).

The [original historical document](history/tmp-audit/docs/audit/bug-backlog.md) remains unchanged for provenance. Its ui/tmp-audit line references, counts, findings and completion statements are historical. Current findings are supported/revised/superseded/unresolved as recorded; no workflow/test removal or general fix is approved.

## Stage5 executed updates

See [current readiness](stage5/readiness.md), [bounded blocker evidence](stage5/blocker-resolution.md) and [latest results](stage5/runs/latest-summary.json). TASK14/DEC015 resolved S5-APP-01 native vec0 update, RV004 LongMem stale config, synthetic evaluator connectivity/schema prerequisites, and S5-APP-02 native login/state handling. All final selected cases pass; full forgetting and real-provider behavior remain unverified.

RV001 rebuild syntax/API remains parked. PB-FAIL-003 timeout oracle conflicts with implemented failed-assistant persistence; no desired policy inferred. Multi-user ownership/idempotency oracle limitations also remain. LongMem default document-neighbor initialization requires embedding assets even in memory-only adapter runs; tests now make this prerequisite explicit, without changing that production behavior. AUD17 exercised graph actual-request protection, TSA11/TSA13 strengthened assertions and other prior limits remain as recorded.

S5-UI-03 — native trace-comment presentation: an affected-run screenshot shows serialized breamon-trace comment text visible in the native transcript. app.py appends that metadata; React explicitly strips it in ChainlitChat.jsx. This is observed presentation evidence, not a new blocker fix or a claim that native message formatting is fully verified. Screenshot retained in blockers-affected-browser.tar.gz. Park for a separate UI task; it does not affect the proposed unreferenced diagram deletion.

## CH-UI-01 — React deleted-fetch failure reporting (static finding)

TASK19 source review also found that either displayed load error hides all rows despite the partial-results message. User policy decision is pending; React browser behavior has not been reproduced in an isolated browser.

`braemon/src/pages/Documents.jsx` and `Memories.jsx` log a rejected deleted/inactive fetch but do not add it to their `errors` list. If both fetches reject, source inspection indicates the UI reports only the active failure instead of the intended all-failed message; an inactive-only failure reports no page error. This is a static finding, not a runtime reproduction. A controlled React test and a separately scoped behavior/bug-fix decision should precede any shared loader hook; it does not block independently verified backend/evaluation cleanup.

## MAINT-01 — Simplify the test suite and its supporting infrastructure

Requested by the user in “Braem. audit co-work”, 2026-10-27. Deferred maintenance task, not a prerequisite for completing every coverage gap or starting an independently protected cleanup batch. See TASK13 and [maintainer scope](stage5/maintainer-scope.md).

- Review overlapping assertions and fixtures by the distinct failure/behavior they protect; consolidate only demonstrated equivalence. Preserve storage, service, HTTP and UI boundaries when they detect different regressions.
- Review the custom isolation runner for simpler equivalent controls and portable configuration; retain verified filesystem, credential and network isolation.
- Keep a small, useful default suite with explicit integration/browser/live-evaluation/manual groups. Separate generated run evidence from maintained documentation and define retention without losing baseline provenance.
- Known leads: three equivalent selector parameter instances and repeated explicit MAB embedding setup. Recheck current consumers and unique coverage before changing them; historical constructor-only and Pillow weaknesses were already repaired.
- Completion: a concrete reduction proposal followed by separately authorized changes, preserved relevant outcome/negative-control checks, independently reviewed isolation, before/after size and runtime evidence, and documented exclusions. Do not remove tests merely because they fail or pass, pursue a line-count quota, or weaken assertions to obtain green results.

Backlog entry only: no test deletion, runner rewrite or evidence removal authorized by this request.

## User-reported functionality check — 2026-10-27

The user reports: “I have already done a full functionality check.” Record this as user-reported manual verification of the current application. Detailed scenarios, exact source revision and results were not supplied. It does not overwrite historical automated failures or deferred coverage. TASK14 reconciles these observations and records subsequent passing automation separately; exact manual surface/revision remains unknown.
