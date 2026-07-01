# MemoryAgentBench Adapter

This optional adapter evaluates incremental memory lifecycle behavior using
MemoryAgentBench-style records. It is an unofficial integration harness, not an
official benchmark implementation or leaderboard scorer.

## What It Exercises

For each example, the adapter:

1. creates isolated SQLite state;
2. replays each chunk as a user message with a neutral assistant acknowledgement;
3. calls the normal `ShortTermMemory.update_memory_if_needed` path after each chunk;
4. optionally invokes `ChatEndAction` between sessions;
5. asks benchmark questions through `CoordinatorAgent`;
6. captures routing, retrieved and expanded `MemoryCandidate` objects,
   `ContextPacket` evidence, provenance, and deterministic metrics.

SQLite remains the source of truth. The adapter does not preload gold answers
into structured memory. The benchmark route explicitly exposes relevant typed
memory sources, so current runs are classified as **production-like with
fixture-assisted routing**, not fully production-routed.

## Local Fixture

Tests and the default command use a tiny committed fixture and require no
internet, model API, Hugging Face download, or CrossEncoder download:

```bash
uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --answer-mode mock
```

Write a JSONL report with:

```bash
uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --answer-mode mock \
  --output reports/memory_agent_bench_fixture.jsonl
```

## External Data

Supply a local JSON or JSONL file with normalized fields:

```json
{
  "example_id": "case-1",
  "competency": "Accurate_Retrieval",
  "sessions": [
    {"session_id": "s1", "chunks": ["I prefer concise answers."]}
  ],
  "questions": ["How should you answer me?"],
  "answers": [["concisely"]]
}
```

The loader also accepts common aliases such as `id`, `ability`, `question`,
`answer`, and top-level `chunks`. Optional Hugging Face support is lazy and
requires installing `datasets`; the repository does not download or commit the
external benchmark.

## Answer Modes

`mock` mode uses deterministic gold-shaped answers so tests can evaluate memory
updates, retrieval, context evidence, and provenance offline. It marks
`generated_answer_grounding_tested=false`. Its answer score must not be cited as
model quality.

`model` mode is opt-in and uses the configured OpenAI-compatible model:

```bash
uv run python evals/memory_agent_bench/run_memory_agent_bench.py \
  --dataset /path/to/memory_agent_bench.jsonl \
  --answer-mode model \
  --output reports/memory_agent_bench_model.jsonl
```

Model mode permits normal LangMem extraction and reports answer metrics
separately. It can incur model latency and cost.

## Metrics and Limitations

The first adapter reports normalized exact/substring checks, whether gold text
appears in `ContextPacket` evidence, source coverage, and provenance presence.
It does not implement LLM-as-judge or claim official MemoryAgentBench scoring.

Mock mode uses a deterministic no-op structured extraction backend while still
calling the production memory-update orchestration. Chat-end gists and
gist-to-raw-span expansion use project components. Therefore it validates
lifecycle wiring but not LangMem extraction quality. Real model runs are
required to assess memory writing and generated-answer grounding.
