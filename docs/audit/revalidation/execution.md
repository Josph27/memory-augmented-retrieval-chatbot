# Existing-check execution evidence

TASK-11, 2026-10-27. Source pinned at1cf4c55; machine details: [execution-results.json](execution-results.json). Independent static isolation review preceded each selected cohort.

| Cohort | Configuration | Pass | Fail | Skip | Additional boundary |
|---|---|---:|---:|---:|---|
| deterministic-core | deterministic | 198 | 7 | 0 | existing test assertions retained |
| deterministic-composition | deterministic | 201 | 28 | 1 | 1 real-model case deselected |
| deterministic-eval-storage | deterministic | 179 | 14 | 0 | existing test assertions retained |
| canonical-offline | canonical | 9 | 8 | 0 | canonical IDs overlap deterministic runs |

**628 distinct deterministic checks:578 passed,49 failed,1 skipped;1 additional real-model test deselected.** Canonical-default offline cohort has17 overlapping checks:9 passed8 failed; do not add these to distinct totals.69 test source files were selected, covering current/new coordinator and consolidation tests, deterministic algorithms, production composition, lifecycle, evaluation adapters and native temporary Chroma. These are configuration-bounded results, not full application acceptance.

## Isolation and configuration

Minimal bwrap namespace mounts /usr, selected system runtime files, read-only /venv and /repo, masked provider/Git files, empty ephemeral /repo/data, writable temporary /work and isolated /tmp,/run,/dev,/proc. Original checkout and real home are absent. Network/PID/IPC/UTS namespaces isolated. The launcher clears inherited env. Runner disables dotenv/plugin autoload/downloads/telemetry/bytecode, patches only canonical storage paths and records explicit deterministic settings. No global guard-success or embedding substitution. Existing test fakes retained.

All accepted runs passed source-write/read-only, native SQLite denial/temporary-write, credential/runtime masking, original-absence and OS network canaries. Later accepted runs also verify synthetic passwd/home. Core205 run predates that additional home canary; it had no dependency home errors or network attempts. No host data/credential reads or writes were needed. Python network hooks log attempted health/telemetry connections; OS network confinement remains the native boundary.

Deterministic configuration selects sqlite structured retrieval, deterministic reranking, rule routing and deterministic previous-gist extraction. Canonical cohort keeps native defaults (hybrid memory/reranker/routing) except ephemeral storage and synthetic endpoint credentials. Passing in the deterministic cohort is not proof of default model/vector behavior.

Reproduce with the existing host dependency venv and installed bwrap (the launcher requires permission to create namespaces):

```bash
python3 docs/audit/revalidation/launch_existing_checks.py deterministic-core
python3 docs/audit/revalidation/launch_existing_checks.py deterministic-composition
python3 docs/audit/revalidation/launch_existing_checks.py deterministic-eval-storage
python3 docs/audit/revalidation/launch_existing_checks.py canonical-offline
```

Launcher uses fixed local worktree/runtime paths and unique private /tmp result directories. Exact commands, harness/cohort hashes, raw-output SHA-256, source commit and outcomes are retained in execution-results.json. [Exact executed inputs](executed-inputs/README.md) match all recorded input hashes; the formatted current runner is AST-equivalent to the accepted synthetic-home variant (unused import removed). No dependency install or live inference.

## Interpretation

- All four genuine Chroma persistence, logical-chunk identity and SQL legacy migration tests passed using existing deterministic embeddings. This tests native storage, not embedding-model quality.
- Existing actual-request composition check fails before answering because neighbor expansion opens the document vectorstore/embedding model with an empty offline cache. It does not reproduce the old exact-equality AUD-17 argument.
- Fake LangMem managers still reach a real health guard; some positive-memory assertions fail there, and some negative tests can pass through an unintended failure path. Green results are read alongside the static assertion assessment.
- Existing vector tests expect errors to propagate while new consolidation tests assert nonfatal vector synchronization failure. Namespace/category changes also affect recall fixtures. Runtime failure alone does not decide the intended policy.
- LongMemEval adapter still consumes removed AppConfig.reranker_cross_encoder_top_k; three existing cases raise AttributeError.
- Source inclusion/provenance and prompt-literal mismatches require behavior/contract reconciliation. No app/test fix, deletion or new product requirement was introduced.

## Failed existing checks

Classifications below are bounded triage, not automatic product-bug verdicts. Raw asserted values and stacks are preserved in the machine results; full original logs remain at the hashed local output paths.

| Cohort | Existing test | Observed failure class |
|---|---|---|
| deterministic-core | `tests/test_semantic_router_v2_validation.py::test_previous_chat_quote_expands_finalized_gist_to_raw_span` | provenance-assumption-mismatch |
| deterministic-core | `tests/test_current_chat_span_retriever.py::test_exact_quote_comes_from_raw_current_chat_messages` | source-inclusion-filtering-assumption |
| deterministic-core | `tests/test_current_chat_span_retriever.py::test_current_user_query_is_excluded_from_span_and_context` | source-inclusion-filtering-assumption |
| deterministic-core | `tests/test_current_chat_span_retriever.py::test_current_chat_span_is_disabled_by_default_but_works_when_enabled` | source-inclusion-filtering-assumption |
| deterministic-core | `tests/test_current_chat_span_retriever.py::test_oversized_span_is_dropped_without_exceeding_context_budget` | source-inclusion-filtering-assumption |
| deterministic-core | `tests/test_gist_raw_span_expansion.py::test_finalized_previous_gist_expands_to_exact_raw_context` | provenance-assumption-mismatch |
| deterministic-core | `tests/test_gist_raw_span_expansion.py::test_current_gist_expands_only_when_source_is_explicitly_enabled` | source-inclusion-filtering-assumption |
| deterministic-composition | `tests/test_architecture_layers.py::test_coordinator_trace_contains_all_trace_only_layers` | offline-model-prerequisite |
| deterministic-composition | `tests/test_architecture_layers.py::test_coordinator_falls_back_when_context_packet_is_invalid` | offline-model-prerequisite |
| deterministic-composition | `tests/test_memory_context_acceptance.py::test_production_recent_messages_keep_old_fact_and_current_query_once` | assertion-mismatch-needs-scoped-triage |
| deterministic-composition | `tests/test_product_failure_atomicity.py::test_answer_timeout_preserves_user_without_fake_assistant` | offline-model-prerequisite |
| deterministic-composition | `tests/test_product_failure_atomicity.py::test_send_and_end_share_one_atomic_chat_guard` | answer-entry-prerequisite-or-race-unresolved |
| deterministic-composition | `tests/test_chat_end_action.py::test_finalized_previous_chat_gist_reaches_context_packet` | provenance-assumption-mismatch |
| deterministic-composition | `tests/test_short_term_memory_scheduling.py::test_live_deferred_post_answer_update_keeps_turns_intact` | offline-model-prerequisite |
| deterministic-composition | `tests/test_short_term_memory_scheduling.py::test_agentic_each_turn_service_policy_evaluates_every_completed_turn` | offline-model-prerequisite |
| deterministic-composition | `tests/test_chat_gist_summarizer.py::test_current_chat_gist_is_not_routed_into_default_context` | source-inclusion-filtering-assumption |
| deterministic-composition | `tests/test_long_term_memory_vector_retrieval.py::test_structured_memory_vector_retrieval_returns_expected_memory` | memory-category-namespace-or-retrieval-mismatch |
| deterministic-composition | `tests/test_long_term_memory_vector_retrieval.py::test_structured_memory_hybrid_retrieval_deduplicates_by_memory_id` | memory-category-namespace-or-retrieval-mismatch |
| deterministic-composition | `tests/test_long_term_memory_vector_retrieval.py::test_structured_memory_vector_retrieval_falls_back_to_sqlite` | memory-category-namespace-or-retrieval-mismatch |
| deterministic-composition | `tests/test_structured_memory_vector_sync.py::test_langmem_production_write_syncs_insert_with_typed_metadata` | guard-prerequisite-plus-unreached-assertion |
| deterministic-composition | `tests/test_structured_memory_vector_sync.py::test_vector_failure_is_explicit_but_sqlite_mode_requires_no_backend` | changed-nonfatal-vector-error-policy |
| deterministic-composition | `tests/test_structured_memory_vector_sync.py::test_synced_vector_memory_reaches_context_with_sqlite_provenance` | memory-category-namespace-or-retrieval-mismatch |
| deterministic-composition | `tests/test_structured_memory_vector_sync.py::test_sqlite_recall_remains_independent_of_vector_backend` | memory-category-namespace-or-retrieval-mismatch |
| deterministic-composition | `tests/test_langgraph_demo_regression.py::test_compact_cross_chat_document_and_casual_demo_regression` | assertion-mismatch-needs-scoped-triage |
| deterministic-composition | `tests/test_e2e_scenarios.py::test_model_mode_accepts_injected_fake_model_without_network` | assertion-mismatch-needs-scoped-triage |
| deterministic-composition | `tests/test_e2e_scenarios.py::test_e2e_report_export_schema` | assertion-mismatch-needs-scoped-triage |
| deterministic-composition | `tests/test_e2e_scenarios.py::test_all_mock_e2e_scenarios_pass` | assertion-mismatch-needs-scoped-triage |
| deterministic-composition | `tests/test_orchestration_demo_modes.py::test_native_remains_default_and_does_not_run_graph` | offline-model-prerequisite |
| deterministic-composition | `tests/test_orchestration_demo_modes.py::test_langgraph_demo_context_packet_is_used_for_model_answer` | offline-model-prerequisite |
| deterministic-composition | `tests/test_orchestration_demo_modes.py::test_langgraph_shadow_keeps_native_context_authoritative` | offline-model-prerequisite |
| deterministic-composition | `tests/test_orchestration_demo_modes.py::test_langgraph_demo_failure_visibly_falls_back_to_native` | offline-model-prerequisite |
| deterministic-composition | `tests/test_langmem_structured_memory.py::test_short_term_memory_uses_langmem_backend_and_stores_memory` | guard-prerequisite-plus-unreached-assertion |
| deterministic-composition | `tests/test_langmem_structured_memory.py::test_langmem_update_preserves_existing_memory_records` | guard-prerequisite-plus-unreached-assertion |
| deterministic-composition | `tests/test_langmem_structured_memory.py::test_processed_messages_marked_only_after_successful_storage` | guard-prerequisite-plus-unreached-assertion |
| deterministic-composition | `tests/test_long_term_store.py::test_cross_chat_structured_memory_is_visible_across_chats` | guard-prerequisite-plus-unreached-assertion |
| deterministic-eval-storage | `tests/test_answer_policy_prompts.py::test_production_system_prompt_keeps_abstention_for_missing_evidence` | prompt-literal-contract-mismatch |
| deterministic-eval-storage | `tests/test_answer_policy_prompts.py::test_generic_answer_policy_qualifies_partial_evidence` | prompt-literal-contract-mismatch |
| deterministic-eval-storage | `tests/test_structured_memory_eval.py::test_lifecycle_eval_runs_local_sample_dataset` | fake-extraction-guard-affects-metrics |
| deterministic-eval-storage | `tests/test_structured_memory_eval.py::test_structured_memory_eval_runs_local_sample_dataset` | fake-extraction-guard-affects-metrics |
| deterministic-eval-storage | `tests/test_longmemeval_adapter.py::test_mock_runner_produces_report_without_live_model` | removed-config-field-consumer |
| deterministic-eval-storage | `tests/test_longmemeval_adapter.py::test_recent_only_report_and_json_export` | removed-config-field-consumer |
| deterministic-eval-storage | `tests/test_longmemeval_adapter.py::test_span_retrieval_mode_uses_raw_message_candidates` | removed-config-field-consumer |
| deterministic-eval-storage | `tests/test_memory_agent_bench_adapter.py::test_mock_answer_mode_is_labeled_honestly` | offline-model-prerequisite |
| deterministic-eval-storage | `tests/test_memory_agent_bench_adapter.py::test_cross_encoder_ablation_is_explicit_and_traceable` | offline-model-prerequisite |
| deterministic-eval-storage | `tests/test_memory_agent_bench_adapter.py::test_jsonl_report_contains_summary_and_results` | offline-model-prerequisite |
| deterministic-eval-storage | `tests/test_memory_agent_bench_adapter.py::test_raw_replay_diagnostic_is_disabled_by_default` | offline-model-prerequisite |
| deterministic-eval-storage | `tests/test_memory_agent_bench_adapter.py::test_enabled_raw_replay_reaches_context_packet` | offline-model-prerequisite |
| deterministic-eval-storage | `tests/test_mab_answer_eval.py::test_answer_execution_uses_existing_answer_agent_and_graph_path` | offline-model-prerequisite |
| deterministic-eval-storage | `tests/test_mab_answer_eval.py::test_mab_history_finalization_persists_memory_gist_and_inactive_chat` | offline-model-prerequisite |
| canonical-offline | `tests/test_orchestration_demo_modes.py::test_native_remains_default_and_does_not_run_graph` | offline-model-prerequisite |
| canonical-offline | `tests/test_orchestration_demo_modes.py::test_langgraph_demo_context_packet_is_used_for_model_answer` | offline-model-prerequisite |
| canonical-offline | `tests/test_orchestration_demo_modes.py::test_langgraph_shadow_keeps_native_context_authoritative` | offline-model-prerequisite |
| canonical-offline | `tests/test_orchestration_demo_modes.py::test_langgraph_demo_failure_visibly_falls_back_to_native` | offline-model-prerequisite |
| canonical-offline | `tests/test_structured_memory_vector_sync.py::test_langmem_production_write_syncs_insert_with_typed_metadata` | guard-prerequisite-plus-unreached-assertion |
| canonical-offline | `tests/test_structured_memory_vector_sync.py::test_vector_failure_is_explicit_but_sqlite_mode_requires_no_backend` | changed-nonfatal-vector-error-policy |
| canonical-offline | `tests/test_structured_memory_vector_sync.py::test_synced_vector_memory_reaches_context_with_sqlite_provenance` | memory-category-namespace-or-retrieval-mismatch |
| canonical-offline | `tests/test_structured_memory_vector_sync.py::test_sqlite_recall_remains_independent_of_vector_backend` | memory-category-namespace-or-retrieval-mismatch |

## Unexecuted checks and explicit reasons

[Machine list](unexecuted-checks.json). Collection itself is deferred for these paths; absence of execution is not a pass. No live model/vector-quality/browser/production-data verification is claimed.

| Path | Reason |
|---|---|
| `tests/e2e/conftest.py` | Browser failure-report hook; not a standalone test. Browser execution not selected. |
| `tests/e2e/product_behavior_chainlit_app.py` | Alternative browser fixture application; requires separately reviewed server/model/startup isolation. |
| `tests/e2e/test_product_behavior_browser.py` | Requires browser, live local service/process lifecycle and separate startup isolation. |
| `tests/product_behavior/__init__.py` | Package marker; no tests. |
| `tests/product_behavior/test_runner.py` | Even non-browser oracle selection dynamically imports app and triggers eager model warm-up. |
| `tests/test_backend.py` | Manual live backend probe; no collected test functions. |
| `tests/test_chainlit_chat_actions.py` | Imports app before fixtures; eager service/model preload requires a separate reviewed collection setup. |
| `tests/test_chainlit_memory_trace_helpers.py` | Imports app before fixtures; helper assertions do not justify unreviewed eager startup. |
| `tests/test_final_eval_wrappers.py` | Spawns shell/Python subprocesses and wrapper artifacts; needs separate confined subprocess contract setup. |
| `tests/test_targeted_eval_wrapper.py` | Spawns wrapper subprocesses; needs separate confined subprocess contract setup. |
| `braemon/e2e/chat-messages.test.mjs` | Browser/socket probe requires running services; real messages/processes would need separately reviewed isolation. |
| `braemon/e2e/smoke.test.mjs` | Browser/socket probe requires running services; real messages/processes would need separately reviewed isolation. |
| `tests/test_socket.cjs` | Browser/socket probe requires running services; real messages/processes would need separately reviewed isolation. |
| `tests/test_socket.js` | Browser/socket probe requires running services; real messages/processes would need separately reviewed isolation. |
| `tests/test_socket_2.js` | Browser/socket probe requires running services; real messages/processes would need separately reviewed isolation. |
| `evals/test_short_term_memory.py` | Standalone diagnostic, not pytest coverage; static audited only. |
| `tests/test_memory_reranker.py::test_cross_encoder_backend_preload_loads_model` | Explicitly requires real model assets; deselected with exact-ID assertion, no download/cache access. |

## Setup attempts and evidence limits

Initial bwrap capability failed under the default tool sandbox (NETLINK_ROUTE denied); the authorized namespace-capability retry succeeded. An early credential-mask canary tried reading a masked character device and failed before imports; replaced with safe device-metadata verification. Initial composition/canonical attempts lacked passwd/home, producing Path.home/getpwuid dependency errors; corrected using synthetic passwd/group bound to /work/home, without changing HOME or reading the real home. Those setup failures are superseded by corrected runs, not product findings. All application/test source files remain unchanged.

The existing dependency environment is reused read-only, not a clean install of the current lockfile. A skip in document_loaders is conditional library availability. Full default app startup, real sqlite-vec embedding/retrieval quality, live provider, browser and subprocess-wrapper checks remain unverified; follow-up isolation prerequisites are explicit.

Full raw accepted-run JSON/console/launch evidence is also preserved in the private recovery directory as `revalidation-runtime-20261027.tar.gz`, with per-file and archive hashes in `revalidation-runtime-manifest.json`. The archive was verified after creation. This supplements the durable condensed repository results; temporary runtime stores were not archived.
