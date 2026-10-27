# Decisions and approval boundary

Updated 2026-10-27. [Original register](history/tmp-audit/docs/audit/decisions.md) retains exact DEC-001–008 and DEC-101–107 wording and provenance.

- DEC-001: retained architecture/capabilities remain binding.
- DEC-002/005: earlier read-only/no-commit restrictions applied to their historical audit tasks. DEC-009 authorizes this migration, port, bounded verification and commits; it does not authorize general fixes or purge.
- DEC-003: zero justified workflow removals; stashed deletions remain unapproved.
- DEC-004/006/008: nine-stage sequence remains; Stage 4 existing-test assessment requires targeted main revalidation before Stage 5 protection expansion.
- DEC-007: original audit chat and independent reviews supplied historical assessment. Internal bounded independent review remains authorized.
- DEC-101–106: document scope, forgetting, fork/edit semantics, deployment and frontend/configuration coverage remain unresolved. No new product policy inferred from migration.
- DEC-107: historical no-removal boundary; DEC016 later authorizes one named PNG and DEC017 subsequently authorizes capability-preserving implementation cleanup across PURGE1.

## DEC-009 — Main-based recovery and transfer

Source: user request to move all work onto a new branch from main, followed by: “Go ahead and implement your solution, make sure to keep the changes on current branch backed-up, so they are still accessible should something fail during the process and we needed to re-start.”

Authorized: preserve original checkout and verified backup; create a separate main-based worktree/branch; port provider behavior and its tests without overwriting newer main functionality; preserve/relabel audit evidence; independently review; perform isolated migration checks; commit coherent verified changes and record impact. Main pinned at locally recorded main/origin/main 2f56d93; no remote freshness claim.

Excluded: wholesale merge/rebase of ui history, stash application, destructive reset, new capability/removal decisions, broad audit-driven app repairs, live provider or production-data tests. Migration-specific test adaptation does not begin general Stage 5 test expansion.

## DEC-010 — Private local-settings transfer

After automatic approval review initially rejected the credential-bearing copy, the user explicitly answered “Copy the existing private settings file” to a question specifying one file, Git exclusion, mode 0600, no displayed contents and preservation of the original. Only that copy is approved and completed; no permission to expose secrets or copy broader runtime state.

## DEC-011 — Complete audit revalidation points 1–4

User instruction 2026-10-27: “Please go ahead and implement this. I expect finalized all the points 1 - 4.” Refers to the coordinator's proposed complete coverage ledger, rerun of existing audit agent, reconciliation of previous findings/test assessments, and static-first isolated execution of consequential existing checks. Authorizes documentation/verification implementation and coherent evidence commits. Does not authorize app/test fixes, removals, live inference or production data access. Intended, implemented and asserted behavior remain distinct; unsupported prior claims are corrected, not rubber-stamped.

DEC011 completion: points1–4 delivered and accepted by coordinator at documented static/selected-execution depth. Existing main audit agent completed six owned assessment documents; coordinator reconciled342relevant paths and131WF/AUD/TSA/TS entries, executed selected confined checks and preserved explicit unverified paths. No app/test fixes, removals or new product policy were approved by accepting this evidence.

## DEC012 — Stage5 protection execution

User instruction2026-10-27 authorizes isolated offline baselines, test infrastructure/configuration, bounded test repairs/additions, audit records, workers and coherent commits. One implementation writer with explicit ownership; preserve dirty work/stashes. Existing audit guides work; no broad audit restart. Live/paid inference, application behavior changes, workflow removals and broad restructuring excluded. Run browser groups when isolated prerequisites exist. Record all outcome categories, initial/post separation, exclusions, external usage evidence and deferred-live proposal; spending needs separate approval. Consequential app defects/behavior choices escalate only affected work while independent protection continues.

## DEC013 — Durable SQL with nonfatal vector synchronization failure

User explicitly chose “Keep SQL success and log vector failure (recommended; matches current code)” on2026-10-27. Protection must assert the committed SQLite memory remains durable and the vector failure is logged. Replace conflicting exception expectations at the combined upsert boundary; retain direct vector-operation error coverage. This approves test contract alignment, not application changes or swallowing SQL failures.

## DEC014 — Manual functionality report and deferred test simplification

Source: user in “Braem. audit co-work”, 2026-10-27: “add the simplification of the test-suite into the backlog. I have already done a full functionality check.”

Authorized now: record deferred MAINT-01/TASK13 and the user-reported manual check; prepare the next coordinator prompt. The check has no supplied scenario matrix or exact source revision and does not supersede automated failure evidence. This request does not itself approve test removals, paid evaluations, application fixes or purging. Any coordinator prompt supplied with this response becomes execution authorization when the user issues it to the coordinator.

## DEC015 — Bounded Stage5 blocker resolution

User instruction authorizes diagnosis and minimal application/evaluation/test-setup fixes for the four recorded blockers; existing regression tests first, narrow protection only, independent review, affected isolated groups and final offline core, coherent commits and a first cleanup **proposal**. Preserve DEC013 SQL success/logged vector failure. Reconcile the reported manual check with native Chainlit versus React and fresh-session automation. No paid/live inference, unrelated fixes, broad test expansion, MAINT-01/TASK13 implementation or purge. The preexisting React type/lock fix and DEC014 audit updates are separately preserved in c487db3 and 785ccd9.

## DEC016 — PURGE1 single-artifact deletion and next proposal

User explicitly approves deletion of docs/mermaid-diagram-2026-07-15-021559.png only, preserving docs/system-component-map.mmd, all other assets, application/tests/evaluations and historical audit evidence. Authorizes consumer/source/diff/link validation, current ledger/decision updates and a coherent commit; application tests need not rerun solely for this unreferenced artifact. No history rewrite/squash. Starting source:3a3ad03e5fb33b23c56aa5f36e49c1f2e413bf67, clean codex/audit-main worktree. See [executed batch](purge1-batch1.md).

Also authorizes preparation, not execution, of at most3 concrete code-removal candidates using existing findings. Live responsibility consolidation belongs to PURGE2. No additional deletion, behavior change, live inference, general fix or MAINT-01/TASK13 implementation approved. Next code change needs its own explicit bounded approval.

## DEC017 — Complete PURGE1 with preserved capabilities

User expanded the assignment to complete PURGE1 across maintained implementation, helpers/modules/scripts/dependencies, backup/patch/generated artifacts and exclusively tied docs/assets. Authorizes autonomous removal only when no unique retained responsibility is established, necessary supporting imports/config/tests/docs, isolated verification, independent challenge of consequential code/dependency removals, and recoverable coherent commits. Do not stop at a candidate list.

Preserve retained workflows, useful optional modes/evaluations/manual diagnostics/fallbacks, credentials/databases/uploads/user data, ignored/runtime data, stashes/recovery backups and historical audit evidence. Static imports alone do not establish safe removal. Consolidation/restructuring belong to PURGE2/PURGE3; MAINT-01/TASK13 remains deferred; no general fixes, live spending or wholesale stash application. Genuine product/value/data decisions block only the affected candidate while independent work continues.

Completion requires recorded dispositions for all relevant repository areas, executed/reviewed justified safe removals, explicit retained/deferred/decision candidates, proportional verification plus final agreed isolated groups/build, updated records and commits. No completion claim with an unresolved PURGE1 decision. Stop after tier-end report for user functionality confirmation; do not begin PURGE2. This supersedes DEC016's proposal-only next-step restriction, not its narrow approved PNG scope.

DEC017 execution: TASK16 engineering completed across the recorded maintained areas; independently reviewed safe removals committed in752065d/3399a2b/858d4f2/3fa357c. All retained workflows, tests/evaluations/data/recovery boundaries preserved at documented verification depth. [Final report](purge1-completion.md) records689selected passes, one real-model exclusion, frontend results and remaining product-oracle/verification limitations. No unresolved PURGE1 removal decision remains. Await user tier-end functionality confirmation; PURGE2 is not begun or authorized by completion.

## DEC018 — PURGE1 acceptance and full PURGE2 authorization

On 2026-10-27 the user confirmed: “the application still works after PURGE1.” This is tier-end manual acceptance; its scenario detail and exact runtime configuration were not specified, so it does not convert excluded or failing automated checks into passes.

The user authorized full PURGE2: assess maintained application, frontend, CLI and evaluation responsibilities using existing audit leads; implement justified behavior-preserving consolidation in coherent verified commits; use one implementation writer and independent challenge of consequential changes. Preserve typed-memory contracts, traces, fallbacks, DEC013, data, credentials, stashes and recovery material. Distinct policies and observable behavior must remain distinct. No live/paid inference, production-data tests, broad restructuring or MAINT-01/TASK13 work. Escalate actual product ambiguities or material scope expansion; continue independent work. Final accumulated isolated groups and appropriate frontend/entrypoint checks required; stop for the user's PURGE2 functionality confirmation. PURGE3 remains unstarted.

DEC018 execution: PURGE1 tier acceptance was recorded as supplied. PURGE2 engineering completed in three independently reviewed batches (`b714855`, `1408a10`, `fcaaef8`), with final 693 selected cases passing and one real-model case excluded. [PURGE2 ledger](purge2-ledger.md) records behavior differences, remaining limitations and manual checklist. No unresolved PURGE2 decision remains. Await user functionality confirmation; PURGE3 has not begun.

## DEC019 — Independent purge challenge and corrective batches

On 2026-10-27 the user requested a fresh independent challenge of PURGE1 and PURGE2, and authorized corrective removals and behavior-preserving generalization. The updated rule permits sharing underlying mechanics behind a few explicit variation points or thin wrappers even when existing behavior differs. Do not infer equivalence from names or reject sharing solely on differing behavior; protect error, ordering, state, fallback, provenance and policy contracts. One writer at a time, independent review of consequential proposals and a sample of retain decisions.

PURGE1 and PURGE2 completion claims are reopened: preliminary independent source inspection found an unused long-term-memory helper and duplicated MAB/LongMemEval resume selection despite prior retention. Existing valid checks/evidence remain historical, not disproved. Track current scope and evidence in [challenge ledger](purge-challenge.md). Preserve data, credentials, history/stashes/recovery; no paid/live inference or production-data tests; no broad PURGE3 or MAINT-01 test simplification. Escalate actual capability/public-contract/data-migration/product choices and continue independent work. Stop for user functionality confirmation before PURGE3.

DEC019 execution: original PURGE1/PURGE2 completion claims were premature. Reviewed corrective removals and shared-mechanics batches are implemented; independent review accepted the bounded retain sample and final evidence. Final isolated 698 selected cases passed, one real-model case excluded. See [challenge ledger](purge-challenge.md). User functionality confirmation is pending; PURGE3 has not started.

## DEC020 — Focused maintainability challenge and React End semantics

User requested three consequential responsibility comparisons, fresh independent challenge, and bounded authorized corrective work; PURGE3 remains stopped. On 2026-10-27 the user explicitly selected the same finalization for React End as Chainlit: flush pending memory, create gist, then inactivate; finalization failure may prevent ending. This authorizes the necessary REST and React error handling correction, not general bug fixing. React partial-fetch error policy remains a pending question. See [focused challenge](purge-challenge.md#focused-maintainability-challenge-task19--dec020).
