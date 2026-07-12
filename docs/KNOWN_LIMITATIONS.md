# Known limitations

This project is a practical-course prototype. The following limitations are
current and intentional unless otherwise noted.

## Product and identity

- The app uses a fixed local user identity.
- Multi-user authorization isolation is not implemented.
- Ended chats are retained and readable, but there is no user-facing archive or
  deletion workflow.
- There is no general memory conflict-resolution UI.

## Operations and consistency

- Upload idempotency is guarded, but there is no unified operation key across
  every possible write path.
- Document upload locks are process-local.
- There is no background reconciliation job for stale document states.
- There is no coordinated automatic deletion of Chroma chunks when document
  metadata is removed or superseded.

## Orchestration

- In `langgraph_demo`, Native fallback preparation performs duplicate
  read-only retrieval work before the graph result becomes authoritative.
- Native remains necessary as a fallback and diagnostic path.

## Retrieval and answer quality

- Broad whole-document summarization is limited by single-pass retrieval and
  context selection; there is no map-reduce or hierarchical summarizer.
- Multi-hop reasoning and temporal event reasoning are not fully solved.
- MAB and LongMemEval runs show quality weaknesses in retrieval, context
  selection, and answer use on hard held-out cases.
- LongMemEval support is a pilot adapter, not an official leaderboard scorer.
- MAB and LongMemEval mainly test conversational memory over replayed histories.
  They should not be used as evidence that uploaded-document RAG is strong or
  weak.
- The current document QA evidence is a smaller subsystem/regression signal,
  not a full broad RAG benchmark.

## Advanced configuration

- `DOCUMENT_RETRIEVAL_MODE` is documented as a config surface, but
  `langchain_chroma` is the only canonical document backend. Other values are
  not a supported product mode.
- Some configuration names are retained as compatibility seams rather than
  polished public API. Examples include `SUMMARY_BATCH_SIZE`,
  `LANGCHAIN_CHUNK_SIZE`, and `LANGCHAIN_CHUNK_OVERLAP`. They should be
  deprecated or folded into the canonical names in a later cleanup pass after
  affected scripts/tests are updated.
- `STRUCTURED_MEMORY_RETRIEVAL_MODE=vector` and `hybrid` are advanced paths.
  The default `sqlite` path remains the reliable, canonical structured-memory
  retrieval behavior.
- `RERANKER_MODE=cross_encoder`, `hybrid`, and `llm` are ablation/diagnostic
  modes. CrossEncoder reranking improved context inclusion in a small ablation
  but did not improve first-stage candidate recall and was much slower, so it is
  not enabled by default.
- `ROUTING_MODE=semantic_full` adds an experimental deterministic semantic
  expansion layer over the rule router. It is useful for ambiguous document and
  memory-reference phrasing, but it is still default-off and should be evaluated
  before any demo switch.
- `ROUTING_MODE=semantic` and `hybrid_semantic` expose the existing Semantic
  Router v2 through the live `RoutingAgent` interface for experiments. They are
  not the canonical default and should be treated as validation targets before
  any production/demo switch.
- `ROUTING_MODE=llm` and `hybrid` use structured-output LLM routing and remain
  diagnostics because they add model-call variance to routing.
- `ORCHESTRATION_MODE=native` and `langgraph_shadow` remain useful diagnostics,
  but `langgraph_demo` is the documented live mode.

## Evaluation

- Product Behavior has two documented remaining failures:
  `PB-PERSIST-005` and `PB-FAIL-010`.
- Browser E2E validation requires local browser and localhost port access.
  Restricted sandboxes can block those tests before application startup.
