# Document QA Eval Scaffold

This directory contains document QA evaluation utilities for the project’s
LangChain-Chroma document-memory backend.

The evals are intentionally lightweight. Deterministic retrieval metrics remain
the primary signal. Optional model-answer mode and RAGAS-compatible export are
available, but normal tests do not require Ollama, internet access, RAGAS, or
model downloads.

## Dataset Format

Each JSONL row contains:

- `case_id`
- `source`
- `document_id`
- `document_text`
- `question`
- `expected_answer`
- `supporting_evidence`
- `answer_anchor`
- `category`

`datasets/squad_style_sample.jsonl` is the committed offline smoke-test dataset.
`datasets/squad_subset.jsonl` can be generated from SQuAD when Hugging Face
`datasets` and internet access are available.
`datasets/nq_subset.jsonl` can be generated from a Natural Questions style
dataset when Hugging Face `datasets` and internet access are available.

## Prepare SQuAD Subset

```bash
uv run python evals/document_qa/prepare_squad_subset.py --limit 20
```

If the dataset cannot be prepared, the script exits gracefully with a clear
message.

## Prepare Natural Questions Subset

SQuAD is a clean span-QA sanity benchmark and is useful for checking basic
document retrieval. Natural Questions is more realistic user-style document QA.
In this project it is used in a filtered, single-hop form: the current metric is
retrieval hit@k, not final answer quality.

The NQ adapter tries configured Hugging Face NQ-style datasets and writes rows
to the same JSONL schema used by the rest of this directory:

```bash
uv run python evals/document_qa/prepare_nq_subset.py --limit 200
```

You can override the dataset if needed:

```bash
uv run python evals/document_qa/prepare_nq_subset.py \
  --dataset-name sjhallo07/natural_questions \
  --split train \
  --limit 200
```

Current recommended benchmark scale:

- 20-50 examples for smoke tests
- 200 examples for presentation/development
- 500 examples for a stronger internal check

The full Natural Questions dataset is not needed for this project stage.

## Run Retrieval Eval

Use LangChain-Chroma retrieval:

```bash
uv run python evals/document_qa/run_document_qa_eval.py \
  --context-mode langchain_chroma \
  --retrieval-scope corpus \
  --top-k 3
```

`--retrieval-scope isolated` indexes only the current case document and is useful
as a smoke test. `--retrieval-scope corpus` indexes all dataset documents into
one temporary corpus and is the meaningful retrieval benchmark because it
includes distractor documents.

The runner also supports `document_text` and `supporting_evidence` placeholder
contexts for scaffold checks, but those are not retrieval benchmarks.

## Compare Modes

The custom keyword/vector/hybrid RAG stack has been removed. The comparison
runner now defaults to the single real document-memory backend:

```bash
uv run python evals/document_qa/compare_retrieval_modes.py \
  --dataset evals/document_qa/datasets/squad_style_sample.jsonl \
  --retrieval-scope corpus \
  --top-k 5
```

## Hit@K Curves

```bash
uv run python evals/document_qa/compare_topk_curves.py \
  --dataset evals/document_qa/datasets/squad_subset.jsonl \
  --modes langchain_chroma \
  --retrieval-scope corpus \
  --top-k-values 1 3 5 10
```

Run the same hit@k curve over a prepared Natural Questions subset:

```bash
uv run python evals/document_qa/compare_topk_curves.py \
  --dataset evals/document_qa/datasets/nq_subset.jsonl \
  --modes langchain_chroma \
  --retrieval-scope corpus \
  --top-k-values 1 3 5 10
```

The table reports:

- `ctx_evidence`
- `ctx_anchor`
- `ctx_expected`

## Answer Modes

Oracle mode is the default:

```bash
uv run python evals/document_qa/run_document_qa_eval.py \
  --context-mode langchain_chroma \
  --answer-mode oracle
```

Oracle answers copy `expected_answer`, so answer metrics are sanity checks and
retrieval metrics are the meaningful signal.

Model answer mode sends retrieved contexts to the configured model:

```bash
uv run python evals/document_qa/run_document_qa_eval.py \
  --dataset evals/document_qa/datasets/squad_subset.jsonl \
  --context-mode langchain_chroma \
  --retrieval-scope corpus \
  --top-k 3 \
  --answer-mode model \
  --limit 5
```

Model mode requires the configured OpenAI-compatible endpoint, such as Ollama.

## RAGAS-Compatible Export

Export rows without requiring RAGAS:

```bash
uv run python evals/document_qa/run_document_qa_eval.py \
  --dataset evals/document_qa/datasets/squad_subset.jsonl \
  --context-mode langchain_chroma \
  --retrieval-scope corpus \
  --top-k 3 \
  --answer-mode model \
  --limit 10 \
  --export-ragas-jsonl evals/document_qa/outputs/ragas_sample.jsonl
```

Optional RAGAS execution is separate:

```bash
uv run python evals/document_qa/run_ragas_eval.py \
  --input evals/document_qa/outputs/ragas_sample.jsonl
```

If RAGAS is unavailable, the runner prints a clear message. RAGAS is most
meaningful with `--answer-mode model`.

## LangChain Baseline

`langchain_baseline.py` is an eval-only experimental baseline that can use
LangChain vector stores such as Chroma or FAISS. It does not change the
production pipeline, which already uses `LangChainChromaRetriever` through the
project’s `RetrieverDispatcher`, `MemoryCandidate`, and `ContextPacket` flow.

## Limitations

- No PDF parsing pipeline beyond the optional local file loader.
- No production document upload UI yet.
- No semantic reranker yet.
- No required RAGAS dependency.
- Natural Questions is currently filtered to single-hop answer-in-context cases.
- HotpotQA and multi-hop retrieval/reasoning evaluation are future work.
- Normal pytest does not require internet, Ollama, Chroma downloads, or model
  generation.
