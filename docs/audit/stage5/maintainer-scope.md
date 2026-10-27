# Maintainer scope and size

User asked for a rough completion estimate and whether the suite is too large. Coordinator estimated ~75% of Stage5 work at that point; this was planning judgment, not statement/branch coverage. No code-coverage percentage has been measured. Avoid target case counts or interpreting passing percentage as coverage.

Through batch3: 628 initial selected cases became635, seven new semantic cases (~1.1%). Default core files were already large. Admitted handler/wrapper/browser cases pre-existed and must not be presented as newly authored protection. Test/fixture lines +820/-122; isolation/canary +852; handwritten docs/config +474; machine JSON evidence +4657. Machine evidence preserves provenance rather than executable maintenance volume. Tests need meaningful unique outcomes; a green count does not justify retention.

Recommended suite shape: focused offline contracts/storage/lifecycle and deterministic eval regressions by default; explicit local UI group; opt-in live/model/costed eval group; manual diagnostics with exact commands. Keep setup dependencies explicit and share only equivalent responsibilities.

One supported future reduction candidate, not approved/performed: TSA12/TS040 tests/test_evidence_constrained_selector.py::test_rank_one_raw_regressions_fit_global_budget[q5/q11/q17/q19]. All four use same100/20-word candidates/scores/provenance/route/budget/assertions; only IDs/generated first-word labels change and fixed query ignores those labels. Keep one boundary case; remove3 redundant parameter instances only after bounded approval or recover distinct fixtures if labels intended distinct historical failures. No exact pytest-node repository consumer found; scripts/inspect_mab_context_case.py refers to a different benchmark q5. External consumers unknown.

Another later consolidation candidate: identical explicitly requested embedding fixture in two MAB test modules. Share actual equivalent setup/assertions without autouse/global scope. No whole-file retirement is justified. Prior constructor-only/Pillow-only assertions were strengthened, so do not use their obsolete weakness to justify removal.

Final Stage5 textual delta versus cb27729 (archive binaries excluded):

| Category | Added | Removed | Net |
|---|---:|---:|---:|
| test source and fixtures | 1033 | 233 | 800 |
| isolation infrastructure | 1015 | 0 | 1015 |
| handwritten docs config | 595 | 35 | 560 |
| machine json | 8042 | 0 | 8042 |
| other | 0 | 0 | 0 |

These are source/evidence changes, not a claim that every line is necessary. Freeze new case expansion here; next work addresses observed blockers and proposes scoped simplification.
