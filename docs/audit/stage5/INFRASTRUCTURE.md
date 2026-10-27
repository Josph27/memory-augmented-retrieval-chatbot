# Stage 5 isolated test infrastructure

Infrastructure responsibility only: no application behavior or existing assertions changed. Source baseline is captured per run rather than hardcoded. Read `groups.json` with the existing test audit for selection evidence. Independent isolation review is required before collecting/running tests.

## Entry points and collection policy

Use host Python stdlib to launch. Dependencies are the original checkout's read-only `.venv`, configurable with `--venv`; no environment installation or downloads occur.

```bash
python3 scripts/run_isolated_tests.py --canary-only --group offline-unit --label isolation-design --timeout 45
python3 scripts/run_isolated_tests.py --collect-only --group offline-unit --label initial-collection --timeout 300
python3 scripts/run_isolated_tests.py --group offline-unit --label initial --timeout 300
python3 scripts/run_isolated_tests.py --group offline-integration --label initial --timeout 600
python3 scripts/run_isolated_tests.py --group offline-integration --configuration canonical --label initial-canonical --timeout 600
```

Without `--group`, both reviewed offline groups run once in one process. Explicit group runs provide cleaner per-group results. Canonical and deterministic variants overlap and must never be added as distinct protection. Post-repair labels should identify the repair, e.g. `--label post-fixture-01`. Each invocation creates a fresh mode-0700 directory under `/tmp`; `--output-root` must be outside the source checkout. Failed/timeout evidence is retained and never retried automatically. Maximum allowed timeout is 3600 seconds; parent controller should use bounded tool yields for updates.

Root `conftest.py` refuses collection unless runner proof confirms separate mount/network namespaces and passed native pre-import canaries. It rejects explicit files outside enabled groups and ignores unregistered modules before import. The runner chooses only reviewed registry files; unknown files fail closed. Root `testpaths=tests` prevents accidental root diagnostic discovery; marker categories describe behavior and do not constitute the import boundary. The one actual cross-encoder preload node is deselected before execution and retained with its reason. Removing that exclusion requires separate model/cache review.

`groups.json` contains 16 offline-unit and 53 offline-integration files (69 distinct prior-reviewed baseline sources). Fake evaluation tests remain offline regressions. App-import composition, shell-wrapper regressions, Python/browser/Node entry points and diagnostics remain visible deferred groups. This is an initial executable registry; the coordinator will reconcile the main auditor's complete entry-point/cost map. Disabled groups cannot be invoked by this launcher; live/expensive/manual categories are additionally refused even if their enabled bit changes.

## Isolation boundary

The launcher clears the inherited environment and creates private mount, network, PID, IPC and UTS namespaces with bubblewrap. It mounts `/usr`, the selected dependency environment and source read-only; `.git`, existing private settings and dotenv files are replaced with `/dev/null`. Existing runtime/cache roots (`data`, `.cache`, `.chainlit`, logs, etc.) are hidden by ephemeral tmpfs. Host `/home`, the original checkout, application stores, sockets and caches are absent. Synthetic passwd/group records resolve the user home to `/work/home`. The sole persistent writable location is a fresh per-run `/work` evidence/output directory; `/tmp`, `/run`, masked runtime roots and device/proc mounts are namespace-local.

Before dependency/application imports, parent and fresh subprocess native canaries verify: old home/checkout absent, private files masked, source writes denied, native SQLite source write denied, native temporary SQLite writes allowed, and native external sockets unroutable. Namespace IDs must differ from the launching host. A supplemental Python audit hook records/blocks network and private-settings attempts; it is not the native isolation boundary and children need not inherit the hook. Unsetting offline environment flags in a wrapper cannot restore host routes/mounts.

Storage defaults are set before app imports and canonical settings constants are explicitly pointed at `/work/default.db` and `/work/chroma`. Structured sqlite-vec shares that isolated SQLite database. Existing test fixture namespaces are ephemeral within these stores. HF/tokenizer/torch/uv/cache/temp outputs point to `/work`; cold model paths can fail as unavailable rather than load host caches. A second fresh child, after synthetic environment setup and before pytest, imports AppConfig/provider settings and verifies inherited dummy inference configuration, disabled dotenv/private loading, and writable resolved storage/cache/temp paths under /work. Child canonical constants may resolve to /work/data/chroma while parent overrides /work/chroma; proof records this difference explicitly. This is configuration/isolation evidence, not semantic vector-namespace protection. Source-relative writes may fail against read-only source; that is an explicit infrastructure/test outcome, not permission to weaken confinement.

Synthetic inference configuration is custom/offline.invalid with a dummy key. Private settings resolution points at a nonexistent `/work/local_settings.py`. No blanket ConnectionGuard-success patch, dispatcher replacement or ContextPacket replacement is applied. Existing local test substitutes remain visible in test evidence. Deterministic variant selects SQLite/rule/deterministic routing/reranking/gist extraction explicitly; canonical variant preserves canonical non-storage choices. Neither variant certifies live-provider or default-model behavior.

## Browser prerequisites and control

Browser remains disabled pending fixture adaptation/review. Optional launcher code mounts only the configured Chrome runtime (`--chrome-runtime`, default `/opt/google/chrome`) and `/etc/fonts` for a browser-category group. That group enables controlled loopback only inside the private network namespace, with parent/child loopback canaries plus unchanged external-denial canaries. If kernel/bubblewrap loopback is unavailable, bootstrap fails closed. Python socket hooks permit only localhost/127.0.0.1/::1 and namespace-local Unix sockets. Offline groups keep loopback blocked. Source services remain isolated from host application services even if ports match.

The runner invokes Python pytest files only. Node entry points stay registered but need their own reviewed runner/runtime/dependency mounts; Python browser execution cannot imply their coverage. Host Chrome presence is not an executed browser result. No Node, Playwright or Chromium dependency is installed or downloaded by this infrastructure.

## Evidence and statistics

Every run stores `source-before.json` and `source-after.json`: exact HEAD/branch/status, index blob IDs, staged/unstaged raw differences and hashes of allowed tracked/untracked working files. Private/runtime files are excluded without opening their contents. Source changes during execution invalidate stability and cause launcher failure. `launch.json` records argv and runner hash; `runtime.json` records interpreter and installed dependency versions after canaries.

`console.log` retains full output. `progress.json` is replaced atomically after collection/deselection and every test phase; timeout retains the last checkpoint. Completed runs add `result.json` and `junit.xml`; bootstrap failures produce structured errors. `launch-result.json` records exit, timeout, evidence presence, elapsed time and source stability. Canaries-only runs import no pytest/test modules and report zero test cases; a controlled post-environment child imports AppConfig/provider settings to verify inherited synthetic configuration before pytest.

Case statistics include expanded node IDs, selected and deselected counts, setup/call/teardown records, collection errors, captured failure output, passed/failed/errored/skipped/xfailed/xpassed counts and not-completed nodes. Collection-only nodes are unexecuted rather than passing. Counts are case counts, not lexical function counts. The exclusion register remains attached to results; counts for never-collected deferred entry points remain unknown until reviewed collection is possible. A fixture skip or expected failure does not count as passing protection.

Zero external inference requests/tokens/cost is supported by the passed native parent/child namespace sentinels, not by mocked SDK call counts. Fake call counts are explicitly unknown unless a later bounded instrument measures them. Controlled local browser service requests are not external inference usage. Do not aggregate overlapping configuration runs or reruns as additional coverage.

## Implementation checks and pending review

- Stdlib syntax compilation without imports: 3 infrastructure files passed.
- Focused Ruff check and formatting: passed.
- Canary-only smoke run: `/tmp/breamon-stage5-xta7ue11`, exit 0, source stable, native parent/child sentinels passed. This predates optional browser support/formatting; run a fresh canary after review for the final snapshot.
- Final canary-only run: `/tmp/breamon-stage5-cbjavp6t`, exit 0, source stable; native parent/child sentinels and post-environment child AppConfig/provider inheritance passed. No pytest/test modules imported.
- No test collection/execution, existing assertion modifications, credential reads, or live inference performed by infrastructure implementation. Controlled child AppConfig/provider imports occur only after native confinement.
- Independent reviewer should verify mount closure, namespace/proof gate, explicit-path collection handling, child inheritance, exclusions and result counting before initial baseline execution. Browser loopback support is unexecuted and browser remains disabled.

Browser tracked `.chainlit/config.toml` is currently masked with the entire runtime directory. Enabling browser coverage requires copying only explicitly reviewed tracked configuration into ephemeral `.chainlit` and separately hashing that input; do not expose ignored auth/cache files.

Independent reviewer accepted the final implementation and canary evidence for offline-unit16/offline-integration53 collection and execution. Eight canaries passed; no remaining offline safety blocker. Browser remains disabled and semantic vector-namespace protection is a separate test claim.
