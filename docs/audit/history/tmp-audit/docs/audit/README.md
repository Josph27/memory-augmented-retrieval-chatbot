# Audit and cleanup handoff

**Package v1.2 · updated 2026-10-27 · documentation only.** Keep stable `WF-*`, `AUD-*`, `DEC-*` and `TASK-*` IDs when updating records. Git versions these files once a user or authorized worker commits them; no commit has been created for this assessment.

Breamon is a semester-project multi-agent typed-memory RAG chatbot. Preserve its spine: source retrievers → `MemoryCandidate[]` → ranking/budgeting → `ContextPacket` → answer → memory update. Reliable loading, storage and prompt assembly remain deterministic. See [root instructions](../../AGENTS.md).

**Objective:** make the retained product understandable and reliably testable before further features. **Current position: Stage 4 / TASK-09 static assessment completed and independently reviewed; Stage 5 protection is next, not started** under DEC-008. Main assessment: existing chat “Audit Breamon repository”; coordinator reconciled independent reviews and ledger. No test collection/execution, test edits/deletions or app fixes occurred. **No workflow or whole test-file removals justified or approved.** Narrow assertion/case replacement/reduction proposals are evidence, not execution approval. Documentation and blocker triage run throughout; unrelated bugs remain parked.

## Reading order and ownership

1. [Decisions](decisions.md): binding user scope, recommendations and unresolved product choices.
2. [Cleanup plan](cleanup-plan.md): ordered tasks, dependencies, completion gates and next action.
   Current Stage 4 evidence: [test-suite assessment](test-suite-audit.md), [inventory](test-suite-inventory.md), [symbol index](test-suite-symbols.md), and [independent reviews](reports/README.md).
3. [Workflow map](workflow-map.md): entry points, owners, state boundaries, consumers, tests and inspection depth. Read the relevant `WF-*` rows before changing a path.
4. [Bug backlog](bug-backlog.md): corrected `AUD-01`–`AUD-20`, counterevidence and isolated verification scenarios; no fixes approved.
5. [Historical reports](reports/README.md): reconstructed first and second audit reports. [Provenance](reports/provenance.md) records checkout limitations; [current fingerprints](reports/current-source-fingerprints.md) detect later source drift.

Maintained documents contain the current interpretation; historical reports explain how it developed. Update evidence and task/decision status together, within authorized scope. Cite a path **and symbol**; line numbers alone drift.

## Evidence limits

- Audits were static. No app, inference, ingestion, tests, migration or index rebuild was executed by the audit/consolidation work. Limited historical syntax checks are not behavioral verification.
- User reports that DeepSeek chat works. Routing, summaries, extraction, evaluations and capacity remain separately unverified.
- Exact original report text and dates were not recoverable here; reconstructions are labelled. Original dirty source is not recoverable from its commit hash. Current fingerprints are not original-audit hashes or source snapshots.
- Main uncertainties: scope/Inspector policy, forgetting semantics, fork/edit inheritance, actual sent context, frontend parity and SQL/vector test isolation. See `DEC-101`–`DEC-106`.
- No secrets, private messages, uploaded documents, runtime stores or stash contents were inspected. Directory presence and syntax inventories do not establish semantic coverage.
