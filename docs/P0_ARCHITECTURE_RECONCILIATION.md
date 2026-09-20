# P0 ARCHITECTURE RECONCILIATION

Date: 2026-09-06. Scope: foundation hardening only — no new features.

## Baseline

- Tests: 43 passed (`python -m pytest tests -q`).
- Migration head: `13cb12f30f53` (initial domain schema).
- Known gaps found by audit: P0-01 … P0-12 below.

## Issue-by-issue plan

| Issue | Current behavior | Architectural gap | Target behavior | Affected modules | Planned tests |
|---|---|---|---|---|---|
| P0-01 | Evidence graph skips PATIENT_REPORTED/CLINICIAN_REPORTED claims; separate MODEL_INFERRED claims duplicate them | Core product claim ("dentist says RCT needed") is never assessed | Findings link to reported claims; dedupe MODEL_INFERRED duplicates; reported claims assessable | pipeline/claims.py, pipeline/assessment.py | P0-01-A/B/C |
| P0-02 | build_findings re-reads raw text with regex, bypassing extraction | Parallel RAW→REGEX→FINDING path | Findings built only from validated ExtractedField outputs; no raw fallback | pipeline/stages.py | P0-02-A/B/C, INV-01 |
| P0-03 | Structural schema only; canonical values weakly validated | TOOTH_900-class values could enter state | Ontology + semantic validation before persistence; controlled failure | pipeline/claims.py, stages.py, ontology | P0-03-A/B/C |
| P0-04 | Rerun duplicates facts; case.version static | No idempotency, no versioning | Effective-input-hash reuse or explicit retry; version bumps on material change | pipeline/orchestrator.py, runs.py, ingestion.py, api/routes.py | P0-04-A/B/C/D |
| P0-05 | `immutable` flag not enforced | Fake immutability | ORM event guards: snapshot/audit fully frozen, artifact source identity frozen; verify_snapshot_integrity() | governance/immutability.py, reporting.py | P0-05-A/B/C/D |
| P0-06 | MANUAL_REVIEW cases still got REPORT_READY | Safety bypass | Per-state report policy; MANUAL_REVIEW→review-pending only; BLOCKED→no report | pipeline/assessment.py, reporting.py, orchestrator.py | P0-06-A/B/C/D |
| P0-07 | Quality rows created but never gate | Gate does not gate | CONTINUE / CONTINUE_WITH_LIMITATIONS / NEEDS_MORE_EVIDENCE / REJECT_ARTIFACT decisions drive workflow | pipeline/stages.py, orchestrator.py | P0-07-A/B/C |
| P0-08 | knowledge_pack_id globally unique | One version per logical pack | Unique (knowledge_pack_id, version); snapshot stores exact pack id+version | domain/models.py, knowledge/pack.py, migration | P0-08-A/B/C |
| P0-09 | Snapshot versions thin | Cannot reconstruct provenance | Snapshot freezes artifact hashes, claim/finding/link/gap IDs, model runs, prompt/schema versions | pipeline/reporting.py | P0-09-A/B/C |
| P0-10 | alembic.ini hardcodes SQLite URL | Migrations ignore DJ_DATABASE_URL | env.py uses app config | alembic/env.py | P0-10-A/B/C |
| P0-11 | Some invariant tests shallow | Weak regression proof | Behavior-level invariant tests | tests/ | INV-01..08 |
| P0-12 | Harness ignores some spec keys | Silent assertion gaps | Harness enforces every spec key, rejects unknown keys; expanded adversarial cases | tests/test_evaluation_harness.py, evaluation/ | full harness |

## Claim/Finding semantic rule (master doc §14–15)

`MENTIONED/PLANNED/RECOMMENDED` document findings link to treatment claims as
`RELEVANT_TO`, never `SUPPORTS`. A treatment plan mentioning RCT supports the
existence of a recommendation, not medical necessity. Necessity assessments remain
INSUFFICIENT_EVIDENCE until Knowledge-Pack evidence exists. No circular evidence.

## Outcome

All 12 issues FIXED. Final verification (2026-09-06):

- Full suite: 86 passed (`python -m pytest tests -q`), verbose run clean.
- Alembic: baseline `13cb12f30f53` + P0 migrations `d632177845ea`, `a5716dc9a797`;
  `DJ_DATABASE_URL` honored (verified against a temporary SQLite target and a
  refusing PostgreSQL URL).
- Manual scenarios A–E: all PASS (`python manual_verification_p0.py`).

Fix map (files):
- P0-01 FIXED: `app/pipeline/claims.py` (reported claims linked + dedupe),
  `app/pipeline/assessment.py` (reported claims assessable).
- P0-02 FIXED: `app/pipeline/stages.py::build_findings_from_extraction`,
  `app/domain/models.py` (Finding.extracted_field_id).
- P0-03 FIXED: `app/pipeline/claims.py::validate_claim_semantics`,
  `app/pipeline/stages.py` (ontology firewall on classification/extraction).
- P0-04 FIXED: `app/pipeline/orchestrator.py` (pipeline-level run, effective-input
  hash, reuse), `app/pipeline/runs.py` (attempt increments), `app/core/artifacts/
  ingestion.py` + `app/api/routes.py` (version bumps), PATCH /cases.
- P0-05 FIXED: `app/governance/immutability.py` (ORM guards, MutableDict-tracked
  JSON, `verify_snapshot_integrity`), registered from `app/domain/models.py`.
- P0-06 FIXED: `app/pipeline/assessment.py` (BLOCKED/MANUAL_REVIEW triggers),
  `app/pipeline/reporting.py` (review-pending/urgent-only reports, integrity check),
  `app/pipeline/orchestrator.py` (state policy).
- P0-07 FIXED: `app/pipeline/stages.py` (QualityDecision), `app/pipeline/
  orchestrator.py` (gate drives NEEDS_MORE_EVIDENCE / rejection / limitations).
- P0-08 FIXED: `app/domain/models.py` (uq logical id + version),
  `app/core/knowledge/pack.py`, migration `d632177845ea`.
- P0-09 FIXED: `app/pipeline/reporting.py::create_snapshot` (full provenance
  payload + version block).
- P0-10 FIXED: `alembic/env.py` (app-config URL override); migrations
  `d632177845ea`, `a5716dc9a797` (+ FK name fix).
- P0-11 FIXED: `tests/test_p0_*.py` (behavior-level invariant tests).
- P0-12 FIXED: `tests/test_evaluation_harness.py` + `evaluation/**` (strict key
  enforcement, unknown keys rejected, expanded adversarial/safety specs).
- §16 FIXED: `app/pipeline/orchestrator.py` (NEEDS_MORE_EVIDENCE/MANUAL_REVIEW
  branches; REPORT_READY only when a real report exists).
