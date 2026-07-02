# Semantic Router v2

## Goal

Semantic Router v2 is a deterministic, typed routing baseline for the
explicitly selected LangGraph read-only pipeline. It converts a query into:

```text
intent
→ temporal scope
→ evidence contract
→ enabled typed-memory sources
→ bounded retrieval-query hints
```

It does not replace the production `RoutingAgent` or `RoutePlanner`.

## Why Query Augmentation Alone Was Not Enough

The teammate playground augmentation decomposed and rewrote queries after
routing. It preserved the original query, but did not emit typed intent,
temporal scope, source requirements, or evidence requirements. It could not
reliably activate raw-span sources, and generated wording could be unsafe for
exact quotation.

Router v2 rewrites the useful idea locally. Original and generated retrieval
queries are separate typed values. Generated variants are routing/retrieval
hints only; they are never user evidence or `MemoryCandidate.content`.

## Intent Labels

- `EXACT_QUOTE`
- `SAME_CHAT_RECALL`
- `PREVIOUS_CHAT_RECALL`
- `STRUCTURED_PREFERENCE_RECALL`
- `DOCUMENT_QA`
- `PROJECT_STATE_SUMMARY`
- `MEMORY_QA`
- `CASUAL_CHAT`

The baseline uses deterministic English and Chinese example patterns. It makes
no model call and is not a complete state-of-the-art semantic router.

## Temporal Scope

Temporal scope is independent of intent:

- `CURRENT_CHAT`
- `PREVIOUS_CHATS`
- `ANY_CHAT`
- `DOCUMENTS`
- `GLOBAL_STRUCTURED_MEMORY`
- `NONE`

This distinction lets an exact-quote intent retain the difference between
same-chat, previous-chat, and ambiguous historical wording.

## Evidence Contracts

The router emits a typed `EvidenceContract`.

For `EXACT_QUOTE`:

```text
requires_raw_span = true
must_not_answer_from_gist_only = true
allows_gist_orientation = true
```

For `DOCUMENT_QA`, document evidence is required. For structured preference
recall, structured-memory evidence is required.

The LangGraph spike validates the contract against candidates that actually
survive context budgeting. Retrieval alone is not enough.

## Intent to Source Plan Mapping

| Intent | Enabled sources |
|---|---|
| Exact quote, current chat | recent, current span |
| Exact quote, previous chat | recent, previous gist, raw span |
| Exact quote, ambiguous scope | recent, current span, previous gist, raw span |
| Same-chat recall | recent, current span |
| Previous-chat recall | recent, previous gist |
| Preference recall | recent, structured |
| Document QA | recent, document |
| Project state | recent, structured, previous gist |
| Unknown-scope memory QA | recent, structured, previous gist |
| Casual chat | recent only |

Gists remain lossy orientation. `current_chat_span` and
`raw_message_span` provide exact transcript evidence.

Routing separates `retrieval_need` (`none`, `possible`, `required`) from
`memory_scope` (`current_chat`, `previous_chat`, `durable`, `document`,
`unknown`). A factual memory question without explicit temporal wording uses
the bounded unknown-scope policy rather than being treated as casual. The MAB
adapter supplies only the non-case-specific `task_context="memory_qa"`; it does
not provide gold answers, expected sources, or candidate IDs.

## LangGraph Spike Integration

The spike opts in explicitly:

```python
build_langgraph_memory_pipeline(
    routing_agent=None,
    dispatcher=dispatcher,
    semantic_router=SemanticRouter(),
    use_semantic_router=True,
)
```

Router v2 adapts its typed result to the existing `RoutePlan`/`SourcePlan`
contract. Existing retrievers, gist expansion, reranking,
`ContextManagerAgent`, and `ContextPacket` remain authoritative.

## Demo Status

- Native production orchestration remains the default.
- Semantic Router v2 is used only when LangGraph Shadow or Demo is explicitly
  selected.
- The router itself is deterministic and makes no model call.
- Graph nodes remain read-only; outer turn persistence is unchanged.
- Generated retrieval variants remain hints and never become evidence.

## Limitations

- Classification is deterministic example matching, not embedding or
  model-based semantic classification.
- Language support is deliberately narrow (`en`, `zh`, `unknown`).
- The existing dispatcher accepts one query per source, so generated variants
  are currently preserved and traced as hints but are not fanned out into
  multiple retrieval calls.
- Direct `raw_message_span` lookup still needs explicit span provenance;
  previous-chat exact evidence normally arrives through gist expansion.
- Route confidence is heuristic and not calibrated.

## Next Steps

1. Expand production-like intent fixtures and ambiguity tests.
2. Add safe multi-query retrieval deduplication behind the spike.
3. Add a structured model backend with timeout, confidence, and deterministic
   fallback.
4. Add an evidence-contract-aware abstention comparison against production.
5. Consider production integration only after route and ContextPacket parity
   tests pass.
