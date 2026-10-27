# Stage5 isolated runner

Use `python3 scripts/run_isolated_tests.py`; plain pytest fails closed before importing test modules. No dependency installation/download or private settings inspection is needed. Default runtime is the original checkout's read-only .venv; override --venv explicitly on another host. Linux bubblewrap and its namespace permissions are prerequisites.

## Commands and selection

```bash
python3 scripts/run_isolated_tests.py --group offline-unit --label check --timeout 300
python3 scripts/run_isolated_tests.py --group offline-integration --label check --timeout 600
python3 scripts/run_isolated_tests.py --group app-composition --label check --timeout 300
python3 scripts/run_isolated_tests.py --group subprocess-wrappers --label check --timeout 300
# Browser is admitted, but currently blocked by an application login defect.
python3 scripts/run_isolated_tests.py --group browser --label after-authorized-app-fix --timeout 600
```

Omitting --group runs the two core groups once in a single process. App composition and wrappers are explicit opt-ins: their pre-import embedding bootstrap / synthetic Git and uv setup have distinct responsibilities and should run in separate processes. Browser is explicit and slow. [groups.json](groups.json) is the pre-import allowlist; [exclusions](exclusions.md) lists commands/reasons for every deferred entry. Fake evaluation regressions remain offline. Node browser, real model preload, live/paid/expensive evaluations and manual diagnostics remain excluded, without capability removal.

--collect-only still requires full isolation. --canary-only imports no pytest/test modules (a controlled fresh child imports only configuration after confinement). --configuration canonical is accepted only for the two core offline groups and preserves their canonical non-storage settings; admitted app/wrapper/browser groups require deterministic setup. Deterministic is the tested Stage5 variant. Variants overlap and cannot be added as unique coverage. Timeout range1–3600s; each run gets a fresh0700 /tmp/breamon-stage5-* directory, never automatic retries. Preserve failure evidence.

## Native isolation and inputs

The launcher clears inherited environment and creates private mount/network/PID/IPC/UTS namespaces. Only /usr, selected dependency runtime, reviewed tool runtimes and read-only source are mounted. Host homes/old checkout/sockets/stores/caches are absent. Git/private dotenv/local_settings are masked or omitted; original files are not opened. Runtime/cache roots are ephemeral. The sole persistent writable run directory is /work; /tmp,/run and masked runtime outputs are namespace-local tmpfs. Source-write and native SQLite negative checks pass before application imports.

SQLite, sqlite-vec, document Chroma, namespaces, HF/tokenizer/torch/uv/config/cache/temp outputs resolve inside synthetic run storage. A native fresh child verifies confinement; a post-environment child verifies inherited dummy provider/cache/storage. Parent canonical settings are explicitly set before app imports. Child canonical Chroma may resolve /work/data/chroma instead of parent /work/chroma; both are confined and proof records the difference. Real semantic namespace/store separation is additionally tested, rather than inferred from temporary SQLite filenames.

Three regular git-tracked assets (.chainlit/config.toml, chainlit.md, public/product-navigation.js) are copied and hashed into a writable synthetic APP_ROOT. Ignored auth/cache files remain hidden. App group uses actual application source/handlers with an explicitly scoped pre-import embeddings-only substitute; no global ConnectionGuard-success, dispatcher or ContextPacket override. Existing per-test substitutes stay visible. Browser child configures canonical SQL/Chroma before first app import and retains its existing synthetic answer/ingestion fixtures. These controls do not verify default models/live extraction.

Wrapper group materializes only hash/mode-verified allowed source inputs into an isolated source copy, mounts it read-only, and supplies writable ephemeral artifacts/.cache. The actual uv executable is read-only and hash/version recorded; UV_NO_SYNC, UV_OFFLINE, UV_PROJECT_ENVIRONMENT=/venv and UV_PYTHON_DOWNLOADS=never prevent environment mutation/download. The prerequisite child tests the wrapper's actual /repo/.cache/uv override. Synthetic temporary Git metadata supports real git calls; it is explicitly NOT project history. Real source-before snapshots remain authoritative. Wrapper HF flag unsets cannot undo native network/storage confinement.

Browser mounts actual configured Chrome plus fonts and permits only private namespace loopback. Native parent/child loopback-success and external-denial checks, Chrome hash/version and a real headless DOM launch passed before collection. Services cannot reach ambient host services even with matching ports. Python browser and React Node groups remain separate. Browser fixture uses sys.executable -m chainlit, isolated writable service roots and retained server logs. Runtime readiness is not inferred from app's models-ready flag.

## Evidence and interpretation

Each run records exact HEAD/branch/status/index IDs, staged/unstaged differences, hashes/modes of allowed working files (including dirty/untracked source), exclusions without reading private/runtime contents, interpreter/dependencies and inputs. Before/after source mismatch invalidates stability. Console, JUnit, per-phase JSON, user properties, exclusion register and prerequisite proofs are retained. Progress is atomically saved so interrupted runs remain honest. Archives under runs/ preserve records/logs, not application databases or secrets.

Per-case counts include parameter expansion, setup/teardown errors, skips/xfails/xpasses, deselections and incomplete nodes. Function counts and42 product-oracle rows are different measures. Product report helpers also contain synthetic browser rows; these are not native browser execution. Do not sum reruns, configurations or historical Stage4 overlaps. Zero external inference requests/tokens/cost is supported by native network controls; fake calls are unknown unless instrumented. Skipped/excluded/xfail cases and setup-blocked scenario bodies are not passing protection.

## Review and execution

Independent review accepted core isolation before initial collection; subsequent batches and admission were accepted before their runs. The wrapper cache gap was corrected and retested before admission. All accepted runs were source-stable. Three existing app assertions were repaired after preserving their initial17/3 evidence; post-repair20/20passed. The existing blank PDF fixture became a nonblank text fixture with the same one-case count; actual PyMuPDF path passed, optional pypdf fixture branch remains unexecuted.

Native browser prerequisites passed, but application login overlay blocked12scenario bodies; the sole passing case checks headless configuration. No bypass or application fix was made. See [readiness](readiness.md), [execution history](execution.md), [review](review-notes.md) and machine [latest results](runs/latest-summary.json).
