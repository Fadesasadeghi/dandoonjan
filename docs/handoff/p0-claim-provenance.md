# P0 claim provenance gate

Date: 2026-09-22. Branch: `agent/sadeghi`.
Starting commit: `e663bc9db6965914df9ea71687d57be03b66db43`.
Pre-flight verified branch, HEAD, origin tracking ref and directly queried remote
tip; all matched the required starting state, with 0 ahead/behind, a clean tree
and no untracked files. Followed AGENTS.md and the approved handoff/roadmap.

## Regression and root cause

Exact locked node ID:
`tests/regression_p0/test_derivation.py::test_same_proposition_keeps_clinician_and_document_provenance`.

Before editing, this failed on the required starting commit: the clinician claim
existed but the document claim list was empty despite a matching document finding.
The assertion was `same proposition lost independent clinician/document source`.

`build_case_claims.add_claim` deduplicated by claim type, subject, treatment and
modality alone. Clinician claims were built first. A matching document proposition
therefore returned the clinician Claim before creating its independent provenance.
The source records were not merged after persistence; document Claim/provenance
creation was suppressed at this boundary.

## Correction and preservation

The same proposition now deduplicates only when source type AND the persisted
source reference also match. Document references include artifact public IDs,
so distinct document references are not collapsed merely by proposition equality.
The existing model-inferred restatement suppression is retained: model candidates
built from those same extracted facts still defer to matching existing claims,
as required by existing P0-01-B coverage. No general deduplication redesign occurs.

The locked clinician/document scenario now has distinct Claim IDs, distinct
ProvenanceRecord IDs with their own truth types, and a traceable document artifact
reference. Same-source proposition matching, canonical semantics, case/derivation
scoping and the pipeline remain unchanged. No historical rows are deleted,
rewritten or repaired. Previously omitted provenance is not restored automatically;
existing reused outcomes may need separately reviewed reprocessing to gain it.

## Files changed

- `app/pipeline/claims.py`: source identity predicate and explanatory comment.
- `docs/handoff/p0-claim-provenance.md`: this gate record.
- `DANDOONJAN_CURRENT_STATE_LOCK.md`: completed gate pointer and current totals.

No tests, migrations, dependencies, packaging, prior gate records or unrelated
production code changed. Later P0 gates were not changed or started.

## Tests

Used the existing isolated Python 3.11 environment:
`/mnt/c/Users/Admin/AppData/Local/Temp/dandoonjan-p0-regression-venv/Scripts/python.exe`.
Synthetic data and deterministic/mock AI only; no environment changes.

- Exact focused node, `-q --tb=short -rfs`, before: 1 failed in 0.77s;
  after: 1 passed in 0.68s. No errors, skips or warnings.
- Relevant existing selection: `tests/test_p0_claims_extraction.py
  tests/test_p0_provenance.py tests/test_pipeline.py tests/test_p01_reconciliation.py
  -q --tb=short`: 51 passed in 14.81s, no failures/errors/skips/warnings.
- `python -m pytest tests --ignore=tests/regression_p0 -q --tb=short`:
  109 passed, 0 failed/errors/skips, 4 unchanged warnings in 24.93s.
- `python -m pytest tests -q --tb=short -rfs`:
  122 passed, 14 expected failures, 2 skipped, 0 errors, 4 warnings in 44.27s.

Compared exact FAILED node IDs with the preceding current-report gate log:
15 failures before, 14 after; only the provenance node above disappeared.
No new failure or unrelated unexpected pass appeared. Expected failures remain
ordinary failing tests, not xfails. All executable storage, case isolation,
historical/current isolation and current-report regressions remain green.

Remaining categories: processing identity (4), terminal reuse parity (3), upload
audit durability (1), migrations/schema/FK integrity (5), packaging (1).

Exact unchanged remaining failure node IDs:

- `tests/regression_p0/test_api_state.py::test_rejected_upload_persists_audit_without_partial_ingestion`
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

- Independent clinician/document provenance for identical normalized propositions.
- Existing model-restatement suppression, claim/provenance and pipeline tests.
- Existing 109-test baseline and completed gate regressions.
- Complete diff/scope review and `git diff --check`; no test weakening or
  secrets, DBs, journals, logs or generated artifacts included.

## NOT VERIFIED / risks

- Real PostgreSQL, concurrency, live providers, deployment, clinical readiness,
  arbitrary multi-document/within-document source variations and legacy provenance
  repair are not certified by this gate's locked scenario.
- Source identity uses the existing source type/reference representation and its
  existing truncation. Within-source occurrence/locator deduplication is not
  redesigned; this gate preserves the approved clinician/document distinction.
- Both Windows symlink tests remain skipped for WinError 1314 (missing privilege).
- Historical missing claims/provenance remain missing until appropriate
  reprocessing; no automatic data repair or reuse invalidation is introduced.
- The other 14 locked P0 defects remain unresolved. Stop after publication.
