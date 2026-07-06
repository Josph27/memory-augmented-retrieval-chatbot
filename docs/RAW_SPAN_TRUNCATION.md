# Anchor-Preserving Raw Span Truncation

## Problem

Raw span retrieval could select the correct source range and still lose the
answer-bearing sentence. The previous formatter serialized the entire span and
then cut characters from the end. A query-centered message in the middle or
end could therefore disappear before context construction.

## Principle

```text
span proves exact content
```

Raw transcript formatting must preserve the message that made a span relevant.
Surrounding dialogue is useful context, but it is lower priority than the
evidential anchor.

## Anchor Definition

- `current_chat_span` uses its deterministic `matched_message_ids`.
- Gist-to-raw expansion uses the query-best source message in the provenance
  range.
- Direct `raw_message_span` lookup accepts `anchor_message_ids` in source-plan
  filters and otherwise selects the query-best message.
- Candidate provenance remains in `source_message_ids`; selected anchors are
  also recorded in `metadata.anchor_message_ids`.

No database schema change is required.

## Truncation Behavior

1. Return the complete chronological span when it fits.
2. Keep complete anchor messages when they fit.
3. Add nearby messages in distance order while respecting `max_chars`.
4. Trim surrounding messages before anchors.
5. Mark omitted earlier, intervening, and later messages explicitly.
6. If one anchor alone exceeds the limit, keep a query-relevant window inside
   that message and mark omitted anchor text.

The formatter is used only for `raw_message_span`, gist-expanded raw spans,
and `current_chat_span`. Document, structured, gist, and recent-message
formatting are unchanged.

## Tests

Focused tests cover:

- a middle answer message in a long gist provenance range;
- a matched current-chat message under a small character cap;
- anchor preservation through `ContextManagerAgent` with a tight budget;
- a single overlong anchor with a distinctive middle token;
- unchanged non-raw candidate content.

## Limitations

- Character limits are not model-tokenizer limits.
- When several anchor messages cannot all fit, the strongest query-matching
  anchor is retained.
- This improves evidence preservation but does not solve multi-hop retrieval,
  reasoning, or live-model grounding.
