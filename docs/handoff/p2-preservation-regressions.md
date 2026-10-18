# P2 #3 — Preservation regression strengthening

Branch: `agent/sadeghi-next-phase`.
Starting HEAD: `5d02f9246069b1177b90a1b90149f8470a1c7646`.
Scope: synthetic data, disposable SQLite, temporary filesystem, Mock/offline only.
Production changes: **NONE**. No frontend, schema or migration changes.

## Baseline and inspection

Before edits, recorded branch, full HEAD and complete `git status --short -uall`.
Baseline evidence is in `/tmp/dandoonjan-p2-preservation-baseline/status.txt` and
`hashes.json`: SHA-256 for all 988 pre-existing modified/untracked files.
This includes the three modified landing PNGs and every untracked constituent
under the existing temporary trees, archive, UI evidence, frontend-demo, tools
and verification files. No baseline entries were task-owned.

Read Gate 1 README and decisions; the next-phase CONTRACT; handoffs
`p1-intake-validation-parity.md`, `p1-processing-retry.md`,
`p2-upload-resource-boundaries.md`, `p2-filesystem-db-consistency.md`, and the
older `p0-historical-current-isolation.md` and `p0-current-report-semantics.md`.
No separate P0 #1 freshness or P0 #2 case-text concurrency handoff exists in the
searched repository documentation. Their commits `ea42a38` and `7e2855f` contain
production/test files only. Inspected their regression files and commit file lists;
older P0 handoffs are historical context, not substitutes for current test evidence.

Inventoried test definitions throughout `tests/regression_p0`, `regression_p1`,
`regression_p2`, `next_phase`, and `upload_management`. Read the directly relevant
freshness, case-text concurrency, processing retry, intake validation, dossier,
review flow, upload boundary, filesystem/DB consistency, ingestion, invariants,
orchestration/reconciliation immutability, derivation/provenance, upload
presentation, auth access/boundary and dossier migration tests/sections.
Inspected shared fixture wiring, dossier update/model, route transaction lifecycle,
DB commit/rollback and actual immutability guards. No parallel fixture stack added.

## Coverage map before additions

“SUFFICIENT” means meaningful protection for the existing scoped contract, not
exhaustive coverage or production certification. Shared persistence tests do not
constitute independent HTTP ACCOUNT/Demo admission tests.

| Invariant | Existing tests (paths under tests/) | ACCOUNT | Demo | Failure paths | Historical state | Before |
| --- | --- | --- | --- | --- | --- | --- |
| New filename/content never replaces existing bytes; duplicate preserves identity/version | regression_p2/test_upload_resource_boundaries.py::test_names_are_labels_and_never_replace; test_filesystem_db_consistency.py::test_exclusive_creation_preserves_existing_file | Yes | Yes | Collision + duplicate DB failure | File hashes, artifact identity/version | SUFFICIENT |
| Rejected/oversized/malformed uploads preserve valid evidence; bounded spool | regression_p2/test_upload_resource_boundaries.py::test_rejection_preserves_existing_evidence, test_oversize_disk_spool_preserves_report_and_artifacts, parser/closure tests | Yes | Yes | Malformed content/metadata, oversize, disconnect | Prior bytes, case/dossier/report | SUFFICIENT |
| Storage/DB failure does not corrupt prior evidence; retry is additive | regression_p2/test_filesystem_db_consistency.py::test_db_failure_preserves_rows_and_prior_bytes_characterizes_orphans, test_storage_failure_rolls_back_and_retry_is_additive, test_failed_upload_preserves_report_authority_and_history | Yes | Yes | Insert, commit, mkdir/open/write/close | Hashes, versions, runs, reports, snapshots | SUFFICIENT |
| Dossier revisions advance only on material edits; no-op/failed write preserves durable state | next_phase/test_dossier.py; regression_p1/test_intake_validation.py::test_dossier_validation_parity; regression_p0/test_case_text_concurrency.py::test_patch_rechecks_committed_inputs_and_version | Yes | Yes, fewer full-row checks | Validation and overlapping PATCH; no direct dossier commit failure | Selected revision fields only | PARTIAL |
| Concurrent case-text changes preserve committed version/history | regression_p0/test_case_text_concurrency.py::test_patch_rechecks_committed_inputs_and_version, test_failed_stale_patch_rolls_back_without_losing_concurrent_commit | Yes | Yes | Failed stale PATCH rollback | Full derived history; revision/version checks | SUFFICIENT |
| Retry keeps failed attempts; changed input preserves snapshots/reports; unchanged success fabricates no history | regression_p1/test_processing_retry.py::test_failure_retry_reuse_and_changed_input_history; next_phase/test_review_flow.py::test_shared_snapshot_reuse_failure_and_history | Yes | Yes (P1) | Repeated failure, retry, failure after success | Full snapshot/report rows, attempt IDs/statuses, reuse run equality | SUFFICIENT |
| Current assessment/report authority is separate from historical availability | regression_p0/test_assessment_freshness.py; regression_p1/test_processing_retry.py; regression_p0/test_api_state.py | Yes | Yes (freshness/P1) | FAILED/RUNNING and changed identity | Historical rows retained; stale reads empty/404 | SUFFICIENT |
| ACCOUNT, other owners, Demo visitors and namespaces isolated; CSRF before work | auth_gate2/test_access.py::test_normal_route_isolation, test_demo_route_isolation, test_denied_work_and_upload_touch; test_boundary.py::test_no_second_case_or_child_query_on_denial; CSRF tests | Yes | Yes | Foreign/missing owner, bad CSRF, expiry | No-work admission assertions; not full dual-owner report lifecycle | SUFFICIENT for admission scope |
| Independent clinician/document provenance preserved | regression_p0/test_derivation.py::test_same_proposition_keeps_clinician_and_document_provenance, test_processing_other_case_preserves_authority_and_evidence; upload_management/test_presentation.py | Shared persistence | Shared handler; no separate provenance lifecycle here | Foreign/missing source rejection | Distinct IDs/provenance and frozen payload | SUFFICIENT for source distinction |
| Snapshot/audit/artifact immutability | test_p0_orchestration.py (P0-05); test_p01_reconciliation.py (D-Q4) | Shared persistence | Shared persistence | ORM update/delete refusal; integrity tamper detection | Protected content/source identity | SUFFICIENT for existing guards |
| Dossier append-only ORM enforcement | app/governance/immutability.py promises update/delete guards; no direct guard tests found | Missing direct test | Missing direct test | Neither guard directly exercised | Later API revisions only | MISSING direct guard coverage |
| Populated migration preserves existing source/history | next_phase/test_dossier_migration.py; regression_p0/test_migrations.py; auth migration fixtures | Shared schema | Shared schema | Legacy/adoption checks | Synthetic prior rows/FK integrity | SUFFICIENT for documented migration scenarios; not rerun |

The matrix was reported before test creation. No production code was edited during
mapping or afterward. Existing coverage for candidate scenarios A, C, D, E, F, G
and I was retained instead of duplicated. Namespace/ownership coverage was reused
rather than building a second authentication fixture system for H.

## Minimal additions

Only new test file: `tests/regression_p2/test_preservation_invariants.py`.
Uses unchanged `tests/regression_p2/conftest.py`, the existing ACCOUNT/Demo
`assessed_case`, `history`, and `records` helpers.

- `test_dossier_failure_noop_and_revision_preserve_history[ACCOUNT/DEMO]`:
  starts from a successful assessment/report; captures all dossier, case, audit,
  assessment, snapshot, processing-run and report columns in detached dictionaries.
  Injects failure at the real DBAPI commit boundary after dossier work. Fresh
  sessions verify exact rollback and unchanged current report/assessment. A no-op
  cannot fabricate a revision. Two subsequent edits each add one revision and
  increment version once; every previous revision column and prior audit row
  remains identical. Derived history stays unchanged while current reads become
  empty/404. No-op audit appends are allowed by the existing contract.
- `test_dossier_revision_guard_preserves_durable_state[ACCOUNT/DEMO-update/delete]`:
  normal ORM rewrite/delete must raise ImmutabilityViolationError; after rollback,
  fresh-session revision contents, dossier presentation and current report remain
  identical. Four cases protect the previously untested dossier listeners.

Six cases total. The two identified gaps are now **VERIFIED WORKING** within this
synthetic SQLite/ORM scope. No newly discovered production defect. No fix gate,
xfail, weakened contract, or production refactor was needed.

Append-only applies to dossier revisions, snapshot content and audit payloads;
ProcessingRun authority and derived current-state status may legitimately become
SUPERSEDED. Artifact classification/extracted metadata is mutable; source identity
is protected. Tests intentionally do not freeze those mutable pointers globally.
Historical availability here means retained DB history, not a newly promised public
historical-report endpoint.

## Validation at this gate

Every Python invocation used
`PYTHONPYCACHEPREFIX=/tmp/dandoonjan-p2-preservation-pycache`.
Sandbox baseline command `timeout 25s python3 -m pytest tests/next_phase/test_dossier.py -q --tb=short`
stalled without a completed result (exit 124). Requested and received permission
for synthetic/offline execution outside the sandbox.

Completed focused command:

```sh
python3 -m pytest tests/regression_p2/test_preservation_invariants.py tests/next_phase/test_dossier.py -q --tb=short
```

**9 passed, 3 warnings in 6.42s**: all six new cases plus three existing dossier
cases. Production was unchanged; this is not a before/after production fix claim.

Relevant regression command:

```sh
python3 -m pytest tests/regression_p0/test_assessment_freshness.py tests/regression_p1/test_processing_retry.py tests/regression_p2/test_upload_resource_boundaries.py tests/regression_p2/test_filesystem_db_consistency.py tests/regression_p0/test_derivation.py tests/test_p0_orchestration.py tests/test_p01_reconciliation.py tests/upload_management/test_presentation.py tests/auth_gate2/test_access.py tests/auth_gate2/test_boundary.py -q --tb=short
```

**220 passed, 3 warnings in 82.49s (0:01:22)**. Combined with the focused run:
**229 passed**, no failures/errors/skips. Both completed commands report existing
Starlette TestClient and FastAPI startup deprecation warnings. Historical pass
counts in older handoffs are not results from this gate. No full repository run. P0 case-text concurrency
was inspected but not rerun: neither its implementation nor test was touched.
Migration and browser suites were not rerun for this test-only change.

## Boundaries and unresolved policy

**AMBIGUOUS, unchanged:** orphan retention/repair, missing-file duplicate repair,
abandoned RUNNING recovery, forced rerun, aggregate multipart/time/quota budgets,
and empty-question clearing policy. No new policy tests or product choices added.
The documented P2 #2 orphan behavior is EXPECTED BY CONTRACT, not a newly found
preservation defect. Cross-store atomicity is not promised.

**PARTIALLY VERIFIED:** isolation is covered by existing admission and no-work
checks, not every combination of two populated owner histories. Immutability is
application ORM enforcement, not a defense against privileged raw SQL. Commit
injection fails before DBAPI commit, not after an ambiguous remote acknowledgement.

**NOT VERIFIED:** PostgreSQL execution, power loss/process kill, actual disk full,
backup/restore, exhaustive malformed-input fuzzing, hosted infrastructure, live
providers, real patient/clinical behavior, and the full repository suite.

## Task files and final repository safety

Exactly two new files:

1. `tests/regression_p2/test_preservation_invariants.py`
2. `docs/handoff/p2-preservation-regressions.md`

Production code changed: **NONE**. Shared fixtures unchanged. Frozen frontend
visuals unchanged. Nothing staged, committed, pushed or deployed. No credentials,
paid/live service, clinical approval, migration or work requiring Mehdi.

Final checks: **988/988 baseline hashes match**, with zero missing/changed original
status entries. Exactly the two task files above are newly untracked. Staged diff
is empty; branch and full HEAD remain unchanged. `git diff --check` passed.
All pre-existing dirty/untracked files were preserved. Nothing was staged,
committed, pushed or deployed.
