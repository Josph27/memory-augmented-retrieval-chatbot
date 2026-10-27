# Audit and cleanup handoff

Updated 2026-10-27. Current baseline: main `2f56d93a18f7b81a3dbf8a6ccb1f4b4260b94086`, branch `codex/audit-main`.

Objective: simplify the retained typed-memory chatbot and make its behavior reliably testable before more features. The prior audit used a deprecated ui baseline by mistake. Its completed static assessment remains historical evidence; Stage 4 is reopened for targeted main revalidation. Migration is authorized under DEC-009. No workflow or test removal is approved.

Read [decisions](decisions.md), [task ledger](cleanup-plan.md), [migration and recovery](migration.md), then [main-baseline impact](main-baseline-impact.md). Consult the relevant [workflow map](workflow-map.md), [backlog](bug-backlog.md), and [test assessment](test-suite-audit.md). These deliberately distinguish old evidence from current checks.

The original audit package is preserved byte-for-byte in [history/tmp-audit](history/tmp-audit/ARCHIVE.md), including reports, dispositions, stable IDs and provider notes. Source links in that archive refer to the old baseline. Do not treat historical source fingerprints or counts as current-main measurements.

Preserve MemoryCandidate → ranking/budgeting → ContextPacket → answer → memory update, SQLite persistence, LangMem cross-chat memory, document RAG, traces, lifecycle and evaluations. Product decisions remain the user's. Bugs stay parked unless they block the authorized task.
