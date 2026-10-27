# Stage5 readiness — test-only work delivered; purge gate not passed

Baseline, isolation, bounded test repairs/protection, independent review and evidence delivery are complete within DEC012/013. Application fixes, live spending and removals were not authorized/performed. No purge began. Current required behavior is not certified merely because many tests pass.

## Latest per-group results

These are disjoint groups at their latest recorded snapshots, not a single clean whole-suite invocation. Every run's exact HEAD/dirty files/hash/source stability is archived; no retries are added as extra coverage. Table duration is pytest session time, not coordinator work or prerequisite wall time.

| Group / responsibilities | Collected | Passed | Failed | Errored | Skipped | Xfailed / Xpassed | Excluded/not run | Duration | Important limits |
|---|---:|---:|---:|---:|---:|---|---|---:|---|
| Offline unit: routing, contexts/budgets/prompts, metrics/input transforms, asset wiring |127|127|0|0|0|0 /0|0 within group|16.07s|Not real model quality/tokenizer or UI behavior |
| Offline integration: SQL/native sqlite-vec/Chroma, memory/document/lifecycle, fake evaluations |509|502|6|0|0|0 /0|1 real cross-encoder preload|36.45s|Native update and eval harness failures; embeddings/inference substitutes explicit |
| App composition: real callbacks/current trace serialization and report harness |20|20|0|0|0|0 /0|0 within group|5.32s|Per-test fakes and startup embeddings substitute;42oracle rows separately below |
| Shell wrappers: actual shell/uv/config/path/status control with fake answer/judge children |21|21|0|0|0|0 /0|0 within group|1.67s|No real provider/judge workflow; synthetic Git metadata |
| Native browser: existing13tests |13|1|0|12|0|0 /0|12scenario bodies blocked during setup, not separate cases|436.13s|One pass is headless configuration; no UI scenario passed |

690collected,1excluded,689selected;671passed6failed12errored,0skipped/xfail/xpass. Of the increase from628initial selected cases,54 were existing but newly admitted; only7 semantic cases were newly authored. No tests deleted. External inference requests/tokens/cost:0 for each executed group, supported by passed native parent/child controls. Fake model calls unknown/uninstrumented. Controlled browser HTTP is not external inference.

Initial core baseline remains separate:629collected/1excluded,577passed50failed1skipped. Initial admitted app20cases17passed3failed is preserved. The old skipped PDF case was repaired and passed under its renamed identity; it is not a new case. [Machine results](runs/latest-summary.json), [initial](runs/initial-summary.json), [history](execution.md), and complete per-run compressed logs/JUnit/proofs under runs/ preserve both states.

Product evaluation has42unique nonbrowser rows:39passed3failed. Report helpers rerun these and add synthetic browser rows; neither repetition nor synthetic rows count as added product/native protection. PB-PERSIST-005 (multi-user ownership) and PB-FAIL-010 (cross-operation idempotency) are documented limitations, not approved scope expansion. PB-FAIL-003 expects only a user row after timeout, while implemented behavior and another regression test retain a typed assistant failure placeholder: this is an oracle/implementation expectation mismatch, not proof of desired product policy. Do not label all42passing because3pytest report/harness tests pass.

## Blockers and proposals requiring expanded authorization

1. **S5-APP-01 — native vector update:** actual384dim vec0 update raises primary-key UNIQUE error in src/memory/long_term_vector_index.py:159. Separate DB/namespace and delete checks passed. Propose a bounded native replacement/update fix preserving row identity, SQL authority and DEC013 logging semantics; rerun existing native/storage tests. No change made.
2. **RV004 — LongMemEval consumer:**3tests fail reading nonexistent AppConfig.reranker_cross_encoder_top_k in evals/longmemeval_adapter/runner.py:415. Propose align this caller with current configuration/class defaults after checking intended ranking cap; no test-only fake attribute or silent skip.
3. **Mock evaluation harness:**2structured-memory regressions fail because the runner's own fake manager still calls real ConnectionGuard before invocation. Propose explicit connectivity substitute only for that synthetic harness, not global production guard. Shared evaluation-runtime edits were kept outside this test-file batch. Preserve CLI defect even though separate per-updater tests now exercise extraction correctly.
4. **S5-APP-02 — native login:** production loading overlay intercepts Sign In;12setuperrors are one shared blocker. Propose one bounded public/product-navigation.js repair retaining authenticated/End/Fork loading feedback and login usability. Separately static const-reassignment paths predict errors after product-state but were not reached. Verify through existing13browsercases, without forceclick/overlay removal in tests.

Existing RV001 rebuild CLI syntax/API defects remain parked; global syntax scan finds its unexpected indent. Full Ruff31diagnostics across8files are byte-for-byte unchanged since initial baseline; focused changed-file checks pass. Current work does not authorize a general lint/bug campaign.

No further behavior choice blocked the authorized test repairs after user DEC013 chose SQLsuccess+loggedvectorfailure. DEC101–106 remain relevant only to concrete future scope/policy work; none is blanket removal approval. Zero workflow removals approved. A bounded application/evaluation blocker batch is the next meaningful authorization; it should not bundle purge or new capabilities. Product-oracle timeout policy can remain a separate explicit decision if a future batch needs it.

## Remaining verification

- Actual live provider/tool extraction, summaries, consolidation and judges; actual model/tokenizer/cross-encoder assets and clean-install/default startup remain unverified. [Deferred live proposal](live-proposal.md) includes representative cases, request/output bounds, retries and instrumentation prerequisites; no spending authorized.
- React Node browser probes and manual diagnostics remain registered/not run; expanded case counts unknown. Native Chainlit cannot stand in for React.
- Full forgetting/cache/history behavior, ambiguous fork/edit/scope semantics and default competing gist/direct parent metadata are not established by narrow vector deletion or gist-only tests.
- Actual selected graph evidence reached the recording model with explicit real Chroma/local embeddings and no fallback, including omission/leak negative controls. This closes the exercised request-path gap, not every possible provider/orchestration combination.

## Maintainer scope

At the user's status question, rough Stage5 completion was estimated75%, not measured code coverage. Offline protection is now largely in place; remaining work is chiefly blockers and integration verification, not adding hundreds of tests. Keep the compact default core, explicit local integration/UI and opt-in live/evaluation/manual groups. See [size and redundancy proposal](maintainer-scope.md): three equivalent selector parameter instances are the only currently well-supported removal candidate; one equivalent boundary case would preserve their unique protection. No reduction approved/performed. A shared explicit MAB fixture is a later bounded consolidation candidate. Do not delete whole test files or infer necessity from green/default-off/test-only labels.

Original tmp-audit checkout/28dirtyfiles, stashes and recovery archive remain preserved; provider changes remain in their separate migration commit. Current coherent Stage5 commits cover only tests/infrastructure/configuration/audit records and3synthetic fixture category values.
