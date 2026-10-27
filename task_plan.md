# Main-baseline migration plan

Scope DEC-009, 2026-10-27. Original provider notes preserved in docs/audit/history/tmp-audit.

- [x] Record source Git state and verify recovery archive.
- [x] Create separate worktree/branch from pinned main.
- [x] Preserve old evidence and port provider behavior around main interfaces.
- [x] Verify isolation, run targeted checks, independently review.
- [x] Commit, verify original checkout unchanged, report readiness and revalidation limits.

No purge, general fixes or production-data tests. Detailed ledger: docs/audit/cleanup-plan.md.
