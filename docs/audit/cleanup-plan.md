# Cleanup plan and task ledger

Updated2026-10-27. Governing DEC008 sequence: inference → audit/handoff → scope → test audit → protection → PURGE1 → PURGE2 → PURGE3 → final acceptance. Documentation/blocker triage throughout. Historical TASK01–09 detail remains [archived](history/tmp-audit/docs/audit/cleanup-plan.md); current evidence overrides stale baseline/completion statements.

| Task | Ownership / dependency | Current state / completion gate |
|---|---|---|
| TASK10 — Recover onto main (DEC009/010) | Coordinator; independent review | Complete. Original checkout/28dirty files/stashes and recovery archive preserved. Main-based provider port committed; private settings copy separately approved/ignored. |
| TASK11 — Audit revalidation points1–4 (DEC011) | Existing Audit Breamon repository main assessor; coordinator coverage/execution; read-only internal isolation/evidence reviews | Complete and coordinator accepted.342relevant file entries; all16WF/20AUD/13TSA/80historicalTS reconciled; fournewRV observations.628distinct deterministic checks578pass49fail1skip +1deselected; canonical17overlap9pass8fail. Explicit unexecuted list and original/source integrity checks. See [assessment](revalidation/static-assessment.md), [coverage](revalidation/coverage-ledger.md), [execution](revalidation/execution.md). |
| TASK01 — Baseline/handoff | Coordinator; TASK10/11 | Current source1cf4c55 with exact actual-old comparison; current documentation durable. Source hashes detect subsequent product drift. |
| TASK09 — Existing-test audit | Main assessor plus bounded independent review; TASK11 | Current file/setup/assertion/consumer assessment complete at documented depth.80current Python sources643lexical tests,82old/current identity union; JS/browser/manual/eval/shell consumers reconciled. Full-suite/default runtime acceptance remains unverified. |
| TASK02/03 — Scope and concrete proposals | Coordinator + user for capability choices | Zero justified workflow removals and none approved. Resolve DEC101–106 only when relevant to a concrete protection/cleanup batch; DEC107 requires explicit removal proposal. |
| TASK04 / TASK12 — Stage5 protection (DEC012) | Coordinator + one implementation writer; independent isolation/repair review | In progress. Reviewed audit checkpoint, executable group/expense map, pre-collection isolation, initial baseline then bounded repairs/protection. Select prerequisite wiring/assertion repair or preserved-outcome protection batch from actual failures. Do not globally bypass guards/backends or silently adapt conflicting policies to green. |
| TASK05/06/07 — Purge/consolidate/restructure | Relevant batch approval and passing protection | Not started. No audit recommendation or obsolete/broken/default-off path authorizes deletion. |
| TASK08 — Acceptance | Implementation tiers + user functionality confirmation | Future. Startup/clean setup, full retained workflows/live-provider/browser/API checks and remaining bugs need explicit verification. |

## Next bounded preparation

1. Use current failures to separate test prerequisite wiring (guard/default document backend/model assets), implementation-characterization drift (sources/categories/provenance), and concrete integration blockers (RV001rebuild syntax/API, RV004LongMemEval field).
2. Choose one protection/adaptation batch with retained outcomes, relevant dependencies and isolation. Preserve existing actual-request, lifecycle, namespace and real temporary-Chroma tests. Browser/app-import/wrapper/live paths have explicit deferred prerequisites in [execution](revalidation/execution.md).
3. Resolve normative vector-error/finalization/scope/forgetting/fork/edit policy only where that batch needs it. Current conflicting assertions document ambiguity; they are not competing approvals.

The nine-stage cleanup order remains. Bugs stay parked unless they block the authorized next batch; no general repair campaign began. The audit completion is not a passing product verdict or Stage5 implementation approval.
