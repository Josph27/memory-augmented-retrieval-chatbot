# Repository garbage audit

This audit records the conservative cleanup decisions for the university-project
repository. It is intentionally narrow: generated artifacts and local runtime
data are preserved, and architecture-bearing code is left in place unless it is
provably unreachable.

## Scope

Inspected entry points included:

- `app.py` and Chainlit lifecycle callbacks
- `src/chat_service.py` and `src/agents/coordinator_agent.py`
- Native and LangGraph orchestration paths
- retrieval dispatch and typed `MemoryCandidate` sources
- Product Behavior browser/evaluation entry points
- documented script and evaluation entry points
- tracked and ignored artifact/runtime paths

The cleanup does not touch MAB or LongMemEval definitions, generated benchmark
artifacts, SQLite/Chroma runtime state, uploaded files, Product Behavior result
archives, or local caches.

## Findings

| Item | Classification | Decision | Rationale |
| --- | --- | --- | --- |
| `src/retrieval/current_chat_chunk_retriever.py` | safe to remove | removed | Placeholder class returned `[]`, was not imported, was not exported, and was not registered in `RetrieverDispatcher`. Current-chat raw access is handled by `CurrentChatSpanRetriever` / `RecentMessagesRetriever`. |
| `src/retrieval/previous_chat_retriever.py` | safe to remove | removed | Placeholder class returned `[]`, was not imported, was not exported, and was not registered in `RetrieverDispatcher`. Previous-chat access is handled by `PreviousChatGistRetriever` plus raw-span expansion/direct raw retrieval. |
| `.gitignore` generated-output patterns | repository hygiene | kept | Ignores browser traces, Playwright reports, Product Behavior output, Chainlit cache/files, and other local generated data without deleting existing artifacts. |
| Tracked `artifacts/**` JSONL evidence | ambiguous / generated evidence | preserved | Some tracked artifacts appear to be historical evaluation evidence. They should be reviewed separately before deciding whether to move or untrack them. |
| `scripts/eval_memory.py` and diagnostic scripts | ambiguous / evaluation support | preserved | Script reachability may be manual/documented rather than imported. No strong evidence that these are dead. |
| CLI/evaluation `print(...)` calls | runtime CLI output | preserved | Most hits are intentional command-line reporting, benchmark output, or test diagnostics rather than stray debug prints. |
| Secret-like environment names | configuration placeholders | preserved | Searches found variable names and test placeholders, not exposed credential values. |
| Historical architecture documents | obsolete or superseded docs | preserved | Several documents overlap, but they contain useful design history. Consolidation should be a documentation task, not code garbage collection. |

## Reachability notes

The active retrieval spine is:

```text
RoutePlan / SourcePlan
-> RetrieverDispatcher
-> source-specific retrievers
-> MemoryCandidate[]
-> reranking / budgeting / selection
-> ContextPacket
```

`RetrieverDispatcher` currently registers:

- `recent_messages`
- `structured_memory`
- `document_memory`
- `current_chat_gist`
- `current_chat_span`
- `previous_chat_gist`
- `raw_message_span`

The removed placeholder modules were not part of this active registry and did
not provide fallback behavior.

## Proposed documentation cleanup for a future task

Keep a small canonical documentation set at the top level of `docs/`:

- `PROJECT_CONTEXT.md`
- `ARCHITECTURE_DECISION.md`
- `AGENT_CONTRACTS.md`
- `DEMO_RUNBOOK.md`
- `EVALUATION_PLAN.md`
- `CURRENT_EVIDENCE_AND_LIMITATIONS.md`
- `CODE_GARBAGE_AUDIT.md`

Then move older run reports, spike notes, and one-off diagnostics into a clearly
named archive such as `docs/archive/`, after checking that current README links
still point to canonical material.

## Remaining manual-review candidates

- Whether tracked generated artifacts under `artifacts/` should remain in Git.
- Whether historical validation reports should be archived.
- Whether older one-off evaluation scripts should be documented or removed.

No runtime database, document store, chat history, Chroma directory, benchmark
output, or uploaded file cleanup was performed.
