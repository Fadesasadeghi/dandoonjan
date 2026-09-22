# P0 case isolation / derivation authority gate

Date: 2026-09-22. Branch: `agent/sadeghi`.
Starting commit: `4b0581a8c7b5680f07cb92a584a8932f6da7b35e`.
Preflight verified that HEAD, the tracking ref, and the directly queried remote
all matched that commit, with 0 ahead/behind, a clean tree, and no untracked files.
On resumption, only the intended five-line orchestrator change existed; no gate
commit or documentation had yet been created.

Authority: [AGENTS.md](../../AGENTS.md), [approved roadmap](gate-1/ROADMAP.md),
[regression gate](p0-regression-tests.md), and [completed storage gate](p0-storage-containment.md).
Scope is the two locked cross-case authority/evidence-reuse regressions only.

## Confirmed root cause

The orchestrator creates a pipeline ProcessingRun owned by the target case and
passes its unique ID to the stages that create derived rows. Reuse selection
already filters by case and chooses that case's active pipeline run.

In `_activate_derivation`, tables with `case_id` were correctly restricted to the
case being processed. For tables without `case_id`, however, the bulk update only
required ACTIVE status and a derivation ID different from the new run. This
superseded rows from every other case, even with unrelated source material.

Affected tables: ArtifactClassification, ArtifactQualityAssessment, Extraction,
TreatmentItem, and EvidenceLink. Each already has a `derivation_run_id` pointing
to ProcessingRun, whose `case_id` provides the needed authority boundary.

Before the fix, the two locked tests reproduced both symptoms: processing B
superseded A's rows, and reusing A returned 0 evidence links instead of 5. A's
pipeline run remained ACTIVE because its separate authority update was already
case-scoped, creating the mismatch between run authority and reusable evidence.

## Implementation and ownership review

Added one ownership predicate to the no-`case_id` branch of `_activate_derivation`:
`derivation_run_id IN (SELECT id FROM processing_runs WHERE case_id = target_case)`.
The existing ACTIVE and not-the-new-derivation predicates remain intact.

The correction restricts the existing lifecycle operation without adding tables,
rewriting the pipeline, copying/collapsing claims, deleting evidence, or changing
provenance. Public APIs and normal single-case authority switching are unchanged.
Rows from another case are not selected, irrespective of document similarity.

Reviewed adjacent authority operations without modifying them:

- Direct-case derived tables already filter `table.case_id == case.id`.
- The ProcessingRun supersession update already filters case, pipeline module,
  ACTIVE authority, and excludes the new run.
- Failure cleanup selects the exact unique derivation ID created locally for the
  target case; it does not use a global ACTIVE-row update.
- Reuse first selects a case-owned active run, then counts that run's active rows.
- Stage row creation propagates the pipeline derivation ID; artifact ownership
  comes from `case.artifacts`, and claims/findings retain their case associations.

No schema migration, data repair, API decision, or Stop Condition was required.

## Exact files changed

- `app/pipeline/orchestrator.py`: five added lines (ownership predicate and comment).
- `docs/handoff/p0-case-isolation.md`: this gate record.
- `DANDOONJAN_CURRENT_STATE_LOCK.md`: current gate pointer, preserving prior references.

All tests, prior gate records, storage code, models, migrations, dependencies,
deployment files, and unrelated production code are unchanged. No secrets,
databases, logs, generated artifacts, or environment files are included.

## Tests and exact failure comparison

Used the existing isolated Windows Python 3.11 environment:
`/mnt/c/Users/Admin/AppData/Local/Temp/dandoonjan-p0-regression-venv/Scripts/python.exe`.
All test data is synthetic; AI is deterministic/mock. No dependencies changed.

| Selection (with `python -m pytest`) | Passed | Failed | Errors | Skipped | Warnings |
| --- | --- | --- | --- | --- | --- |
| `tests/regression_p0/test_derivation.py::test_processing_other_case_preserves_authority_and_evidence -q --tb=short`, before fix | 0 | 2 | 0 | 0 | 0 |
| Same focused selection, after fix and before interruption | 2 | 0 | 0 | 0 | 0 |
| `tests/test_p01_reconciliation.py tests/test_p0_orchestration.py tests/test_pipeline.py -q --tb=short` | 39 | 0 | 0 | 0 | 2 |
| `tests --ignore=tests/regression_p0 -q --tb=short` | 109 | 0 | 0 | 0 | 4 |
| `tests -q --tb=short -rfs` | 118 | 18 expected | 0 | 2 | 4 |

The successful focused result (2 passed in 0.92s) was retained from the completed
pre-interruption verification, as confirmed in the resumption handoff. It was not
unnecessarily rerun. All three broader selections were executed after resumption.

Exactly these failure node IDs disappeared from the previous gate's 20 failures:

- `tests/regression_p0/test_derivation.py::test_processing_other_case_preserves_authority_and_evidence[authority]`
- `tests/regression_p0/test_derivation.py::test_processing_other_case_preserves_authority_and_evidence[reuse]`

Compared the full combined failure-ID set against the prior gate's reported node
IDs and locked regression inventory: all 18 other failures remain, with no new
failures or unrelated unexpected passes. Total combined cases remain 138.
The two skips remain the Windows symlink privilege cases (`WinError 1314`).
Warnings are the existing Starlette/httpx, AnyIO, and FastAPI deprecations.

## Remaining expected P0 failures

| Category | Failure count |
| --- | --- |
| Historical/current safety and assessment isolation | 2 |
| Source-distinct claim provenance | 1 |
| Processing identity: model/provider/pack version/pack identity | 4 |
| Reportless terminal reuse safety parity | 3 |
| Stale current report after BLOCKED processing | 1 |
| Rejected-upload audit durability | 1 |
| Populated migrations, startup-schema adoption, schema FK drift, SQLite FK enforcement | 5 |
| Docker frontend packaging | 1 |

These failures remain visible and unfixed. Exact names and baseline evidence are
preserved in the [regression gate record](p0-regression-tests.md).

## Verification boundaries and risks

- **VERIFIED WORKING:** the locked A-process/B-process/A-reuse scenarios preserve
  A's derived authority and five reusable evidence links, correct case ownership,
  A's snapshot, and B's state during A reuse. Existing single-case revision,
  failure/retry, provenance, orchestration, and pipeline tests remain green.
- **VERIFIED BROKEN:** the 18 remaining locked regression failures above.
- **NOT VERIFIED:** real PostgreSQL behavior, concurrent processing/load (including
  the five-request acceptance target), repair/reprocessing of already-corrupted
  derived data, and shared-source scenarios beyond existing coverage. Existing
  Gate 1 deployment/provider/browser/HEIC/backup/clinical verification limits remain.
  Symlink tests remain skipped; the storage gate was not reopened or modified.
- **RISKS:** this predicate prevents future cross-case supersession; it does not
  restore rows previously marked SUPERSEDED by the old implementation. Ownership
  relies on the existing derivation-to-case association; this gate does not repair
  malformed legacy associations or the separately audited FK/migration defects.

Full diff and whitespace review, unchanged-test/scope checks, Python syntax, and
local documentation-link checks accompany this gate. Stop after one
`fix: isolate derived state by case authority` commit, push to
`origin agent/sadeghi`, and publication verification. Historical/Current Isolation
and later gates require the next instruction.
