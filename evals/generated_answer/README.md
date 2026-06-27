# Generated-Answer Memory/RAG Eval

This eval checks whether retrieved memory/context supports a correct, grounded
answer. It is an eval-only scaffold and does not change the chatbot runtime.

## Dataset Schema

Each JSONL row supports:

- `case_id`
- `task_type`
- `query`
- `setup_fixture` or future fixture references
- `expected_sources`
- `expected_answer_contains`
- `forbidden_answer_contains`
- `should_abstain`
- `gold_answer`
- `gold_evidence`
- `benchmark_name`
- `split`
- `notes`

Controlled cases may also include `mock_answer`. Retrieved context fixtures are
stored under `setup_fixture.retrieved_contexts` with `source`, `content`, and
optional provenance metadata.

This shape is intended to support later adapters:

- SQuAD/Natural Questions subsets can map question, document chunks, answer,
  and evidence into document-QA cases.
- LongMemEval/PerLTQA-style cases can map long-term memory operations,
  questions, expected answers, and evidence into structured-memory cases.
- LoCoMo-style episodic cases can map session summaries, previous-chat gists,
  raw spans, and answers into episodic-memory cases.

## Modes

Deterministic mock mode:

```bash
uv run python evals/generated_answer/run_generated_answer_eval.py --mode mock
```

Optional configured model mode:

```bash
uv run python evals/generated_answer/run_generated_answer_eval.py --mode model
```

Model mode uses the existing OpenAI-compatible model configuration and grounded
document-QA prompt. It exits clearly when required configuration is missing.

Replay previously generated answers:

```bash
uv run python evals/generated_answer/run_generated_answer_eval.py \
  --mode replay \
  --replay-answers path/to/answers.jsonl
```

Replay rows use:

```json
{"case_id": "document_grounded_qa", "answer": "LangChain-Chroma is preferred."}
```

Export a JSON report:

```bash
uv run python evals/generated_answer/run_generated_answer_eval.py \
  --mode mock \
  --output reports/generated_answer_eval.json
```

## Metrics

- `answer_contains_expected`
- `forbidden_claim_violations`
- `abstain_accuracy`
- `expected_source_used`
- `retrieved_context_used`
- `overall_case_pass_rate`

## Relationship to Other Evals

- Document retrieval hit@k evaluates whether answer-bearing document chunks are
  retrieved.
- Structured memory lifecycle eval evaluates ADD, NOOP, UPDATE, RETRIEVE, and
  ABSTAIN memory behavior.
- Multi-source retrieval eval evaluates source selection and retrieval without
  grading generated answers.
- This eval grades controlled answers against expected content, forbidden
  claims, source use, retrieved evidence, and abstention.

## Limitations

This is a small controlled regression benchmark. It is not a substitute for
full LongMemEval, PerLTQA, LoCoMo, RAGAS, or ARES evaluation. The internal cases
provide end-to-end sanity checks while keeping the schema compatible with
future public-benchmark subset adapters.
