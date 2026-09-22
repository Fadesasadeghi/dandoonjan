# P0 historical/current isolation gate

Date: 2026-09-22. Branch: `agent/sadeghi`.
Starting commit: `a793ddfc67014b345d80fc109c316a7af13ba7aa`.
Pre-flight confirmed HEAD, tracking ref and directly queried remote tip matched,
0 ahead/0 behind, and a clean working tree without untracked files.

## Root cause and implementation

`run_safety_gate` selected critical gaps and low-confidence material claims by
case alone. Old derivations remain persisted, and the previous derivation stays
active until the new pipeline completes. Case scope or ACTIVE status alone
therefore cannot isolate the in-progress safety computation. Both queries now
require the supplied `derivation_run_id` and ACTIVE row status as well as case
ownership. Confidence thresholds and safety policy are unchanged.

The public assessment endpoint selected every assessment for the case. It now
joins the owning ProcessingRun and requires the same case, pipeline module,
SUCCEEDED status, ACTIVE run authority and ACTIVE assessment status. This uses
the established published authority boundary rather than insertion time or an
unfinished run's rows. Assessment generation already selects its supplied
current derivation; that path is unchanged.

Historical claims, assessments, safety results and snapshots remain preserved.
No rows are deleted or migrated. Existing contaminated stored results are not
recomputed by this query correction; legacy/unowned rows are not promoted to
current authority. Previously contaminated persisted results may require a
separately reviewed reprocessing/repair plan. No automatic repair is performed.

The `/report` query and report-selection semantics are unchanged. This does not
fix stale-current-report access after BLOCKED processing; its locked regression
still fails. Reports can reflect corrected safety on future processing, but no
historical-report API or selection policy is introduced.

## Exact files changed

- `app/pipeline/assessment.py`: scope both safety evidence queries.
- `app/api/routes.py`: select only authoritative current assessments.
- `docs/handoff/p0-historical-current-isolation.md`: this gate record.
- `DANDOONJAN_CURRENT_STATE_LOCK.md`: current gate pointer; prior records retained.

No tests were changed or weakened. No storage/orchestrator implementation,
migrations, dependencies, deployment configuration or prior gate records changed.

## Tests and exact failure comparison

All tests used the existing isolated Python 3.11 executable:
`/mnt/c/Users/Admin/AppData/Local/Temp/dandoonjan-p0-regression-venv/Scripts/python.exe`.
Synthetic data and deterministic/mock providers only.

Exact focused node IDs (also the only failures removed):

- `tests/regression_p0/test_derivation.py::test_historical_low_confidence_does_not_contaminate_current_safety`
- `tests/regression_p0/test_derivation.py::test_current_assessment_excludes_historical_derivations`

Before fix: 2 failed in 1.40s. Safety was MANUAL_REVIEW instead of NORMAL;
the current endpoint returned six assessments instead of three.
After fix: 2 passed in 1.16s; no failures, errors, skips or xfails.
These regressions also assert preservation of historical low-confidence claims,
superseded assessments, the old safety result and unchanged snapshot payload.

Relevant existing selection: `tests/test_api.py`, `tests/test_p0_orchestration.py`,
`tests/test_p01_reconciliation.py`, `tests/test_invariants.py`,
`tests/test_adversarial.py`, with `-q --tb=short`:
51 passed, 0 failed/errors/skipped, 4 warnings in 9.08s.

Existing suite: `python -m pytest tests --ignore=tests/regression_p0 -q --tb=short`:
109 passed, 0 failed/errors/skipped, 4 warnings in 20.09s.

Combined suite: `python -m pytest tests -q --tb=short -rfs`:
120 passed, 16 expected failures, 2 skipped, 0 errors, 4 warnings in 34.06s.
Failures remain ordinary failing tests, not xfails. Exact FAILED node IDs were
compared against the prior case-isolation gate log (18 failures): only the two
focused nodes disappeared, with no new or unexpectedly removed failures.

Remaining expected failures by category: source-distinct provenance (1),
processing identity (4), reportless terminal reuse parity (3), stale current
report (1), rejected-upload audit durability (1), migrations/schema/SQLite FK
integrity (5), Docker/frontend packaging (1).

Exact remaining failure node IDs:

- `tests/regression_p0/test_api_state.py::test_blocked_revision_never_returns_historical_report_as_current`
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

- Current safety and public assessments exclude the reproduced historical data.
- Historical rows and snapshots remain preserved in the focused scenarios.
- Existing 109-test behavior remains green; executable storage regressions and
  both case-isolation regressions still pass in the combined run.
- Stale-current-report regression remains failing for its separate gate.
- Complete source diff reviewed; `git diff --check` passes. Scope contains only
  the two selection corrections and gate documentation, with no test weakening.

## NOT VERIFIED / risks and limitations

- Real PostgreSQL runtime, concurrent processing/load, live providers, hosted
  deployment, browser behavior, actual Docker runtime, backup/restore and clinical
  readiness are not verified by this gate.
- Both Windows directory-symlink cases remain skipped due to WinError 1314
  (missing symlink privilege), as in the prior gate.
- Persisted contaminated outcomes are not repaired or invalidated automatically;
  no legacy database repair was attempted or verified.
- The historical critical-gap query is corrected at the same safety selection
  boundary; the two locked scenarios specifically exercise low-confidence history
  and assessment accumulation, not a separate historical critical-gap fixture.
- The 16 other locked defects remain unresolved. No later P0 gate was started.
