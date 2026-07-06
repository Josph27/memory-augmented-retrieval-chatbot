# End-to-End Memory/RAG Scenarios

This integration harness runs controlled scenarios through the real
`CoordinatorAgent` orchestration path:

```text
RoutingAgent
-> RetrieverDispatcher
-> MemoryReranker
-> ContextManagerAgent
-> ContextPacket
-> answer model
-> WorkflowTrace
```

Each scenario uses an isolated temporary SQLite database. Structured memory,
previous-chat gist, and raw-message span scenarios use their real SQLite-backed
retrievers. Mock mode injects deterministic document and semantic-vector
backends so tests do not load embedding models, Chroma, or a live API.

## Run

Deterministic mock mode:

```bash
uv run python evals/e2e_scenarios/run_e2e_scenarios.py --mode mock
```

Export a report:

```bash
uv run python evals/e2e_scenarios/run_e2e_scenarios.py \
  --mode mock \
  --output reports/e2e_scenario_report.json
```

Optional configured model mode:

```bash
uv run python evals/e2e_scenarios/run_e2e_scenarios.py \
  --mode model \
  --limit 2
```

Model mode requires `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `MODEL_NAME`. It
exits with a clear skip reason when configuration is missing.

## Coverage

Controlled scenarios cover:

- document questions
- exact structured-memory preferences
- semantic/hybrid long-term-memory retrieval
- previous-chat gist retrieval
- raw-span provenance
- distractor context with abstention
- hybrid reranker ordering

Reported metrics:

- `expected_source_present`
- `expected_context_included`
- `reranker_top_source_correct`
- `answer_contains_expected`
- `forbidden_claim_violations`
- `abstain_correctness`
- `scenario_pass_rate`

The JSON report includes active sources, source plans, retrieved candidates,
reranked candidates, ContextPacket sections/messages, answer text, and
WorkflowTrace metadata.

## Relationship to Other Tests

- Component unit tests isolate individual classes and failure modes.
- Multi-source retrieval eval checks source selection and retrieval without
  running the full coordinator or grading answers.
- Generated-answer eval grades controlled answers from prepared contexts but
  does not build those contexts through the runtime coordinator.
- This harness connects the major layers in one isolated integration flow.

## Limitations

These are small controlled regression scenarios. Mock document/vector adapters
do not measure production Chroma retrieval quality, and fake answers do not
measure real model quality. This harness complements rather than replaces
SQuAD/NQ retrieval benchmarks, structured-memory lifecycle evaluation,
LongMemEval/PerLTQA/LoCoMo-style benchmarks, or RAGAS/ARES evaluation.
