# AUDIT

Source: the established Gate 1 findings supplied in the approved handoff, recorded
without inventing reproduction details. These tests were not rerun for the
documentation-only lock.

## VERIFIED WORKING — tested scope only

Existing automated suite: **109 total; 109 passed; 0 failed; 0 skipped; 4 warnings**.
Existing manual verification scenarios also passed. Warning details were not
provided in the handoff and are not inferred here.

Verified working in the tested scope:

- Local application startup and health endpoints.
- Basic case API lifecycle, including case creation/retrieval/update.
- Artifact upload and mock processing.
- Normal assessment/report flow and tested idempotent reuse.
- Fresh SQLite initialization and local restart persistence.
- Common file validation and duplicate upload detection.
- Tested snapshot protections and mocked OpenRouter behavior.

## VERIFIED BROKEN — independent reproduced defects/gaps

1. Cross-case derivation authority/isolation failure.
2. Historical assessment/safety contamination.
3. An old report can be returned as current after newer processing is BLOCKED.
4. Source-distinct clinician/document claims can lose provenance through destructive deduplication.
5. Material model/knowledge-pack configuration is not fully represented in processing reuse identity.
6. Fresh/reused early-exit behavior can lose safety-state parity.
7. Populated Alembic migration paths can fail.
8. Migration schema and ORM model schema have drift.
9. Startup-created databases cannot safely enter the Alembic lifecycle directly.
10. SQLite foreign-key enforcement was disabled in the tested runtime connection.
11. Internal storage path containment can be bypassed by sibling-prefix/path-boundary behavior.
12. Rejected uploads do not reliably persist their audit event.
13. Docker packaging omits frontend runtime content required by application startup.

Passing existing tests does not negate these independent findings. No remediation
is claimed by this documentation commit.

## PARTIALLY VERIFIED

Local/mock and selected normal paths have the coverage listed above. That coverage
does not establish general correctness of reuse, isolation, safety, migrations,
or deployment. Packaging omission is an established finding; actual Docker
build/run behavior remains unverified.

## NOT VERIFIED — not yet fully verified

- Real PostgreSQL runtime.
- Live AI provider.
- Actual Docker build/run.
- Real hosted Render/Netlify environment.
- Real browser behavior.
- HEIC support.
- Concurrency/load behavior, including the approved five-request acceptance target.
- Backup/restore.
- Clinical correctness/readiness.

These areas are not described as broken merely because verification is incomplete.
