# Independent PURGE1 / PURGE2 challenge

TASK18 / DEC019. Baseline `f554c24`, clean `codex/audit-main`. Fresh read-only reviewers inspect core/retrieval, storage/memory, and frontend/evaluations/operations; one implementation writer, independent challenge of consequential changes and sampled retain decisions. The user's PURGE1 functionality acceptance remains recorded; PURGE2 has not received user acceptance. Existing test evidence is preserved.

Preliminary outcome: both completion claims are reopened. Source inspection found a no-consumer long-term-memory helper missed by PURGE1 and identical LongMem/MAB resume-cache selection missed by PURGE2. The latter shows that reporting the evaluation/cache area fully exhausted was premature; it does not itself establish a regression in the earlier batches. Full relevant areas are being reassessed under the updated variation rule, not re-running all historic work.

| Candidate / area | Consumers, behavior and proposed boundary | Benefit, risk and protection | Disposition |
|---|---|---|---|
| PURGE1: `memory_state_from_records` in `src/memory/long_term_store.py` | Source-wide search finds only the definition; no package export, config/CLI/eval/runtime/test consumer. Preserve the separately used `record_to_memory_state_record`. | Remove one obsolete concept; low risk, verify references and existing memory/LangMem cases. | Review and implementation pending. |
| PURGE2: MAB and LongMem answer/judge cache lookup | Both runners select the latest matching answer and completed judge with identical bodies; LongMem already imports the MAB runner, so share those two existing helpers without a new dependency. Answer key remains usable as keyword. Shell answer-only lookup excludes failed answers and stays distinct. | One place for resume-cache matching; exercise latest row, accepted failed status, judge key and existing fake resume/judge-only cases. Earlier broad evaluation/cache retention missed shared mechanics. | Review and implementation pending. |
| Other areas, including three repeated inclusive-range mergers and native/demo preparation | Direct source and consumer challenge under way; compare boundaries and relevant policies instead of treating differences as automatic exclusion. | Identify protection and abstraction cost before any batch. | Pending independent findings. |

Prior [PURGE1 evidence](purge1-ledger.md) and [PURGE2 evidence](purge2-ledger.md) remain available. No live/paid inference, private stores or credentials are used.
