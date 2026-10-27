# Migration findings

Main adds canonical settings and connection guards: provider settings must use a separate module and memory guard must follow the resolved endpoint. Preserve retries/timeouts and application defaults.

Independent static impact review finds sqlite-vec replacing structured Chroma, augmented prompt validation, eager model preload, cwd logs, new React E2E and scheduling changes. Historical AUD-17/20 arguments are superseded; runtime conclusions remain open. See docs/audit/main-baseline-impact.md.
