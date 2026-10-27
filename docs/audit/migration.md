# Main-based recovery and migration

2026-10-27. Authorized by DEC-009; private local-settings copy additionally authorized by DEC-010. Provider implementation commit: `ef0ed2b`. Documentation/evidence committed separately on the same branch.

## Result and provenance

- New branch: `codex/audit-main`; worktree `/home/josph/.codex/worktrees/audit-main/repo`.
- Exact base: main `2f56d93a18f7b81a3dbf8a6ccb1f4b4260b94086`, also recorded origin/main at migration time. No fetch; no claim about later remote updates.
- Original worktree `/home/josph/UNI/TUM/PRAK-AGENTS/repo` stays on `tmp-audit` at `c3ffee2dae6b6ce6daa8a145e347e61fa4989672`, with all six tracked modifications and 22 untracked files preserved. This branch descended from deprecated ui `f4fc7c2`.
- Both stashes retained unchanged: `8ebd28f9b6ff9ed2de6f42b2140ef27553485fe4`, `bfc7b9a329becd9cf3310d73606782e9158ab839`. Neither inspected/applied.
- Main's canonical settings, guard implementation, dependency manifests/lock and newer application architecture retained. No merge/rebase of ui history, schema migration, workflow/test removal, or broad bug repair.

## Recovery copies

Private recovery directory:
`/home/josph/.codex/visualizations/2026/10/27/01a17c90-af7a-73e3-a898-6d83405fa321/breamon-recovery-20261027`

Directory mode 0700; files mode 0600. Contains `files.tar.gz`, `manifest.json`, `working-tree.patch`, empty `index.patch`, `handoff-commit.patch`, `status.txt`, `stashes.txt`, and `README.txt`. Archive includes exact working versions of all 28 modified/untracked files; SHA-256 and file modes were checked individually against the source. Original branch/history remains in the shared repository; archive is a dirty-work recovery package, not a complete repository clone.

Archive SHA-256:
`bdf296c4f9e87618e049446c0822603430ffb2cd9274fc32326e93588e085de2`

Recovery procedure: first use the intact original tmp-audit checkout. If a separate reconstruction is needed, create a disposable checkout at c3ffee2, verify archive and manifest, then extract into that disposable checkout. The archive already contains complete working file versions; do not also apply working-tree.patch over them. The patch is an alternative representation of tracked changes. Do not extract over unfamiliar newer edits or apply the deletion stashes. No reset is needed to restart migration from pinned main.

Ignored `.env`, credentials, runtime stores, uploads, dependencies and caches were excluded from the recovery archive and left in the original checkout. At the user's subsequent explicit approval, only ignored `local_settings.py` was copied opaquely to the new worktree, verified byte-identical, mode 0600, without displaying contents. It is excluded from Git. Other ignored local state was not transferred. `.env` is not copied; the existing frontend/auth/environment setup must be checked during later startup verification.

## Transfer accounting

| Original work | Destination / treatment |
|---|---|
| c3ffee2 handoff instructions | Audit block added to main AGENTS; current README handoff points to corrected baseline. Main's current architecture wording retained. |
| Six dirty tracked files | Provider behavior ported into main app/config/LangMem/model wrapper; env example and README adapted around main startup/configuration. Old whole files not substituted. |
| Old untracked src/settings.py | Ported to src/provider_settings.py; main's unrelated canonical src/settings.py preserved byte-for-byte. Custom falls back to canonical provider defaults; env overrides local provider settings. |
| local_settings.example.py | Preserved sanitized template. |
| tests/test_provider_settings.py | Nine original provider checks adapted; four migration-specific tests added, existing checks strengthened for guard/timeout and factory serialization. |
| Sixteen audit documents | Byte-identical under history/tmp-audit/docs/audit; current root documents route through baseline-impact warnings and corrected ledger. |
| task_plan/findings/progress notes | Exact old copies under history/tmp-audit; new root files track migration. |
| Ignored local provider configuration | Explicitly approved private copy; no key content or hash published. |

[Historical snapshot hash manifest](history/tmp-audit/snapshot-sha256.json) covers 21 copied audit/notes/instruction/readme files. Historical relative links to application code require the original checkout; no old implementation was restored merely to make archived links resolve.

## Verification performed

- All 28 original dirty-file hashes matched the backup after implementation; original branch/HEAD and status/stash records checked unchanged. Historical snapshot hashes matched all 21 copies.
- Main `src/settings.py`, `src/connection_guard.py`, `pyproject.toml`, `uv.lock` byte-identical to pinned main. Other tracked changes reviewed against main; no unrelated source paths changed.
- Python syntax compilation of the seven provider-related Python files passed without importing or writing bytecode. Verification runner also syntax/lint checked.
- Focused Ruff checks on new provider module/tests, config, model wrapper, LangMem and verification runner passed. Including app.py reports existing F401 `NATIVE` at line 25; reproduced on untouched main, left unchanged. No claim of whole-project lint success.
- `git diff --check` passed.
- **23 focused checks passed with zero unexpected audited isolation violations; four optional platform probes were blocked.** Thirteen provider checks plus existing prompt-message/comparator checks. One dependency deprecation warning (`trustcall` importing LangGraph Send) remains.
- Real OpenAI and ChatOpenAI SDK request serialization used HTTP MockTransport; LangMem test calls production create_real_langmem_manager with manager assembly substituted. Checks include shared selection, precedence, invalid/missing credentials using synthetic values, canonical settings preservation, guard endpoint/checking, timeout/retry options, and historical/missing-chat model selection.
- No live provider request, app server import/startup, browser run, ingestion, real-store access, dependency installation, full-suite collection or full LangMem extraction/evaluation was performed.

Reproduce this bounded run with the existing dependency environment (replace interpreter path if needed):

```bash
/home/josph/UNI/TUM/PRAK-AGENTS/repo/.venv/bin/python -I -B \
  /home/josph/.codex/worktrees/audit-main/repo/docs/audit/checks/run_migration_checks.py \
  /home/josph/.codex/worktrees/audit-main/repo
```

The [runner](checks/run_migration_checks.py) clears inherited environment, disables dotenv and pytest plugin autoload before imports, uses synthetic credentials and a temporary cwd/SQL/Chroma/cache root, overrides canonical storage defaults, disables bytecode, and applies Python audit hooks against private/runtime reads, writes outside the temp root, network and subprocess execution. Dependency `ldconfig`, `gcc`, `ld`, `uname` probes were denied; their libraries used fallbacks. These are bounded Python execution guards, **not a complete OS sandbox or certified full-suite isolation**. Do not expand its test list without inspecting new import/side-effect paths.

Initial harness attempts were rejected by its own strict policy: cached tempfile root first pointed at /tmp, then four optional platform probes were treated as failures. No denied operation executed. Set tempfile.tempdir to the private temp root; continue blocking exact optional probes but report them separately. Final persisted runner passed. The initial shell used unavailable `python`; rerun with python3. Runner late-import lint flags were annotated because controls must precede imports.

## Independent review and remaining work

`migration_plan_review` independently inspected source preservation, provider precedence, guards/timeouts, LangMem contracts and test assertions. No blocker found. Suggested custom-local precedence, missing-history and real-factory serialization checks were added; follow-up review accepted their coverage and bounded isolation claims. Reviewer did not execute tests.

`main_baseline_impact` independently compared AUD-01–20 and TSA-01–13 against main. [Full matrix](main-baseline-impact.md): exact-equality prompt rejection (AUD-17) and separate structured-vector directory (AUD-20) arguments are superseded; neither finding is declared runtime fixed. React E2E, sqlite-vec, canonical settings, scheduling, preload and cwd logging change audit coverage/isolation assumptions.

TASK-10 migration is complete. TASK-09 main revalidation remains: refresh changed/new test inventory and consequential conclusions, then establish full isolation before collection/execution. Live startup/provider behavior and full memory/evaluation/frontend functionality remain unverified on this new branch. No new capability choice or purge approval is implied.
