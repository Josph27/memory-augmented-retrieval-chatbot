# Main baseline impact: independent static review

**Historical migration-time triage.** Current conclusions and execution evidence are in [TASK11 revalidation](revalidation/static-assessment.md); that package supersedes this preliminary matrix where it differs.

2026-10-27; reviewer `main_baseline_impact`; main `2f56d93`. Read-only source comparison, no application imports, test execution or private data inspection. This is bounded migration triage, not a new exhaustive audit. **Supported** means static evidence remains; **Changed** means old evidence materially changed or is superseded. Neither means runtime confirmation or resolution. Original detailed evidence remains in [historical backlog](history/tmp-audit/docs/audit/bug-backlog.md) and [test assessment](history/tmp-audit/docs/audit/test-suite-audit.md).

## AUD findings

| ID | Current static status | Evidence / required revalidation |
|---|---|---|
| AUD-01 | Supported | `DocumentRegistry.resolve` still falls back to global Ready documents; `answer_inspector.serialize_candidate` retains association filtering. Scope/inspection mismatch remains. |
| AUD-02 | Supported, expanded | `api_routes.register_api_routes.end_chat` directly marks inactive. `app.end_chat_handler` now includes previous-chat gist finalizer and `ChatEndAction`. Recheck both frontends. |
| AUD-03 | Changed; concern supported | API hard delete still uses unnamespaced memory_id; activation endpoints bypass store sync. sqlite-vec, categories/namespaces and normalization changed; recheck cache/SQL/vector/relearning semantics. |
| AUD-04 | Changed; document concern supported | Document `similarity_search_with_score` plus unchanged `[0,1]` normalization remains suspect. Structured index now converts cosine distance with `max(0, 1-distance/2)`; reranking changed. Final ordering unverified. |
| AUD-05 | Supported, request integration changed | Unknown-model context fallback remains. `ModelWrapper.chat` has guards/timeouts but no explicit output-token limit. Provider/model limits separately unverified. |
| AUD-06 | Changed; policy-specific concern | Scheduled `update_memory_if_needed` retains oldest batches and `allow_noop=False`; agentic_each_turn consumes valid no-ops and uses latest units; chat_end_only skips online work. End failure behavior changed. Do not generalize starvation across policies. |
| AUD-07 | Supported; expanded | `app` constructs dirs/Database and eagerly invokes `chat_service_for_model` (embedding/cross-encoder preload). `AppConfig.load` takes most values directly from settings; env-only isolation insufficient. |
| AUD-08 | Supported | FastAPI handlers still return `(body, status)` tuples; client relies on HTTP status. |
| AUD-09 | Supported, downstream changed | Upload still reads request before try, uses unscoped indexing and success-only unlink. `DocumentIngestionAgent.index_file` now generates a model-backed summary. |
| AUD-10 | Changed | `app.on_message` now executes `handle_user_turn` in executor. Blanket synchronous-answer claim superseded; indexing, post-answer memory and native end remain synchronous. Responsiveness unmeasured. |
| AUD-11 | Changed | Canonical settings/AppConfig replace general env configuration. Graph SemanticRouter/native gist gates still differ; new source forcing, scheduling, reranker and summary configuration need current map. |
| AUD-12 | Changed | Dockerfile/requirements.txt absent; PyMuPDF declared. Python >=3.10 vs `datetime.UTC` remains. New run.sh/startup.py/uv setup unverified. Do not restore removed artifacts. |
| AUD-13 | Supported, port-dependent | Answer/judge shell wrappers retain legacy OPENAI/MODEL_NAME gates. Main provider migration does not certify all evaluation paths. |
| AUD-14 | Changed; concern supported | Custom routes still lack auth dependencies; user-content printing remains. Docker exposure evidence obsolete; new log endpoints expand surfaces. |
| AUD-15 | Changed | Oracle/full-context/injected-memory eval limitations remain. React now has E2E; “no React tests” is false. Native browser model extracts Question from augmented prompts. |
| AUD-16 | Supported | `Database.fork_chat` copies messages/gists/inspections and processed flags, omits chat_documents. Desired inheritance unresolved. |
| AUD-17 | Changed; old contradiction superseded | `validate_model_messages` and `latest_message_index` accept latest-user text contained in augmented content. Exact-equality argument no longer proves fallback. Real-composition recording-model test remains useful; full request evidence still needs isolated execution. |
| AUD-18 | Changed; parity incomplete | React consumes processing-stage and embedded traces; failed answers now emit a message. No consumers for product-state/product-error/answer-inspections found; composer still gates on connection/loading. Recheck concrete parity. |
| AUD-19 | Supported | Native edit enabled; SQLiteChainlitDataLayer update_step/delete_step no-op; on_message saves new message. New update_message_content supports assistant traces, not edit reconciliation. |
| AUD-20 | Changed; old path superseded | SQLiteLongTermMemoryStore passes its own Database through StructuredMemoryVectorSync into sqlite-vec. Index requires that Database and raises if missing. No independently configured structured-memory Chroma directory. Downloads and partial SQL/vector failures remain concerns. |

## TSA findings

| ID | Current static status | Evidence / next action |
|---|---|---|
| TSA-01 | Supported; expanded | App imports before fixtures plus eager models; isolate canonical settings and cwd-relative logs before collection. |
| TSA-02 | Changed | Vector sync now binds same SQL DB; embedding loads/post-commit failures remain. Old separate persistent-vector argument superseded. |
| TSA-03 | Supported | navigation_all_active lacks expected IDs; read_only counters hardcoded; splitter/source-inspection oracles remain. |
| TSA-04 | Supported; AUD link changed | `test_langgraph_demo_context_packet_is_used_for_model_answer` asserts actual request equals packet and no fallback through real composition. Retain; AUD-17 no longer predicts failure. |
| TSA-05 | Changed | Untagged Chroma score and scheduled empty-output assertions remain; augmented prompt acceptance and policy-specific no-op tests changed contracts. |
| TSA-06 | Supported, fixtures changed | Cache updater remains distinct from durable store/vector tests; categories/namespaces/index interface changed. Success-only storage test still lacks injected failure. |
| TSA-07 | Changed | Native fixture limits remain; new React `chat-messages.test.mjs`, `smoke.test.mjs`/test:e2e require services and send messages. Chroma env alone no longer configures app isolation. |
| TSA-08 | Supported, sibling changed | Contention test Event then immediate return lacks overlap barrier. Timeout sibling now expects failed assistant message/inspection. |
| TSA-09 | Changed | Root upload probes already absent; test_backend and JS socket probes remain live diagnostics. Do not restore removed probes. |
| TSA-10 | Supported; expanded | Deferred updater swaps estimator after ChatService construction; Gemma tokenizer path remains. Main adds model preload. |
| TSA-11 | Supported | `test_non_raw_candidate_content_is_unchanged` remains constructor/literal equality. Narrow removal proposal remains unapproved. |
| TSA-12 | Supported, selector changed | q5/q11/q17/q19 still use equivalent 100/20-token boundaries with differing labels. Preserve generic boundary before reducing cases. |
| TSA-13 | Supported, manifest changed | Pillow test checks installed metadata, not explicit dependency. pyproject declares it; requirements.txt absent. |

## Isolation and next audit work

- Canonical `settings.LANGCHAIN_CHROMA_PERSIST_DIR` must be set before app import; DATABASE_PATH env still honored.
- App import can warm embedding/cross-encoder; disable/fake downloads before importing production paths.
- `ShortTermMemory.dump_memory_consolidation_log` writes `logs/memory/<chat_id>/batch_*.json` under cwd. Isolate cwd too.
- Memory vectors are now same-DB sqlite-vec; document Chroma still needs separate isolation. Include connection-guard network probes and tokenizer/embedding caches.
- Re-inventory new coordinator/consolidation/React tests and changed scheduling/end/timeout behavior. Old 80-file/602-function totals are historical.
- No AUD finding is newly declared runtime verified here. Bounded provider/prompt checks are recorded separately in [migration](migration.md); they are not full product acceptance.
