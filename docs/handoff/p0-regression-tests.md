# P0 regression-test gate

Recorded: 2026-09-22. Scope: tests and documentation only; no fixes implemented.
Parent: approved Gate 1 commit `b7f5801dd11d8d6f7ba774c9d3b15c6d28a1366d`
on `agent/sadeghi`. Before editing, HEAD, the local tracking ref, and the remote
branch all matched that commit, and the working tree was clean.

Authority: [Gate 1 audit](gate-1/AUDIT.md), [roadmap](gate-1/ROADMAP.md),
[approved decisions](gate-1/DECISIONS.md), and [AGENTS.md](../../AGENTS.md).
This gate encodes expected correct behavior before production changes. Expected
failures are ordinary pytest failures, not `xfail`, skips, or weakened assertions.
Encoding a regression does not mean its defect is fixed.

## Test structure and prior coverage

All new tests are under [tests/regression_p0](../../tests/regression_p0/).
The local `conftest.py` reuses the existing root `db`, `case`, and `pdf_bytes`
fixtures; its PDF helper follows the existing PyMuPDF/ingestion pattern. It scopes
settings to temporary storage/databases and deterministic Mock AI. API tests use
TestClient with a temporary engine/session factory and the actual `get_db`
transaction lifecycle, without overriding commit/rollback behavior.

New tests are separate because the nearest existing tests exercise useful but
different conditions. No existing test was edited or weakened.

| Group | Closest existing coverage | Missing boundary encoded here |
| --- | --- | --- |
| A: Storage | `test_ingestion.py::test_storage_keys_opaque_and_no_original_path` | Internal read/write containment, sibling-prefix boundaries, outside absolute paths, symlinks. |
| B: Authority | `test_p01_reconciliation.py::test_dq1_revision_rerun_does_not_accumulate`, `test_dq1_no_authority_vacuum_on_failure` | Two independently processed cases and subsequent A reuse. |
| C: History/current state | `test_p0_orchestration.py::test_p0_06_a_manual_review_blocks_normal_report`; P0.1 single-case revision tests | A low-confidence historical run followed by a normal-confidence revision; public assessment selection. |
| D: Current report | `test_api.py::test_case_lifecycle`, `test_report_404_before_processing`; `test_p0_06_b_blocked_safety_no_report` | BLOCKED processing after a successful report, with preserved historical report/snapshot. |
| E: Provenance | `test_p0_provenance.py::test_inv04_identical_statements_stay_distinct`; `test_p0_claims_extraction.py::test_p0_01_b_no_duplicate_model_inferred_claim` | Same subject, treatment, and modality from clinician and document. Existing provenance coverage uses different modalities and therefore misses this collision. |
| F: Identity | `test_p0_orchestration.py::test_p0_04_d_modified_case_new_processing_identity`; knowledge-pack version tests in `test_p0_provenance.py` | Configuration-only changes with unchanged case inputs. |
| G: Terminal reuse | `test_p01_reconciliation.py::test_d2_needs_more_evidence_reused`, `test_d3_blocked_without_artifacts_no_report`, `test_d8_reuse_result_same_contract` | NORMAL, CAUTION, and BLOCKED terminal results without snapshots/reports. |
| H: Migrations/integrity | `test_p0_provenance.py::test_p0_10_a_alembic_targets_dj_database_url` | Populated predecessors, startup-schema adoption, actual migrated FK shape, and runtime SQLite FK enforcement. |
| I: Rejected audit | `test_api.py::test_unsupported_upload_rejected_with_safe_message`; ingestion rejection tests | Audit durability after the failed request closes, with no partial ingestion. |
| J: Packaging | No existing deterministic Docker inclusion test found; `test_api.py::test_presentation_home_and_demo_sample` covers the source checkout | Static COPY source/layout coverage for the frontend file required at startup/runtime. |

## Exact regression inventory and observed outcomes

Paths below are relative to `tests/regression_p0/`. There are **29 new test cases**.

### A — `test_storage.py`

- `test_storage_descendant_round_trip`: **PASS**; a true descendant is stored/read correctly.
- `test_storage_read_rejects_escape[sibling-prefix]` and
  `[absolute-sibling-prefix]`: **EXPECTED FAIL**; outside synthetic bytes are read
  without `StorageError` because the sibling name starts with the root string.
- `test_storage_read_rejects_escape[parent]` and `[absolute-outside]`: **PASS**;
  the existing string-prefix check already rejects these non-prefix escapes.
- `test_storage_write_rejects_parent_escape[store-neighbor]`: **EXPECTED FAIL**;
  the write is allowed outside the root through the sibling-prefix boundary.
- `test_storage_write_rejects_parent_escape[outside]`: **PASS**; the existing
  check rejects this ordinary parent escape before creating outside files.
- `test_storage_rejects_symlink_escape[read]` and `[write]`: **SKIPPED / NOT VERIFIED**;
  Windows returned `WinError 1314` when creating the directory symlink. Both are
  encoded and will execute on a platform with directory-symlink support.

The four passes are validated controls, not evidence that general containment is
fixed. Their paths differ from the audited sibling-prefix bypass; they were not
artificially changed to fail.

### B/C/E/F/G — `test_derivation.py`

All 12 cases below are **EXPECTED FAIL**:

- `test_processing_other_case_preserves_authority_and_evidence[authority]`:
  processing B changes A's artifact/claim-scoped derived rows from ACTIVE to
  SUPERSEDED. The test expires ORM state after bulk SQL and preserves B's state
  and A's snapshot while checking A's ownership links.
- `test_processing_other_case_preserves_authority_and_evidence[reuse]`:
  A reuse returns **0 evidence links instead of 5** after processing B.
- `test_historical_low_confidence_does_not_contaminate_current_safety`:
  current normal-confidence claims still yield MANUAL_REVIEW instead of NORMAL.
  Historical low-confidence claims, safety state, and snapshot remain preserved.
- `test_current_assessment_excludes_historical_derivations`:
  the current endpoint returns **6 assessments instead of the current 3**.
  The assessment engine itself scopes the new rows; public selection accumulates
  history, while safety queries independently include historical claims.
- `test_same_proposition_keeps_clinician_and_document_provenance`:
  the document finding exists for the identical RECOMMENDED proposition, but its
  independent document claim is absent. No new within-source deduplication rule
  is prescribed.
- `test_material_processing_configuration_invalidates_reuse[model]`, `[provider]`,
  `[pack-version]`, and `[pack-identity]`: configuration changes incorrectly reuse
  the old derivation. Provider change uses an in-process MockProvider subclass,
  including a replacement constructor; no live adapter call or credential is used.
  Earlier snapshots are preserved, and the tests require new processing afterward.
- `test_reused_reportless_terminal_result_preserves_safety[normal]`, `[caution]`,
  and `[blocked]`: reuse returns `safety_state=None` instead of the fresh safety
  state. Tests also check terminal status/report semantics, stable run count,
  and preservation of the derivation's rows.

### D/I — `test_api_state.py`

- `test_blocked_revision_never_returns_historical_report_as_current`:
  **EXPECTED FAIL**; `/report` returns HTTP 200 with the old report after the
  changed revision returns BLOCKED/no report. Historical report and snapshot
  preservation are checked first. No particular future historical API or error
  status is imposed.
- `test_rejected_upload_persists_audit_without_partial_ingestion`:
  **EXPECTED FAIL**; a separate post-request session finds **0** `artifact_rejected`
  events instead of 1. No artifact/file/version change occurred, and the earlier
  case audit record remains intact.

### H — `test_migrations.py`

All five cases are **EXPECTED FAIL**:

- `test_populated_initial_upgrade_preserves_finding`: valid synthetic data is
  inserted at `13cb12f30f53`, then upgrade to `d632177845ea` fails on
  `NOT NULL constraint failed: _alembic_tmp_findings.predicate`.
- `test_populated_pre_p01_upgrade_preserves_processing_run`: a populated
  `a5716dc9a797` predecessor fails upgrading to head on
  `NOT NULL constraint failed: _alembic_tmp_processing_runs.authority`.
- `test_startup_created_database_can_enter_alembic_lifecycle`: actual SQLite
  startup schema creation followed by the documented Alembic upgrade fails on
  `table audit_events already exists`. No blind stamping or proposed adoption
  design is added; preservation of a synthetic user is required.
- `test_migrated_finding_treatment_item_fk_matches_model`: empty upgrade succeeds,
  but inspection finds the ORM's `findings.treatment_item_id → treatment_items.id`
  FK missing from the migrated schema.
- `test_runtime_sqlite_connections_enforce_foreign_keys`: application
  `make_engine` returns a runtime connection with `PRAGMA foreign_keys = 0`.

Predecessor fixtures use their real migrated schemas, explicit required values,
valid parent rows, and `foreign_key_check` before upgrade. Migration failures are
production upgrade failures, not invalid fixture inserts. No migration file,
schema workaround, or test-only backfill was introduced.

### J — `test_packaging.py`

- `test_docker_copy_includes_frontend_at_application_runtime_path`:
  **EXPECTED FAIL**; the current single-stage Dockerfile's COPY layout omits
  `/app/frontend/index.html`. This bounded static check does not simulate all
  Docker instructions or certify build context filtering, building, or runtime.

## Executed checks

Windows CPython **3.11**, in a temporary virtual environment populated from the
unchanged `requirements.txt`. Relevant installed versions: pytest 9.1.1,
SQLAlchemy 2.0.54, Alembic 1.20.0, FastAPI 0.141.1, Starlette 1.6.0,
Pydantic 2.13.5, PyMuPDF 1.28.2. Repository dependency declarations were not changed.
The first environment probe could not collect tests because SQLAlchemy was absent;
after isolated environment setup, there were no collection or fixture errors.

| Command (using that environment's `python`) | Total | Passed | Failed | Errors | Skipped | Warnings |
| --- | --- | --- | --- | --- | --- | --- |
| `python -m pytest tests/regression_p0 -q --tb=short -rfs` | 29 | 4 | 23 | 0 | 2 | 4 |
| `python -m pytest tests --ignore=tests/regression_p0 -q --tb=short` | 109 | 109 | 0 | 0 | 0 | 4 |
| `python -m pytest tests -q --tb=short -rfs` | 138 | 113 | 23 | 0 | 2 | 4 |

The focused results were reproduced on a second run. The combined run has the same
23 new expected failures and two platform skips; all 109 pre-existing tests still
pass. Existing-suite regression count: **0**. Accidental test/fixture errors: **0**.
The four warnings concern Starlette/httpx, AnyIO BlockingPortal, and FastAPI's
deprecated startup event API (two occurrences); no warning was suppressed.

Python syntax and complete diff/whitespace checks were reviewed. Only six new
test/helper files, this gate record, and the state-lock pointer are in scope.
Production code, migrations, dependency declarations, and existing tests remain
unchanged. No credentials, temporary databases, logs, or generated artifacts are
included in the commit.

## Remaining limits and next boundary

- **NOT ENCODED:** none of the requested audited defect classes A–J was omitted.
  Arbitrary additional model sampling settings are not separately encoded: the
  current pipeline configuration exposes provider/model selection, covered here;
  no future processing manifest is invented by these tests.
- **NOT VERIFIED:** symlink read/write enforcement on a capable platform; actual
  Docker build/run and full context filtering; PostgreSQL runtime/migrations;
  live provider and hosted Render/Netlify behavior; real browser behavior; HEIC;
  concurrency/load (including five simultaneous requests); backup/restore;
  clinical correctness/readiness. These are not claimed broken solely because
  they were not exercised.
- The requirements are not fully pinned; this environment reproduces the baseline
  test count but is not asserted to match every original audit package version.
- Minimal populated SQLite fixtures capture the named failures; they do not
  establish safety for every possible populated schema/data combination.
- All captured failures remain unfixed. No materially different root cause or new
  product/API decision was required for this gate.

Stop after the single `test: lock P0 regression coverage` commit, push to
`origin agent/sadeghi`, and publication evidence report. Storage Containment and
all later implementation gates require the next instruction.
