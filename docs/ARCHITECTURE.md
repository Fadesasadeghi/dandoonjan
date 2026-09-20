# Architecture

Modular monolith (Python/FastAPI). Flow is mandatory:

USER QUESTION + RAW ARTIFACTS -> SECURE INGESTION -> CLASSIFICATION -> QUALITY GATE ->
STRUCTURED EXTRACTION -> NORMALIZATION -> CLAIM MODEL -> EVIDENCE GRAPH ->
KNOWLEDGE PACK POLICY -> GAP ANALYSIS -> ASSESSMENT -> SAFETY GATE ->
IMMUTABLE SNAPSHOT -> PATIENT REPORT.

There is no code path from FILE to LLM to PATIENT ANSWER (INV-01, tested).

Layout: `app/domain` (models/enums), `app/core` (cases, artifacts, ontology,
knowledge), `app/ai` (gateway, providers, prompts, schemas), `app/pipeline`
(stages, claims, assessment, reporting, orchestrator, runs), `app/governance`
(provenance/audit), `app/security` (ingestion), `app/api` (routes), `frontend/`
(static RTL UI), `evaluation/` (golden/adversarial/safety), `tests/`, `alembic/`.

Modules map to canonical IDs 00_APP_SHELL .. 19_EVALUATION_HARNESS as logical
boundaries, not services. Deployment: WEB+API+WORKER+DB+OBJECT STORAGE (V0: single
process, filesystem storage, synchronous worker path).

## P0 immutability (P0-05)

Real immutability is enforced by ORM event guards (UPDATE *and* DELETE on
protected entities; bulk update/delete of protected entities is banned in app code
by a static architectural test) (`app/governance/immutability.py`):
AssessmentSnapshot and AuditEvent rows are fully append-only; Artifact source
identity (storage_key, sha256, file_size, filenames, detected MIME) cannot be
overwritten. Violations raise ImmutabilityViolationError at flush. Snapshot
integrity is verifiable via `verify_snapshot_integrity(snapshot)` (sha256 of
canonical payload+versions), and the report composer refuses unverified snapshots.
`alembic/env.py` targets DJ_DATABASE_URL via app config (P0-10), never a
hardcoded dev file.
