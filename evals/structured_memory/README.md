# Structured Memory Evaluation

This directory contains small deterministic benchmarks for structured long-term
memory.

The current runner evaluates cross-chat memory wiring and a small memory
lifecycle mini benchmark:

```text
Chat 1 messages
-> fake LangMem extraction output
-> ShortTermMemory.update_memory_if_needed
-> SQLite long_term_memories
-> StructuredMemoryRetriever in Chat 2
-> deterministic scoring
```

It does not call a live model. The extraction output is supplied by the dataset
so the benchmark focuses on storage, retrieval, and answer-use checks.

Run:

```bash
uv run python evals/structured_memory/run_structured_memory_eval.py --mode mock
uv run python evals/structured_memory/run_structured_memory_eval.py \
  --dataset evals/structured_memory/datasets/lifecycle_sample.jsonl \
  --mode mock
```

Metrics:

- `memory_write_success`
- `memory_retrieval_hit`
- `answer_uses_memory`
- `answer_avoids_false_memory`
- `write_action_correct`
- `noop_correct`
- `update_correct`
- `retrieval_hit`
- `answer_uses_correct_memory`

Lifecycle cases:

- ADD durable preference or constraint
- NOOP temporary irrelevant fact
- UPDATE changed preference
- RETRIEVE memory in a new chat
- ABSTAIN when no memory exists

Limitations:

- Mock mode does not evaluate LangMem extraction quality.
- Oracle answers are deterministic placeholders, not generated model answers.
- Full LongMemEval / PerLTQA / LoCoMo-style evaluation remains future work.
