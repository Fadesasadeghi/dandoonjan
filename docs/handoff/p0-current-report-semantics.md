# P0 current report semantics gate

Date: 2026-09-22. Branch: `agent/sadeghi`.
Starting commit: `fb0ee28f71a2d0d28dd0a30455646162c79d9e1b`.
Pre-flight verified HEAD, tracking ref and directly queried remote tip matched,
0 ahead/0 behind, a clean working tree and no untracked files.

## Confirmed root cause and correction

`app/api/routes.py::case_report` previously selected reports by case alone,
ordered by descending Report.id. After a newer BLOCKED run generated no report,
that query still returned the old successful report with HTTP 200.

Reports and snapshots already carry `derivation_run_id`. The pipeline activates
a successfully completed terminal run (including BLOCKED), superseding the old
run's authority. Snapshot.case_version records the input revision; edits and new
artifact ingestion increment Case.version. No timestamp defines current authority.

The query now joins the report's ProcessingRun and AssessmentSnapshot. It requires:

- Report, run and snapshot ownership by the requested case.
- A pipeline run with SUCCEEDED status and ACTIVE authority.
- Snapshot and report belonging to that same derivation.
- Snapshot.case_version matching the current Case.version.

The retained descending report ID only chooses among reports within this eligible
context; it cannot select historical authority as a fallback. If no report
qualifies, the existing HTTP 404 `REPORT_NOT_READY` response is used. Success
response fields are unchanged. This also prevents an old revision from being
presented as current merely because its run remains ACTIVE before reprocessing.

Historical reports and snapshots remain persisted, unchanged. No report was
deleted, overwritten or destructively superseded to implement the fix. No new
history API is introduced. Report composition, pipeline authority switching and
`_reused_result` are untouched: reportless terminal reuse safety parity was NOT
fixed or changed, and its three locked failures remain.

Existing correctly linked historical rows require no data repair for this
selection correction to work. Malformed or legacy/unowned reports are not
promoted into current authority; any separate legacy repair/reprocessing remains
outside this gate. No persisted data was repaired or migrated.

## Files changed

- `app/api/routes.py`: only the current-report selection query.
- `docs/handoff/p0-current-report-semantics.md`: this gate record.
- `DANDOONJAN_CURRENT_STATE_LOCK.md`: current pointer and prior-gate reference.

No tests, other production code, migrations, dependencies, deployment files or
prior gate records changed. No secrets, temporary logs, DBs, journals or generated
artifacts are included. Complete source diff and `git diff --check` reviewed.

## Verification

Used the existing isolated Python 3.11 environment:
`/mnt/c/Users/Admin/AppData/Local/Temp/dandoonjan-p0-regression-venv/Scripts/python.exe`.
All scenarios use synthetic data and deterministic/mock AI; no dependencies changed.

Exact focused node ID and sole removed failure:
`tests/regression_p0/test_api_state.py::test_blocked_revision_never_returns_historical_report_as_current`.

Before fix (`-q --tb=short -rfs`): 1 failed, 0 errors/skips, 4 warnings in 1.68s.
After a successful old report and a changed BLOCKED revision, GET /report returned
HTTP 200 with the same old report ID, contrary to the no-historical-as-current
invariant. After fix, the same locked regression: 1 passed, 0 failed/errors/skips,
4 warnings in 1.49s. Its historical report content and snapshot payload assertions
also pass. Existing no-report API behavior is HTTP 404.

Relevant tests: `tests/test_api.py tests/test_pipeline.py tests/test_p0_orchestration.py
tests/test_p01_reconciliation.py -q --tb=short`:
44 passed, 0 failed/errors/skips, 4 warnings in 8.72s.

Existing suite: `python -m pytest tests --ignore=tests/regression_p0 -q --tb=short`:
109 passed, 0 failed/errors/skips, 4 warnings in 21.07s.

Combined: `python -m pytest tests -q --tb=short -rfs`:
121 passed, 15 expected failures, 2 skipped, 0 errors, 4 warnings in 35.56s.
Failures are ordinary failures, not xfails. Exact FAILED node IDs were compared
with the preceding historical/current gate log: only the focused node disappeared
from its 16 failures; no new failure or unrelated unexpected pass appeared.

Remaining categories: provenance (1), processing identity (4), reportless terminal
reuse parity (3), rejected-upload audit durability (1), migrations/schema/SQLite
FK integrity (5), Docker/frontend packaging (1).

Exact remaining failure node IDs:

- `tests/regression_p0/test_api_state.py::test_rejected_upload_persists_audit_without_partial_ingestion`
- `tests/regression_p0/test_derivation.py::test_same_proposition_keeps_clinician_and_document_provenance`
- `tests/regression_p0/test_derivation.py::test_material_processing_configuration_invalidates_reuse[model]`
- `tests/regression_p0/test_derivation.py::test_material_processing_configuration_invalidates_reuse[provider]`
- `tests/regression_p0/test_derivation.py::test_material_processing_configuration_invalidates_reuse[pack-version]`
- `tests/regression_p0/test_derivation.py::test_material_processing_configuration_invalidates_reuse[pack-identity]`
- `tests/regression_p0/test_derivation.py::test_reused_reportless_terminal_result_preserves_safety[normal]`
- `tests/regression_p0/test_derivation.py::test_reused_reportless_terminal_result_preserves_safety[caution]`
- `tests/regression_p0/test_derivation.py::test_reused_reportless_terminal_result_preserves_safety[blocked]`
- `tests/regression_p0/test_migrations.py::test_populated_initial_upgrade_preserves_finding`
- `tests/regression_p0/test_migrations.py::test_populated_pre_p01_upgrade_preserves_processing_run`
- `tests/regression_p0/test_migrations.py::test_startup_created_database_can_enter_alembic_lifecycle`
- `tests/regression_p0/test_migrations.py::test_migrated_finding_treatment_item_fk_matches_model`
- `tests/regression_p0/test_migrations.py::test_runtime_sqlite_connections_enforce_foreign_keys`
- `tests/regression_p0/test_packaging.py::test_docker_copy_includes_frontend_at_application_runtime_path`

## VERIFIED

- The locked BLOCKED revision no longer exposes its historical report as current.
- Historical report content and snapshot payload remain unchanged.
- Existing API/report/orchestration behavior remains green in tested scope.
- All executable completed storage, case-isolation and historical/current
  isolation regressions still pass in the combined suite.
- Terminal reuse parity implementation is unchanged and its failures remain.

## NOT VERIFIED / risks and limitations

- Real PostgreSQL, live providers, concurrent processing/load, browser/hosted
  deployment, actual Docker runtime, backup/restore and clinical readiness were
  not verified by this gate.
- Two storage symlink cases remain skipped because Windows lacks symlink privilege
  (WinError 1314); completed storage implementation is unchanged.
- The locked regression exercises successful-report → revised BLOCKED processing.
  Arbitrary malformed associations and concurrent authority transitions are not
  certified by this scenario. The predicate relies on established ownership and
  revision metadata; no legacy data repair is attempted.
- The other 15 locked defects remain unresolved. No later P0 gate was started.
