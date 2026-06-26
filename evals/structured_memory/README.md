# Structured Memory Evaluation

This directory contains small deterministic benchmarks for structured long-term
memory.

The current runner evaluates cross-chat memory wiring:

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
```

Metrics:

- `memory_write_success`
- `memory_retrieval_hit`
- `answer_uses_memory`
- `answer_avoids_false_memory`

Limitations:

- Mock mode does not evaluate LangMem extraction quality.
- Oracle answers are deterministic placeholders, not generated model answers.
- Full LongMemEval / PerLTQA / LoCoMo-style evaluation remains future work.
