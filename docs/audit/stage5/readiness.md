# Stage5 readiness — bounded blockers resolved

TASK14 / DEC015 is complete: all four recorded automated blockers were reconciled and minimally fixed, with independent review and final isolated verification. DEC013 SQL-success/logged-vector-failure is preserved. No purge began; MAINT-01/TASK13 test simplification remains deferred. Sufficient protection exists to propose the artifact-only batch below; workflow removals still need their own consumer evidence, protection and approval.

## Final disjoint groups

| Group / responsibilities | Collected | Passed | Failed | Errored | Skipped | Xfailed / Xpassed | Excluded | Pytest duration |
|---|---:|---:|---:|---:|---:|---|---|---:|
| offline-unit: routing, context, prompts, metrics, asset wiring | 127 | 127 | 0 | 0 | 0 | 0 / 0 | 0 within group | 16.39s |
| offline-integration: SQL/native vectors/Chroma, memory/document/lifecycle, fake evaluations | 509 | 508 | 0 | 0 | 0 | 0 / 0 | 1 cross-encoder preload | 36.20s |
| app-composition: real callbacks, trace serialization and report harness | 20 | 20 | 0 | 0 | 0 | 0 / 0 | 0 within group | 6.70s |
| subprocess-wrappers: shell/uv/config/status with fake answer/judge children | 21 | 21 | 0 | 0 | 0 | 0 / 0 | 0 within group | 2.04s |
| browser: native Chainlit fresh login and lifecycle/Inspector journeys | 13 | 13 | 0 | 0 | 0 | 0 / 0 | 0 within group | 86.16s |

690collected,1excluded,689selected; **689passed,0failed/errored/skipped/xfail/xpass**. Browser13 means1headless configuration check plus12actual UI journeys. No cases were added in TASK14; previous Stage5 added7semantic cases and admitted54existing cases. Counts are cases including parameter expansion, not functions or a coverage percentage.

All five runs used identical frozen working-source snapshots: HEAD785ccd9 plus the same documented dirty application/tests/audit files; before/after hashes match in every run. Final application/test bytes were then committed unchanged in a02bcfa,4dbcaa4,bc28550. Documentation/evidence updates followed execution. [Machine results](runs/latest-summary.json), [initial/affected/final separation](runs/blockers-summary.json), [batch explanation](blocker-resolution.md) and full compressed logs/JUnit/source/runtime/native-control proofs under runs/ provide provenance. Durations are individual pytest sessions, not elapsed project time.

External inference requests/tokens/cost: **0 for every executed group**, supported by native parent/child network confinement and fresh synthetic storage/configuration controls. Fake model-call totals remain unknown. Controlled browser loopback HTTP is not external inference. The separately preserved React type fix passed an isolated offline Vite build; React browser probes remain unexecuted.

## What the blockers established

- Native sqlite-vec update: unsupported replacement became transactional delete+insert for single and batch indexing, stable row IDs and duplicate-input last-write-wins. Existing native update case now proves changed vector bytes/similarity, repeated indexing and rollback on invalid dimensions; direct errors and DEC013 combined-store logging remain protected.
- LongMemEval: removed the stale AppConfig field reference; existing reranker default500 is unchanged. Three existing regressions explicitly provide local embeddings with real temporary Chroma; default eager document initialization still needs model assets outside this controlled setup.
- Synthetic structured-memory evaluator: its fake manager now gets a local connectivity substitute and explicit SQLite retrieval. Six obsolete fixture category values conform to the current schema; text/update identity/metrics stay intact. Existing tests verify actual fake-manager invocation and reject real guard calls.
- Native login/loading: startup overlay waits for an authenticated composer; reassigned state is mutable; End/Fork overlays remain. The original browser setup assumed graph mode while production defaults native; its fixture now explicitly requests graph mode, and exact toolbar assertions include the existing Consolidation Log. All original Inspector/provenance/read-only/reload/model-call assertions remain. No forced interaction, overlay bypass or suppressed error;12browser page-error logs are empty.

## Original and intermediate evidence retained

Original Stage5 core baseline:629collected/1excluded,577passed50failed1skipped. Before TASK14, the latest integration was502pass6fail and native browser1configuration pass12setup errors. Fresh reconfirmation again gave502/6 integration. The new repeated browser reconfirmation was intentionally stopped:1passed6setup errors6unfinished, exit143; this partial run does not replace the original complete13-case evidence.

After application fixes, integration505pass3fail exposed missing embedding assets; browser9pass4fail exposed fixture mode and toolbar expectations. Those prerequisite/assertion repairs were reviewed before final runs. No retry totals are added as coverage. [Execution history](execution.md) remains intact.

## Remaining limits and cleanup impact

The42unique nonbrowser product-oracle rows remain **39passed3failed**, separate from pytest harness passes: PB-PERSIST-005 multi-user ownership, PB-FAIL-010 broader idempotency and PB-FAIL-003 timeout-only-user oracle versus implemented typed assistant failure persistence. No desired timeout policy inferred. None affects the proposed diagram-artifact removal.

Live providers/extraction/summaries/consolidation/judges, actual model/tokenizer/cross-encoder assets, clean-install/default startup, React browser execution, full forgetting/cache/history semantics, ambiguous fork/edit/scope policy and default competing gist/direct parent metadata remain outside this certification. Registered live/expensive/manual/Node groups stay excluded, with expanded deferred counts unknown; see [exclusions](exclusions.md) and [live proposal](live-proposal.md). No spending authorized. Existing RV001 rebuild syntax/API defects and unrelated lint findings remain parked. Native screenshots also show trace-comment text in the transcript; this presentation finding is recorded without expanding the batch.

## First cleanup proposal — approval pending

Remove **only** docs/mermaid-diagram-2026-07-15-021559.png (3,063,514bytes), retain docs/system-component-map.mmd and all other assets/evaluations/code/tests. Two independent inspections found no runtime/config/CLI/evaluation/asset/operational consumer; filename references occur only in audit inventories. The image is a pre-rendered component map; exact regeneration/layout equivalence is not claimed. Tradeoff: lose this ready-rendered image, retain editable source; checkout shrinks about3.06MB, Git history size does not.

After approval: verify only the approved artifact is deleted, retained source exists, consumer/reference search remains clean, and audit disposition is updated without rewriting historical manifests. No behavior or workflow removal is included. Current automated protection and user-reported manual check remain available; rerunning application tests solely for this unreferenced PNG is unnecessary. **Proposal only; file remains present.**
