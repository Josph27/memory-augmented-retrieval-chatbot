# Coverage ledger — finalized actual-checkout revalidation

TASK-11,2026-10-27. Old tmp-audit c3ffee2 plus28verified dirty/untracked working files; assessed current source1cf4c55. [Machine manifest](coverage-manifest.json) records exact source hashes, import connectivity and per-path assessment evidence. [Static assessment](static-assessment.md) defines depth/limits; [file assessment](file-assessments.md) gives semantic groups.

**342 relevant union paths reconciled:324 product source/config/docs/test paths,14 evaluation inputs,4assets.** Four product paths are already absent on main, leaving338current relevant paths. Runtime/generated contents, audit metadata and immutable history have explicit separate scope states. Unchanged files were rechecked for changed consumers/configuration; hash equality is not a no-effect claim.

| Scope | Change | Files |
|---|---|---|
| asset-metadata | added | 2 |
| asset-metadata | unchanged | 2 |
| audit-metadata | added | 3 |
| audit-metadata | modified | 12 |
| audit-metadata | removed | 7 |
| evaluation-input-contract | unchanged | 14 |
| immutable-historical-snapshot | added | 23 |
| product-source-config-doc-test | added | 35 |
| product-source-config-doc-test | modified | 78 |
| product-source-config-doc-test | removed | 4 |
| product-source-config-doc-test | unchanged | 207 |
| runtime-or-generated-excluded | added | 1 |
| runtime-or-generated-excluded | content-excluded | 2 |
| runtime-or-generated-excluded | removed | 2 |

## Every-file accounting

Source/import detection is static navigation only; dynamic entry/CLI/config/JS/asset responsibility is reconciled in the assessment groups. Public diagrams/assets receive metadata/reference assessment, not rendered-image correctness. No private runtime content read.

| Path | Old→current | Assessment state | Evidence / depth |
|---|---|---|---|
| `.chainlit/config.toml` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 27: C1 |
| `.dev/start-dev.sh` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 28: O1 startup/process/log configuration |
| `.dev/stop-dev.sh` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 29: O1 startup/process/log configuration |
| `.env.example` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 30: C1 |
| `.gitignore` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 31: C1 |
| `.python-version` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 32: C1 |
| `AGENTS.md` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 33: D1 source/config/workflow claim |
| `Dockerfile` | removed | baseline-absence-reconciled | [file assessment](file-assessments.md) line 34: B1 historical launch/manual probe |
| `LICENSE` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 35: C1 |
| `README.md` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 36: D1 source/config/workflow claim |
| `app.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 37: S0/S3/U1 actual callback/main/error/preload |
| `braemon/.doc.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 38: D1 source/config/workflow claim |
| `braemon/.gitignore` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 39: C1 |
| `braemon/.oxlintrc.json` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 40: C1 |
| `braemon/README.md` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 41: D1 source/config/workflow claim |
| `braemon/console-forward-plugin.mjs` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 42: U1 functional consumer; visuals bounded |
| `braemon/e2e/chat-messages.test.mjs` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 43: U1 functional consumer; visuals bounded |
| `braemon/e2e/smoke.test.mjs` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 44: U1 functional consumer; visuals bounded |
| `braemon/index.html` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 45: U1 functional consumer; visuals bounded |
| `braemon/package-lock.json` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 46: C1 |
| `braemon/package.json` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 47: C1 |
| `braemon/public/favicon.svg` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 48: X1 asset/doc/UI reference |
| `braemon/public/icons.svg` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 49: X1 asset/doc/UI reference |
| `braemon/src/App.jsx` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 50: U1 functional consumer; visuals bounded |
| `braemon/src/api.js` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 51: U1 functional consumer; visuals bounded |
| `braemon/src/components/ChainlitChat.jsx` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 52: U1 functional consumer; visuals bounded |
| `braemon/src/components/ChainlitChat.jsx.orig` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 53: X1 unimported patch artifact |
| `braemon/src/components/ChainlitChat.jsx.rej` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 54: X1 unimported patch artifact |
| `braemon/src/components/ChatActions.jsx` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 55: U1 functional consumer; visuals bounded |
| `braemon/src/components/ErrorBoundary.jsx` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 56: U1 functional consumer; visuals bounded |
| `braemon/src/components/Layout.jsx` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 57: U1 functional consumer; visuals bounded |
| `braemon/src/components/ModelLoadingScreen.jsx` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 58: U1 functional consumer; visuals bounded |
| `braemon/src/index.css` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 59: U1 functional consumer; visuals bounded |
| `braemon/src/main.jsx` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 60: U1 functional consumer; visuals bounded |
| `braemon/src/pages/Chat.jsx` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 61: U1 functional consumer; visuals bounded |
| `braemon/src/pages/Chats.jsx` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 62: U1 functional consumer; visuals bounded |
| `braemon/src/pages/Diagnostics.jsx` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 63: U1 functional consumer; visuals bounded |
| `braemon/src/pages/Documents.jsx` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 64: U1 functional consumer; visuals bounded |
| `braemon/src/pages/Home.jsx` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 65: U1 functional consumer; visuals bounded |
| `braemon/src/pages/Memories.jsx` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 66: U1 functional consumer; visuals bounded |
| `braemon/src/pages/RetrievalLogs.jsx` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 67: U1 functional consumer; visuals bounded |
| `braemon/vite.config.js` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 68: U1 functional consumer; visuals bounded |
| `chainlit.md` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 69: D1 source/config/workflow claim |
| `data/chatbot.db.old` | added | excluded-private-runtime-or-generated-content | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `data/chroma_db/chroma.sqlite3` | content-excluded | excluded-private-runtime-or-generated-content | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `data/database.sqlite3` | content-excluded | excluded-private-runtime-or-generated-content | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/ARCHITECTURE.md` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 70: D1 source/config/workflow claim |
| `docs/DATA_LIFECYCLE.md` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 71: D1 source/config/workflow claim |
| `docs/DEMO_RUNBOOK.md` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 72: D1 source/config/workflow claim |
| `docs/EVALUATION.md` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 73: D1 source/config/workflow claim |
| `docs/FuturePlans.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 74: D1 source/config/workflow claim |
| `docs/KNOWN_LIMITATIONS.md` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 75: D1 source/config/workflow claim |
| `docs/REFERENCE.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 76: D1 source/config/workflow claim |
| `docs/TROUBLESHOOTING.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 77: D1 source/config/workflow claim |
| `docs/audit/README.md` | modified | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/bug-backlog.md` | modified | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/checks/run_migration_checks.py` | added | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/cleanup-plan.md` | modified | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/decisions.md` | modified | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/AGENTS.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/ARCHIVE.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/README.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/README.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/bug-backlog.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/cleanup-plan.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/decisions.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/reports/01-initial-audit.reconstructed.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/reports/02-coverage-audit.reconstructed.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/reports/03-test-suite-independent-review.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/reports/04-test-suite-lifecycle-review.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/reports/05-test-suite-deterministic-review.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/reports/README.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/reports/current-source-fingerprints.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/reports/provenance.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/test-suite-audit.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/test-suite-inventory.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/test-suite-symbols.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/docs/audit/workflow-map.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/findings.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/progress.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/snapshot-sha256.json` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/history/tmp-audit/task_plan.md` | added | preserved-immutable-evidence | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/main-baseline-impact.md` | added | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/migration.md` | added | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/reports/01-initial-audit.reconstructed.md` | removed | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/reports/02-coverage-audit.reconstructed.md` | removed | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/reports/03-test-suite-independent-review.md` | removed | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/reports/04-test-suite-lifecycle-review.md` | removed | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/reports/05-test-suite-deterministic-review.md` | removed | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/reports/README.md` | modified | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/reports/current-source-fingerprints.md` | removed | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/reports/provenance.md` | removed | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/test-suite-audit.md` | modified | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/test-suite-inventory.md` | modified | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/test-suite-symbols.md` | modified | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/audit/workflow-map.md` | modified | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `docs/mermaid-diagram-2026-07-15-015743.png` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 78: X1 asset/doc/UI reference |
| `docs/mermaid-diagram-2026-07-15-021559.png` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 79: X1 asset/doc/UI reference |
| `docs/one-turn-sequence.mmd` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 80: D1 source/config/workflow claim |
| `docs/system-component-map.mmd` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 81: D1 source/config/workflow claim |
| `evals/README.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 82: D1 source/config/workflow claim |
| `evals/answer_heldout_analysis.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 83: E1 test/runner/supplied-data responsibility |
| `evals/document_qa/README.md` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 84: D1 source/config/workflow claim |
| `evals/document_qa/answer_generation.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 85: E1 test/runner/supplied-data responsibility |
| `evals/document_qa/compare_retrieval_modes.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 86: E1 test/runner/supplied-data responsibility |
| `evals/document_qa/compare_topk_curves.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 87: E1 test/runner/supplied-data responsibility |
| `evals/document_qa/datasets/squad_style_sample.jsonl` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 88: I1 runner/schema/manifest consumer |
| `evals/document_qa/datasets/squad_subset.jsonl` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 89: I1 runner/schema/manifest consumer |
| `evals/document_qa/diagnose_dataset.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 90: E1 test/runner/supplied-data responsibility |
| `evals/document_qa/langchain_baseline.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 91: E1 test/runner/supplied-data responsibility |
| `evals/document_qa/metrics.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 92: E1 test/runner/supplied-data responsibility |
| `evals/document_qa/prepare_nq_subset.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 93: E1 test/runner/supplied-data responsibility |
| `evals/document_qa/prepare_squad_subset.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 94: E1 test/runner/supplied-data responsibility |
| `evals/document_qa/ragas_export.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 95: E1 test/runner/supplied-data responsibility |
| `evals/document_qa/run_document_qa_eval.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 96: E1 test/runner/supplied-data responsibility |
| `evals/document_qa/run_ragas_eval.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 97: E1 test/runner/supplied-data responsibility |
| `evals/e2e_scenarios/README.md` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 98: D1 source/config/workflow claim |
| `evals/e2e_scenarios/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 99: E1 test/runner/supplied-data responsibility |
| `evals/e2e_scenarios/datasets/e2e_scenarios.jsonl` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 100: I1 runner/schema/manifest consumer |
| `evals/e2e_scenarios/run_e2e_scenarios.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 101: E1 test/runner/supplied-data responsibility |
| `evals/generated_answer/README.md` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 102: D1 source/config/workflow claim |
| `evals/generated_answer/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 103: E1 test/runner/supplied-data responsibility |
| `evals/generated_answer/datasets/generated_answer_sample.jsonl` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 104: I1 runner/schema/manifest consumer |
| `evals/generated_answer/run_generated_answer_eval.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 105: E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_adapter/README.md` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 106: D1 source/config/workflow claim |
| `evals/longmemeval_adapter/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 107: E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_adapter/fixtures/tiny_longmemeval_sample.jsonl` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 108: C1 |
| `evals/longmemeval_adapter/loader.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 109: E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_adapter/run_longmemeval_adapter.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 110: E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_adapter/runner.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 111: E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_adapter/schema.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 112: E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_adapter/scoring.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 113: E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_adapter/span_retriever.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 114: E1 test/runner/supplied-data responsibility |
| `evals/longmemeval_answer_eval.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 115: E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/README.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 116: D1 source/config/workflow claim |
| `evals/mab_answer_eval/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 117: E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/__main__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 118: E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/artifacts.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 119: E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/judge.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 120: E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/manifest.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 121: E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/metrics.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 122: E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/runner.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 123: E1 test/runner/supplied-data responsibility |
| `evals/mab_answer_eval/schemas.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 124: E1 test/runner/supplied-data responsibility |
| `evals/manifests/longmemeval_answer_heldout_v1.yaml` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 125: I1 runner/schema/manifest consumer |
| `evals/manifests/mab_answer_heldout_v1.yaml` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 126: I1 runner/schema/manifest consumer |
| `evals/manifests/mab_answer_judge_calibration_v1.yaml` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 127: I1 runner/schema/manifest consumer |
| `evals/manifests/mab_answer_smoke_v1.yaml` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 128: I1 runner/schema/manifest consumer |
| `evals/manifests/mab_context_pipeline_targeted_v1.json` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 129: I1 runner/schema/manifest consumer |
| `evals/manifests/mab_four_case_forensic_validation_v1.json` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 130: I1 runner/schema/manifest consumer |
| `evals/manifests/mab_post_fix_targeted_v1.json` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 131: I1 runner/schema/manifest consumer |
| `evals/memory_agent_bench/README.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 132: D1 source/config/workflow claim |
| `evals/memory_agent_bench/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 133: E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/adapter.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 134: E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/fixtures/tiny_sample.jsonl` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 135: C1 |
| `evals/memory_agent_bench/loader.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 136: E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/metrics.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 137: E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/raw_replay.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 138: E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/run_memory_agent_bench.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 139: E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/runner.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 140: E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/schemas.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 141: E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/selected_suite.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 142: E1 test/runner/supplied-data responsibility |
| `evals/memory_agent_bench/selection.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 143: E1 test/runner/supplied-data responsibility |
| `evals/multi_source_retrieval/README.md` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 144: D1 source/config/workflow claim |
| `evals/multi_source_retrieval/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 145: E1 test/runner/supplied-data responsibility |
| `evals/multi_source_retrieval/datasets/source_selection_sample.jsonl` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 146: I1 runner/schema/manifest consumer |
| `evals/multi_source_retrieval/run_multi_source_retrieval_eval.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 147: E1 test/runner/supplied-data responsibility |
| `evals/product_behavior/README.md` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 148: D1 source/config/workflow claim |
| `evals/product_behavior/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 149: E1 test/runner/supplied-data responsibility |
| `evals/product_behavior/cases/documents.yaml` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 150: C1 |
| `evals/product_behavior/cases/failures.yaml` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 151: C1 |
| `evals/product_behavior/cases/lifecycle.yaml` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 152: C1 |
| `evals/product_behavior/cases/navigation.yaml` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 153: C1 |
| `evals/product_behavior/cases/persistence.yaml` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 154: C1 |
| `evals/product_behavior/loader.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 155: E1 test/runner/supplied-data responsibility |
| `evals/product_behavior/models.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 156: E1 test/runner/supplied-data responsibility |
| `evals/product_behavior/oracle.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 157: E1 test/runner/supplied-data responsibility |
| `evals/product_behavior/report.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 158: E1 test/runner/supplied-data responsibility |
| `evals/product_behavior/runner.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 159: E1 test/runner/supplied-data responsibility |
| `evals/structured_memory/README.md` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 160: D1 source/config/workflow claim |
| `evals/structured_memory/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 161: E1 test/runner/supplied-data responsibility |
| `evals/structured_memory/datasets/cross_chat_sample.jsonl` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 162: I1 runner/schema/manifest consumer |
| `evals/structured_memory/datasets/lifecycle_sample.jsonl` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 163: I1 runner/schema/manifest consumer |
| `evals/structured_memory/metrics.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 164: E1 test/runner/supplied-data responsibility |
| `evals/structured_memory/run_structured_memory_eval.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 165: E1 test/runner/supplied-data responsibility |
| `evals/test_short_term_memory.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 166: T1 stable TS + current dependencies |
| `evals/typed_memory_e2e/README.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 167: D1 source/config/workflow claim |
| `evals/typed_memory_e2e/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 168: E1 test/runner/supplied-data responsibility |
| `evals/typed_memory_e2e/cases.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 169: E1 test/runner/supplied-data responsibility |
| `evals/typed_memory_e2e/run_typed_memory_e2e.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 170: E1 test/runner/supplied-data responsibility |
| `evals/typed_memory_e2e/runner.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 171: E1 test/runner/supplied-data responsibility |
| `evals/typed_memory_e2e/schemas.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 172: E1 test/runner/supplied-data responsibility |
| `findings.md` | modified | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `local_settings.example.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 173: C1 |
| `progress.md` | modified | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `public/product-navigation.js` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 174: U1/S3 native window events/Inspector/log |
| `pyproject.toml` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 175: C1 |
| `reports/e2e_scenario_model_report.json` | removed | excluded-private-runtime-or-generated-content | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `reports/generated_answer_model_report.json` | removed | excluded-private-runtime-or-generated-content | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `requirements.txt` | removed | baseline-absence-reconciled | [file assessment](file-assessments.md) line 176: B1 historical launch/manual probe |
| `run.sh` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 177: O1 startup/process/log configuration |
| `scripts/.doc.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 178: D1 source/config/workflow claim |
| `scripts/eval_memory.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 179: O1 diagnostic/eval/rebuild operator |
| `scripts/final_eval_paths.sh` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 180: O1 diagnostic/eval/rebuild operator |
| `scripts/index_document_file.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 181: O1 diagnostic/eval/rebuild operator |
| `scripts/inspect_document_memory.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 182: O1 diagnostic/eval/rebuild operator |
| `scripts/inspect_eval_run.sh` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 183: O1 diagnostic/eval/rebuild operator |
| `scripts/inspect_long_term_memory.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 184: O1 diagnostic/eval/rebuild operator |
| `scripts/inspect_mab_context_case.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 185: O1 diagnostic/eval/rebuild operator |
| `scripts/inspect_raw_message_span.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 186: O1 diagnostic/eval/rebuild operator |
| `scripts/lib/load_eval_env.sh` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 187: O1 diagnostic/eval/rebuild operator |
| `scripts/rebuild_long_term_memory_index.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 188: O1 diagnostic/eval/rebuild operator |
| `scripts/rebuild_previous_chat_gists.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 189: O1 diagnostic/eval/rebuild operator |
| `scripts/run_final_52.sh` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 190: O1 diagnostic/eval/rebuild operator |
| `scripts/run_final_52_and_judge.sh` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 191: O1 diagnostic/eval/rebuild operator |
| `scripts/run_final_judge.sh` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 192: O1 diagnostic/eval/rebuild operator |
| `scripts/run_mab_post_fix_targeted.sh` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 193: O1 diagnostic/eval/rebuild operator |
| `scripts/token_monitor.py` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 194: O1 diagnostic/eval/rebuild operator |
| `scripts/validate_final_answer_run.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 195: O1 diagnostic/eval/rebuild operator |
| `scripts/verify_natural_long_term_memory_flow.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 196: O1 diagnostic/eval/rebuild operator |
| `src/.doc.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 197: D1 named source-owner functional claims |
| `src/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 198: C1 package/export; transitive caller impact |
| `src/actions/.doc.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 199: D1 named source-owner functional claims |
| `src/actions/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 200: C1 package/export; transitive caller impact |
| `src/actions/chat_end.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 201: S3 history/document/native lifecycle |
| `src/actions/chat_fork.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 202: S3 history/document/native lifecycle |
| `src/agents/.doc.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 203: D1 named source-owner functional claims |
| `src/agents/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 204: C1 package/export; transitive caller impact |
| `src/agents/chat_agent.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 205: S2/S1 typed contract/thin agent; callers traced |
| `src/agents/context_builder_agent.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 206: S2/S1 typed contract/thin agent; callers traced |
| `src/agents/context_manager_agent.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 207: S2 typed retrieval/ranking/context/answer |
| `src/agents/coordinator_agent.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 208: S2 typed retrieval/ranking/context/answer |
| `src/agents/document_ingestion_agent.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 209: S3 history/document/native lifecycle |
| `src/agents/short_term_memory_agent.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 210: S2/S1 typed contract/thin agent; callers traced |
| `src/api_routes.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 211: S2/S1 typed contract/thin agent; callers traced |
| `src/chainlit_data_layer.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 212: S3 history/document/native lifecycle |
| `src/chat_service.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 213: S0/S1/S3 config/composition/provider |
| `src/config.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 214: S0/S1/S3 config/composition/provider |
| `src/connection_guard.py` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 215: S0/S1/S3 config/composition/provider |
| `src/context/.doc.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 216: D1 named source-owner functional claims |
| `src/context/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 217: C1 package/export; transitive caller impact |
| `src/context/context_budget_allocator.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 218: S2 typed retrieval/ranking/context/answer |
| `src/context/context_builder.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 219: S2 typed retrieval/ranking/context/answer |
| `src/context/context_comparator.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 220: S2 typed retrieval/ranking/context/answer |
| `src/context/dynamic_budget.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 221: S2 typed retrieval/ranking/context/answer |
| `src/context/evidence_selector.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 222: S2 typed retrieval/ranking/context/answer |
| `src/context/model_profile.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 223: S2 typed retrieval/ranking/context/answer |
| `src/context/prompt_messages.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 224: S2 typed retrieval/ranking/context/answer |
| `src/context/token_estimator.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 225: S2 typed retrieval/ranking/context/answer |
| `src/core/.doc.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 226: D1 named source-owner functional claims |
| `src/core/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 227: C1 package/export; transitive caller impact |
| `src/core/contracts.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 228: S2/S1 typed contract/thin agent; callers traced |
| `src/database.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 229: S1 SQL/vec/extraction/lifecycle consumers |
| `src/documents/.doc.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 230: D1 named source-owner functional claims |
| `src/documents/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 231: C1 package/export; transitive caller impact |
| `src/documents/inspection.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 232: S3 history/document/native lifecycle |
| `src/documents/loaders.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 233: S3 history/document/native lifecycle |
| `src/documents/registry.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 234: S3 history/document/native lifecycle |
| `src/documents/splitters.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 235: S3 history/document/native lifecycle |
| `src/inspection/.doc.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 236: D1 named source-owner functional claims |
| `src/inspection/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 237: C1 package/export; transitive caller impact |
| `src/inspection/answer_inspector.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 238: S3 history/document/native lifecycle |
| `src/lifecycle/.doc.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 239: D1 named source-owner functional claims |
| `src/lifecycle/operation_guard.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 240: S3 history/document/native lifecycle |
| `src/memory/.doc.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 241: D1 named source-owner functional claims |
| `src/memory/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 242: C1 package/export; transitive caller impact |
| `src/memory/chat_gist_summarizer.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 243: S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/constants.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 244: S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/langmem_structured.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 245: S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/long_term_store.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 246: S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/long_term_vector_index.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 247: S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/memory_trace.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 248: S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/previous_chat_gist.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 249: S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/short_term.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 250: S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/structured_memory_vector_sync.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 251: S1 SQL/vec/extraction/lifecycle consumers |
| `src/memory/structured_state.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 252: S1 SQL/vec/extraction/lifecycle consumers |
| `src/model_wrapper.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 253: S0/S1/S3 config/composition/provider |
| `src/orchestration/.doc.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 254: D1 named source-owner functional claims |
| `src/orchestration/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 255: C1 package/export; transitive caller impact |
| `src/orchestration/demo_orchestration.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 256: S2 typed retrieval/ranking/context/answer |
| `src/orchestration/langgraph_memory_pipeline.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 257: S2 typed retrieval/ranking/context/answer |
| `src/provider_settings.py` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 258: S0/S1/S3 config/composition/provider |
| `src/retrieval/.doc.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 259: D1 named source-owner functional claims |
| `src/retrieval/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 260: C1 package/export; transitive caller impact |
| `src/retrieval/cross_encoder_reranker.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 261: S2 typed retrieval/ranking/context/answer |
| `src/retrieval/current_chat_gist_retriever.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 262: S2 typed retrieval/ranking/context/answer |
| `src/retrieval/current_chat_span_retriever.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 263: S2 typed retrieval/ranking/context/answer |
| `src/retrieval/gist_raw_span_expander.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 264: S2 typed retrieval/ranking/context/answer |
| `src/retrieval/langchain_chroma_retriever.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 265: S2 typed retrieval/ranking/context/answer |
| `src/retrieval/previous_chat_gist_retriever.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 266: S2 typed retrieval/ranking/context/answer |
| `src/retrieval/raw_message_span_retriever.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 267: S2 typed retrieval/ranking/context/answer |
| `src/retrieval/recent_messages_retriever.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 268: S2 typed retrieval/ranking/context/answer |
| `src/retrieval/reranker.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 269: S2 typed retrieval/ranking/context/answer |
| `src/retrieval/retriever_dispatcher.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 270: S2 typed retrieval/ranking/context/answer |
| `src/retrieval/structured_memory_retriever.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 271: S1 SQL/vec/extraction/lifecycle consumers |
| `src/routing/.doc.md` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 272: D1 named source-owner functional claims |
| `src/routing/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 273: C1 package/export; transitive caller impact |
| `src/routing/query_analyzer.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 274: S2 typed retrieval/ranking/context/answer |
| `src/routing/retrieval_query.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 275: S2 typed retrieval/ranking/context/answer |
| `src/routing/route_planner.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 276: S2 typed retrieval/ranking/context/answer |
| `src/routing/routing_agent.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 277: S2 typed retrieval/ranking/context/answer |
| `src/routing/semantic_contracts.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 278: S2 typed retrieval/ranking/context/answer |
| `src/routing/semantic_router.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 279: S2 typed retrieval/ranking/context/answer |
| `src/settings.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 280: S0/S1/S3 config/composition/provider |
| `src/ui/design.md` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 281: D1 source/config/workflow claim |
| `startup.py` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 282: O1 startup/process/log configuration |
| `task_plan.md` | modified | excluded-from-product-review-audit-metadata | Explicit scope exclusion; original history/private/runtime contents not treated as new implementation. |
| `test_upload.py` | removed | baseline-absence-reconciled | [file assessment](file-assessments.md) line 283: B1 historical launch/manual probe |
| `test_upload_real.py` | removed | baseline-absence-reconciled | [file assessment](file-assessments.md) line 284: B1 historical launch/manual probe |
| `tests/e2e/conftest.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 285: T1 stable TS + current dependencies |
| `tests/e2e/product_behavior_chainlit_app.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 286: T1 stable TS + current dependencies |
| `tests/e2e/test_product_behavior_browser.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 287: T1 stable TS + current dependencies |
| `tests/fixtures/docs/sample_report.txt` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 288: T1 stable TS + current dependencies |
| `tests/product_behavior/__init__.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 289: T1 stable TS + current dependencies |
| `tests/product_behavior/test_inventory.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 290: T1 stable TS + current dependencies |
| `tests/product_behavior/test_runner.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 291: T1 stable TS + current dependencies |
| `tests/test_answer_inspector.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 292: T1 stable TS + current dependencies |
| `tests/test_answer_policy_prompts.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 293: T1 stable TS + current dependencies |
| `tests/test_architecture_layers.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 294: T1 stable TS + current dependencies |
| `tests/test_backend.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 295: T1 stable TS + current dependencies |
| `tests/test_chainlit_chat_actions.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 296: T1 stable TS + current dependencies |
| `tests/test_chainlit_data_layer.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 297: T1 stable TS + current dependencies |
| `tests/test_chainlit_memory_trace_helpers.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 298: T1 stable TS + current dependencies |
| `tests/test_chat_end_action.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 299: T1 stable TS + current dependencies |
| `tests/test_chat_fork_action.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 300: T1 stable TS + current dependencies |
| `tests/test_chat_gist_summarizer.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 301: T1 stable TS + current dependencies |
| `tests/test_chat_lifecycle.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 302: T1 stable TS + current dependencies |
| `tests/test_chat_service_file_uploads.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 303: T1 stable TS + current dependencies |
| `tests/test_chroma_document_store.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 304: T1 stable TS + current dependencies |
| `tests/test_context_builder.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 305: T1 stable TS + current dependencies |
| `tests/test_context_comparator.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 306: T1 stable TS + current dependencies |
| `tests/test_context_manager_agent.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 307: T1 stable TS + current dependencies |
| `tests/test_coordinator_agent.py` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 308: T1 stable TS + current dependencies |
| `tests/test_current_chat_span_retriever.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 309: T1 stable TS + current dependencies |
| `tests/test_direct_raw_retrieval.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 310: T1 stable TS + current dependencies |
| `tests/test_document_ingestion_agent.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 311: T1 stable TS + current dependencies |
| `tests/test_document_inspection.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 312: T1 stable TS + current dependencies |
| `tests/test_document_loaders.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 313: T1 stable TS + current dependencies |
| `tests/test_document_memory.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 314: T1 stable TS + current dependencies |
| `tests/test_document_product_lifecycle.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 315: T1 stable TS + current dependencies |
| `tests/test_document_qa_answer_generation.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 316: T1 stable TS + current dependencies |
| `tests/test_document_qa_compare.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 317: T1 stable TS + current dependencies |
| `tests/test_document_qa_diagnostics.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 318: T1 stable TS + current dependencies |
| `tests/test_document_qa_langchain_baseline.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 319: T1 stable TS + current dependencies |
| `tests/test_document_qa_metrics.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 320: T1 stable TS + current dependencies |
| `tests/test_document_qa_prepare.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 321: T1 stable TS + current dependencies |
| `tests/test_document_qa_prepare_nq.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 322: T1 stable TS + current dependencies |
| `tests/test_document_qa_ragas_export.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 323: T1 stable TS + current dependencies |
| `tests/test_document_qa_topk_curves.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 324: T1 stable TS + current dependencies |
| `tests/test_dynamic_memory_budget.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 325: T1 stable TS + current dependencies |
| `tests/test_e2e_scenarios.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 326: T1 stable TS + current dependencies |
| `tests/test_evidence_constrained_selector.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 327: T1 stable TS + current dependencies |
| `tests/test_final_eval_wrappers.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 328: T1 stable TS + current dependencies |
| `tests/test_generated_answer_eval.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 329: T1 stable TS + current dependencies |
| `tests/test_gist_memory_infrastructure.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 330: T1 stable TS + current dependencies |
| `tests/test_gist_processing_state.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 331: T1 stable TS + current dependencies |
| `tests/test_gist_raw_span_expansion.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 332: T1 stable TS + current dependencies |
| `tests/test_langchain_chroma_retriever.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 333: T1 stable TS + current dependencies |
| `tests/test_langgraph_demo_regression.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 334: T1 stable TS + current dependencies |
| `tests/test_langgraph_memory_pipeline.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 335: T1 stable TS + current dependencies |
| `tests/test_langmem_structured_memory.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 336: T1 stable TS + current dependencies |
| `tests/test_long_term_memory_vector_retrieval.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 337: T1 stable TS + current dependencies |
| `tests/test_long_term_store.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 338: T1 stable TS + current dependencies |
| `tests/test_longmemeval_adapter.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 339: T1 stable TS + current dependencies |
| `tests/test_longmemeval_answer_eval.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 340: T1 stable TS + current dependencies |
| `tests/test_mab_answer_eval.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 341: T1 stable TS + current dependencies |
| `tests/test_memory_agent_bench_adapter.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 342: T1 stable TS + current dependencies |
| `tests/test_memory_consolidation.py` | added | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 343: T1 stable TS + current dependencies |
| `tests/test_memory_context_acceptance.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 344: T1 stable TS + current dependencies |
| `tests/test_memory_reranker.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 345: T1 stable TS + current dependencies |
| `tests/test_memory_trace.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 346: T1 stable TS + current dependencies |
| `tests/test_model_token_accounting.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 347: T1 stable TS + current dependencies |
| `tests/test_multi_source_retrieval_eval.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 348: T1 stable TS + current dependencies |
| `tests/test_orchestration_demo_modes.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 349: T1 stable TS + current dependencies |
| `tests/test_previous_chat_gist_generation.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 350: T1 stable TS + current dependencies |
| `tests/test_product_failure_atomicity.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 351: T1 stable TS + current dependencies |
| `tests/test_product_navigation_asset.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 352: T1 stable TS + current dependencies |
| `tests/test_prompt_messages.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 353: T1 stable TS + current dependencies |
| `tests/test_provider_settings.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 354: T1 stable TS + current dependencies |
| `tests/test_raw_span_anchor_truncation.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 355: T1 stable TS + current dependencies |
| `tests/test_retrieval_query_simplification.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 356: T1 stable TS + current dependencies |
| `tests/test_routing_agent.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 357: T1 stable TS + current dependencies |
| `tests/test_semantic_router.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 358: T1 stable TS + current dependencies |
| `tests/test_semantic_router_v2_validation.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 359: T1 stable TS + current dependencies |
| `tests/test_short_term_memory_scheduling.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 360: T1 stable TS + current dependencies |
| `tests/test_socket.cjs` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 361: T1 stable TS + current dependencies |
| `tests/test_socket.js` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 362: T1 stable TS + current dependencies |
| `tests/test_socket_2.js` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 363: T1 stable TS + current dependencies |
| `tests/test_structured_memory_eval.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 364: T1 stable TS + current dependencies |
| `tests/test_structured_memory_vector_sync.py` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 365: T1 stable TS + current dependencies |
| `tests/test_targeted_eval_wrapper.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 366: T1 stable TS + current dependencies |
| `tests/test_typed_memory_e2e_benchmark.py` | unchanged | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 367: T1 stable TS + current dependencies |
| `uv.lock` | modified | static-role-and-consumer-assessed | [file assessment](file-assessments.md) line 368: C1 |
