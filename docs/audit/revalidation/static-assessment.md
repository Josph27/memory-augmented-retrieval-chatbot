# Main revalidation assessment

TASK-11 · 2026-10-27 · source commit `1cf4c553b12281fefb7daea5141e9cddfce6ca48`, branch `codex/audit-main`. This assessment completes the assigned static revalidation and reconciles the coordinator's separately executed existing checks. It does not authorize fixes, deletion or new product policy.

## 1. Result and reading order

The main-based implementation differs materially from the deprecated audit checkout. Preserve historical AUD/TSA identities, but use the revised conclusions here before planning protection tests. No workflow or whole test-file removal is justified by this assessment.

1. [Workflow reconciliation](workflow-reconciliation.md): WF-01–16 responsibilities, entry points, consumers, state and failure paths, test relationships and inspection depth.
2. [Findings register](findings-register.md): all20 historical AUD findings,13 TSA claims, material recommendations and four distinct RV observations, with counterevidence and verification requirements.
3. [Test assessment](test-assessment.md) and [test inventory](test-inventory.md): assertion value, changed dependencies, stable historical identities and bounded execution interpretation.
4. [File assessments](file-assessments.md) and coordinator [coverage ledger](coverage-ledger.md): exact per-path coverage and explicit exclusions, rather than treating syntax inventory as semantic review.
5. Coordinator [execution record](execution.md), [machine outcomes](execution-results.json), [unexecuted checks](unexecuted-checks.json) and [independent review](review-notes.md): runtime and isolation provenance.

## 2. Established changes and consequential uncertainty

- **AUD-17's old strict-equality mechanism is superseded.** Augmented user content is now accepted by the validator/comparator. The existing actual-request test was executed but stopped before answer generation at eager document-neighbor embedding initialization. Request parity remains unverified; do not call it either broken by the old mechanism or fixed at runtime.
- **AUD-20's separate structured-vector-root mechanism is superseded.** SQL and sqlite-vec share the supplied Database. Their operations still have separate failure/commit behavior: upsert catches vector errors after durable SQL; delete may propagate after soft deletion. Existing and new tests assert competing exception contracts.
- **AUD-06 is policy-dependent.** Scheduled oldest batches can repeatedly reject empty extraction; latest-turn agentic mode consumes no-ops, and chat-end-only skips online processing. Batch growth and End can change progress. Native End can accept a normal partial result; the renamed rejection test does not assert chat activity despite its name. REST End still bypasses native consolidation/gists (AUD-02).
- **Scope, forgetting and lifecycle remain product decisions.** Intentional global document fallback differs from Inspector visibility (AUD-01); SQL deletion does not define erasure across cache, messages, gists and later extraction (AUD-03); fork omits document associations (AUD-16). These observations do not authorize removal of retained capabilities.
- **Current defaults change unchanged consumers.** Canonical settings, hybrid modes, per-category namespaces, merged default retrievers, guard probes and eager model dependencies affect tests/evaluations whose own source is unchanged. Unknown-model application limits are not measurements of DeepSeek capacity (AUD-05).
- **New distinct evidence:** RV-001 vector-rebuild CLI has syntax/API incompatibility; RV-002 old/new vector exception assertions conflict; RV-003 coordinator failure marking can be overwritten on a later branch (static conditional scenario); RV-004 LongMemEval reads a removed AppConfig attribute, with three existing isolated cases raising AttributeError. Exact owners and reproduction limits are in the register. Bugs remain parked.

## 3. Coverage and provenance

The [manifest](coverage-manifest.json) compares actual old working-source content with the current source, not just commit trees. It contains392 union records;342 relevant rows are individually assessed:324 product/source/configuration/documentation/test paths,14 evaluation-input contracts and4 asset metadata paths. Audit metadata, immutable historical records and runtime/generated material have separate classifications. Input contracts were checked without reading private or benchmark conversation/document text; binary assets were not rendered.

Current Python test sources number80, containing643 lexically declared test functions; these are not collection totals. All80 historical test identities are reconciled, with two absent root probes and two appended identities making82 union rows.59 evaluation Python sources and the shell, JavaScript, React and development entry points have consumer/selection reconciliation. Per-file groups state semantic depth and limits; no claim of every helper branch or flag combination is made.

Static assessors did not import the application, collect/run tests, initialize storage or call inference. The coordinator separately executed628 distinct deterministic checks:578 passed,49 failed,1 skipped, with one real-model case deselected. A canonical-offline cohort has17 overlapping checks (9 passed,8 failed), which must not be added to unique totals. Accepted runs selected69 test source files under OS confinement, temporary storage, masked secrets/private home and blocked network. Four genuine temporary-Chroma tests passed with existing deterministic embeddings. Setup-superseded runs and exact canaries are recorded separately. These are bounded checks, not whole-suite or product acceptance.

At final source inspection HEAD remained pinned as above. Pre-existing working changes were `docs/audit/cleanup-plan.md`, `docs/audit/decisions.md`, `findings.md`, `progress.md`, `task_plan.md`, plus untracked `docs/audit/revalidation/`; they belong to concurrent documentation/verification work. This assessor owns only the six maintained assessment files named in section1 and this document. Source digests in the manifest detect current drift; they neither recover old source nor retroactively fingerprint the original audits. Exact original audit text/baselines and dirty-state limits remain in the historical package; reconstructed reports remain explicitly reconstructed.

## 4. Next authorized boundary and remaining gaps

Static evidence is sufficient to begin choosing a bounded protection-test batch after the coordinator accepts TASK-11. That future batch is not implemented here. First reconcile prerequisite isolation and characterize actual request/trace selection, source-specific retrieval assertions and SQL/vector partial outcomes; do not globally force guards to succeed or count prerequisite failures as tested product behavior. Resolve normative sharing/forgetting/finalization/fork/edit contracts before asserting a new policy.

Still unverified: live provider compatibility/capacity and LangMem extraction; real embedding/cross-encoder quality; ordinary application startup/import and full-suite collection; browser reconnect/chat-switch/edit/native-vs-React parity; complete HTTP framework status/context/auth behavior; model-backed summaries and changed PDF behavior; cancellation/concurrency and all partial-storage recovery paths; live evaluation datasets/judges and all optional flags. Existing output is historical unless explicitly in the accepted execution record. No secrets, private histories, uploaded documents or production stores were inspected. Cosmetic rendering, external numeric/model claims and every unchanged helper branch were not exhaustively reviewed.

The agreed sequence and approval authority remain in [cleanup plan](../cleanup-plan.md) and [decisions](../decisions.md). This package supplies evidence for the next decision; it does not approve any removal, repair or restructuring.
