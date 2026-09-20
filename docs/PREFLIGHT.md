# PREFLIGHT — Phase 0 Repository Audit

Date: 2026-09-06

## Current state (before implementation)
- Repository `E:\dandon` was completely empty (no code, no config, no git history).
- No existing stack to reuse; no conflicts.

## Toolchain found
- Python 3.11.15 (pip available), Node 24 / npm 11 (unused for V0 frontend).
- Python packages installed: FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, pytest,
  httpx, python-multipart, pymupdf, pillow.

## Reuse candidates
- None (empty repo). All components bootstrapped per the locked architecture.

## Conflicts / deviations (documented, minimal)
1. **Dev database**: `SQLite` is the default `DJ_DATABASE_URL` for offline local dev/tests;
   production points to PostgreSQL via the same SQLAlchemy models. Alembic migration
   `13cb12f30f53_initial_domain_schema` provides the clean path from an empty DB.
2. **Worker**: V0 processing is invoked synchronously by `POST /cases/{id}/process`
   (no queue needed at this scale); every stage records a `ProcessingRun` so a real
   queue can be introduced without changing stage code.
3. **Frontend**: a single-page static RTL app (3 screens) served by FastAPI at `/ui`
   instead of Next.js — zero build step, matches "do not overbuild frontend".
4. **Report composer**: deterministic template composer over the Assessment Snapshot
   (no LLM in the report path). This is stricter than the allowed "AI for explanation"
   and keeps V0 fully offline-verifiable.

## Implementation path
Sequential phases 1-14 per the master prompt; architecture locked as specified.
