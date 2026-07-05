# Product Behavior Benchmark Baseline

- Run ID: `product_behavior_baseline_20260705_v2`
- Cases: **50**
- Passed: **23**
- Failed: **19**
- Errors: **0**
- Browser not executed: **8**
- Overall pass rate: **46.0%**
- Runtime: **415.935 ms**

## Category results

| Category | Passed | Total | Not executed | Rate |
|---|---:|---:|---:|---:|
| documents | 3 | 15 | 1 | 20.0% |
| failures | 4 | 10 | 0 | 40.0% |
| lifecycle | 6 | 10 | 4 | 60.0% |
| navigation | 5 | 8 | 3 | 62.5% |
| persistence | 5 | 7 | 0 | 71.4% |

## Reliability metrics

- Deterministic: 23/50 (executed 42, rate 46.0%)
- Browser E2E: 0/8 (executed 0, rate n/a)
- LLM-dependent: 0/0 (executed 0, rate n/a)
- Scope isolation: 7/14 (executed 14, rate 50.0%)
- Idempotency: 3/5 (executed 5, rate 60.0%)
- No collateral damage: 8/16 (executed 14, rate 50.0%)
- LLM pass@1 / pass^3: not applicable; this baseline made no model calls.

## Failed cases by root cause

### Browser E2E was implemented but no browser execution was requested.

- `PB-DOC-002` (not_executed): {"browser_available": false}
- `PB-LIFE-001` (not_executed): {"browser_available": false}
- `PB-LIFE-005` (not_executed): {"browser_available": false}
- `PB-LIFE-006` (not_executed): {"browser_available": false}
- `PB-LIFE-009` (not_executed): {"browser_available": false}
- `PB-NAV-001` (not_executed): {"browser_available": false}
- `PB-NAV-003` (not_executed): {"browser_available": false}
- `PB-NAV-008` (not_executed): {"browser_available": false}

### Document retrieval has no filename/reference resolver or allowed-document scope.

- `PB-DOC-005` (failed): {"supported": false}
- `PB-DOC-010` (failed): {"supported": false}

### The authoritative Chroma document path has no persisted chat-document association.

- `PB-DOC-004` (failed): {"supported": false}
- `PB-PERSIST-006` (failed): {"supported": false}

### Document ingestion indexes content but has no persisted document lifecycle/status registry.

- `PB-DOC-001` (failed): {"chunk_count": 1, "index_calls": 1, "indexed": true, "persisted_status": null}

### Document retrieval has no controlled zero-result retry policy.

- `PB-DOC-013` (failed): {"supported": false}

### LangChainChromaRetriever ignores chat_id and has no allowed document ID filter.

- `PB-DOC-012` (failed): {"supported": false}

### Lexical routing activates document memory, but no active/latest document ID is resolved.

- `PB-DOC-008` (failed): {"document_routes": {"look at that report": false, "the file I uploaded": true, "the uploaded document": true}, "resolved_document_ids": []}

### Message execution and End Chat do not share a transactional or per-chat concurrency guard.

- `PB-FAIL-008` (failed): {"supported": false}

### No product document registry exists to detect multi-document ambiguity.

- `PB-DOC-011` (failed): {"supported": false}

### RetrieverDispatcher propagates source exceptions instead of returning a recoverable typed error.

- `PB-FAIL-002` (failed): {"exception": "retrieval failed", "false_evidence": 0, "message_delta": 0}

### The UI reports an indexing error, but no persisted document record can transition to Failed.

- `PB-FAIL-001` (failed): {"persisted_failed_status": false, "truthful_ui_error": true}

### The current product has one fixed local-user identity and no per-user chat ownership.

- `PB-PERSIST-005` (failed): {"supported": false}

### The project intentionally has no Chinese routing capability.

- `PB-DOC-009` (failed): {"supported": false}

### The router has no conversational document-reference resolver for 'it'.

- `PB-DOC-007` (failed): {"enabled_sources": ["recent_messages", "structured_memory"], "intent": "general_question"}

### There is no cross-operation idempotency key covering messages, documents, memories, and chunks.

- `PB-FAIL-010` (failed): {"database_mentions_idempotency": false, "message_idempotency_key": false}

### There is no persisted Ready/Failed document lifecycle available before generation.

- `PB-DOC-015` (failed): {"supported": false}

### There is no persisted document readiness barrier shared across concurrent UI events.

- `PB-FAIL-009` (failed): {"supported": false}

### Timeout handling is not a typed product state; OpenAI errors become persisted assistant error text and generic timeouts may propagate.

- `PB-FAIL-003` (failed): {"catches_openai_error": true, "typed_failed_answer_status": false, "user_persisted_before_generation": true}

## Untestable gaps

- The eight browser scenarios are implemented as explicit E2E cases but were not executed because no browser harness was available.
- No real-model scenarios were included in this baseline, so pass@1 and pass^3 are not applicable.
- Cross-user isolation cannot be exercised because the product exposes one fixed local user and stores no chat owner.
- Document readiness, association, ambiguity, and scoped retrieval cannot be fully exercised because the authoritative Chroma path has no product document registry.
- Send/End and Upload/Send race invariants lack a shared production concurrency seam; these remain capability failures rather than simulated passes.

## Recommended next fix order

1. Add ownership and scope enforcement where data leakage is possible.
2. Define atomic Send/End behavior and per-chat lifecycle concurrency.
3. Add a document lifecycle registry with Ready/Failed status and chat association.
4. Pass explicit allowed document IDs into retrieval.
5. Add filename, pronoun, latest-document, and ambiguity resolution.
6. Add typed retrieval/answer failure states and retry idempotency.
7. Execute the frozen browser suite and address visual polish last.

## Case inventory

| Case | Category | Layer | Status |
|---|---|---|---|
| `PB-DOC-001` | documents | repository/service | failed |
| `PB-DOC-002` | documents | browser E2E | not_executed |
| `PB-DOC-003` | documents | Chainlit handler/data-layer | passed |
| `PB-DOC-004` | documents | repository/service | failed |
| `PB-DOC-005` | documents | repository/service | failed |
| `PB-DOC-006` | documents | repository/service | passed |
| `PB-DOC-007` | documents | repository/service | failed |
| `PB-DOC-008` | documents | repository/service | failed |
| `PB-DOC-009` | documents | repository/service | failed |
| `PB-DOC-010` | documents | repository/service | failed |
| `PB-DOC-011` | documents | repository/service | failed |
| `PB-DOC-012` | documents | repository/service | failed |
| `PB-DOC-013` | documents | repository/service | failed |
| `PB-DOC-014` | documents | repository/service | passed |
| `PB-DOC-015` | documents | repository/service | failed |
| `PB-FAIL-001` | failures | Chainlit handler/data-layer | failed |
| `PB-FAIL-002` | failures | repository/service | failed |
| `PB-FAIL-003` | failures | repository/service | failed |
| `PB-FAIL-004` | failures | Chainlit handler/data-layer | passed |
| `PB-FAIL-005` | failures | Chainlit handler/data-layer | passed |
| `PB-FAIL-006` | failures | Chainlit handler/data-layer | passed |
| `PB-FAIL-007` | failures | Chainlit handler/data-layer | passed |
| `PB-FAIL-008` | failures | repository/service | failed |
| `PB-FAIL-009` | failures | repository/service | failed |
| `PB-FAIL-010` | failures | repository/service | failed |
| `PB-LIFE-001` | lifecycle | browser E2E | not_executed |
| `PB-LIFE-002` | lifecycle | Chainlit handler/data-layer | passed |
| `PB-LIFE-003` | lifecycle | Chainlit handler/data-layer | passed |
| `PB-LIFE-004` | lifecycle | repository/service | passed |
| `PB-LIFE-005` | lifecycle | browser E2E | not_executed |
| `PB-LIFE-006` | lifecycle | browser E2E | not_executed |
| `PB-LIFE-007` | lifecycle | Chainlit handler/data-layer | passed |
| `PB-LIFE-008` | lifecycle | repository/service | passed |
| `PB-LIFE-009` | lifecycle | browser E2E | not_executed |
| `PB-LIFE-010` | lifecycle | repository/service | passed |
| `PB-NAV-001` | navigation | browser E2E | not_executed |
| `PB-NAV-002` | navigation | Chainlit handler/data-layer | passed |
| `PB-NAV-003` | navigation | browser E2E | not_executed |
| `PB-NAV-004` | navigation | repository/service | passed |
| `PB-NAV-005` | navigation | Chainlit handler/data-layer | passed |
| `PB-NAV-006` | navigation | Chainlit handler/data-layer | passed |
| `PB-NAV-007` | navigation | Chainlit handler/data-layer | passed |
| `PB-NAV-008` | navigation | browser E2E | not_executed |
| `PB-PERSIST-001` | persistence | repository/service | passed |
| `PB-PERSIST-002` | persistence | repository/service | passed |
| `PB-PERSIST-003` | persistence | repository/service | passed |
| `PB-PERSIST-004` | persistence | Chainlit handler/data-layer | passed |
| `PB-PERSIST-005` | persistence | repository/service | failed |
| `PB-PERSIST-006` | persistence | repository/service | failed |
| `PB-PERSIST-007` | persistence | repository/service | passed |

## Interpretation

- Browser cases are not treated as passing when browser execution is unavailable.
- Unsupported product capabilities remain failed rather than weakening expectations.
- This run used deterministic repository/service and Chainlit data-layer probes only.
- No production behavior, MAB, LongMemEval, or model configuration was changed.
