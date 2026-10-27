# Independent bounded evidence review

TASK-11,2026-10-27. Internal agents reviewed source and coordinator artifacts without imports, collection, execution, edits or private/runtime reads. This supports the selected verification boundary and consequential evidence corrections; it is not an independent second exhaustive audit.

## Isolation review

`revalidation_isolation` inspected the migration guard, current import/storage/model paths and every selected test cohort's setup. Recommended OS confinement for native SQLite/Chroma, canonical settings overrides before import, explicit deterministic and canonical-default cohorts, and exclusion of app-import/browser/live/wrapper paths. Required credential masking and exact real-model deselection were implemented. Dynamic app imports in product_behavior/test_runner.py were identified and excluded despite its non-browser selector.

The reviewer inspected the final runner and minimal bwrap mount plan before execution. Native SQLite/source-write, temporary store, absent original checkout/runtime stores, masked credentials and OS network canaries ran before dependency imports. Synthetic passwd/home correction addressed a sandbox portability problem; real home/caches were never exposed. Python guards are supplementary to OS isolation, not a substitute. Existing fake managers reaching real health guards were deliberately not patched to success.

All25 eval/storage files were separately inspected for fixture/fake/dry-run boundaries before running. Genuine Chroma storage uses existing deterministic embeddings. Metric/mock/source-string passes retain their stated limitations.

## Consequential finding review

`main_baseline_impact` independently checked AUD02/03/05/17/20 and the new LongMemEval consumer failure against source and accepted cohort JSON. Corroborated:

- End extraction rejection can return partial counts normally; ChatEndAction then continues to inactivation. Exceptions are a different path. Test name claiming active state does not itself assert the active flag.
- LangMem normalization attributes permitted user IDs but does not deterministically check textual support using source_text_by_id.
- Unknown-model fallback with default arguments resolves through262144 application cap;4096 applies only without native,endpoint or application limit. Actual provider capacity remains unverified.
- Old exact-equality AUD17 mechanism is superseded. Current recording-model check is blocked before answer generation by unconditional neighbor expansion evaluating the default vectorstore/embedding loader. Request parity remains unverified.
- Structured sqlite-vec now uses the same Database; this does not make SQL/vector operations atomic. Upsert catches/logs vector failure after SQL commit; delete may propagate after soft deletion. Existing/new tests assert different upsert exception contracts.
- LongMemEval build_reranker reads removed AppConfig.reranker_cross_encoder_top_k; three existing tests raise AttributeError. This is an application/evaluation consumer integration problem, not only a stale assertion.

Required wording refinement: cache fallback occurs when the primary namespace/query retrieval yields no active records, not only when all SQL is empty. Unrelated active SQL can still exist.

All refinements were sent to the main assessor for incorporation in its owned findings/workflow/test documents. Runtime counts are628distinct deterministic checks plus17overlapping canonical-default checks; they must not be summed as unique coverage. Temporary Chroma passes do not verify whole-turn or live vector quality.
