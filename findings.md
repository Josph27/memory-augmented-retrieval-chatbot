# Migration findings

Main adds canonical settings and connection guards: provider settings must use a separate module and memory guard must follow the resolved endpoint. Preserve retries/timeouts and application defaults.

Independent static impact review finds sqlite-vec replacing structured Chroma, augmented prompt validation, eager model preload, cwd logs, new React E2E and scheduling changes. Historical AUD-17/20 arguments are superseded; runtime conclusions remain open. See docs/audit/main-baseline-impact.md.

TASK-11 execution: minimal bwrap namespace succeeded with authorized escalation, native SQL/source/network canaries verified. Synthetic passwd/home needed for dependency portability; initial missing-home runs superseded. Deterministic core205:198pass7fail, zero network attempts. Corrected composition230selected:201pass28fail1skip, heavy real-model test deselected. Canonical-offline17:9pass8fail. Failures expose changed source inclusion/provenance/category/vector error semantics and unmocked guard/embedding prerequisites; no app/test fixes. Additional independently reviewed25-file eval/storage cohort running.
