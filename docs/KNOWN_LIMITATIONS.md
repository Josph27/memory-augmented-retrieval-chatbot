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

## Evaluation

- Product Behavior has two documented remaining failures:
  `PB-PERSIST-005` and `PB-FAIL-010`.
- Browser E2E validation requires local browser and localhost port access.
  Restricted sandboxes can block those tests before application startup.
