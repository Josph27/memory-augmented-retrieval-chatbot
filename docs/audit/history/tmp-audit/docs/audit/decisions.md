# Decisions and approval boundary

Package v1.0 · 2026-10-27. Only direct user instructions count as approvals; audits and this register cannot authorize deletions. Source descriptions below refer to messages in this chat, not independently stored transcripts.

## Explicit user instructions

| ID | Decision / scope | Approval source | Status |
|---|---|---|---|
| DEC-001 | Preserve the typed-memory architecture, deterministic operational boundaries, Chainlit/history/recent memory, durable cross-chat memory, document RAG, trace and evaluation capabilities. | User-supplied project context and AGENTS.md instructions; also root `AGENTS.md`, “Architecture to Preserve” / “Essential Features”. | Binding constraint; no capability removal approved. |
| DEC-002 | Audit read-only; do not inspect secrets/private content or mutate app state, Git or stashes; no app, inference, ingestion or dependency installation. | Initial audit request and continuation request. | Applied to both audits; current documentation exception is DEC-005. |
| DEC-003 | Park bugs; select at most five genuinely unnecessary workflows with checked consumers and distinct-value/replacement evidence. Approval would authorize removal planning only. | User message beginning “Return to the original cleanup plan.” | Backlog saved; no qualifying workflow was recommended. **No workflow removal has been approved.** |
| DEC-004 | Follow baseline → product decisions → protection tests → approved removals → consolidation → restructuring → final verification/documentation. | Current user instruction explicitly calls this the agreed sequence. | Governing sequence; later stages are not blanket execution approval. |
| DEC-005 | Consolidate only `docs/audit/`, preserve existing material, distinguish provenance, and create no commits. | Current message beginning “Preserve the knowledge from your audit”. | Authorized now; implementation, test execution and removal remain outside scope. |
| DEC-006 | Audit the existing test suite before selecting an implementation-consolidation batch or expanding protection tests. Inventory tests/test-like scripts; distinguish intended, implemented and asserted behavior; assess assertions, mocks, production relevance, isolation and unique coverage; classify retain/strengthen/replace/removal candidate/unresolved. | User instruction to coordinator, 2026-10-27, beginning “We have refined the sequence”. | Static assessment completed; no collection/execution, test changes/deletions or app fixes. Collection/execution still require verified isolation; recommendations are not implementation approval. |
| DEC-007 | Assign main assessment and follow-ups to existing chat “Audit Breamon repository”; monitor/read results; use internal agents for independent bounded reviews of consequential recommendations and a retained-test sample. | Same user instruction, 2026-10-27. | Delivered and reviewed. Main assessment plus two internal reviewers; detailed evidence in `test-suite-*` docs and reports 03–05. No materially blocking behavior ambiguity arose. |
| DEC-008 | Use nine-stage plan: 1 inference; 2 audit/handoff; 3 scope decisions (zero candidates valid); 4 existing-test audit (current); 5 protection; 6 PURGE1 approved code/artifacts; 7 PURGE2 consolidation; 8 PURGE3 restructuring; 9 acceptance/backlog review. Documentation and blocker triage throughout. | User synchronization message to coordinator, 2026-10-27, beginning “Here is the most up-to-date execution plan”. | Current sequence, refining DEC-004/006. Coordinator handles bounded implementation/verification/review at each authorized tier; user decides capability changes and validates product. Current assessment still forbids test/app changes; no specific purge batch approved. |

The assistant's earlier question offering a narrower implementation/artifact cleanup plan was **not** an approval. The current request authorizes preserving that proposal and task sequence, not executing it. Stashed deletions remain unapproved and untouched.

DEC-006 refines DEC-004's sequence by inserting TASK-09 after the handoff and before cleanup-batch selection or protection expansion. DEC-005 describes the earlier consolidation task; its documentation-only boundary is now supplemented by DEC-006/007, not permission to implement recommendations.

## Recommendations and unresolved choices — not approvals

Recommended defaults are proposals for a later user decision, not reconstructed consent.

| ID | Open question / recommended default | Reason and tradeoff | Related evidence |
|---|---|---|---|
| DEC-101 | Should chats without attachments use global documents? Default proposal: explicit chat associations; an explicit global-library option if wanted. | Predictable scope and inspection; loses implicit library recall unless deliberately selected. Existing global fallback is intentional, so this changes policy. | WF-06/07/12; AUD-01/09/16. |
| DEC-102 | Does deleting memory hide a record, suppress future learning, or erase source material? Default proposal: suppression from structured recall/re-extraction with history retained unless separately erased. | Avoids surprising resurrection; requires suppression identity/provenance policy and does not erase raw history. | WF-08/09; AUD-03. |
| DEC-103 | What does fork inherit? Default proposal: copy document associations/provenance intentionally; share underlying immutable documents unless lifecycle policy requires copies. | Makes inherited conversation evidence available; sharing needs an explicit later-removal rule. Do not copy all caches automatically. | WF-12; AUD-16. |
| DEC-104 | What should editing a past turn do to later messages and derived memory? Default proposal: define persisted edit plus dependent-state invalidation before promising full edit support. | Coherent history requires more than changing displayed text; turning off support temporarily would itself need approval. | WF-04; AUD-19. |
| DEC-105 | Is the supported deployment private local use or network access? Default proposal: local single-user scope with explicit authenticated API boundary. | Small prototype scope; does not promise multi-user tenancy. | WF-01/14; AUD-14. |
| DEC-106 | Which frontend/orchestration/configuration combinations must be protected? Default proposal: retain Chainlit and the typed source/packet contract; keep React and graph/native fallbacks pending explicit scope decisions and parity tests. | Existing consumers and important fallback behavior prevent evidence-based deletion now; retaining combinations increases test scope. | WF-02/03/14/15; AUD-11/15/18. |
| DEC-107 | Approve a workflow/file removal? No default deletion. First require consumer checks, replacement coverage, benefit and protection evidence in a concrete proposal. | None currently meets the workflow-removal threshold. Redundant code is a refactoring candidate, not proof of unnecessary product behavior. | TASK-03/05/06. |

## Recording later decisions

Append a new stable decision ID or update the question with an explicit source, date, precise approved scope and planning-versus-execution boundary. Do not replace an open question with an inferred answer. Preserve superseded decisions and identify their successor.
