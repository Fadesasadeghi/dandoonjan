# P0 terminal reuse parity gate

Date: 2026-09-22. Branch: `agent/sadeghi`.
Starting commit: `b43982134d490f93ec44dbe22e6fb40189bcbc89`.
Pre-flight verified HEAD, tracking ref, directly queried remote tip, 0 ahead/behind,
a clean working tree and no untracked files.

## Locked regressions and root cause

- `tests/regression_p0/test_derivation.py::test_reused_reportless_terminal_result_preserves_safety[normal]`
- `tests/regression_p0/test_derivation.py::test_reused_reportless_terminal_result_preserves_safety[caution]`
- `tests/regression_p0/test_derivation.py::test_reused_reportless_terminal_result_preserves_safety[blocked]`

Before correction all three failed: the fresh run returned NORMAL, CAUTION or
BLOCKED, but reuse returned `safety_state=None` when no snapshot/report existed.
The reuse path read safety only from `AssessmentSnapshot`. BLOCKED had a persisted
`SafetyResult`, but NORMAL and CAUTION early terminal paths returned intake safety
without persisting any safety row.

## Correction

`_reused_result` now reads the persisted `SafetyResult` for the reusable
`derivation_run_id` when no snapshot exists. The NORMAL/CAUTION no-processable-
artifact terminal path now persists its original `intake_state` and reasons via
`_record_safety_result` before authority activation. BLOCKED already used this
mechanism. No `screen_case_text` recomputation was added.

This restores the original terminal safety semantics from persisted run state.
Reuse eligibility and the processing-identity hash are unchanged. Report and
snapshot generation, case authority, current-report selection, and historical
state are unchanged. No schema/migration change is required: `SafetyResult` and
its derivation link already exist.

The correction adds persisted SafetyResult rows for future NORMAL/CAUTION early
terminal runs. Existing runs that lack those rows are not rewritten or repaired;
no destructive data operation occurs. No test expectations were changed.

## Tests

Used the existing isolated Python 3.11 environment:
`/mnt/c/Users/Admin/AppData/Local/Temp/dandoonjan-p0-regression-venv/Scripts/python.exe`.

- Focused before: 3 failed.
- Focused after: 3 passed in 0.54s.
- Relevant existing orchestration/reuse/pipeline/API tests: 44 passed, 4 warnings.
- Existing suite: 109 passed, 0 failed/errors, 4 warnings in 15.85s.
- Combined suite: 129 passed, 7 expected failures, 2 skipped, 0 errors,
  4 warnings in 27.51s.

Exact comparison with the processing-identity gate's 10 failures: only the three
terminal-reuse nodes above disappeared. No new failure appeared. Upload audit,
five migration/schema/FK failures, and packaging remain unchanged. Storage,
case isolation, historical/current isolation, current-report, claim provenance,
and processing-identity regressions remain green.

Remaining expected failures:

- `tests/regression_p0/test_api_state.py::test_rejected_upload_persists_audit_without_partial_ingestion`
- `tests/regression_p0/test_migrations.py::test_populated_initial_upgrade_preserves_finding`
- `tests/regression_p0/test_migrations.py::test_populated_pre_p01_upgrade_preserves_processing_run`
- `tests/regression_p0/test_migrations.py::test_startup_created_database_can_enter_alembic_lifecycle`
- `tests/regression_p0/test_migrations.py::test_migrated_finding_treatment_item_fk_matches_model`
- `tests/regression_p0/test_migrations.py::test_runtime_sqlite_connections_enforce_foreign_keys`
- `tests/regression_p0/test_packaging.py::test_docker_copy_includes_frontend_at_application_runtime_path`

## VERIFIED / NOT VERIFIED / RISKS

VERIFIED: fresh and reused NORMAL, CAUTION and BLOCKED reportless terminal
results expose the same safety state; persisted state is used; no schema change;
all completed gates remain green in the combined suite.

NOT VERIFIED: repair of preexisting runs without SafetyResult rows, PostgreSQL,
concurrency, live providers, deployment, clinical readiness, and Windows symlink
cases (WinError 1314).

RISKS: historical reportless terminal rows created before this correction may not
be reusable with parity until reprocessed; no automatic repair was attempted.
The seven remaining P0 failures are outside this gate. Upload Audit, Migrations,
and Packaging were not changed. No later gate was started.
