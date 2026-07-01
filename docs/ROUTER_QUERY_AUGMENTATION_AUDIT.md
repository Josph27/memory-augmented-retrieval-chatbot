# Router and Query Augmentation Audit

## Current Router Summary

### Facts from current code

The production default is deterministic rule routing:

```text
RoutingAgent(mode="rule")
→ RoutePlanner
→ QueryAnalyzer
→ RoutePlan / SourcePlan[]
```

`QueryAnalyzer` lowercases and normalizes whitespace, then performs substring
checks against fixed English phrase lists. It emits five coarse signals:

- current-chat recall;
- previous-memory recall;
- document question;
- decision question;
- task question.

`RoutePlanner` maps the highest-priority signal to one intent and context
profile. The default source policy is:

| Source | Default behavior |
|---|---|
| `recent_messages` | Always enabled |
| `structured_memory` | Always enabled |
| `document_memory` | Enabled for document-term matches |
| `previous_chat_gist` | Enabled only when its environment flag is true **and** a previous-memory phrase matches |
| `current_chat_span` | Always disabled unless a caller explicitly modifies the plan |
| `raw_message_span` | Always disabled unless a caller explicitly modifies the plan |
| `current_chat_gist` | Disabled |
| legacy gist aliases | Disabled |

The router supports `rule`, `llm`, and `hybrid` modes, but the optional LLM
schema contains only three booleans: recent, structured, and document memory.
Its conversion function returns `False` for every other source. Hybrid mode
preserves deterministic recent/structured decisions and lets the model decide
document memory; it is not a hybrid semantic router over all typed sources.

Fallback behavior is conservative: recent and structured memory remain enabled,
while document memory is disabled after a hard planner failure. Model errors,
invalid JSON, and low confidence fall back to the rule route.

### Offline query matrix

The current rule router produced:

| Query class | Observed intent | Enabled evidence sources |
|---|---|---|
| `Quote exactly what I said...` | `general_question` | recent, structured |
| `What exact phrase did I use...` | `general_question` | recent, structured |
| `What were my exact words...` | `general_question` | recent, structured |
| `How did I phrase...` | `general_question` | recent, structured |
| `Can you quote my earlier message...` | `current_chat_question` | recent, structured |
| Chinese quote/provenance examples | `general_question` | recent, structured |
| `What did I say earlier in this chat?` | `current_chat_question` | recent, structured |
| `What did we discuss last time?` | `previous_memory_question` | recent, structured; gist only if configured |
| preference recall | `general_question` | recent, structured |
| uploaded-report question | `document_question` | recent, structured, document |
| current task summary | `task_question` | recent, structured |
| casual chat | `general_question` | recent, structured |

This confirms that recognizing a memory-oriented profile does not currently
activate the exact evidence source needed for that profile.

## Current Router Limitations

1. Routing is deterministic substring classification by default. Context
   profiles are selected from those lexical signals.
2. There is no `EXACT_QUOTE` or provenance intent.
3. `RoutePlan` contains generic metadata and source filters, but no explicit
   evidence contract such as `requires_raw_span`.
4. Same-chat recall can be classified, but `current_chat_span` remains disabled.
5. Previous-chat recall can enable `previous_chat_gist` only behind a flag.
   `raw_message_span` remains disabled as a direct source; gist expansion can
   derive it only after a relevant gist is retrieved.
6. Preference recall works incidentally because structured memory is always on,
   not because the router recognizes a preference intent.
7. Document routing handles explicit English document terms reasonably, but its
   broad terms (`source`, `text`) can create false positives.
8. Project-state summaries receive a memory profile but no current-chat gist or
   span source.
9. Chinese and paraphrased provenance queries are not recognized.
10. LLM/hybrid routing cannot activate current spans, previous gists, or raw
    spans because those fields are absent from its structured output.

The current router can reliably separate explicit document wording and several
English memory/task phrases from casual chat. It cannot reliably distinguish
exact quote, semantic same-chat recall, semantic previous-chat recall,
preference recall, or multilingual variants.

## Quote / Provenance Failure Mode

The observed difference between these prompts is downstream, not routing:

```text
Quote exactly what I said about X.
What exact phrase did I use about X?
```

Both currently route to only `recent_messages` and `structured_memory`.
Neither enables `current_chat_span`, `previous_chat_gist`, or
`raw_message_span`.

When tests or diagnostic code explicitly provide a gist/raw candidate, the
deterministic reranker boosts `raw_message_span` for:

```text
exactly, exact words, quote, evidence, provenance, did i say
```

It does not include `exact phrase`, `wording`, or Chinese equivalents. This is
why “Quote exactly...” can rank an already-retrieved raw span more strongly.
The reranker cannot retrieve a missing source, so this boost does not repair the
production routing gap.

Current quote tests mostly prove component behavior after manually enabling a
span source:

- current-chat span retrieval preserves exact messages;
- gist candidates expand to raw spans;
- raw spans can outrank gists;
- raw evidence can reach ContextPacket.

`tests/test_routing_agent.py` explicitly asserts gist/raw sources are disabled
by default. There is no production routing test asserting that any quote
paraphrase activates a raw-capable source.

## Teammate Query Augmentation Findings

### Files inspected from `origin/playground-j`

- `src/agents/query_augmentation_agent.py`
- `src/routing/query_decomposer.py`
- `src/routing/semantic_expander.py`
- narrow wiring in `src/agents/coordinator_agent.py`
- construction/defaults in `src/chat_service.py`, `src/config.py`, and `app.py`
- `SubQuery`/WorkflowTrace changes in `src/core/contracts.py`
- design notes and test references

No files were checked out, merged, or copied.

### Component behavior

`QueryDecomposer`:

- calls the configured LLM;
- asks for one to three independent strings;
- returns `SubQuery(text=...)`;
- falls back to the original query for malformed JSON and selected exceptions;
- does not populate `intent` or `sources`.

`SemanticExpander`:

- makes a separate LLM call for every subquery;
- asks the model to append up to five search keywords;
- accepts arbitrary nonempty output longer than the input;
- returns the original subquery on exceptions;
- does not return structured keywords, entities, intent hints, confidence, or
  evidence requirements.

`QueryAugmentationAgent`:

- composes decomposition and expansion;
- returns an immutable `AugmentedQuery`;
- preserves the original string in `original`;
- returns rewritten text through `sub_queries`.

### Wiring findings

1. **Routing happens before augmentation.** The original query creates the
   `RoutePlan`; augmentation cannot improve the intent or evidence contract.
2. `SubQuery.sources` is empty because neither teammate component populates it.
3. The coordinator may detect document terms in an expanded query, but its
   `replace(sp, query=...)` operation does not set `enabled=True`. It therefore
   does not reliably activate a source that the original route disabled.
4. Augmented text is used as a retrieval query, while reranking still uses the
   original query. The original user message remains intact and augmentation is
   not inserted into ContextPacket as user evidence, which is a good property.
5. Candidate deduplication uses `record_id` without source in its key. Equal IDs
   from different typed sources can collide.
6. Augmentation is enabled by default in teammate `AppConfig` and
   `ChatService`. One turn can add one decomposition call plus up to three
   expansion calls before answer generation.
7. The augmenter depends only on the existing model wrapper and adds no major
   library dependency, but its model type is concrete rather than a small
   protocol.
8. There is no dedicated committed
   `tests/test_query_augmentation_agent.py`; the only test reference is a
   comment that augmentation may call a model.
9. The current branch version does define `AugmentedQuery` in the agent module.
   However, `WorkflowTrace` references `"AugmentedQuery | None"` from core
   contracts without defining/importing the type there. Resolving that
   annotation cleanly risks a core↔agent dependency cycle.
10. Semantic expansion can invent or alter wording. That is unsafe if an
    expanded query is later treated as the phrase to quote or as evidence.

The isolated modules do not write SQL or replace ContextBuilder/reranker.
However, the teammate integration changes CoordinatorAgent, contracts, config,
and default runtime behavior, so it is not a narrow drop-in.

## Reusability Assessment

**Classification: Useful idea only; rewrite locally.**

| Criterion | Assessment |
|---|---|
| Typed output | Partial: typed subqueries, but no typed hints/contracts |
| Original query preserved | Yes |
| Variants preserved separately | Partially, as rewritten subqueries |
| Intent/evidence hints | No |
| Entity extraction | No |
| Quote/provenance support | No explicit support |
| Multilingual guarantee | No |
| Direct SQL/context/reranker coupling | Modules: no; integration: broad coordinator changes |
| Dependency impact | Low |
| Offline determinism | No |
| Mockability/tests | Technically mockable, but concrete model typing and no focused tests |
| Safe default | No; teammate config enables it |
| Failure behavior | Partial; decomposition does not catch all model failures |

The useful ideas are:

- preserve the original query;
- represent variants explicitly;
- inject augmentation behind an interface;
- trace augmentation separately;
- use fallback to the original query.

The existing implementation should not be ported because it runs after routing,
does not produce source/evidence hints, adds multiple model calls, lacks focused
tests, and can semantically contaminate exact-quote retrieval.

## Recommended Router v2 Architecture

### Proposed flow

```text
User query
→ QueryAugmenter
→ IntentRouter / RoutePlanner
→ RoutePlan + EvidenceContract
→ RetrieverDispatcher(original query + safe variants)
→ gist→raw-span expansion
→ evidence-contract validation
→ MemoryReranker
→ ContextManagerAgent
→ ContextPacket
→ evidence-contract validation before answer
```

The smallest safe first implementation should be deterministic and default-off:

1. Add immutable query-analysis contracts in `src/routing/`, not in an agent
   module imported by `src/core/contracts.py`.
2. Implement a deterministic augmenter/classifier for explicit English and
   Chinese quote/provenance phrases.
3. Feed typed intent/evidence hints into a Router v2 adapter around the existing
   `RoutePlanner`; preserve Router v1 as the default.
4. Use `original_query` for user-message persistence, exact-evidence matching,
   reranking, and final prompt.
5. Use variants only for source selection and broad retrieval. Never store them
   as user messages or candidates.
6. For exact quote, use target/entity terms extracted conservatively from the
   original query when searching raw spans. Do not use model-injected wording as
   quoted content.
7. Validate that a raw candidate actually reaches ContextPacket. If not,
   abstain or state that exact wording cannot be verified.
8. Add optional model augmentation only after the deterministic path and
   evidence contracts are tested. It must have structured output, timeout,
   confidence threshold, and deterministic fallback.

This preserves `MemoryCandidate`, `RetrieverDispatcher`, gist expansion,
MemoryReranker, ContextManagerAgent, ContextPacket, and WorkflowTrace.

## Proposed AugmentedQuery Contract

```python
@dataclass(frozen=True)
class AugmentedQuery:
    original_query: str
    normalized_query: str
    variants: tuple[str, ...]
    intent_hints: tuple[str, ...]
    evidence_hints: tuple[str, ...]
    entities: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
```

Additional rules:

- `original_query` is immutable and always available.
- `variants` are deduplicated, bounded, and marked synthetic.
- deterministic hints record the matching policy/version in metadata;
- model variants, if later added, record model, confidence, and fallback;
- variants never become `MemoryCandidate.content`;
- variants never satisfy provenance or citation requirements.

Recommended intent labels:

```text
EXACT_QUOTE
SAME_CHAT_RECALL
PREVIOUS_CHAT_RECALL
STRUCTURED_PREFERENCE_RECALL
DOCUMENT_QA
PROJECT_STATE_SUMMARY
CASUAL_CHAT
```

Temporal scope should be represented separately when possible:
`CURRENT_CHAT`, `PREVIOUS_CHAT`, `AMBIGUOUS`, or `NOT_APPLICABLE`. Exact quote
and temporal scope are orthogonal; collapsing them into one intent loses useful
source-planning information.

## Proposed Intent → Source Plan Mapping

| Intent | Sources | Notes |
|---|---|---|
| `EXACT_QUOTE` + current scope | recent, `current_chat_span` | Raw current-chat transcript is mandatory |
| `EXACT_QUOTE` + previous scope | recent, `previous_chat_gist`; derived `raw_message_span` | Gist locates episode; expanded raw span proves wording |
| `EXACT_QUOTE` + ambiguous scope | recent, current span, previous gist; derived raw span | Bound limits; require raw evidence before answer |
| `SAME_CHAT_RECALL` | recent, current span, structured | Gist optional only as orientation |
| `PREVIOUS_CHAT_RECALL` | structured, previous gist; raw expansion when exactness requested | Previous gist requires its feature flag/availability |
| `STRUCTURED_PREFERENCE_RECALL` | structured, recent | SQLite remains source of truth |
| `DOCUMENT_QA` | document, recent | Require document provenance/citation |
| `PROJECT_STATE_SUMMARY` | recent, structured; future current gist/span if enabled | Do not enable current gist by default in first patch |
| `CASUAL_CHAT` | recent, structured current default | Avoid expensive span/document retrieval |

Direct `raw_message_span` retrieval currently expects provenance/range filters.
For previous-chat exact quotes, the practical path is:

```text
previous_chat_gist retrieval
→ GistRawSpanExpander
→ raw_message_span candidate
```

Simply enabling a filterless raw-span source is not sufficient.

## Proposed Evidence Contracts

```python
@dataclass(frozen=True)
class EvidenceContract:
    requires_raw_span: bool = False
    requires_document_citation: bool = False
    requires_structured_memory: bool = False
    allows_gist_orientation: bool = True
    must_not_answer_from_gist_only: bool = False
```

Recommended contracts:

| Intent | Contract |
|---|---|
| Exact quote | raw required; gist allowed for orientation; gist-only forbidden |
| Document QA | document citation required |
| Preference recall | structured memory required when answering from remembered preference |
| General episodic recall | gist allowed; raw optional unless wording/evidence requested |

Contract validation should inspect actual included ContextPacket candidates, not
only routed or retrieved sources. A retrieved raw span that is dropped by budget
does not satisfy `requires_raw_span`.

If a contract is unsatisfied:

- do not fabricate exact wording;
- answer that exact evidence is unavailable;
- optionally ask whether the user means the current or a previous chat;
- record the failure in WorkflowTrace.

## Test Plan

1. Augmentation preserves `original_query` byte-for-byte.
2. Deterministic augmentation maps all listed English quote paraphrases to
   `EXACT_QUOTE`.
3. Chinese quote/provenance phrases map to `EXACT_QUOTE`.
4. `What exact phrase did I use about X?` activates a raw-capable source plan.
5. Current-scope exact quote enables `current_chat_span`.
6. Previous-scope exact quote enables `previous_chat_gist` and permits derived
   `raw_message_span`.
7. Gist-only ContextPacket fails the exact-quote evidence contract.
8. Missing raw evidence produces abstention/insufficient-evidence trace rather
   than a quoted answer.
9. Casual chat does not activate span, gist, or document retrieval.
10. Document QA activates `document_memory` and requires document provenance.
11. Preference recall activates/retains `structured_memory`.
12. Project-state summary preserves current safe defaults until current gist is
    explicitly enabled.
13. Synthetic variants never appear as user messages or MemoryCandidate
    evidence.
14. Router v1 behavior remains unchanged when Router v2 is disabled.
15. Optional model augmentation falls back on missing model, timeout, malformed
    JSON, low confidence, unknown intents, or unknown sources.
16. Production-path acceptance test covers:
    Router v2→dispatcher→gist expansion/current span→reranker→budget→
    ContextPacket→contract validation.

Use a table-driven multilingual corpus rather than adding isolated phrase checks
throughout RoutePlanner and reranker.

## Implementation Risks

1. **Query contamination:** model expansion can invent words that later look
   like user wording. Keep original and synthetic text strictly separated.
2. **Latency:** teammate augmentation can make up to four extra model calls per
   turn. Start deterministic and default-off.
3. **Source explosion:** ambiguous quote routing may query current and previous
   history. Enforce limits and trace source costs.
4. **False confidence:** source activation does not prove evidence reached the
   prompt. Validate ContextPacket.
5. **Temporal ambiguity:** “earlier” may mean this chat or an older chat. Model
   this explicitly or ask clarification.
6. **Multilingual tokenization:** current span retrieval tokenizes only
   `[a-z0-9]+`; routing Chinese quote intent is not enough to retrieve Chinese
   evidence. A later Unicode-aware retriever update will be needed.
7. **Hybrid router mismatch:** the current LLM schema cannot express new typed
   sources/contracts. Do not call it Router v2 without extending and validating
   the schema.
8. **Contract compatibility:** adding required fields directly to RoutePlan can
   break many tests/fixtures. Prefer optional metadata or a wrapper decision
   initially, then migrate deliberately.
9. **Availability:** previous-chat gist retrieval is config-controlled and
   current gist stays default-off. Router v2 must distinguish requested source
   from available source.
10. **Teammate dedup bug:** never deduplicate solely by `record_id`; include
    source and provenance identity.

## Recommended Next Step

Implement one small, default-off commit:

```text
feat: add deterministic Router v2 query and evidence contracts
```

Scope:

- add local immutable `AugmentedQuery` and `EvidenceContract` contracts;
- add deterministic intent/evidence hint classification for the specified
  English and Chinese quote phrases;
- add a Router v2 adapter that maps only `EXACT_QUOTE` to existing raw-capable
  source plans;
- add trace output and table-driven tests;
- leave CoordinatorAgent and production defaults unchanged;
- do not add decomposition, LLM expansion, query variants, or multi-hop
  retrieval in the first commit.

After that passes, add a second production-path acceptance commit that validates
raw evidence reaches ContextPacket and enforces abstention when it does not.
Only then evaluate an optional structured LLM augmenter behind config.
