# Gist-to-Raw Window Selection

## Problem

A retrieved gist can cover many source messages while raw evidence must remain
bounded. The expander previously merged both overlapping and merely adjacent
gist ranges, then selected one contiguous 12-message window around the best
lexical match. Several adjacent 80-message gist segments could therefore
collapse into one large range and produce only one raw window.

That behavior reduced source coverage and removed the identity of individual
parent gists.

## Selection Policy

For each retrieved gist provenance segment:

1. include every message when the segment fits `max_messages`;
2. otherwise score messages by deterministic query-term overlap;
3. choose the strongest query-matching message;
4. take a bounded contiguous window around that message;
5. preserve chronological order;
6. pass the selected anchor to anchor-preserving character truncation.

Overlapping gist ranges are still merged and deduplicated. Adjacent,
non-overlapping gist segments now remain independent so each can contribute one
bounded raw candidate. Reranking and context budgeting still decide which
candidates reach `ContextPacket`.

The default remains 12 messages and 4,000 characters per expanded span.

## Anchor and Provenance Handling

Expanded candidates retain:

- source chat ID;
- original start/end message IDs;
- included source message IDs;
- parent gist ID/source;
- query-selected anchor message IDs.

No production selection logic uses benchmark gold answers. Query relevance and
persisted gist provenance are the only runtime signals.

## Boundedness

The policy does not expand an entire long chat:

- each parent segment produces at most one `max_messages` window;
- overlapping ranges are deduplicated;
- character formatting remains capped;
- `ContextBudgetAllocator` still enforces per-source and total limits.

Keeping adjacent segments independent can create more raw candidates when many
gists are retrieved. Existing source limits, reranking, and context budgets
bound prompt inclusion.

## Diagnostics

Each expanded raw candidate records bounded metadata:

- `parent_gist_id` / `parent_gist_ids`;
- `provenance_message_count`;
- `included_message_ids` (capped at 20);
- `omitted_message_ids_count`;
- `anchor_message_ids`;
- `selection_reason`;
- `window_char_count`.

Candidate `source_message_ids` continue to identify every message in the
selected window.

## MemoryAgentBench Miss Diagnosis

The targeted `Test_Time_Learning` miss was
`recsys_redial_full-row-1`, gold label `7008`.

- Gold appeared once in replay message `2421`.
- That message belonged to gist segment `2401–2480`.
- The retrieved top-eight gists did not include that segment.
- Retrieved raw windows therefore could not cover message `2421`.

This was primarily a parent-gist retrieval miss, not character truncation and
not a bounded-window miss inside a retrieved parent. The adjacent-range fix
does not claim to solve that specific case. It prevents a separate loss mode
where multiple retrieved adjacent gists were collapsed before expansion.

## Tests

Focused tests verify:

- all messages survive for small provenance;
- a query-relevant near-end message is selected instead of the prefix;
- overlapping ranges still merge;
- adjacent ranges produce independent query-centered windows;
- diagnostics remain bounded.

## Limitations

- This remains single-window retrieval per gist segment.
- It does not retrieve an omitted parent gist.
- It does not assemble distant multi-hop evidence.
- It does not use benchmark gold answers in production.
- It does not validate live-model answer grounding.
