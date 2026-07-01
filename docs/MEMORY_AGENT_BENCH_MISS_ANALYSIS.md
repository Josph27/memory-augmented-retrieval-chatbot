# MemoryAgentBench Evidence Miss Analysis

## Run Context

- Dataset: official `ai-hyz/MemoryAgentBench`
- Split: `Conflict_Resolution`
- Rows: 3
- Questions per row: 1
- Answer mode: mock; generated-answer grounding was not tested
- Report:
  `reports/memory_agent_bench_real_subset_mock_diagnostic.jsonl`
- Branch: `integration/playground-demo`
- Commit before diagnostics: `a6e5ad5`
- Replay chunk bound: 4,000 characters
- Gist finalization: deterministic, at most 80 messages per gist
- Gist raw-span expansion: at most 12 messages and 4,000 formatted characters
- Routing: benchmark-controlled, fixture-assisted typed-source route
- Reranker: deterministic
- Structured memory in mock mode: recording no-op backend

The rerun added bounded adapter-only diagnostics: gold-bearing replay chunk and
message IDs, candidate text matches at each stage, raw-span provenance overlap,
dropped candidates, and a failure-stage classification.

## Summary

| Example | Chunks | Gold in replay? | Gist retrieved? | Raw span expanded? | Reranked high? | Budget kept? | Gold in ContextPacket? | Failure Stage |
|---|---:|---|---|---|---|---|---|---|
| `mh_6k-row-1` | 7 | Yes, chunk 4 / message 9 | Yes | Yes; IDs 1–12 covered message 9, but formatted text truncated it | Raw span rank 1 | Yes; no drops | No | Raw formatting/character truncation |
| `mh_32k-row-2` | 35 | Yes, chunk 6 / message 13 | Yes | Yes; IDs 51–62 covered the Bagratuni first hop, not message 13 | Raw span rank 1 | Yes; no drops | No | Distant second-hop evidence not selected |
| `mh_64k-row-3` | 69 | Yes; relevant IDs 33 and 71 | Yes, two gists | Yes; IDs 27–38 covered Nate→Sweden, not Sweden→German | Raw span rank 1 | Yes; no drops | Literal “German” present | Metric false positive; correct two-hop chain incomplete |

The original 1/3 evidence-containment result overstates useful evidence recall.
The third case contains the literal gold string in unrelated gist text, but the
selected context does not contain the complete fact chain supporting the answer.
For these three cases, complete multi-hop support reached ContextPacket in 0/3.

## Example-by-example Analysis

### Example 1: `factconsolidation_mh_6k-row-1`

- Question: “What is the country of citizenship of the spouse of the author of
  Our Mutual Friend?”
- Gold answer: `Belgium`
- Relevant replay facts:
  - chunks 1 and 2, message IDs 3 and 5: conflicting authors of
    *Our Mutual Friend*, including Charles Darwin;
  - chunk 4, message ID 9: “Charles Darwin is married to Amala Paul”;
  - chunk 4, message ID 9: “Amala Paul is a citizen of Belgium.”
- Replay: all seven chunks were stored incrementally.
- Gist generation: one gist covered message IDs 1–14, including all relevant
  facts. Its deterministic text retained only compact first/last user excerpts,
  so it did not contain `Belgium`.
- Gist retrieval: retrieved gist ID 1.
- Expansion: generated raw span `...:1-12`. Its provenance included message 9,
  but `truncated=true`; the formatted 4,000-character content stopped before
  the Belgium statement.
- Reranking: the raw span ranked first (`0.524`), above the gist (`0.431`).
- Budget/context: raw span received 1,181 tokens; gist received 644. Both were
  included and no candidate was dropped.
- Metric: normalization was not the cause. Neither retrieved nor final candidate
  text contained normalized `belgium`.

**Diagnosis:** the right source range was identified, but raw-span formatting
truncated the answer-bearing part while still reporting all selected message
IDs as provenance. This is an expansion/formatting issue, not reranking or
budget loss.

**Recommended fix:** make raw-span character bounding select whole,
query-relevant messages before formatting, and report only message IDs whose
text actually survives formatting. For multi-hop questions, preserve all
matched fact-bearing messages rather than a contiguous prefix.

### Example 2: `factconsolidation_mh_32k-row-2`

- Question: “Where did the religion associated with the Bagratuni Dynasty come
  into existence?”
- Gold answer: `Taipei`
- Relevant replay facts:
  - chunk 28, message ID 57: Bagratuni Dynasty→Christianity;
  - chunk 6, message ID 13: Christianity→founded in Taipei.
- Replay: all 35 chunks were stored incrementally.
- Gist generation: one gist covered IDs 1–70. The deterministic first/last
  summary did not retain either complete two-hop chain or `Taipei`.
- Gist retrieval: retrieved gist ID 1.
- Expansion: selected IDs 51–62 around the query-specific Bagratuni occurrence.
  This correctly captured the first hop but did not include distant message 13.
- Reranking: the expanded raw span ranked first (`0.579`), above the gist
  (`0.509`).
- Budget/context: raw span received 1,182 tokens and gist 644. Both were
  included; no candidates were dropped.
- Metric: normalization was not the cause. `Taipei` was absent before reranking
  and remained absent from ContextPacket.

**Diagnosis:** lexical, single-window expansion found the query entity but
cannot perform the second retrieval hop from Christianity to Taipei. This is a
retrieval/expansion limitation and a conflict-resolution multi-hop requirement.

**Recommended fix:** add adapter-level chunk retrieval and an optional bounded
second hop: retrieve the Bagratuni chunk, extract the linked entity
`Christianity`, then retrieve chunks containing that entity. Do not increase a
single contiguous window enough to cover the whole transcript.

### Example 3: `factconsolidation_mh_64k-row-3`

- Question: “In which language are the official documents written in the
  country of citizenship of Nate ‘Tiny’ Archibald?”
- Gold answer: `German`
- Relevant replay facts:
  - chunk 16, message ID 33: Nate “Tiny” Archibald→Sweden;
  - chunk 35, message ID 71: Sweden→official language German.
- Replay: all 69 chunks were stored incrementally.
- Gist generation: two bounded gists covered IDs 1–80 and 81–138.
- Gist retrieval: both gists were retrieved.
- Expansion: adjacent gist ranges merged, then one 12-message lexical window
  (IDs 27–38) was selected. It covered message 33 and the Nate→Sweden first hop,
  but not message 71 and the Sweden→German second hop.
- Reranking: the raw span ranked first (`0.543`); both gists followed
  (`0.472` each).
- Budget/context: raw span received 1,182 tokens and previous-chat gists 644.
  All three candidates were included; none were dropped.
- Metric: reported success because normalized `german` appeared in gist ID 1.
  The dataset contains `German` in 38 replay chunks, mostly unrelated to the
  required chain. Literal answer containment therefore produced a false
  positive.

**Diagnosis:** the selected raw evidence contains only the first hop. The
reported pass is metric strictness in the opposite direction: it is too
permissive for a common answer string and does not verify supporting relations.

**Recommended fix:** evaluate expected evidence statements or supporting
message IDs, not only the final answer literal. Retrieval still needs a bounded
second hop from Sweden to its latest applicable official-language fact.

## Cross-cutting Findings

1. **Dataset schema/chunking:** all gold strings were present in replayed chunks,
   so ingestion did not lose them. Character-based chunk boundaries can split
   fact lists awkwardly, but were not the direct cause of these misses.
2. **Memory update:** mock structured extraction intentionally stored no
   structured facts. The run therefore evaluated deterministic episodic
   gist/span behavior, not production LangMem conflict consolidation.
3. **Gist compression:** deterministic gists keep compact first/last excerpts.
   They are useful as orientation but cannot preserve thousands of independent
   facts or conflict chains.
4. **Gist retrieval:** a gist was found in every case. The failures happened
   after coarse gist selection.
5. **Expansion/windowing:** this was the primary retrieval bottleneck. One
   contiguous 12-message window cannot recover distant multi-hop facts.
6. **Raw formatting:** case 1 exposed a provenance mismatch: selected message
   IDs covered the gold message, but character truncation removed its text.
7. **Reranking:** expanded raw spans ranked first in all three cases. Reranking
   cannot recover evidence absent from candidate text.
8. **Budget allocation:** no candidate was dropped. Source budgets were
   nonzero and all retrieved candidates reached ContextPacket.
9. **Metric strictness:** literal normalized answer containment was correct for
   cases 1 and 2, but falsely credited case 3 due to an unrelated occurrence.
10. **Conflict semantics:** these questions require resolving duplicated or
    contradictory relations and performing two-hop joins. A deterministic gist
    plus one lexical span is not sufficient.

## Recommended Fixes

1. **Low-risk diagnostics/reporting**
   - Keep the bounded replay/candidate-stage diagnostics added by this audit.
   - Add expected evidence statements or official supporting IDs when the
     dataset exposes them.
   - Distinguish literal answer presence from complete evidence-chain coverage.
   - Correct raw-span provenance after character truncation.

2. **Adapter/schema/chunking**
   - Split fact-list contexts on complete numbered facts rather than arbitrary
     character boundaries.
   - Index each bounded replay chunk as a benchmark-only retrievable span while
     preserving message IDs and order.

3. **Retrieval/expansion**
   - Use query-to-chunk retrieval as the first hop.
   - Add a bounded second-hop retrieval over entities found in first-hop facts.
   - Return multiple noncontiguous evidence spans instead of one oversized
     contiguous range.

4. **Reranker/query intent**
   - Rerank only after both first- and second-hop candidates exist.
   - Add relation-chain coverage features for benchmark diagnostics rather than
     merely boosting a larger raw span.

5. **Structured conflict-resolution memory**
   - Run a separate real-model smoke test to determine whether LangMem extracts,
     updates, and supersedes these relation facts correctly.
   - Preserve temporal/order metadata so later conflicting facts can supersede
     earlier ones deterministically.
   - Do not infer production conflict-resolution quality from mock no-op mode.

## What Not To Claim Yet

- This is not official MemoryAgentBench accuracy or leaderboard scoring.
- Mock answers do not test generated-answer grounding.
- The original 1/3 literal evidence rate is diagnostic only and includes one
  false positive.
- This three-row sample does not estimate overall benchmark performance.
- Fixture-assisted routing does not validate production router generalization.
- Mock no-op structured memory does not evaluate LangMem extraction or update
  quality.
