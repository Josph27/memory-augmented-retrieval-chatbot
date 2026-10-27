# Cleanup plan and task ledger

Updated2026-10-27. Governing DEC008 sequence: inference → audit/handoff → scope → test audit → protection → PURGE1 → PURGE2 → PURGE3 → final acceptance. Documentation/blocker triage throughout. Historical TASK01–09 detail remains [archived](history/tmp-audit/docs/audit/cleanup-plan.md); current evidence overrides stale baseline/completion statements.

| Task | Ownership / dependency | Current state / completion gate |
|---|---|---|
| TASK10 — Recover onto main (DEC009/010) | Coordinator; independent review | Complete. Original checkout/28dirty files/stashes and recovery archive preserved. Main-based provider port committed; private settings copy separately approved/ignored. |
| TASK11 — Audit revalidation points1–4 (DEC011) | Existing Audit Breamon repository main assessor; coordinator coverage/execution; read-only internal isolation/evidence reviews | Complete and coordinator accepted.342relevant file entries; all16WF/20AUD/13TSA/80historicalTS reconciled; fournewRV observations.628distinct deterministic checks578pass49fail1skip +1deselected; canonical17overlap9pass8fail. Explicit unexecuted list and original/source integrity checks. See [assessment](revalidation/static-assessment.md), [coverage](revalidation/coverage-ledger.md), [execution](revalidation/execution.md). |
| TASK01 — Baseline/handoff | Coordinator; TASK10/11 | Historical assessment source1cf4c55 with exact actual-old comparison; subsequent product changes and current3fa357c verification are recorded in TASK14/16. Source hashes detect product drift. |
| TASK09 — Existing-test audit | Main assessor plus bounded independent review; TASK11 | Current file/setup/assertion/consumer assessment complete at documented depth.80current Python sources643lexical tests,82old/current identity union; JS/browser/manual/eval/shell consumers reconciled. Full-suite/default runtime acceptance remains unverified. |
| TASK02/03 — Scope and concrete proposals | Coordinator + user for capability choices | Zero justified workflow removals and none approved. Resolve DEC101–106 only when relevant to a concrete protection/cleanup batch; DEC107 requires explicit removal proposal. |
| TASK04 / TASK12 — Stage5 protection (DEC012) | Coordinator + one implementation writer; independent isolation/repair review | Test protection delivered; subsequent TASK14/DEC015 resolves the four automated blockers. Final689selected cases pass across5disjoint groups,1real-model case excluded;12native UIjourneys pass. [Readiness](stage5/readiness.md) gives remaining limits and a bounded artifact proposal, not blanket workflow-removal approval. |
| TASK05/06/07 — Purge/consolidate/restructure | Relevant batch approval and passing protection | PURGE1 acceptance under DEC018 remains recorded; the user-requested DEC019 challenge has reopened PURGE1/PURGE2 assessment and corrective batches under TASK18. PURGE3 not started. |
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

## TASK15 — PURGE1 approved artifact (DEC016)

Complete: start3a3ad03, clean active worktree. Rechecked exact/stem references and operational asset/packaging/loader rules; only audit/proposal references, no active consumer. Removed exactly the approved3,063,514-byte PNG. Retained Mermaid source hash unchanged; exact visual reproduction not claimed. Current records updated; historical inventories/evidence untouched. Diff/scope/local Markdown links and git diff --check validated; no application tests rerun for this non-code deletion. [Batch and Git recovery](purge1-batch1.md).

Next instruction expanded to full PURGE1 under DEC017/TASK16; the prior proposal-only restriction is superseded. MAINT-01/TASK13 remains deferred.

## TASK16 — Complete PURGE1 (DEC017)

Engineering complete and accepted by user under DEC018. Coordinator owns area/candidate ledger, source-state/counts, batches, evidence and commits; internal read-only assessors cover backend, dependencies/evaluations/scripts, and frontend/docs/assets/config/test-infrastructure disposition. Exactly one implementation writer at a time, plus independent consequential review. Starting code baseline3a3ad03; TASK15 artifact batch separately preserved.

Completion gates: maintained-area accounting including protected runtime/data metadata; all safe removals executed/reviewed in coherent batches; retained versus PURGE2/3 versus genuine decisions explicit; affected verification and final agreed isolated core/app/wrapper/browser/build groups; counts/sizes, current docs and tier-end manual acceptance. No general audit restart, test-suite simplification or PURGE2 work.

TASK16 completion: all463baseline tracked paths accounted in11areas; all justified safe removals implemented/reviewed in4logical commits. Code174files/43,788→43,330lines; generated/template/patch files6→1,3,085,270bytes removed; frontend direct runtime declarations10→9 with identical transitive Core retained. Tests/evaluation fixtures unchanged. Final five disjoint groups690collected/689selected,689passed,1real-model exclusion,0failed/errored/skipped/xfail/xpass; frontend dependency/API/plugin/build/lint passed with3existingwarnings. Exact source provenance and independent review in [completion](purge1-completion.md), [area/candidate ledger](purge1-ledger.md) and [results](purge1-runs/final-summary.json). Separate42-row product oracle remains39pass/3fail. No unresolved PURGE1 decision. Protected runtime/data/history/stashes intact. User confirmed functionality on 2026-10-27; DEC018 authorizes PURGE2.

## TASK17 — Full PURGE2 consolidation (DEC018)

Engineering complete; user tier-end functionality confirmation pending. Coordinator owns the consolidation ledger, verification and commits; one implementation writer at a time, independent read-only assessments/reviews. Baseline: clean `ae35188` on `codex/audit-main`. Use the existing audit and PURGE1 dispositions; compare actual contracts and consumers before each batch. Record retained/deferred opportunities and meaningful differences in [PURGE2 ledger](purge2-ledger.md).

Completion: justified safe consolidations implemented/reviewed, maintained areas dispositioned, no consequential regression or pending product decision, relevant isolated groups plus final accumulated checks, documentation and commits complete. Stop for tier-end user functionality confirmation; no PURGE3 or MAINT-01/TASK13.

TASK17 completion: three independently reviewed responsibility batches committed in `b714855`, `1408a10`, `fcaaef8`. All relevant maintained areas have bounded dispositions, no outstanding product decision or known consequential regression. Final five isolated groups: 694 collected, 693 selected/passed, one real cross-encoder exclusion; zero failures/errors/skips/xfail/xpass. Frontend checks/build/lint passed with three warnings. Separate product-oracle rows remain 39/42; live models and React browser remain unexecuted. Exact evidence, area decisions, counts and acceptance checklist are in [PURGE2 ledger](purge2-ledger.md). Stop for user PURGE2 functionality confirmation; no PURGE3.

## TASK18 — Independent purge challenge and corrections (DEC019)

Corrective engineering complete; user functionality confirmation pending. Baseline: clean `f554c24` on `codex/audit-main`. Fresh independent read-only reviewers own core orchestration, storage/memory, and frontend/evaluation/operations; coordinator is the sole implementation writer. Review source and consumers directly, then contrast prior ledgers. Challenge consequential proposals and sampled retain decisions independently.

Track concrete responsibilities, variation points, consumers, tests, risk, previous-pass weaknesses and dispositions in the [challenge ledger](purge-challenge.md). Reopen affected phases where findings justify it; run isolated affected/final checks, independently review changes, and commit coherent removal/consolidation batches. User PURGE1 acceptance remains prior evidence; no PURGE2 acceptance is inferred. Stop for functionality confirmation before PURGE3.

TASK18 completion: both prior completion claims reopened; two corrective removal batches and six consolidation batches independently reviewed and committed. All previously identified justified candidates implemented; specific retained/deferred paths and CH-UI-01 are recorded in [challenge ledger](purge-challenge.md) and backlog. Final isolated groups 699 collected/698 passed/one excluded, zero failures/errors/skips; frontend checks/build/lint passed with three warnings. Product oracle remains 39/42 and live/model/React browser checks unexecuted. Await user functionality confirmation before PURGE3.

## TASK19 — Focused maintainability challenge (DEC020)

Three responsibility comparisons and independent challenges recorded in the [existing challenge ledger](purge-challenge.md#focused-maintainability-challenge-task19--dec020). User-approved React End parity implemented and independently reviewed; isolated affected groups and frontend checks passed. React partition failure behavior awaits user decision; native/graph shared retrieval policy needs a product decision before unification. PURGE3 remains unstarted. Retain DEC013, data and recovery material; MAINT-01 remains deferred.

## TASK20 — PURGE3 restructuring plan (awaiting prerequisite)

The user requested PURGE3 and explicitly instructed that moves pause if required prior acceptance is outstanding. Planning baseline is clean `codex/audit-main` at `514c32a5a9d624664eada0758aebae7d9e4fdc2b`; PURGE1 was accepted, but the PURGE2 corrective state (TASK18) and subsequent React End correction (TASK19) have no recorded user functionality confirmation. This is a planning snapshot, not a claim that the user accepted it. Pause dependent moves until the user confirms or explicitly changes that prerequisite. No app, data or command changes have been made in TASK20.

| Current → proposed | Navigation/ownership and disposition |
|---|---|
| Root `app.py`, `startup.py`, `run.sh` → retain | Chainlit adapter/startup and existing entry commands are immediately discoverable; document their working-directory requirements accurately. |
| `src/chat_service.py`, `src/agents/`, `src/{routing,retrieval,context,memory,orchestration,core}/` → retain | `ChatService` is the top-level turn/composition boundary, with responsibility-named packages. A one-file `application/` package would not move app composition or improve dependency direction; it would churn imports in apps, evaluations, scripts and tests. |
| `src/agents/document_ingestion_agent.py` and `src/documents/{loaders,splitters,registry,inspection}.py` → retain | Ingestion combines document primitives, Chroma, optional model and summary persistence; it is an agent-level composition role. Moving it into lower-level document primitives would obscure this ownership. Keep the known dependency direction and record both locations in the orientation map. |
| `src/database.py`, `src/config.py`, `src/provider_settings.py`, `src/model_wrapper.py` → retain | Storage/provider/configuration are top-level explicit modules. Moving database alone has broad imports and no demonstrated reduction in concepts; do not change data destinations. |
| `braemon/`, `evals/<suite>/`, `tests/` → retain | Frontend, evaluation suites and behavioral tests already have recognizable locations. Preserve existing entry points and MAINT-01 deferral. |
| `scripts/.doc.md` → proposed `scripts/README.md`, with reviewed and corrected command inventory; leave script files in `scripts/` | A visible, accurate operational index and root README link improve discovery without changing command paths. Review first: current inventory contains broad claims about script flags, working directories and storage safety that must be verified, and it omits the safe isolated test runner. Do not run rebuilds, live evaluations or touch real data to validate descriptions. |
| Current `docs/` and `docs/audit/` → retain; update existing current indexes | Explain current architecture and safe commands once; preserve historical reports, snapshots, generated outputs and runtime data in place. |

Two independent assessments and a fresh reviewer challenged proposed moves. In particular, grouping scripts into subdirectories would alter documented paths and `__file__`-derived roots, shell sibling sourcing and evaluation-wrapper tests. Moving `ChatService` or the ingestion agent would add indirection/churn without changing their actual responsibilities. Thus no Python module move is currently justified solely for symmetry; revisit only with concrete dependency/navigation evidence after the gate.

After acceptance: (1) validate and revise the existing script index, making it visible as `scripts/README.md` and linking it from root README; preserve all command paths and classify live/data-affecting commands. (2) Reconcile current root README, AGENTS and affected maintained docs with actual startup/configuration, turn tracing, ingestion, memory persistence, safe tests and optional evaluations; avoid duplicating guidance. (3) Check paths, links, packaging, startup/help and documented working directories; independently review the changes. (4) On the accumulated state run isolated core, integration, app-composition, wrapper, native browser and frontend checks, reporting React/browser/live exclusions and existing failures separately; commit coherent reviewed batches. Any later justified code move requires consumer, path and proportional test checks before implementation. Stop for final manual acceptance; no MAINT-01 or backlog repair.
