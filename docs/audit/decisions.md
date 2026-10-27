# Decisions and approval boundary

Updated 2026-10-27. [Original register](history/tmp-audit/docs/audit/decisions.md) retains exact DEC-001–008 and DEC-101–107 wording and provenance.

- DEC-001: retained architecture/capabilities remain binding.
- DEC-002/005: earlier read-only/no-commit restrictions applied to their historical audit tasks. DEC-009 authorizes this migration, port, bounded verification and commits; it does not authorize general fixes or purge.
- DEC-003: zero justified workflow removals; stashed deletions remain unapproved.
- DEC-004/006/008: nine-stage sequence remains; Stage 4 existing-test assessment requires targeted main revalidation before Stage 5 protection expansion.
- DEC-007: original audit chat and independent reviews supplied historical assessment. Internal bounded independent review remains authorized.
- DEC-101–106: document scope, forgetting, fork/edit semantics, deployment and frontend/configuration coverage remain unresolved. No new product policy inferred from migration.
- DEC-107: no removal approval.

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
