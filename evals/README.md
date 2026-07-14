# Evaluation Suite

**TL;DR:** 12 evaluation categories covering document retrieval (hit@k),
structured memory lifecycle, multi-source selection, generated answer quality,
end-to-end scenarios, product behavior (50 frozen cases), typed-memory E2E,
MemoryAgentBench answer eval, LongMemEval pilot, held-out answer analysis,
short-term memory tests, and RAGAS-compatible export. Most evals support a
deterministic `--mode mock` that requires no model, Chroma, or network access.

---

## Eval landscape

```
evals/
├── document_qa/              ← Retrieval hit@k benchmarks (SQuAD, NQ, Chroma)
│   ├── datasets/             ← Committed smoke-test JSONL + optional prepared subsets
│   └── outputs/              ← Generated eval artifacts (not committed)
├── structured_memory/        ← ADD/NOOP/UPDATE/RETRIEVE/ABSTAIN lifecycle eval
├── e2e_scenarios/            ← Full CoordinatorAgent integration: route → retrieve → answer
├── multi_source_retrieval/   ← Source selection + retrieval without answer grading
├── generated_answer/         ← Controlled answer quality from prepared contexts
├── typed_memory_e2e/         ← Typed-memory end-to-end benchmark
├── product_behavior/         ← 50 frozen product scenarios (navigation, lifecycle, docs, failures)
├── mab_answer_eval/          ← MemoryAgentBench held-out answer evaluation with judge model
├── memory_agent_bench/       ← MAB adapter: raw replay, gist, span comparison
├── longmemeval_adapter/      ← LongMemEval pilot adapter (span retrieval, scoring)
├── answer_heldout_analysis.py    ← Cross-run analysis of held-out answer failures
├── longmemeval_answer_eval.py    ← LongMemEval answer evaluation with judge model
└── test_short_term_memory.py     ← End-to-end current-chat short-term memory tests
```

---

## Eval categories

| # | Category | Directory | One-liner |
|---|---|---|---|
| 1 | **Document QA** | `document_qa/` | Retrieval hit@k over SQuAD and NQ subsets using LangChain-Chroma. Oracle and model answer modes. Optional RAGAS export. |
| 2 | **Structured Memory** | `structured_memory/` | ADD, NOOP, UPDATE, RETRIEVE, ABSTAIN lifecycle. Fake LangMem extraction → SQLite → retrieval → answer checks. |
| 3 | **E2E Scenarios** | `e2e_scenarios/` | Full `CoordinatorAgent` pipeline. Document, structured memory, previous-chat gist, raw-span, distractor, and reranker scenarios. |
| 4 | **Multi-Source Retrieval** | `multi_source_retrieval/` | Source selection and retrieval correctness. Checks `recent_messages`, `structured_memory`, `document_memory`, `previous_chat_gist`, `raw_message_span`. No answer grading. |
| 5 | **Generated Answer** | `generated_answer/` | Controlled answer grading from prepared contexts. Checks expected content, forbidden claims, source use, abstention. |
| 6 | **Typed-Memory E2E** | `typed_memory_e2e/` | End-to-end typed memory benchmark. Cases span structured, episodic, and document memory integration. |
| 7 | **Product Behavior** | `product_behavior/` | 50 frozen app-level scenarios: navigation (8), lifecycle (10), persistence (7), documents (15), failures/races/idempotency (10). 48 pass, 2 documented failures. |
| 8 | **MAB Answer Eval** | `mab_answer_eval/` | Held-out MemoryAgentBench answer evaluation. Judge-model scoring with manifest-based case selection. Supports native and graph execution modes. |
| 9 | **MemoryAgentBench** | `memory_agent_bench/` | MAB adapter: raw replay, gist-only, and span-retrieval comparison. Selected suite with deterministic and model modes. |
| 10 | **LongMemEval Adapter** | `longmemeval_adapter/` | Pilot adapter for LongMemEval-style cases. `recent_only`, `gist_only`, `span_retrieval`, `full` memory modes. Unofficial scoring. |
| 11 | **LongMemEval Answer Eval** | `longmemeval_answer_eval.py` | Answer-level evaluation for LongMemEval cases using a judge model. Builds contexts via span retrieval and grades with OpenAI judge. |
| 12 | **Answer Heldout Analysis** | `answer_heldout_analysis.py` | Cross-run analysis of held-out answer evaluation failures. Classifies failures into pipeline failures, correct-without-context, evidence-blocked, and context-quality categories. |

---

## Root-level files

### `answer_heldout_analysis.py`

Cross-run analysis tool. Loads results from multiple MAB answer eval or
LongMemEval answer eval output directories, classifies each case by primary
failure category, and computes summary statistics:

| Category | Meaning |
|---|---|
| `pipeline_failure` | Case did not complete (failed stage recorded) |
| `grounded_pipeline_success` | Judge correct + gold context present |
| `correct_without_gold_context` | Judge correct but gold context absent |
| `evidence_blocked_answer` | Evidence contract unsatisfied, answer may be abstention |
| `context_quality_issue` | Gold candidate present but not in context |
| `incorrect_judge_outcome` | Context available but judge scored incorrect |

Reports per-category counts, per-question-type breakdowns, and evidence
contract statistics. Reads from `mab_answer_eval` artifact conventions.

### `longmemeval_answer_eval.py`

Standalone LongMemEval answer evaluation runner. For each case:

1. Loads case from `longmemeval_adapter.loader`
2. Builds message-span context via `LongMemEvalMessageSpanRetriever`
3. Generates answer through `ChatAgent` (configured model)
4. Ends the chat via `ChatEndAction`
5. Evaluates answer with an OpenAI judge model
6. Runs secondary judge on disagreement for adjudication

Outputs results following `mab_answer_eval` artifact conventions
(`results.jsonl`, `summary.json`, judge comparison artifacts). Requires
`JUDGE_MODEL` and `JUDGE_API_KEY`.

### `test_short_term_memory.py`

End-to-end current-chat short-term memory tests using a temporary SQLite
database and real `ModelWrapper`. Each `ShortTermMemoryCase` defines:

- Setup messages injected into a chat
- A question to ask
- Expected answer content and forbidden content
- Memory content that should be persisted

Makes actual LLM calls — requires an OpenAI-compatible endpoint.

---

## How to run evals

All evals share common patterns:

### Mock mode (no model, deterministic)

```bash
# Document retrieval
uv run python evals/document_qa/run_document_qa_eval.py \
  --context-mode langchain_chroma --retrieval-scope corpus --top-k 3

# Structured memory lifecycle
uv run python evals/structured_memory/run_structured_memory_eval.py --mode mock

# E2E scenarios
uv run python evals/e2e_scenarios/run_e2e_scenarios.py --mode mock

# Multi-source retrieval
uv run python evals/multi_source_retrieval/run_multi_source_retrieval_eval.py --mode mock

# Generated answer
uv run python evals/generated_answer/run_generated_answer_eval.py --mode mock

# Product behavior
ORCHESTRATION_MODE=langgraph_demo uv run python -m evals.product_behavior.runner
```

### Model mode (requires API endpoint)

```bash
# Document QA with real answers
uv run python evals/document_qa/run_document_qa_eval.py \
  --dataset evals/document_qa/datasets/squad_subset.jsonl \
  --context-mode langchain_chroma --retrieval-scope corpus --top-k 3 \
  --answer-mode model --limit 10

# LongMemEval pilot
uv run python evals/longmemeval_adapter/run_longmemeval_adapter.py \
  --dataset-path path/to/longmemeval.jsonl --limit 20 \
  --memory-mode full --answer-mode model

# MAB answer eval
uv run python -m evals.mab_answer_eval \
  --manifest evals/memory_agent_bench/manifests/some_manifest.json \
  --output-dir artifacts/mab_eval/run_001 \
  --judge-model MODEL_ID --execution-mode native
```

---

## Environment requirements

| Requirement | Needed for | Not needed for |
|---|---|---|
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | Model and judge modes | Mock modes |
| `MODEL_NAME` | Model answer generation | Mock/fixture answers |
| `JUDGE_MODEL`, `JUDGE_API_KEY` | MAB/LongMemEval answer evals | All other evals |
| HuggingFace `datasets` | `prepare_squad_subset.py`, `prepare_nq_subset.py` | Using pre-committed datasets |
| `sentence-transformers` | Cross-encoder reranker mode | Deterministic reranker |
| RAGAS | `run_ragas_eval.py` | All other evals |
| Chrome / browser | Product behavior E2E browser tests | All 42 non-browser product tests |
| Chroma | Document QA with `langchain_chroma` | Mock modes, structured memory mock |

---

## Manifests directory

Some evals (MAB, typed-memory E2E) use case manifests — JSON files defining
which cases to run, their splits, and execution parameters. Manifests live in
the respective eval directories (e.g., `memory_agent_bench/manifests/`).

---

## Relationship between evals

```
Document QA (hit@k) ────── checks retrieval, not answers
Structured Memory ──────── checks memory lifecycle, not answers
Multi-Source Retrieval ─── checks source selection, not answers
    │
    └──→ E2E Scenarios ── connects routing → retrieval → answer
                                │
    Generated Answer ──────────┤ grades answers from prepared contexts
    Typed-Memory E2E ──────────┤ typed memory end-to-end
    MAB Answer Eval ───────────┤ held-out judge-scored answers
    LongMemEval Answer Eval ───┤ LongMemEval judge-scored answers
                                │
    Product Behavior ──────────┘ 50 frozen product scenarios
    Answer Heldout Analysis ─── post-hoc failure classification
```

---

## Limitations

- Mock modes validate plumbing, not model or retrieval quality.
- Chroma document retrieval requires embedding model download on first run.
- LongMemEval adapter is unofficial — not a leaderboard scorer.
- Browser E2E tests require local Chrome and port binding.
- Output artifacts in `outputs/` and `artifacts/` are generated and should
  not be committed.
