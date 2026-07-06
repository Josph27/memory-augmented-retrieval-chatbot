# MemoryAgentBench Real Subset Mock Run

## Environment

- Branch: `integration/playground-demo`
- Commit before compatibility edits: `ce4aef8`
- Dataset source: `ai-hyz/MemoryAgentBench` on Hugging Face
- Split: `Conflict_Resolution`
- Dataset rows requested/completed: 3/3
- Questions per row: 1
- Answer mode: mock
- Model grounding: not tested
- Internet/Hugging Face: available; unauthenticated Hub access succeeded
- External data handling: streamed through `datasets`; no benchmark dataset was
  copied into the repository

The official dataset exposes competency-named splits rather than a conventional
`test` split. Each row contains one long `context` string and parallel
`questions`/`answers` arrays. The adapter deterministically divided `context`
into bounded 4,000-character chunks for incremental replay.

## Commands Run

Baseline fixture:

```bash
uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --answer-mode mock \
  --output reports/memory_agent_bench_fixture.jsonl

head -n 3 reports/memory_agent_bench_fixture.jsonl
wc -l reports/memory_agent_bench_fixture.jsonl
```

Official schema and split inspection:

```bash
uv run python - <<'PY'
from datasets import get_dataset_config_names, get_dataset_split_names

name = "ai-hyz/MemoryAgentBench"
print(get_dataset_config_names(name))
print(get_dataset_split_names(name))
PY
```

Real subset:

```bash
uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --dataset-id ai-hyz/MemoryAgentBench \
  --split Conflict_Resolution \
  --limit 3 \
  --question-limit 1 \
  --answer-mode mock \
  --output reports/memory_agent_bench_real_subset_mock.jsonl

wc -l reports/memory_agent_bench_real_subset_mock.jsonl
head -n 5 reports/memory_agent_bench_real_subset_mock.jsonl
```

Verification:

```bash
uv run python -m compileall src tests evals
uv run ruff check .
uv run pytest
git diff --check
```

## Results

- Examples attempted/completed: 3/3
- Result rows written: 3, plus one JSONL summary row
- Competency observed: `Conflict_Resolution`
- Context chunks replayed: 7, 35, and 69
- Incremental memory-update path calls: 7, 35, and 69
- Mock structured-backend calls: 10, 66, and 134
- `ChatEndAction` calls: one per example
- WorkflowTrace errors: none
- ContextPacket sources observed: `previous_chat_gist`, `raw_message_span`
- Provenance present: 3/3
- Gold text present in ContextPacket evidence: 1/3
- Generated-answer grounding tested: false

All official rows selected for this run represented one session. Therefore,
there was no between-session transition inside an example, but the configured
session finalization path invoked `ChatEndAction` after each replayed session.

The question-turn pipeline completed in approximately 7.85 ms, 18.11 ms, and
21.20 ms respectively. These timings exclude Hugging Face download/streaming
and replay preparation; the main model call is deterministic and effectively
zero in mock mode.

## Sample Output Fields

Each result contains:

- `example_id`, `competency`, `session_count`, and `replayed_chunk_count`;
- question and gold answers;
- `mock_answer=true` and `generated_answer_grounding_tested=false`;
- route plan and active typed-memory sources;
- retrieved and post-expansion candidates;
- ContextPacket evidence summary and source coverage;
- provenance and stale-memory flags;
- memory-update and chat-end lifecycle counts;
- compact WorkflowTrace data, including timings, reranker data, context-manager
  budgets, prompt source, and errors;
- explicit notes that mock answer grounding was not tested.

## Interpretation

This run validates that the adapter can stream and normalize a small subset of
the real MemoryAgentBench dataset, replay bounded chunks incrementally, invoke
the project memory lifecycle, finalize sessions, run the CoordinatorAgent
question path, and export traceable JSONL results.

It does **not** validate live-model answer grounding. Mock predictions use the
gold answer deliberately, so their answer match rate is not meaningful.
The 1/3 evidence-containment result is only a small retrieval/context diagnostic.
This run is not an official MemoryAgentBench score or leaderboard claim.

## Issues Found

1. The official split names are `Accurate_Retrieval`, `Test_Time_Learning`,
   `Long_Range_Understanding`, and `Conflict_Resolution`; there is no `test`
   split.
2. Official rows use `context` rather than materialized `chunks` or `sessions`.
   The adapter now performs deterministic bounded chunking and records the
   generated chunk count.
3. A row can contain 100–200 questions. A separate `--question-limit` is needed
   for genuinely small dry runs.
4. Normal-turn mock no-op extraction repeatedly examines the same oldest
   unprocessed batch because `accepted=False` does not advance semantic
   processing state. `ChatEndAction` treats the no-op as valid and completes,
   but the repeated calls are inefficient.
5. Deterministic chat-end gist summaries retain only bounded orientation. For
   these conflict-resolution rows, only one of three gold answers survived
   retrieval and ContextPacket selection.
6. The benchmark-controlled route is fixture-assisted and should not be
   presented as validation of production RoutingAgent generalization.

## Next Steps

1. Run more `Conflict_Resolution` rows in mock mode with checkpointed reporting.
2. Add per-competency and per-source retrieval summaries before expanding to
   much larger `Accurate_Retrieval` or `Test_Time_Learning` contexts.
3. Decide whether valid mock no-op batches should be marked processed during
   replay to avoid repeated work, without changing production semantics.
4. Run a one-example real-model smoke test to evaluate LangMem extraction and
   generated-answer grounding separately.
5. Add task-aware scoring normalization only after aligning it with the
   official per-dataset metrics.
