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
