# P0 Migrations / Integrity

- Starting commit: `d7a28b56a2299ca20d479dc9adfbc9f90472dfcb`
- Scope: populated synthetic migration safety, startup-schema adoption, migrated FK integrity, and SQLite FK enforcement.

## Changes

- Alembic online migrations now run inside the connection transaction, preserving revision rows.
- Startup-created databases are adopted only after strict current-schema and FK validation and only for a head target.
- `findings.predicate` is added nullable, existing NULL rows are backfilled to `MENTIONED`, then the column is made NOT NULL.
- `processing_runs.authority` is added nullable, existing NULL rows are backfilled to `NON_AUTHORITATIVE`, then the column is made NOT NULL.
- The reachable head `4f2c9d7e1a10` repairs the physical `findings.treatment_item_id → treatment_items.id` FK.
- SQLite runtime connections enable `PRAGMA foreign_keys=ON`.

All existing rows are preserved; no database recreation or destructive migration was used.

## Verification

- Focused migration regressions: **5 passed, 2 warnings** (recorded successful run, 8.45s).
- Existing suite excluding `tests/regression_p0`: **109 passed, 4 warnings**.
- Combined suite: **134 passed, 2 expected failures, 2 skipped, 4 warnings**.
- Remaining expected failures are rejected-upload audit durability and Docker/frontend packaging.
- `git diff --check`: passed.
- Migration graph head: `4f2c9d7e1a10`.

## Not verified / risks

Real PostgreSQL deployment, hosted environments, and production backup/restore remain outside this gate. Startup adoption is intentionally fail-closed for schemas that do not match the validated current application signature.
