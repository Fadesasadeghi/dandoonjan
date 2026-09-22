# P0 processing identity gate

Date: 2026-09-22. Branch: `agent/sadeghi`.
Starting commit: `3bc053ba879861fffde01bc56119e83b0643b3b1`.
Pre-flight reverified the branch, required HEAD, tracking ref, direct remote tip,
0 ahead/behind, clean working tree and no untracked files. The uncommitted change
was limited to `app/pipeline/orchestrator.py`; its diff and `git diff --check`
matched the intended correction.

## Regressions and root cause

The four locked nodes were:

- `tests/regression_p0/test_derivation.py::test_material_processing_configuration_invalidates_reuse[model]`
- `tests/regression_p0/test_derivation.py::test_material_processing_configuration_invalidates_reuse[provider]`
- `tests/regression_p0/test_derivation.py::test_material_processing_configuration_invalidates_reuse[pack-version]`
- `tests/regression_p0/test_derivation.py::test_material_processing_configuration_invalidates_reuse[pack-identity]`

Before the correction all four failed because `effective_input_hash` omitted the
material processing configuration; reuse compared only case inputs and module
versions. Each changed configuration therefore found the prior ACTIVE/SUCCEEDED
run and returned `reused=True`.

## Correction and identity definition

The existing deterministic hash now includes:

- pipeline schema and module versions (existing dimensions);
- configured AI provider;
- configured AI model name;
- active knowledge-pack stable ID and version;
- case text/version and artifact public ID, hash and extracted text (existing inputs).

The active pack is read through the existing knowledge-pack boundary before hash
calculation. Reuse lookup remains unchanged and still requires case ownership,
pipeline module, SUCCEEDED status, ACTIVE authority and equal input hash. No new
manifest, table or architecture abstraction was introduced.

The correction changes reuse decisions over existing ProcessingRun rows: old
stored hashes are preserved, not rewritten. A previously stored run is reused only
when its stored identity equals the newly calculated identity; configuration
changes create a fresh run. No migration, data repair or destructive rewrite is
needed. Newly created runs persist the expanded hash in the existing
`ProcessingRun.input_hash` column.

`_reused_result`, safety-state restoration and reportless terminal behavior were
not touched. Terminal Reuse Parity is a separate gate and remains unresolved.
Case authority, historical/current selection, current-report authority and claim
provenance are unchanged.

## Files changed

- `app/pipeline/orchestrator.py`: processing identity hash inputs and call site.
- `docs/handoff/p0-processing-identity.md`: this gate record.
- `DANDOONJAN_CURRENT_STATE_LOCK.md`: current gate pointer and totals.

No tests, migrations, dependencies, packaging files, or prior gate records changed.

## Verification

Used the existing isolated Python 3.11 environment:
`/mnt/c/Users/Admin/AppData/Local/Temp/dandoonjan-p0-regression-venv/Scripts/python.exe`.
Synthetic data and deterministic/mock providers only.

- Focused before: all four nodes failed (1.21s).
- Focused after: 4 passed in 1.07s, no errors/skips.
- Relevant existing processing/orchestration/reuse/configuration tests: 52 passed,
  2 warnings, no failures/errors.
- Existing suite (`tests --ignore=tests/regression_p0`): 109 passed, 0 failures/errors,
  4 warnings in 16.16s.
- Combined suite: 126 passed, 10 expected failures, 2 skipped, 0 errors,
  4 warnings in 27.43s.

Exact comparison with the preceding claim-provenance gate's 14 failures: only the
four processing-identity nodes above disappeared. No new failure or unrelated
pass appeared. Storage, case isolation, historical/current isolation, current
report semantics and claim provenance regressions remain green. The three terminal
reuse parity failures remain failing as required.

Remaining expected failure nodes:

- `tests/regression_p0/test_api_state.py::test_rejected_upload_persists_audit_without_partial_ingestion`
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

- Provider, model, knowledge-pack version and knowledge-pack identity changes
  invalidate inappropriate reuse.
- Matching identity still uses the existing eligible-reuse path.
- Existing data is preserved; only future reuse comparisons change.
- No migration or dependency change was required.
- Terminal Reuse Parity was not fixed. Later gates were not changed or started.
- Diff scope and whitespace checks pass; no temporary artifacts or secrets included.

## NOT VERIFIED / risks

- Previously stored hashes from before this correction do not encode the added
  dimensions; they remain preserved and may not be reusable when compared with a
  newly calculated expanded identity. No automatic repair or backfill occurs.
- Real provider behavior, PostgreSQL, concurrency, hosted deployment and clinical
  readiness remain outside this gate. Windows symlink cases remain skipped due to
  WinError 1314.
- The other 10 locked P0 failures remain unresolved.
