# File-level assessment and scope reconciliation

TASK-11 · 2026-10-27 · pinned1cf4c55. Every relevant manifest path is explicitly enumerated below:324 product union rows +14 evaluation inputs +4 assets =342. Group references describe assessment, consumers and limits, not merely an automated inventory. AST symbol names are navigation, not semantic proof. Compare actual old working-source hashes in coverage-manifest; historical report text remains reconstructed.

## 1. Evidence groups

- **S0 application/source composition:** app.py callbacks, eager model startup, model selection, executor answer, native lifecycle/log/trace; main/error/caller branches inspected. src/config/provider_settings/settings/connection_guard/model_wrapper source assessed including actual-old provider diff. Consumers: Chainlit, custom API, ChatService and eval factories; not live provider acceptance.
- **S1 memory/storage:** Database schema/connection and changed document/fork/memory methods; short_term scheduled/latest/replay/end/cache/flags/logging; LangMem normalization/guard/persistence; category namespaces/store/sqlite-vec/sync and retrieval fallback. Changed paths and connected consumers semantically read. No observed private state; TTL/grounding and partial outcomes bounded in WF08/AUD03/06/20.
- **S2 context/retrieval/routing/graph:** changed coordinator/ranker/dispatcher/neighbor/summary/source forcing, all changed main/failure branches and relevant unchanged allocator/model profile/token estimator/manager/semantic sources read. Per-regex/helper exhaustive proof not claimed. Consumers: native/graph/eval/test; no quality claim. WF03/07/10, AUD04/05/11/17 and RV003.
- **S3 lifecycle/document/inspection:** every API route body, scoped ingestion/loading/summary/deletion, unchanged End/Fork/registry/Inspector/data-layer boundaries read. Source/failure/retry/scoping/transaction edges examined; full external framework/version behavior unexecuted. WF02/04/05/06/09/11/12/13, AUD01/02/08/09/14/16/19.
- **U1 UI/runtime asset source:** functional React route/API/socket/event/lifecycle/readiness/trace/log and native JS branches read; cosmetic JSX/CSS rendering is bounded. Build configs/dev logger/client dependency selectors checked. New live E2E source fully read. No browser or visual QA. WF14/AUD18/TSA07/09.
- **T1 test source:** current setup/assertions, mocks, production boundary, isolation and unique coverage reconciled per stable TS rows/test-assessment. Changed tests read directly; unchanged assertion knowledge reused only after digest and changed-consumer review. Not every helper branch reread. Runtime outcome belongs execution.md, not static syntax inventory.
- **E1 evaluation support:** all59 current eval Python paths reconciled. Pure schemas/metrics/exports/loaders/report and fake/injected/fixture/oracle/roleless/role-aware model selection checked against tests and callers. Current canonical/default/guard/category/API influence tracked for unchanged modules; no all-case corpus/flag quality certification. LongMemEval removed-field defect RV004, raw provider gate AUD13.
- **O1 operators/launch:** CLI/parser/entry/I-O/selected flags and current dependencies traced for inspect/index/rebuild/eval/verify tools and shell. Vector rebuild invalid source/API RV001; new token monitor reads developer Pi sessions only when run (none read). Startup/run.sh Vite+exec control flow read; child/process/port shutdown not executed. Shell .dev paths unchanged but inherit current app effects.
- **D1 documentation:** functional/config/mode/lifecycle/verification prose, named API responsibility and material tables/diagrams cross-checked to owners; numeric file counts/illustrative syntax/cosmetics/external model facts not all certified. Detailed discrepancies in section3. Docs/FuturePlans is proposal, not approval. Relevant role docs separately read by owning bounded subassessors.
- **C1 configuration/build/package:** variable names/manifest/lock/runtime/template/package/test selection checked; no dependency installation, clean build or version-eligibility assertion. Canonical vs env split important. .env.example/template reviewed without reading private .env/local_settings. .python-version3.12 vs pyproject>=3.10 noted.
- **I1 input contract:** evaluation manifest/dataset paths and declared load_jsonl/load_examples/load_manifest/resolve_cases/schema consumers checked. Benchmark/user text not reread; source hash equality is not current category/namespace/all-case validation.
- **X1 metadata exclusion:** binary/generated diagrams/public assets or patch artifacts checked for role/reference only; no contents/render/deletion. Runtime stores/reports/private data, tool metadata and immutable historical snapshots excluded from semantic content review, not classified junk.
- **B1 absent baseline:** already removed Docker/requirements/root upload probes; historical consumers reconciled, not removal by this task, no restoration implied.

All S/U/T/E groups use repository-relative path plus qualified symbols in linked workflow-reconciliation/findings-register/test-assessment. C/D/I/X groups explain limits rather than claiming app behavior verified. No unchanged-unaffected inference or cleanup approval.

## 2. Exact per-path ledger

| Path | Old actual→current | Assessment / consumer group |
|---|---|---|
| `.chainlit/config.toml` | unchanged | C1 |
| `.dev/start-dev.sh` | unchanged | O1 startup/process/log configuration |
| `.dev/stop-dev.sh` | unchanged | O1 startup/process/log configuration |
| `.env.example` | modified | C1 |
| `.gitignore` | unchanged | C1 |
| `.python-version` | unchanged | C1 |
| `AGENTS.md` | modified | D1 source/config/workflow claim |
| `Dockerfile` | removed | B1 historical launch/manual probe |
| `LICENSE` | unchanged | C1 |
| `README.md` | modified | D1 source/config/workflow claim |
| `app.py` | modified | S0/S3/U1 actual callback/main/error/preload |
| `braemon/.doc.md` | added | D1 source/config/workflow claim |
| `braemon/.gitignore` | unchanged | C1 |
| `braemon/.oxlintrc.json` | unchanged | C1 |
| `braemon/README.md` | modified | D1 source/config/workflow claim |
| `braemon/console-forward-plugin.mjs` | unchanged | U1 functional consumer; visuals bounded |
| `braemon/e2e/chat-messages.test.mjs` | added | U1 functional consumer; visuals bounded |
| `braemon/e2e/smoke.test.mjs` | added | U1 functional consumer; visuals bounded |
| `braemon/index.html` | unchanged | U1 functional consumer; visuals bounded |
| `braemon/package-lock.json` | unchanged | C1 |
| `braemon/package.json` | modified | C1 |
| `braemon/public/favicon.svg` | unchanged | X1 asset/doc/UI reference |
| `braemon/public/icons.svg` | unchanged | X1 asset/doc/UI reference |
| `braemon/src/App.jsx` | modified | U1 functional consumer; visuals bounded |
| `braemon/src/api.js` | modified | U1 functional consumer; visuals bounded |
| `braemon/src/components/ChainlitChat.jsx` | modified | U1 functional consumer; visuals bounded |
| `braemon/src/components/ChainlitChat.jsx.orig` | unchanged | X1 unimported patch artifact |
| `braemon/src/components/ChainlitChat.jsx.rej` | unchanged | X1 unimported patch artifact |
| `braemon/src/components/ChatActions.jsx` | added | U1 functional consumer; visuals bounded |
| `braemon/src/components/ErrorBoundary.jsx` | unchanged | U1 functional consumer; visuals bounded |
| `braemon/src/components/Layout.jsx` | modified | U1 functional consumer; visuals bounded |
| `braemon/src/components/ModelLoadingScreen.jsx` | added | U1 functional consumer; visuals bounded |
| `braemon/src/index.css` | unchanged | U1 functional consumer; visuals bounded |
| `braemon/src/main.jsx` | modified | U1 functional consumer; visuals bounded |
| `braemon/src/pages/Chat.jsx` | modified | U1 functional consumer; visuals bounded |
| `braemon/src/pages/Chats.jsx` | modified | U1 functional consumer; visuals bounded |
| `braemon/src/pages/Diagnostics.jsx` | unchanged | U1 functional consumer; visuals bounded |
| `braemon/src/pages/Documents.jsx` | modified | U1 functional consumer; visuals bounded |
| `braemon/src/pages/Home.jsx` | modified | U1 functional consumer; visuals bounded |
| `braemon/src/pages/Memories.jsx` | modified | U1 functional consumer; visuals bounded |
| `braemon/src/pages/RetrievalLogs.jsx` | added | U1 functional consumer; visuals bounded |
| `braemon/vite.config.js` | unchanged | U1 functional consumer; visuals bounded |
| `chainlit.md` | modified | D1 source/config/workflow claim |
| `docs/ARCHITECTURE.md` | modified | D1 source/config/workflow claim |
| `docs/DATA_LIFECYCLE.md` | modified | D1 source/config/workflow claim |
| `docs/DEMO_RUNBOOK.md` | modified | D1 source/config/workflow claim |
| `docs/EVALUATION.md` | modified | D1 source/config/workflow claim |
| `docs/FuturePlans.md` | added | D1 source/config/workflow claim |
| `docs/KNOWN_LIMITATIONS.md` | modified | D1 source/config/workflow claim |
| `docs/REFERENCE.md` | added | D1 source/config/workflow claim |
| `docs/TROUBLESHOOTING.md` | added | D1 source/config/workflow claim |
| `docs/mermaid-diagram-2026-07-15-015743.png` | added | X1 asset/doc/UI reference |
| `docs/mermaid-diagram-2026-07-15-021559.png` | added | X1 asset/doc/UI reference |
| `docs/one-turn-sequence.mmd` | added | D1 source/config/workflow claim |
| `docs/system-component-map.mmd` | added | D1 source/config/workflow claim |
| `evals/README.md` | added | D1 source/config/workflow claim |
| `evals/answer_heldout_analysis.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/document_qa/README.md` | modified | D1 source/config/workflow claim |
| `evals/document_qa/answer_generation.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/document_qa/compare_retrieval_modes.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/document_qa/compare_topk_curves.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/document_qa/datasets/squad_style_sample.jsonl` | unchanged | I1 runner/schema/manifest consumer |
| `evals/document_qa/datasets/squad_subset.jsonl` | unchanged | I1 runner/schema/manifest consumer |
| `evals/document_qa/diagnose_dataset.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/document_qa/langchain_baseline.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/document_qa/metrics.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/document_qa/prepare_nq_subset.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/document_qa/prepare_squad_subset.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/document_qa/ragas_export.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/document_qa/run_document_qa_eval.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/document_qa/run_ragas_eval.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/e2e_scenarios/README.md` | unchanged | D1 source/config/workflow claim |
| `evals/e2e_scenarios/__init__.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/e2e_scenarios/datasets/e2e_scenarios.jsonl` | unchanged | I1 runner/schema/manifest consumer |
| `evals/e2e_scenarios/run_e2e_scenarios.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/generated_answer/README.md` | unchanged | D1 source/config/workflow claim |
| `evals/generated_answer/__init__.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/generated_answer/datasets/generated_answer_sample.jsonl` | unchanged | I1 runner/schema/manifest consumer |
| `evals/generated_answer/run_generated_answer_eval.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_adapter/README.md` | unchanged | D1 source/config/workflow claim |
| `evals/longmemeval_adapter/__init__.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_adapter/fixtures/tiny_longmemeval_sample.jsonl` | unchanged | C1 |
| `evals/longmemeval_adapter/loader.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_adapter/run_longmemeval_adapter.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_adapter/runner.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_adapter/schema.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_adapter/scoring.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_adapter/span_retriever.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_answer_eval.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/README.md` | added | D1 source/config/workflow claim |
| `evals/mab_answer_eval/__init__.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/__main__.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/artifacts.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/judge.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/manifest.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/metrics.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/runner.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/schemas.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/manifests/longmemeval_answer_heldout_v1.yaml` | unchanged | I1 runner/schema/manifest consumer |
| `evals/manifests/mab_answer_heldout_v1.yaml` | unchanged | I1 runner/schema/manifest consumer |
| `evals/manifests/mab_answer_judge_calibration_v1.yaml` | unchanged | I1 runner/schema/manifest consumer |
| `evals/manifests/mab_answer_smoke_v1.yaml` | unchanged | I1 runner/schema/manifest consumer |
| `evals/manifests/mab_context_pipeline_targeted_v1.json` | unchanged | I1 runner/schema/manifest consumer |
| `evals/manifests/mab_four_case_forensic_validation_v1.json` | unchanged | I1 runner/schema/manifest consumer |
| `evals/manifests/mab_post_fix_targeted_v1.json` | unchanged | I1 runner/schema/manifest consumer |
| `evals/memory_agent_bench/README.md` | added | D1 source/config/workflow claim |
| `evals/memory_agent_bench/__init__.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/adapter.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/fixtures/tiny_sample.jsonl` | unchanged | C1 |
| `evals/memory_agent_bench/loader.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/metrics.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/raw_replay.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/run_memory_agent_bench.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/runner.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/schemas.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/selected_suite.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/selection.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/multi_source_retrieval/README.md` | unchanged | D1 source/config/workflow claim |
| `evals/multi_source_retrieval/__init__.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/multi_source_retrieval/datasets/source_selection_sample.jsonl` | unchanged | I1 runner/schema/manifest consumer |
| `evals/multi_source_retrieval/run_multi_source_retrieval_eval.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/product_behavior/README.md` | unchanged | D1 source/config/workflow claim |
| `evals/product_behavior/__init__.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/product_behavior/cases/documents.yaml` | unchanged | C1 |
| `evals/product_behavior/cases/failures.yaml` | unchanged | C1 |
| `evals/product_behavior/cases/lifecycle.yaml` | unchanged | C1 |
| `evals/product_behavior/cases/navigation.yaml` | unchanged | C1 |
| `evals/product_behavior/cases/persistence.yaml` | unchanged | C1 |
| `evals/product_behavior/loader.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/product_behavior/models.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/product_behavior/oracle.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/product_behavior/report.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/product_behavior/runner.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/structured_memory/README.md` | unchanged | D1 source/config/workflow claim |
| `evals/structured_memory/__init__.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/structured_memory/datasets/cross_chat_sample.jsonl` | unchanged | I1 runner/schema/manifest consumer |
| `evals/structured_memory/datasets/lifecycle_sample.jsonl` | unchanged | I1 runner/schema/manifest consumer |
| `evals/structured_memory/metrics.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/structured_memory/run_structured_memory_eval.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/test_short_term_memory.py` | unchanged | T1 stable TS + current dependencies |
| `evals/typed_memory_e2e/README.md` | added | D1 source/config/workflow claim |
| `evals/typed_memory_e2e/__init__.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/typed_memory_e2e/cases.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/typed_memory_e2e/run_typed_memory_e2e.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/typed_memory_e2e/runner.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `evals/typed_memory_e2e/schemas.py` | unchanged | E1 test/runner/supplied-data responsibility |
| `local_settings.example.py` | unchanged | C1 |
| `public/product-navigation.js` | modified | U1/S3 native window events/Inspector/log |
| `pyproject.toml` | modified | C1 |
| `requirements.txt` | removed | B1 historical launch/manual probe |
| `run.sh` | added | O1 startup/process/log configuration |
| `scripts/.doc.md` | added | D1 source/config/workflow claim |
| `scripts/eval_memory.py` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/final_eval_paths.sh` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/index_document_file.py` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/inspect_document_memory.py` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/inspect_eval_run.sh` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/inspect_long_term_memory.py` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/inspect_mab_context_case.py` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/inspect_raw_message_span.py` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/lib/load_eval_env.sh` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/rebuild_long_term_memory_index.py` | modified | O1 diagnostic/eval/rebuild operator |
| `scripts/rebuild_previous_chat_gists.py` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/run_final_52.sh` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/run_final_52_and_judge.sh` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/run_final_judge.sh` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/run_mab_post_fix_targeted.sh` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/token_monitor.py` | added | O1 diagnostic/eval/rebuild operator |
| `scripts/validate_final_answer_run.py` | unchanged | O1 diagnostic/eval/rebuild operator |
| `scripts/verify_natural_long_term_memory_flow.py` | unchanged | O1 diagnostic/eval/rebuild operator |
| `src/.doc.md` | added | D1 named source-owner functional claims |
| `src/__init__.py` | unchanged | C1 package/export; transitive caller impact |
| `src/actions/.doc.md` | added | D1 named source-owner functional claims |
| `src/actions/__init__.py` | unchanged | C1 package/export; transitive caller impact |
| `src/actions/chat_end.py` | unchanged | S3 history/document/native lifecycle |
| `src/actions/chat_fork.py` | unchanged | S3 history/document/native lifecycle |
| `src/agents/.doc.md` | added | D1 named source-owner functional claims |
| `src/agents/__init__.py` | unchanged | C1 package/export; transitive caller impact |
| `src/agents/chat_agent.py` | unchanged | S2/S1 typed contract/thin agent; callers traced |
| `src/agents/context_builder_agent.py` | unchanged | S2/S1 typed contract/thin agent; callers traced |
| `src/agents/context_manager_agent.py` | unchanged | S2 typed retrieval/ranking/context/answer |
| `src/agents/coordinator_agent.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/agents/document_ingestion_agent.py` | modified | S3 history/document/native lifecycle |
| `src/agents/short_term_memory_agent.py` | unchanged | S2/S1 typed contract/thin agent; callers traced |
| `src/api_routes.py` | modified | S2/S1 typed contract/thin agent; callers traced |
| `src/chainlit_data_layer.py` | unchanged | S3 history/document/native lifecycle |
| `src/chat_service.py` | modified | S0/S1/S3 config/composition/provider |
| `src/config.py` | modified | S0/S1/S3 config/composition/provider |
| `src/connection_guard.py` | added | S0/S1/S3 config/composition/provider |
| `src/context/.doc.md` | added | D1 named source-owner functional claims |
| `src/context/__init__.py` | unchanged | C1 package/export; transitive caller impact |
| `src/context/context_budget_allocator.py` | unchanged | S2 typed retrieval/ranking/context/answer |
| `src/context/context_builder.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/context/context_comparator.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/context/dynamic_budget.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/context/evidence_selector.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/context/model_profile.py` | unchanged | S2 typed retrieval/ranking/context/answer |
| `src/context/prompt_messages.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/context/token_estimator.py` | unchanged | S2 typed retrieval/ranking/context/answer |
| `src/core/.doc.md` | added | D1 named source-owner functional claims |
| `src/core/__init__.py` | unchanged | C1 package/export; transitive caller impact |
| `src/core/contracts.py` | unchanged | S2/S1 typed contract/thin agent; callers traced |
| `src/database.py` | modified | S1 SQL/vec/extraction/lifecycle consumers |
| `src/documents/.doc.md` | added | D1 named source-owner functional claims |
| `src/documents/__init__.py` | unchanged | C1 package/export; transitive caller impact |
| `src/documents/inspection.py` | modified | S3 history/document/native lifecycle |
| `src/documents/loaders.py` | modified | S3 history/document/native lifecycle |
| `src/documents/registry.py` | unchanged | S3 history/document/native lifecycle |
| `src/documents/splitters.py` | modified | S3 history/document/native lifecycle |
| `src/inspection/.doc.md` | added | D1 named source-owner functional claims |
| `src/inspection/__init__.py` | unchanged | C1 package/export; transitive caller impact |
| `src/inspection/answer_inspector.py` | unchanged | S3 history/document/native lifecycle |
| `src/lifecycle/.doc.md` | added | D1 named source-owner functional claims |
| `src/lifecycle/operation_guard.py` | unchanged | S3 history/document/native lifecycle |
| `src/memory/.doc.md` | added | D1 named source-owner functional claims |
| `src/memory/__init__.py` | unchanged | C1 package/export; transitive caller impact |
| `src/memory/chat_gist_summarizer.py` | unchanged | S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/constants.py` | modified | S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/langmem_structured.py` | modified | S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/long_term_store.py` | modified | S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/long_term_vector_index.py` | modified | S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/memory_trace.py` | unchanged | S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/previous_chat_gist.py` | modified | S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/short_term.py` | modified | S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/structured_memory_vector_sync.py` | modified | S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/structured_state.py` | modified | S1 SQL/vec/extraction/lifecycle consumers |
| `src/model_wrapper.py` | modified | S0/S1/S3 config/composition/provider |
| `src/orchestration/.doc.md` | added | D1 named source-owner functional claims |
| `src/orchestration/__init__.py` | unchanged | C1 package/export; transitive caller impact |
| `src/orchestration/demo_orchestration.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/orchestration/langgraph_memory_pipeline.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/provider_settings.py` | added | S0/S1/S3 config/composition/provider |
| `src/retrieval/.doc.md` | added | D1 named source-owner functional claims |
| `src/retrieval/__init__.py` | unchanged | C1 package/export; transitive caller impact |
| `src/retrieval/cross_encoder_reranker.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/retrieval/current_chat_gist_retriever.py` | unchanged | S2 typed retrieval/ranking/context/answer |
| `src/retrieval/current_chat_span_retriever.py` | unchanged | S2 typed retrieval/ranking/context/answer |
| `src/retrieval/gist_raw_span_expander.py` | unchanged | S2 typed retrieval/ranking/context/answer |
| `src/retrieval/langchain_chroma_retriever.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/retrieval/previous_chat_gist_retriever.py` | unchanged | S2 typed retrieval/ranking/context/answer |
| `src/retrieval/raw_message_span_retriever.py` | unchanged | S2 typed retrieval/ranking/context/answer |
| `src/retrieval/recent_messages_retriever.py` | unchanged | S2 typed retrieval/ranking/context/answer |
| `src/retrieval/reranker.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/retrieval/retriever_dispatcher.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/retrieval/structured_memory_retriever.py` | modified | S1 SQL/vec/extraction/lifecycle consumers |
| `src/routing/.doc.md` | added | D1 named source-owner functional claims |
| `src/routing/__init__.py` | unchanged | C1 package/export; transitive caller impact |
| `src/routing/query_analyzer.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/routing/retrieval_query.py` | unchanged | S2 typed retrieval/ranking/context/answer |
| `src/routing/route_planner.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/routing/routing_agent.py` | modified | S2 typed retrieval/ranking/context/answer |
| `src/routing/semantic_contracts.py` | unchanged | S2 typed retrieval/ranking/context/answer |
| `src/routing/semantic_router.py` | unchanged | S2 typed retrieval/ranking/context/answer |
| `src/settings.py` | modified | S0/S1/S3 config/composition/provider |
| `src/ui/design.md` | unchanged | D1 source/config/workflow claim |
| `startup.py` | added | O1 startup/process/log configuration |
| `test_upload.py` | removed | B1 historical launch/manual probe |
| `test_upload_real.py` | removed | B1 historical launch/manual probe |
| `tests/e2e/conftest.py` | unchanged | T1 stable TS + current dependencies |
| `tests/e2e/product_behavior_chainlit_app.py` | modified | T1 stable TS + current dependencies |
| `tests/e2e/test_product_behavior_browser.py` | unchanged | T1 stable TS + current dependencies |
| `tests/fixtures/docs/sample_report.txt` | unchanged | T1 stable TS + current dependencies |
| `tests/product_behavior/__init__.py` | unchanged | T1 stable TS + current dependencies |
| `tests/product_behavior/test_inventory.py` | unchanged | T1 stable TS + current dependencies |
| `tests/product_behavior/test_runner.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_answer_inspector.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_answer_policy_prompts.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_architecture_layers.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_backend.py` | modified | T1 stable TS + current dependencies |
| `tests/test_chainlit_chat_actions.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_chainlit_data_layer.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_chainlit_memory_trace_helpers.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_chat_end_action.py` | modified | T1 stable TS + current dependencies |
| `tests/test_chat_fork_action.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_chat_gist_summarizer.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_chat_lifecycle.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_chat_service_file_uploads.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_chroma_document_store.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_context_builder.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_context_comparator.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_context_manager_agent.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_coordinator_agent.py` | added | T1 stable TS + current dependencies |
| `tests/test_current_chat_span_retriever.py` | modified | T1 stable TS + current dependencies |
| `tests/test_direct_raw_retrieval.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_document_ingestion_agent.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_document_inspection.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_document_loaders.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_document_memory.py` | modified | T1 stable TS + current dependencies |
| `tests/test_document_product_lifecycle.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_document_qa_answer_generation.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_document_qa_compare.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_document_qa_diagnostics.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_document_qa_langchain_baseline.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_document_qa_metrics.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_document_qa_prepare.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_document_qa_prepare_nq.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_document_qa_ragas_export.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_document_qa_topk_curves.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_dynamic_memory_budget.py` | modified | T1 stable TS + current dependencies |
| `tests/test_e2e_scenarios.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_evidence_constrained_selector.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_final_eval_wrappers.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_generated_answer_eval.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_gist_memory_infrastructure.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_gist_processing_state.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_gist_raw_span_expansion.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_langchain_chroma_retriever.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_langgraph_demo_regression.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_langgraph_memory_pipeline.py` | modified | T1 stable TS + current dependencies |
| `tests/test_langmem_structured_memory.py` | modified | T1 stable TS + current dependencies |
| `tests/test_long_term_memory_vector_retrieval.py` | modified | T1 stable TS + current dependencies |
| `tests/test_long_term_store.py` | modified | T1 stable TS + current dependencies |
| `tests/test_longmemeval_adapter.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_longmemeval_answer_eval.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_mab_answer_eval.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_memory_agent_bench_adapter.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_memory_consolidation.py` | added | T1 stable TS + current dependencies |
| `tests/test_memory_context_acceptance.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_memory_reranker.py` | modified | T1 stable TS + current dependencies |
| `tests/test_memory_trace.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_model_token_accounting.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_multi_source_retrieval_eval.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_orchestration_demo_modes.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_previous_chat_gist_generation.py` | modified | T1 stable TS + current dependencies |
| `tests/test_product_failure_atomicity.py` | modified | T1 stable TS + current dependencies |
| `tests/test_product_navigation_asset.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_prompt_messages.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_provider_settings.py` | modified | T1 stable TS + current dependencies |
| `tests/test_raw_span_anchor_truncation.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_retrieval_query_simplification.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_routing_agent.py` | modified | T1 stable TS + current dependencies |
| `tests/test_semantic_router.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_semantic_router_v2_validation.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_short_term_memory_scheduling.py` | modified | T1 stable TS + current dependencies |
| `tests/test_socket.cjs` | unchanged | T1 stable TS + current dependencies |
| `tests/test_socket.js` | unchanged | T1 stable TS + current dependencies |
| `tests/test_socket_2.js` | unchanged | T1 stable TS + current dependencies |
| `tests/test_structured_memory_eval.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_structured_memory_vector_sync.py` | modified | T1 stable TS + current dependencies |
| `tests/test_targeted_eval_wrapper.py` | unchanged | T1 stable TS + current dependencies |
| `tests/test_typed_memory_e2e_benchmark.py` | unchanged | T1 stable TS + current dependencies |
| `uv.lock` | modified | C1 |

## 3. Concrete material documentation discrepancies

| Exact document paths | Source counterevidence and disposition |
|---|---|
| README.md;AGENTS.md | Native/React/sqlite-vec scope largely aligns; achievements are claims, not acceptance. Full End flush and primary UI/native Inspector parity not guaranteed. Reported48/50/heldout outcomes historical, not this run. |
| docs/DATA_LIFECYCLE.md;docs/DEMO_RUNBOOK.md | Normal rejected batch can still end inactive. Intentional global Ready fallback narrows unconditional chat-scope. Env agentic options do not universally override canonical AppConfig. Requested native/authoritative LangGraph expectation conflicts. |
| docs/KNOWN_LIMITATIONS.md;docs/REFERENCE.md | Structured Chroma dir/collection obsolete; unknown4096 conditional on no app cap. document_summaries table claim differs summary_text field. Env tables/memory deletion/readiness claims need actual owner policy. |
| docs/TROUBLESHOOTING.md | Structured Chroma cleanup advice obsolete; documented rebuild currently invalid syntax/API. python app.py not Chainlit launch. No destructive advice executed. |
| docs/ARCHITECTURE.md;docs/one-turn-sequence.mmd;docs/system-component-map.mmd | Structured-vector Chroma edge obsolete. Inline memory precedes result/service inspection. Coordinator→EndAction and RoutingAgent→SemanticRouter direct delegation false; comparator shape distinct orchestration identity overlap. Simplified diagrams omit neighbor/log/frontend/error paths. |
| docs/FuturePlans.md | Workspaces/tags/Obsidian/config UI proposals; no current capability requirement, implementation or approval inferred. |
| src/.doc.md | Universal env dominance/no downstream getenv false. New provider_settings responsibility separate from canonical settings. |
| src/actions/.doc.md;src/lifecycle/.doc.md;src/documents/.doc.md;src/inspection/.doc.md | REST End bypasses Action; upload claim belongs scoped service. PDF paragraph claim conflicts normalization. Summary optional; native bounded inspection differs React trace/raw log. |
| src/agents/.doc.md | Retrieval errors do not universally skip LLM (RV003). Logging after optional graph, legacy can generate, document cap49152 not32K, limited exception catch not all memory errors. |
| src/context/.doc.md | Allocator before planner; overlap intersection/min and inclusive threshold, not Jaccard strict>. Parent ID on raw child; required evidence may be dropped in final overflow. |
| src/core/.doc.md;src/memory/.doc.md | Core typed contracts retained; extraction source attribution not lexical proof, TTL helper not wired, SQL/vec/cache/progress not atomic. No automatic expiry/full finalization guarantee. |
| src/orchestration/.doc.md | Wrapper semantic default differs bare factory; graph no explicit write node not I-O guarantee. Graph error→native differs validation→legacy. Always-safe native claim unsupported. |
| src/retrieval/.doc.md;src/routing/.doc.md | Startup hybrid !=pure CE; DOCUMENT_TOP_K not enforced retrieval count. Registration !=activation; neighbor can initialize even pass-through. New enabled_sources not document-only; graph source-presence evidence enforcement exists. |
| scripts/.doc.md | Read-only inspector label ignores Database initialization; malformed/obsolete long-term Chroma rebuild; final52 answer benchmarks not ProductBehavior50. All-help/safe/stopped-app absolutes unsupported. |
| braemon/.doc.md;braemon/README.md | Documents upload UI claim stale, SDK chat upload retained. Native product-state/Inspector distinct React dropdown. Smoke/chat checks narrower than advertised lifecycle. |
| evals/README.md;evals/document_qa/README.md;evals/mab_answer_eval/README.md;evals/memory_agent_bench/README.md;evals/typed_memory_e2e/README.md | Keep mock/oracle/full-context/raw-replay/roleless distinctions; no-LLM not no guard/embedding I-O. Example paths/flags and history metrics not verified execution; all benchmark contents excluded. |
| chainlit.md | Native welcome/product copy, not authoritative current React/default/verification record. |

## 4. Exclusions and remaining depth

Coordinator manifest separately enumerates audit-metadata (22 rows), immutable historical snapshot (23), runtime/generated (5). Those paths are not assessor-owned product edits. Preserve archived package byte-for-byte; history relative source links require old checkout. Runtime/generated exclusions include data/chatbot.db.old, data/chroma_db/chroma.sqlite3, data/database.sqlite3 and removed report JSON; no contents read. Asset4 rows above metadata only;14 input rows schema/consumer only. Secrets/private local settings, conversations/uploads, stores, private recovery payloads, vendor/cache and external Pi sessions not read.

No blanket syntax-only semantic review claim. Functional source/prose and test setup/assertion coverage is bounded as recorded; full external framework/provider/embedding/browser behavior, every regex/metric/CLI flag, cosmetic rendering, benchmark quality and private contents are not certified. This ledger reconciles342named paths; it does not make every branch runtime verified.
