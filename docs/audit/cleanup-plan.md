# Cleanup plan and task ledger

Updated2026-10-27. Governing DEC008 sequence: inference → audit/handoff → scope → test audit → protection → PURGE1 → PURGE2 → PURGE3 → final acceptance. Documentation/blocker triage throughout. Historical TASK01–09 detail remains [archived](history/tmp-audit/docs/audit/cleanup-plan.md); current evidence overrides stale baseline/completion statements.

| Task | Ownership / dependency | Current state / completion gate |
|---|---|---|
| TASK10 — Recover onto main (DEC009/010) | Coordinator; independent review | Complete. Original checkout/28dirty files/stashes and recovery archive preserved. Main-based provider port committed; private settings copy separately approved/ignored. |
| TASK11 — Audit revalidation points1–4 (DEC011) | Existing Audit Breamon repository main assessor; coordinator coverage/execution; read-only internal isolation/evidence reviews | Complete and coordinator accepted.342relevant file entries; all16WF/20AUD/13TSA/80historicalTS reconciled; fournewRV observations.628distinct deterministic checks578pass49fail1skip +1deselected; canonical17overlap9pass8fail. Explicit unexecuted list and original/source integrity checks. See [assessment](revalidation/static-assessment.md), [coverage](revalidation/coverage-ledger.md), [execution](revalidation/execution.md). |
| TASK01 — Baseline/handoff | Coordinator; TASK10/11 | Current source1cf4c55 with exact actual-old comparison; current documentation durable. Source hashes detect subsequent product drift. |
| TASK09 — Existing-test audit | Main assessor plus bounded independent review; TASK11 | Current file/setup/assertion/consumer assessment complete at documented depth.80current Python sources643lexical tests,82old/current identity union; JS/browser/manual/eval/shell consumers reconciled. Full-suite/default runtime acceptance remains unverified. |
| TASK02/03 — Scope and concrete proposals | Coordinator + user for capability choices | Zero justified workflow removals and none approved. Resolve DEC101–106 only when relevant to a concrete protection/cleanup batch; DEC107 requires explicit removal proposal. |
| TASK04 / TASK12 — Stage5 protection (DEC012) | Coordinator + one implementation writer; independent isolation/repair review | Test protection delivered; subsequent TASK14/DEC015 resolves the four automated blockers. Final689selected cases pass across5disjoint groups,1real-model case excluded;12native UIjourneys pass. [Readiness](stage5/readiness.md) gives remaining limits and a bounded artifact proposal, not blanket workflow-removal approval. |
| TASK05/06/07 — Purge/consolidate/restructure | Relevant batch approval and passing protection | Not started. No audit recommendation or obsolete/broken/default-off path authorizes deletion. |
| TASK08 — Acceptance | Implementation tiers + user functionality confirmation | Future. Startup/clean setup, full retained workflows/live-provider/browser/API checks and remaining bugs need explicit verification. |

## Historical Stage5 preparation sequence (completed/superseded)

1. Use current failures to separate test prerequisite wiring (guard/default document backend/model assets), implementation-characterization drift (sources/categories/provenance), and concrete integration blockers (RV001rebuild syntax/API, RV004LongMemEval field).
2. Choose one protection/adaptation batch with retained outcomes, relevant dependencies and isolation. Preserve existing actual-request, lifecycle, namespace and real temporary-Chroma tests. Browser/app-import/wrapper/live paths have explicit deferred prerequisites in [execution](revalidation/execution.md).
3. DEC013 resolves combined SQL/vector upsert: SQL success with logged vector failure. Other finalization/scope/forgetting/fork/edit choices remain deferred until material to a concrete batch; assertions are not competing approvals.

The nine-stage cleanup order remains. Bugs stay parked unless they block the authorized next batch; no general repair campaign began. The audit completion is not a passing product verdict or Stage5 implementation approval.

## TASK12 completion and remaining gate

Owned batches: infrastructure runner/config/registry/canaries; existing actualrequest/LangMem/concurrency; storage/nativevectors/Chroma/meaningfulassertions; source/category/embeddingfixtures; existing app/wrapper/browser admission and3app assertion repairs. Exactlyone writer atatime; independent isolation/consequential review and15unchangedtest sample. Initial and repair evidence retained.7newsemanticcases; no testsdeleted. All relevant tests executed offline withsource snapshots, externalnetworkdenial andsyntheticstorage. Browser12scenario bodies blocked byobservedloginappdefect, not omitted.

Historical next decision (now authorized/completed by DEC015/TASK14): application/evaluation blocker proposal in stage5/readiness.md (nativevectorupdate, staleLongMem configuration caller, synthetic evaluator guard, login/loadingJS); no capability expansion/purge bundled. RV001rebuild and timeoutoracle expectation remain explicit backlog items. Live proposal prepared but notauthorized. Maintainer concern recorded; only3equivalentselector parameter instances currently justified as later reductioncandidate. No reductionapproved/performed.

## TASK13 — Deferred test-suite simplification (MAINT-01)

User requested backlog entry on 2026-10-27. Scope: demonstrated test/fixture overlap, isolation-runner complexity and portability, default versus opt-in groups, and generated-evidence retention. Planning/implementation to be scheduled after immediate blocker triage, or alongside a cleanup batch touching the same responsibility. This entry does not authorize removal or infrastructure replacement. Preserve unique outcome protection and verified isolation; require a concrete reviewed proposal and before/after evidence.

### Manual verification update

User reports a full functionality check (DEC014). This supplies manual verification evidence without converting existing automated failures into passes. Next proposed implementation remains a bounded triage/repair of Stage5 blockers, followed by affected-group and final core verification; no exhaustive coverage target or broad overlap audit is required before a separately approved, adequately protected purge batch.

## TASK14 — Bounded Stage5 blocker resolution (DEC015)

Complete. Coordinator owns evidence/ledger/commits; one implementation writer owns native vector replacement, LongMemEval caller, synthetic evaluation harness/fixtures, native navigation asset and narrowly affected existing tests. Independent reviewers own consequential code and native/manual reconciliation. Dependencies: TASK12 baseline/isolation, DEC013 and DEC014.

Reconfirmation: integration again collected509/selected508,502passed6failed/1excluded; source stable. Fresh native Chainlit browser again hit the login overlay; the repeated-failure run was deliberately interrupted, with incomplete cases recorded separately. Preserve both original complete and new partial evidence. Completion: independently reviewed minimal fixes, affected groups and final offline core on stable final source, honest remaining limits, and a small consumer-checked cleanup proposal; no deletion. See [batch evidence](stage5/blocker-resolution.md).

TASK14 completion: final five groups on identical stable working source collected690/selected689, all689passed;1real-model preload excluded,0errors/skips/xfails. Independent source/runtime review accepted; native browser13pass includes12journeys. No new cases. Commits a02bcfa/4dbcaa4/bc28550 preserve native vectors, evaluations and native login fixes separately. Remaining product-oracle39/3 and deferred verification are explicit; no unrelated fixes/purge/test simplification. Next user checkpoint: approval/rejection of the single unreferenced diagram-PNG proposal in readiness. No product ambiguity blocks that proposal.
