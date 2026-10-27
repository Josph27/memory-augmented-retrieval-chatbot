# Stage5 protection plan — TASK12 / DEC012

- [x] Verify Git state; preserve reviewed audit package and separate documentation checkpoint.
- [x] Classify executable groups/expensive paths; default exclusion policy and commands.
- [x] Implement independently reviewed collection/runtime isolation and negative sentinels.
- [x] Run and preserve initial per-group baseline with exact dirty source state.
- [x] Repair test/infra defects; strengthen misleading tests and fill clear protection gaps in bounded batches.
- [x] Independent review and post-repair runs, preserving initial failures.
- [x] Per-group statistics, live proposal, readiness/blockers, current ledger and coherent commits.

Constraints: one implementation writer; no app behavior changes, live inference, purge or stash/reset. Main audit chat reads expense/group scope; internal reviewer reads isolation/repair design. Runtime results must distinguish collected cases from function counts and overlapping runs.

Test-only delivery complete; purge gate remains unpassed pending separately authorized application/evaluation blocker work. No application code fix, live inference or purge performed. See docs/audit/stage5/readiness.md.
