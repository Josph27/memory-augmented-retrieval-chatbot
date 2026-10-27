# Main-based audit revalidation — completed points1–4

Read [assessment](static-assessment.md), [coverage ledger](coverage-ledger.md), [file assessments](file-assessments.md), [findings](findings-register.md), [workflow reconciliation](workflow-reconciliation.md), [test assessment](test-assessment.md), [test inventory](test-inventory.md), and [execution](execution.md). [Machine claim register](claim-reconciliation.json) ties stable identities to their current disposition.

Validation (no app/test imports):

```bash
python3 docs/audit/revalidation/validate_revalidation.py --check-original
```

This checks342relevant paths, current source drift,80historicaltestIDs,WF/AUD/TSA completeness, all current test-source execution/exclusion accounting, history, exact executed input hashes, results and local links. --check-original additionally verifies old dirty-state backup/status/stashes and raw-execution archive. The assessment's semantic depth and runtime exclusions remain explicit; a structural validator is not a second semantic audit.
