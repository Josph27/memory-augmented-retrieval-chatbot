# Evidence and checkout provenance

Package v1.0 · recorded 2026-10-27. **Commit identifiers alone do not identify audited working-copy bytes.** No original source archive, original source hashes or exact audit transcripts were recovered. No stash was used to reconstruct them.

## 1. Historical audits

| Record | Commit / branch | Dirty content and reliability | Verification boundary |
|---|---|---|---|
| First architecture audit | Recorded shared baseline `f4fc7c265f963cf516b5b8a13ee2ea0ad4ee24f7`, `tmp-audit`. | Provider changes were present; individual first-pass status timing/bytes unavailable. Attribution comes from the surviving backlog and retained conversation context, not a recovered primary report. Original date unavailable. | Static reading; historical syntax-only checks reported, not a behavioral test run. No launch, inference, ingestion, installs or private-state inspection. |
| Second coverage/challenge audit | Same recorded shared baseline; no independently recoverable second-pass snapshot. | Same known provider work; cannot prove all files identical between passes. Original date unavailable. | Static caller/failure/middleware/installed-framework-source tracing. No reproductions executed; later isolated tests proposed. |
| Bug-parking/cleanup brief | Started at `f4fc7c…`, `tmp-audit`; separate worker commit advanced HEAD to `c3ffee2dae6b6ce6daa8a145e347e61fa4989672`. | Separate commit changed AGENTS/README handoff instructions only. Backlog was this task's sole write; no workflow removal recommended or approved. | Documentation plus narrow consumer/reference checks; no application imports/tests. |
| Current consolidation | Observed `c3ffee2dae6b6ce6daa8a145e347e61fa4989672`, `tmp-audit`. | Existing backlog preserved; only `docs/audit/` changed by this task. Fingerprints describe current non-secret source, not historical dirty bytes. | Source text/symbol/path/link checks and hashing only. No app, tests, ingestion, inference or commits. |

Known recorded working-copy status, shared historical baseline and consolidation start:

```text
 M .env.example
 M README.md
 M app.py
 M src/config.py
 M src/memory/langmem_structured.py
 M src/model_wrapper.py
?? findings.md
?? local_settings.example.py
?? progress.md
?? src/settings.py
?? task_plan.md
?? tests/test_provider_settings.py
```

At consolidation start `?? docs/audit/` also existed, containing only the backlog. This list records known changes, not their original contents. Private `.env`/`local_settings.py` were not opened or fingerprinted. No branch, index, stash or commit was changed by this task.

## 2. Evidence labels and conflicts

- **Static:** source establishes call/wiring/control flow under specified conditions. Confidence “confirmed” does not mean the failure was reproduced.
- **Executed:** audit syntax checks were reported historically; current consolidation checks only document/reference integrity and hashes. No passing application test result is claimed.
- **User report:** DeepSeek app/chat works; does not establish memory/routing/summary/eval compatibility.
- **Historical worker note:** root `progress.md` describes provider work and prior focused test results; `findings.md`/`task_plan.md` also concern that task. They are not the missing audit reports or freshly verified outcomes.
- **Hypothesis/conditional scenario:** starvation, edit persistence effects, live capacity errors and vector contamination require isolated reproduction. Counterevidence and necessary conditions are retained in the backlog.
- **Product decision:** only directly sourced approvals in `decisions.md`. Global fallback docstring establishes intentional code policy, not a new user approval; stale docs do not decide scope.

Installed Chainlit/Chroma sources informed the second audit's request/auth/edit/distance interpretation. Their complete installation/version snapshot was not preserved; recheck against the environment used for protection tests. Version-range manifests and current fingerprints do not pin that past runtime.

## 3. Coverage and exclusions

| Area | Depth / limitation |
|---|---|
| `app.py`, `src/` | Core main/failure paths inspected as listed per WF; helper inventory/AST parsing alone was not semantic review. Not every branch was proven. |
| `braemon/`, `public/`, `.chainlit/` | Source/configuration and lifecycle event wiring inspected; no actual browser run, build or reconnect verification. Vendor/build/log contents excluded. |
| `tests/`, root upload/socket probes | Selected assertions/fixtures/isolation inspected; remaining tests mapped. No tests executed; probes are not assumed isolated. |
| `evals/` | Entry modes, production substitutions and selected isolation/provider paths inspected; not all metrics/CLI combinations. Dataset/runtime output contents excluded. |
| `scripts/`, `.dev/` | CLI/launch inventory plus selected provider/DB paths; several helpers mapped only. No script execution. |
| `docs/`, root documentation/manifests/Dockerfile | Claims compared selectively; no complete documentation line audit or clean-install/container verification. No checked `.github` CI directory; external CI unknown. |
| `reports/`, `data/`, `logs/`, `.files`/uploads | Generated or runtime contents excluded, especially private conversations/documents/indexes. Presence is not deletion evidence. |
| `.venv*`, vendor dependencies, caches, generated frontend output | Excluded except specific installed framework source contracts. No cache writes/import initialization. |
| `.git`, stashes, `.aws`, tool metadata/credential directories, private settings | No content inspection beyond read-only Git baseline metadata/status; secrets and stash contents excluded. |

## 4. Fingerprint use

[Current fingerprints](current-source-fingerprints.md) record SHA-256 over selected non-secret source files as observed during consolidation. Compare before relying on old symbol/line evidence. A match detects lack of drift since consolidation only; a mismatch requires checking relevant evidence. Hashes cannot recover content, do not identify historical audited dirty bytes, and do not replace a reproducible source snapshot.
