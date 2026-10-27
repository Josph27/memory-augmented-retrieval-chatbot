# Stage 5 execution and repair evidence

Initial unchanged tests ran at e7ad3b7. Both launches had stable exact source/index/dirty snapshots and passed native parent/child confinement. Full console, JUnit, machine outcomes, dependency inventory and source/proof records are preserved in runs/initial-*.tar.gz; initial-summary.json is the compact case-level index. Archives contain execution records only, not private settings or application databases.

| Initial group | Responsibilities | Collected | Passed | Failed | Errored | Skipped | Xfailed / Xpassed | Excluded | Test duration |
|---|---|---:|---:|---:|---:|---:|---|---|---:|
| Offline unit | Routing, context/budget/prompt assembly, metrics/preparation transforms, asset wiring |127|124|3|0|0|0 /0|0 within group|12.97s|
| Offline integration | SQLite/Chroma, memory/document/lifecycle composition, fake eval regression |502|453|47|0|1|0 /0|1 actual cross-encoder preload|34.01s|

629 cases collected including one excluded node;628 selected unique cases across disjoint groups.577 passed,50 failed,1 skipped. Excluded/skipped are not passing protection. External inference requests/tokens/cost were zero, supported by passed native network controls. Fake model call counts were not instrumented and remain unknown. Deferred groups were never collected and have unknown expanded case counts. Stage4 overlaps these cases and must not be added to these totals.

## Initial failure classification

Independent read-only triage reconciled all50 failures:

- Unit:2 stale prompt literals (test/assertion);1 tracked Chainlit config hidden by runtime masking (infrastructure).
- Integration:17 offline prerequisite failures (16 eager real embedding loads plus race entry timeout before model);9 merged-dispatcher/source-selection assertion defects;1 latest-user rendered-message assertion defect;9 category/namespace fixtures;7 fake-manager guard prerequisite gaps;1 superseded vector upsert exception expectation (DEC013);3 missing AppConfig field failures in LongMemEval (application/evaluation consumer defect).
- The two structured-memory mock-eval failures among guard gaps arise in the evaluation harness, not local tests. Changing that shared evaluation code is outside this test-only batch. Preserve them visibly pending a separately approved fix.
- Classification identifies the first observed blocker; repaired setup can expose consequential deeper failures. Do not count repaired prerequisites as established outcomes until rerun.

## Repair batch 1

Explicit local dependencies retain real Chroma, dispatcher, coordinator, context/budget and actual request composition. Strengthened graph evidence is older than recent window, with unique selected/distractor contents and assertion negative controls. Send/End has a held generation barrier and verifies pending End before release. LangMem fixtures use per-instance connectivity controls, require manager invocation, distinguish actual empty output from connection failure and inspect storage-before-flags ordering. The infrastructure exposes only tracked, hashed .chainlit/config.toml inside its otherwise ephemeral masked directory. No application code changed.

Post-repair outcomes and independent acceptance are recorded after execution; initial archives remain immutable.

Independent read-only review accepted batch1 before execution. Post-batch1: unit127collected,125passed2failed,pytest duration recorded in machine summary; integration503collected including1deselected,463passed38failed1skipped. All modified cases passed, including the new explicit guard rejection case. Both runs source stable and external requests/tokens/cost0; fake calls unknown. Exact durations and expanded outcomes are in runs/post-batch1-summary.json; full evidence in matching archives. These overlap the initial baseline and are not additional unique coverage.

## Repair batch2 — storage and meaningful assertions

Independent review accepted9test/supportfiles; coordinator corrected two setup issues before execution (fake delete lookup; extension-loaded native inspection connection). Run post-batch2:509collected/508selected,475passed32failed1skipped/1deselected;30.5s approximate, exact duration in machine summary. All strengthened SQL/logging/manager and Chroma separation cases passed. New native sqlite-vec separate and delete parameters passed; update failed with UNIQUE constraint on vec_memories primary key from actual INSERT OR REPLACE. No native-path substitution or skip was added. Failed snapshot-write test passed with pending flags and deliberate seam restoration inside the test.

A second new failure was a test setup defect: the nonraw formatting fixture supplied an unranked score=None and was legitimately excluded below minimum utility. It is corrected to ranked score1.0 with every content/provenance assertion retained; rerun remains required. Initial and post-batch2 failed evidence stays preserved.

### S5-APP-01 — native vector update

Actual native384-dimensional test first indexes a record, updates the same SQL identity, then calls LongTermMemoryVectorIndex.upsert_record. sqlite-vec raises sqlite3.OperationalError: UNIQUE constraint failed on vec_memories primary key at src/memory/long_term_vector_index.py:159. Separate-store/namespace and delete cases pass. This is an observed application defect, not a new desired vector-error policy; DEC013 still requires SQL durability/logging at the combined store boundary. Recommend a separately approved native replacement/update repair with this regression retained. No application fix authorized/performed.

Ranked-input correction independently accepted and rerun:509collected/508selected,476passed31failed1skipped,1excluded. Nonraw processing passed; native update failure remains. Full corrected run and previous failed fixture run both archived separately; external requests/tokens/cost0, fake counts unknown, stable source. This overlaps prior runs.

Withdrawn prerequisite claim: a worker inferred scripts/lib/load_eval_env.sh was absent from a search omission; coordinator verified tracked2218-byte file via git ls-files/git show/direct read. Helper exists; no missing-helper blocker. User and reviewers were explicitly corrected. Wrapper admission still needs real uv, synthetic Git metadata and ephemeral artifacts.
