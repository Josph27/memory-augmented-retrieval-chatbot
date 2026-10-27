## 1. Classification register

Read-only assessment at `cb2772925ccfe964371a30e25b5fcfab57e3f178`. No files changed, application imports, collection, execution or provider calls.

Use [execution-cohorts.json](/home/josph/.codex/worktrees/audit-main/repo/docs/audit/revalidation/execution-cohorts.json) as an exact path register: its three deterministic cohorts contain **69 distinct test files**. The following partition classifies all current test-like entry points; “offline” describes the required execution contract, not a claim that current setup already enforces it.

| Group | Exact membership / selection | Treatment |
|---|---|---|
| **Offline-unit** | Within the 69-file register: `test_prompt_messages`, `test_context_comparator`, `test_context_builder`, `test_dynamic_memory_budget`, `test_routing_agent`, `test_semantic_router`, `test_retrieval_query_simplification`, `test_memory_trace`, `test_answer_policy_prompts`, `test_product_navigation_asset`, `test_document_qa_answer_generation`, `test_document_qa_diagnostics`, `test_document_qa_metrics`, `test_document_qa_prepare`, `test_document_qa_prepare_nq`, `product_behavior/test_inventory` | Pure contracts, injected models/resources, source or asset assertions. No real inference needed. |
| **Offline-integration** | Remaining **53 files** in that register, except the real cross-encoder node below | Temporary SQL/Chroma, SDK MockTransport, composition, storage, fake inference and evaluation regressions. Keep these evaluation tests in default coverage. Some currently require bounded guard/loader setup repairs. |
| **Offline-integration, collection prerequisite** | `tests/test_chainlit_chat_actions.py`, `tests/test_chainlit_memory_trace_helpers.py`, `tests/product_behavior/test_runner.py` | First two import `app` at collection; third dynamically imports it through product oracles. Admit only after pre-import isolation is established. |
| **Offline-integration, subprocess prerequisite** | `tests/test_final_eval_wrappers.py`, `tests/test_targeted_eval_wrapper.py` | Stub executors, synthetic artifacts and `--check` contracts. They are **not live evaluation tests**. Need isolated subprocess environment and caches. |
| **Browser-isolated** | `tests/e2e/test_product_behavior_browser.py` plus `conftest.py` and fixture application | Intended deterministic local browser coverage. Fixture imports production app before replacing services. Headless-setting test can eventually be classified separately as unit. |
| **Expensive evaluation/model-assets** | `tests/test_memory_reranker.py::test_cross_encoder_backend_preload_loads_model` | Real model load/download; no provider inference inherently required. Keep explicit opt-in. |
| **Manual, potentially live-provider** | `tests/test_backend.py`; three `tests/test_socket*` scripts | Backend CLI performs a real turn. Socket scripts send on every connection and may resend after reconnect. Not default pytest/browser checks. |
| **Browser/manual, potentially live-provider** | `braemon/e2e/chat-messages.test.mjs`, `smoke.test.mjs` | Ambient localhost services. Chat script sends two turns; smoke sends no explicit prompt but opens app/socket startup paths. Neither currently supplies isolated services. |
| **Support, not test cases** | Python package markers, browser hook and fixture application | Retain consumers; do not inflate test counts. |
| **Live-provider diagnostic** | `evals/test_short_term_memory.py`, `scripts/eval_memory.py`, `scripts/verify_natural_long_term_memory_flow.py` | Real extraction remains even when ordinary answers/filler are fake. These are not offline because their names mention tests or fast mode. |

The current `tests/` tree has **76 test-named Python files**, plus three support files; the standalone `evals/test_short_term_memory.py` explains the historical **80 Python-source** total.

## 2. Evaluation modes and request bounds

| Entry/mode | Classification and actual work |
|---|---|
| Generated-answer runner `mock`/`replay`; multisource, typed-memory mock, structured-memory mock | Offline regressions. Structured mock still reaches `ConnectionGuard` before its fake manager; composition may initialize default embedding dependencies. Fix those seams rather than excluding evaluation coverage wholesale. |
| Generated-answer `model` | Live: one generator call per selected case; `--limit` defaults to unrestricted. |
| Document QA oracle + supplied evidence/text | Offline metrics/scaffold. Oracle answers do not measure generation. |
| Document QA Chroma / retrieval comparisons | Local integration or expensive evaluation depending on real embedding/model assets. Model-answer mode adds one answer call per case. Top-k curve loops over **cases × modes × unique positive k**; defaults k=`1,3,5,10`, always oracle answers. |
| MAB/LongMemEval adapter `mock` | Offline composition regressions, subject to loaders/default dependencies. MAB loops **examples × questions**; `--limit` alone does not bound questions. LongMemEval seeds deterministic session transcripts and uses a no-op updater. |
| MAB/LongMemEval adapter `model` | Live answer generation plus any enabled routing/reranking calls. MAB has `--question-limit`; selected-suite example limit defaults to50. LongMemEval `--limit` defaults unrestricted. |
| MAB/LongMemEval answer-and-judge runners | Live/expensive. `--max-cases` defaults unrestricted. For N uncached successful cases, **N answer stages + N–2N logical judge requests**, before transport retries and transitive calls. Resume can reduce calls but is not a hard budget. |
| Final answer/judge shell workflows | Expensive/live. Heldout manifests contain **33 MAB +19 LongMemEval cases**. Other manifest counts: smoke3, calibration12, context-targeted8, post-fix-targeted14, “four-case” forensic6. Names are not bounds. |
| RAGAS runner | Expensive/live unless separately configured otherwise. Four metrics invoke third-party evaluation machinery; no local row limit or request budget. Exact calls depend on RAGAS version, contexts, embeddings and retries. |
| Dataset preparation CLIs | Manual/network/data preparation; SQuAD output limit20, NQ200 by default. Those are output limits, not download/scan bounds. Conversion helper tests remain offline. |
| Product-behavior runner | Offline integration for repository/handler oracles after startup isolation; browser rows are separate. `repetitions` is recorded metadata: `run_cases` evaluates each selected case once, not that many times. |
| Inspect/validate utilities | Manual operational checks; some open configured stores or initialize clients. Synthetic artifact-validator tests remain offline integration. |

Request accounting must include:

- `ModelWrapper.chat`: one completion attempt, `max_retries=0`; health cache miss can add **up to two HTTP probes**. No explicit answer output-token cap here.
- Native LLM routing and optional LLM reranking: additional model calls. Deterministic `SemanticRouter` itself makes none.
- Document ingestion: optional summary-model call per indexed file.
- LangMem: separate `ChatOpenAI`, retries0, but manager invocation can perform multiple internal model/tool iterations. No project-level total-request cap established.
- Judge: [evaluate_with_judge](/home/josph/.codex/worktrees/audit-main/repo/evals/mab_answer_eval/judge.py) permits one repair, **300 output tokens per attempt**. Its SDK client does not explicitly set retries/timeouts; therefore two logical requests are not a verified two-HTTP-attempt bound.
- Model assets: embedding, tokenizer and cross-encoder downloads can occur without any paid inference.

## 3. Minimal default selection and prerequisite repairs

Recommended registered markers: `offline_unit`, `offline_integration`, `browser_isolated`, `live_provider`, `expensive_evaluation`, `manual`. Default should select only the first two.

**Markers alone are insufficient:** pytest imports modules before marker deselection. Set `testpaths=["tests"]`; exclude app-import, browser and manual modules **before collection** until their prerequisites are repaired. Initially retain the exact69-file allowlist, deselect the single real-preload node, and run under the existing confinement boundary. Admit deferred offline files incrementally.

Prerequisites:

- **App-import tests:** isolate canonical settings, dotenv, SQL, document Chroma, cwd logs and model/cache paths before importing `app`; intercept startup warmup explicitly. Keep actual helper/handler behavior under test.
- **Wrapper tests:** mask `.env`/private settings, clear inherited credentials, use synthetic environment, temporary runs/cache and preinstalled dependencies. `load_eval_env` reads repository `.env`; `enable_eval_online_mode` deliberately unsets HF offline variables. Existing stub children are safe responsibilities, but external confinement must survive these environment changes.
- **Native browser:** replace hardcoded macOS Chrome path, isolate subprocess startup before its production import, use installed executable/dependencies without `uv` resolution/download, permit loopback only, and terminate the process group. Temporary DB and environment Chroma override alone do not isolate canonical settings.
- **React probes:** provide dedicated fixture backend/frontend and temporary browser profile; exclude ambient localhost defaults. Socket probes need reconnect/resend bounds before automation.

Do not globally force health guards to succeed: fake positive-memory cases should prove the manager ran; explicit unavailable-provider cases should still exercise real rejection behavior.

## 4. Deferred live proposal

These are proposals requiring separate execution/spending approval:

| Tiny check | Proposed hard bound |
|---|---|
| Provider wire smoke | One synthetic prompt; one completion attempt; ≤64 output tokens; no extraction, routing, reranking or judge. |
| Structured extraction smoke | One synthetic fact batch; cap **all manager model requests at3**, ≤256 output tokens each; no conversation replay. Stop if instrumentation cannot enforce the cap. |
| Grounded document answer | One synthetic local document, one query; preinstalled embeddings, summary disabled, deterministic routing/ranking; one completion ≤128 output tokens. |
| Judge-only smoke | One frozen synthetic answer; one judge request ≤300 output tokens. Test malformed-output repair offline first. |

Across an approved batch: serial execution, SDK retries0, no automatic reruns, explicit overall deadline, stop on authentication/rate-limit/timeout or request-cap breach. Count health probes separately from billable completions.

Instrument at the actual SDK/transport boundary: provider/model, attempt count, request ID, latency, input/output/cache token usage, finish reason and status; omit credentials and prompt contents. Current wrappers primarily return strings, and runner `judge_calls` counts stages rather than repairs/transport retries—neither is sufficient for spending enforcement.

**Cost remains unknown** until the selected provider/model, current pricing, usage accounting and separate spending approval are established. No live check is needed to complete the bounded offline test/infrastructure batch.