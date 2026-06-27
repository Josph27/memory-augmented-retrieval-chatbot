# Multi-Source Retrieval Eval

This eval checks whether the system selects and retrieves from the right memory
source. It is retrieval/source-selection only; it does not grade final LLM answer
quality.

It differs from the other evals:

- Document QA hit@k eval checks whether document chunks contain expected
  answer/evidence text.
- Structured memory lifecycle eval checks ADD, NOOP, UPDATE, RETRIEVE, and
  ABSTAIN behavior for long-term structured memory.
- Model-answer/RAGAS-style eval checks generated answers and faithfulness when
  model mode is enabled.

This eval covers source labels such as:

- `recent_messages`
- `structured_memory`
- `document_memory`
- `previous_chat_gist`
- `raw_message_span`
- abstain/no relevant memory

Run:

```bash
uv run python evals/multi_source_retrieval/run_multi_source_retrieval_eval.py --mode mock
```

Export a trace report:

```bash
uv run python evals/multi_source_retrieval/run_multi_source_retrieval_eval.py \
  --mode mock \
  --output reports/multi_source_retrieval_eval.json
```

Mock mode uses deterministic fixture candidates and does not call Chainlit, a
cluster model, Chroma, or any live API.
