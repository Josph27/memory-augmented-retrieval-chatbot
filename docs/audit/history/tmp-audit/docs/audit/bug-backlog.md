# Parked audit bug backlog

Package v1.0 · reconciled 2026-10-27. **Status of every AUD entry: open/parked; no fix implemented or approved by this package.** Disposition below records how the audit conclusion changed, not task completion. See [decisions](decisions.md), [workflow map](workflow-map.md) and [historical provenance](reports/provenance.md). Version 1.0 preserves the pre-existing backlog's 20 IDs, corrections and counterevidence; it adds navigation/status metadata rather than reopening the audit.

## 1. Baseline and interpretation

Consolidated from the first audit and its static follow-up; not a new execution report. Baseline: branch `tmp-audit`, commit `f4fc7c265f963cf516b5b8a13ee2ea0ad4ee24f7`. Evidence refers to the current working copy, including pre-existing changes to `.env.example`, `README.md`, `app.py`, `src/config.py`, `src/memory/langmem_structured.py`, and `src/model_wrapper.py`; untracked provider settings and tests were also present. The stashed deletions were neither inspected nor applied. This backlog does not approve removal or implementation.

During backlog preparation, a separate commit advanced HEAD to `c3ffee2dae6b6ce6daa8a145e347e61fa4989672`, changing only `AGENTS.md` and `README.md` with handoff instructions. This task did not make that commit or those edits. The new instructions were read; they do not change the application evidence below. Referenced `docs/audit/README.md` and `docs/audit/decisions.md` were absent at inspection, so prior audit context and code, rather than an assumed decision register, supply this backlog's basis.

**Confidence:** confirmed means code behavior or wiring established by inspection, not an executed failure. Strongly supported means the failure scenario still depends on conditions requiring isolated reproduction. **Priority:** P1 affects retained answer correctness, durable state, or isolation; P2 affects narrower paths, diagnostics, configuration, or operations. Conditional deployment severity is stated explicitly.

All verification below is proposed, not performed. Use synthetic messages/documents, temporary SQLite and vector paths, fake inference/embedding transports, and no production credentials. Do not import `app` before isolation is established. Historical evaluation output establishes no current result. Paths and line numbers are repository-relative.

## 2. Correctness and lifecycle

### AUD-01 — Retrieval scope and document inspection disagree

- **Disposition:** reclassified/narrowed; structural/product-policy issue, P2; **confirmed** inconsistency.
- **Evidence:** `src/documents/registry.py:57–97` intentionally falls back to global Ready documents when the chat has none. `src/retrieval/retriever_dispatcher.py:112–134` propagates the resolved scope; `src/inspection/answer_inspector.py:196–209` instead requires explicit chat associations. `tests/test_document_product_lifecycle.py:210` covers chats that already have associated documents, not the empty-chat fallback.
- **Impact/limits:** candidates can be eligible for retrieval but unavailable through Inspector. Global fallback itself is intentional, not an established unauthorized-access defect; actual prompt inclusion is separately affected by AUD-17.
- **Direction/verification:** decide global-versus-chat scope, then align registry, inspection, ingestion and fork semantics. Seed two synthetic chats, only one associated document; compare retrieved, selected, displayed and actual model context separately.

### AUD-02 — REST chat end bypasses finalization

- **Disposition:** retained; defect, P1; **confirmed** divergent paths.
- **Evidence:** React end control at `braemon/src/components/ChainlitChat.jsx:185` calls the REST handler, which only marks inactive (`src/api_routes.py:88–97`). Chainlit calls `ChatEndAction` (`app.py:198–224`), whose memory/gist flush and process-local guard precede inactivation (`src/actions/chat_end.py:71–89`). No later end callback guarantees the skipped flush.
- **Direction/verification:** use the authoritative, model-aware finalizer for both callers. With pending synthetic messages, compare both entry points; inject flush failure and an in-flight turn. Extend `tests/test_chat_end_action.py` with route-level parity and idempotency assertions.

### AUD-03 — Memory deletion has inconsistent representations and semantics

- **Disposition:** retained/narrowed; defect plus forgetting-policy decision, P1; **confirmed** representation mismatch; future resurrection is conditional.
- **Evidence:** `src/api_routes.py:173–185` physically deletes by memory ID without namespace or cache/vector handling. Canonical `src/memory/long_term_store.py:302–315` soft-deletes by namespace and synchronizes vectors. Retrieval can fall back to compatibility caches (`src/retrieval/structured_memory_retriever.py:48–97`); vector hits rehydrate SQL and filter active records (`:114–116`, `:160–205`), so an orphan vector alone does not expose deleted text. LangMem combines SQL/cache state (`src/memory/langmem_structured.py:142–155`); supported future extraction may upsert the same fact (`:216–240`, `:369–380`; store `:212–273`).
- **Direction/verification:** define deletion as hiding, suppression from future extraction, or erasure. Canonical delete alone cannot implement all three. Test namespaces, caches, SQL, vector entries, raw/gist history and subsequent supported extraction. Historical messages are not automatically replayed merely because a record is deleted.

### AUD-04 — Chroma distance contributes in the wrong direction

- **Disposition:** retained/narrowed; defect, P1; **confirmed** scoring error, final-order reversal unverified.
- **Evidence:** `src/retrieval/langchain_chroma_retriever.py:159` selects the distance-returning `similarity_search_with_score`; normalization preserves distances in `[0,1]` and switches formula above one (`:273–280`). `src/memory/long_term_vector_index.py:152–158` uses the same convention. Higher normalized values contribute positively in `src/retrieval/reranker.py:468–522`; other features, optional rerankers and context utility/cost selection can offset this. `tests/test_langchain_chroma_retriever.py:38–60` currently asserts unchanged input scores.
- **Direction/verification:** normalize according to the selected API's distance/relevance contract in both adapters. Compare distances 0.1 and 0.8 with equal other features, then vary lexical scores and token costs; assert contribution and final selection separately. Installed Chroma wrapper documentation was inspected; no live query was run.

### AUD-05 — Unknown models inherit an unsafe context assumption

- **Disposition:** retained/narrowed; configuration defect, P1; **confirmed** default resolution, provider rejection unverified.
- **Evidence:** only Gemma has a native profile (`src/context/model_profile.py:65`); resolution can treat the 262,144 application cap as an unknown model's effective limit instead of the 4,096 fallback (`:120–163`). Non-Gemma token estimates are approximate (`src/context/token_estimator.py:437–452`); `src/model_wrapper.py:34–39` sends no explicit output-token limit despite a budgeting reserve.
- **Direction/verification:** separate application cap, verified model capacity and output allocation. Test unknown IDs, stored chat model IDs, explicit overrides and request options offline. Context pruning exists; its resolved ceiling is the concern. No claim is made about DeepSeek's actual capacity or live compatibility.

### AUD-06 — Empty online extraction can repeatedly block later batches

- **Disposition:** retained/conditional; defect, P1; **strongly supported** deterministic scenario.
- **Evidence:** empty extraction becomes `no_valid_memories` (`src/memory/langmem_structured.py:171–175`). Online processing disallows no-op completion, leaves message flags unchanged and selects oldest pending batches (`src/memory/short_term.py:254`, `:309–350`, `:374–465`). `tests/test_langmem_structured_memory.py:176` intentionally asserts unsummarized messages after empty extraction. End processing allows valid no-op completion (`tests/test_chat_end_action.py:255–295`).
- **Direction/verification:** distinguish successful empty extraction from extraction failure before advancing. Use two user/assistant pairs, batch size two, trigger one, no protected suffix and generous token cap; fake extractor always returns empty for pair one and would accept pair two. Repeated online calls should eventually reach pair two. Smaller incomplete batches can grow; configuration changes, different extraction output or chat end can permit progress, so starvation is not unconditional.

### AUD-08 — REST error tuples do not set HTTP status

- **Disposition:** retained; defect, P2; **confirmed** handler/framework contract, unexecuted response scenario.
- **Evidence:** `src/api_routes.py:48`, `:54–56`, `:181` return `(body, status)` from FastAPI handlers; the framework serializes ordinary return values rather than applying Flask-style status tuples. `braemon/src/api.js:14` relies on `response.ok`.
- **Direction/verification:** use explicit HTTP errors/responses and a consistent client error shape. Register routes in an isolated FastAPI app; assert status and body for missing resources and injected database failures, then client-visible rejection. No HTTP reproduction was run.

### AUD-09 — Global upload uses an unavailable request contract and bypasses registry

- **Disposition:** retained/strengthened; defect, P2; **confirmed** wiring, HTTP failure unexecuted.
- **Evidence:** `src/api_routes.py:119–163` reads `cl.context.request` before its `try`; installed Chainlit context has no request attribute and ordinary FastAPI middleware does not establish a Chainlit session context. React Documents calls this endpoint (`braemon/src/api.js:48`). Downstream unscoped ingestion (`src/chat_service.py:216–225`; `src/agents/document_ingestion_agent.py:37–68`; `src/retrieval/langchain_chroma_retriever.py:68–109`) indexes vectors without creating SQL registry records. Temporary-file unlink also occurs only on success.
- **Direction/verification:** inject a framework Request and define complete registry/scope/error-cleanup behavior. Isolated HTTP test should establish the first failure; separately invoke the downstream path with synthetic upload/embedding fixtures and compare SQL listing, vectors and normal scoped retrieval. Chat socket attachments take a different path. Fixing request injection alone is insufficient.

### AUD-16 — Fork omits explicit document associations

- **Disposition:** retained; lifecycle/policy inconsistency, P2; **confirmed** copy boundary, intended semantics unresolved.
- **Evidence:** `src/database.py:493–662` copies messages, gists and inspections but not `chat_documents`; inherited messages are marked summarized and the legacy memory cache is not copied. Global document fallback (AUD-01) can mask the document-association omission.
- **Direction/verification:** decide whether fork inherits document access, then test explicit associations, retrieval, Inspector and later document changes in both chats. Do not assume copying all caches or re-extracting inherited messages is desirable.

### AUD-17 — Retrieved-context prompt fails exact-message validation

- **Disposition:** retained; defect, P1; **confirmed** static contradiction, runtime answer impact unexecuted.
- **Evidence:** `src/context/context_builder.py:314–324` augments the final user content when retrieved context exists. `src/context/prompt_messages.py:65–81` requires the unchanged original user message; comparison at `src/context/context_comparator.py:152–164` also treats it as missing. Invalid assembly falls back to legacy model messages (`src/agents/coordinator_agent.py:241–244`), while trace/inspection can retain the selected packet.
- **Impact/limits:** document/gist/historical-span evidence may be selected and displayed but absent from the actual generation request. Structured-only or unaugmented recent-message cases may remain valid; insufficient-evidence paths may avoid generation entirely.
- **Direction/verification:** align builder, validator and comparison contracts, and record actual sent context. Extend the recording-model assertion in `tests/test_orchestration_demo_modes.py:83–112` using the real builder and nonempty document/span context; assert no fallback and equality between inspected and sent evidence. Do this before using answer quality to judge retrieval value.

### AUD-18 — React misses backend lifecycle/error inspection events

- **Disposition:** retained; frontend integration defect, P2; **confirmed** missing consumer wiring, browser behavior unexecuted.
- **Evidence:** backend emits product state, error and inspection events (`app.py:164`, `:375`); native `public` custom script handles these, whereas React entry/component has no corresponding product-event listener. Its composer gate is connection-only (`braemon/src/components/ChainlitChat.jsx:330`); inactive-chat handling at `app.py:109` and failed-answer handling may emit events without an assistant response.
- **Direction/verification:** implement parity for the retained frontend contract. Use synthetic backend events to assert ended-chat state, visible failed-answer error and inspection presentation. Test chat switch/reconnect separately; no specific reconnect defect is established by this finding.

### AUD-19 — Native edit path does not reconcile persisted/derived history

- **Disposition:** retained; defect, P2; **strongly supported**, requires native edit reproduction.
- **Evidence:** `.chainlit/config.toml:45` enables editing; installed Chainlit socket edit handling rewrites session messages and invokes `on_message`. `src/chainlit_data_layer.py:48–51` implements update/delete as no-ops; `app.py:139` persists a new user message. There is no corresponding persisted-history replacement or derived-memory invalidation on this path.
- **Direction/verification:** define edit semantics, then edit a synthetic resumed conversation and reload; compare session, SQLite, later messages and derived memories. Establish supported edit/update callbacks before choosing a reconciliation strategy. This is not evidence that conversation editing has no product value.

## 3. Isolation, integration and operations

### AUD-07 — Imports and inspection commands can initialize the configured database

- **Disposition:** retained/narrowed; operational/isolation defect, P1; **confirmed** capability; no observed data loss.
- **Evidence:** `app.py:36–46` creates runtime directories and opens Database at import; `src/database.py:98–101` initializes schema, including destructive legacy-table migration capability at `:253–278`. `tests/test_chainlit_chat_actions.py:6` and `tests/test_chainlit_memory_trace_helpers.py:5` import before test monkeypatching. Source-inspection oracles also import app (`evals/product_behavior/oracle.py:285`, `:377`, `:547`, `:777`, `:804`). Database inspection scripts construct Database (`scripts/inspect_long_term_memory.py:25–26`; `scripts/inspect_raw_message_span.py:43–44`).
- **Counterevidence/direction/verification:** browser fixture exports a temporary path before app import (`tests/e2e/test_product_behavior_browser.py:94–114`); provider tests use AST inspection. Isolate before import or separate composition/read-only opening. Compare sentinel synthetic legacy/current databases in subprocesses with and without pre-exported temporary paths. Migration code is not proof that real data was lost.

### AUD-10 — Synchronous work runs inside asynchronous handlers

- **Disposition:** retained; operational defect, P2; **confirmed** call structure, latency unmeasured.
- **Evidence:** `app.py:143–173` performs synchronous service/model work in async message handling; `src/model_wrapper.py:34–39` calls the synchronous completion client. Ingestion and memory updates also have synchronous boundaries.
- **Direction/verification:** isolate blocking work or use asynchronous transports while preserving lifecycle guards. Block a fake model/indexer and assert another session can make progress, with cancellation and end-chat behavior covered. No measured responsiveness claim was made.

### AUD-11 — Configuration switches select different behavior across orchestration paths

- **Disposition:** retained; structural/configuration issue, P2; **confirmed** wiring differences.
- **Evidence:** default graph composition selects SemanticRouter (`src/orchestration/demo_orchestration.py:74–81`), independently of native rule/LLM/hybrid routing. Previous-gist enablement is applied by `src/routing/route_planner.py:255` but not equivalently by graph `src/routing/semantic_router.py:401–431`. Current-gist generation settings are not wired into normal composition; custom chunker settings and production LangChain chunk settings govern different consumers.
- **Direction/verification:** specify supported configuration ownership, then assert each switch changes the actual constructed router, sources, generator or splitter in each entry point. Preserve meaningful path differences; an unwired/default-off capability is not a removal candidate by itself.

### AUD-12 — Dependency/runtime/container declarations disagree

- **Disposition:** retained; packaging defect, P2; **confirmed** declaration differences; clean-install failure unexecuted.
- **Evidence:** `Dockerfile:13–17` installs the smaller requirements manifest and copies only app/src, omitting native custom public/config assets. `pyproject.toml:6` permits Python 3.10 while `evals/product_behavior/runner.py:7` imports `datetime.UTC` (3.11+). PDF loader dependencies and full RAG dependencies are not consistently declared across manifests; Docker's `RECENT_MESSAGE_LIMIT` at `:11` does not match the effective application setting.
- **Direction/verification:** choose supported installation/runtime contracts and exercise clean isolated installs, native asset availability and a synthetic PDF load. No dependencies were installed or containers launched during the audit.

### AUD-13 — Evaluation wrappers retain legacy provider-variable gates

- **Disposition:** retained/narrowed; integration defect, P2; **confirmed** wrapper mismatch; DeepSeek execution unverified.
- **Evidence:** `scripts/run_final_52.sh:62–63` and `scripts/run_final_judge.sh:61–62` demand legacy OpenAI-style variables before resolved-provider execution. Direct evaluator entry points have different answer-model override precedence; judge settings are separately resolved. This does not establish that every evaluator uses a stale provider implementation.
- **Direction/verification:** validate resolved settings per answer/judge role. Use mocked transport with DeepSeek-only, custom and mixed environments plus CLI/model overrides; assert final endpoint, model, key-presence handling and options. Do not expose credential values.

### AUD-14 — Custom API authorization and content logging weaken deployment boundary

- **Disposition:** retained; security/operational issue, P2 locally, P1 if reachable by untrusted clients; **confirmed** missing route-level boundary and logging.
- **Evidence:** custom routes register without authentication dependencies (`src/api_routes.py:31` onward); Chainlit's own authenticated route contracts do not automatically protect them. Docker binds all interfaces (`Dockerfile:23`). `app.py:107` unconditionally prints full user content.
- **Direction/verification:** decide the supported network boundary, authenticate custom access and avoid unconditional message logging. In an isolated app assert anonymous API denial independently of Chainlit login. Single-user local deployment reduces exposure; multi-user tenancy was not inferred as a requirement.

### AUD-15 — Evaluation modes establish narrower claims than production behavior

- **Disposition:** retained; protection/claims gap, P2; **confirmed** substitutions, not a reason to delete evaluations.
- **Evidence:** document QA defaults include full document context and oracle answers (`evals/document_qa/run_document_qa_eval.py:70`, `:114`, `:256`); structured evaluation injects memory outputs and returns oracle answers (`evals/structured_memory/run_structured_memory_eval.py:105–147`). Product behavior includes a custom splitter path (`evals/product_behavior/oracle.py:627`) and source-string assertions. Browser tests use fixture models/indexers and do not establish React parity; document-QA's custom answer prompt does not exercise AUD-17's production assembly.
- **Direction/verification:** label fixture/oracle/live and production/nonproduction boundaries; add the smallest real-composition tests for answer context, lifecycle parity and frontend events. Keep diagnostic/oracle modes with distinct value. Import mutation risk is tracked once under AUD-07.

### AUD-20 — Temporary SQL evaluation can still target persistent vectors

- **Disposition:** retained/conditional; isolation defect, P1; **confirmed** configuration path; no actual contamination observed.
- **Evidence:** `evals/structured_memory/run_structured_memory_eval.py:108–109` creates temporary SQL but constructs the store without disabling environment-selected vector sync. `src/memory/long_term_store.py:190–210`, `:267–273` resolve/synchronize the index; `src/memory/long_term_vector_index.py:66` resolves its independent persistence path. Vector/hybrid mode can therefore send synthetic evaluation memories to the normal index despite temporary SQL, potentially colliding with namespace/IDs or leaving orphans.
- **Direction/verification:** explicitly isolate every persistence backend and namespace for each harness. With injected sentinel vector storage, set vector/hybrid modes and assert all writes remain temporary; include post-SQL-commit sync failure. Audit sibling temporary-SQL consumers before generalizing the fix. This is distinct from import-time SQL initialization (AUD-07).

## 4. Consolidation and prerequisites

- AUD-01 owns scope/visibility policy; the selected-versus-sent prompt discrepancy belongs to AUD-17.
- AUD-03 owns forgetting semantics across SQL, cache, vector and future extraction; stale vector text recall alone was not established.
- AUD-07 owns early imports/SQL initialization; AUD-15 retains only evaluation-coverage limitations. AUD-20 covers independently configured vector persistence.
- AUD-02 owns REST finalization; AUD-18 owns React consumption of lifecycle/error events. Neither implies the other path can be removed.
- AUD-04 establishes an incorrect score contribution, not unconditional final ordering. AUD-05 makes no inference about live DeepSeek limits. AUD-06 is conditional on stable batch selection and repeated empty output.
- Start protection work with isolated composition and actual-prompt assertions. Decide document scope, forgetting and fork/edit semantics before tests freeze ambiguous product policy. These prerequisites do not authorize fixes or workflow deletions.

## 5. Stable symbol and workflow index

Use these qualified owners with the file/line evidence above; supplementary line numbers describe dirty working-copy source and can drift. Test paths identify protection leads, not passing executions. For shell/build/manifest evidence the relevant entry is the top-level script body or declaration, not an invented function.

| Finding | Path and symbol / entry owner | Workflow |
|---|---|---|
| AUD-01 | `src/documents/registry.py::DocumentRegistry.resolve`; `src/inspection/answer_inspector.py::serialize_candidate` | WF-07/13 |
| AUD-02 | `src/api_routes.py::register_api_routes.end_chat`; `src/actions/chat_end.py::ChatEndAction.execute` | WF-11 |
| AUD-03 | `src/api_routes.py::register_api_routes.delete_memory`; `src/memory/long_term_store.py::SQLiteLongTermMemoryStore.delete`; `src/memory/langmem_structured.py::LangMemStructuredMemoryState.update` | WF-08/09 |
| AUD-04 | `src/retrieval/langchain_chroma_retriever.py::normalize_score`; `src/retrieval/reranker.py::MemoryReranker.score_candidate`; `src/memory/long_term_vector_index.py::LongTermMemoryVectorIndex` | WF-07/08 |
| AUD-05 | `src/context/model_profile.py::resolve_context_window`; `src/context/token_estimator.py::build_token_estimator`; `src/model_wrapper.py::ModelWrapper.chat` | WF-01/03 |
| AUD-06 | `src/memory/short_term.py::ShortTermMemory.{_apply_batch,_select_pending_batch}`; `src/memory/langmem_structured.py::LangMemStructuredMemoryState.update` | WF-08/11 |
| AUD-07 | `app.py` module composition; `src/database.py::Database.{__init__,init_schema}`; `evals/product_behavior/oracle.py` source-inspection functions | WF-01/15/16 |
| AUD-08 | `src/api_routes.py::register_api_routes` nested error returns; `braemon/src/api.js::fetchChatMessages` and other API exports | WF-04/14 |
| AUD-09 | `src/api_routes.py::register_api_routes.upload_document`; `src/chat_service.py::ChatService.index_document_file`; `src/agents/document_ingestion_agent.py::DocumentIngestionAgent.index_file` | WF-06 |
| AUD-10 | `app.py::on_message`; `src/model_wrapper.py::ModelWrapper.chat` | WF-03 |
| AUD-11 | `src/orchestration/demo_orchestration.py::run_read_only_langgraph_orchestration`; `src/routing/semantic_router.py::sources_for`; `src/routing/route_planner.py::RoutePlanner` | WF-03/10 |
| AUD-12 | `Dockerfile` install/COPY/CMD; `pyproject.toml` runtime/dependencies; `evals/product_behavior/runner.py` module import; `src/documents/loaders.py::load_pdf_file` | WF-01/05/15 |
| AUD-13 | `scripts/run_final_52.sh` and `scripts/run_final_judge.sh` environment-validation bodies; answer/judge CLI resolution | WF-15 |
| AUD-14 | `src/api_routes.py::register_api_routes`; `app.py::{auth_callback,on_message}`; `Dockerfile` CMD | WF-01/14 |
| AUD-15 | `evals/document_qa/run_document_qa_eval.py::main`; `evals/structured_memory/run_structured_memory_eval.py::run_case`; `evals/product_behavior/oracle.py::document_large_chunk_retrieval` | WF-15 |
| AUD-16 | `src/database.py::Database.fork_chat`; `src/actions/chat_fork.py::ChatForkAction.execute` | WF-12 |
| AUD-17 | `src/context/context_builder.py::ContextBuilder.build_trace_messages`; `src/context/prompt_messages.py::validate_model_messages`; `src/context/context_comparator.py::latest_message_index`; `src/agents/coordinator_agent.py::CoordinatorAgent.run_turn` | WF-03/13 |
| AUD-18 | `app.py::{send_product_state,send_product_error,send_answer_inspections}`; `public/product-navigation.js::{applyProductState,applyAnswerInspections}`; `braemon/src/components/ChainlitChat.jsx::ChainlitChat` | WF-13/14 |
| AUD-19 | `src/chainlit_data_layer.py::SQLiteChainlitDataLayer.{update_step,delete_step}`; `app.py::on_message`; `.chainlit/config.toml` edit setting | WF-04 |
| AUD-20 | `evals/structured_memory/run_structured_memory_eval.py::run_case`; `src/memory/long_term_store.py::SQLiteLongTermMemoryStore.{__init__,upsert}`; `src/memory/long_term_vector_index.py::LongTermMemoryVectorIndex.from_env` | WF-08/15 |
