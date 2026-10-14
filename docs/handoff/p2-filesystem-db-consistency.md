# P2 #2 — Filesystem / database consistency

Baseline branch: `agent/sadeghi-next-phase`.
Baseline HEAD: `d7dfc8ee62138c11dd684b22ccbc264f5a210b1b`.
Scope: synthetic ACCOUNT and Demo; disposable SQLite and temporary storage;
Mock/offline providers only. No production edits were justified by this audit.

## Contract and inspected areas

Read the approved Gate 1 README, decisions, roadmap and storage audit references,
P2 #1 handoff, P0 storage handoff, and phase-7 storage/recovery documentation.
Inspected `app/security/ingestion.py`, `app/core/artifacts/ingestion.py`,
`app/db.py`, ACCOUNT/Demo routes, case admission/locking, dossier revisions,
artifact/case/report/snapshot models, audit helpers, immutability guards,
processing orchestrator, report composition, sample PDF generation, startup,
deployment preflight and browser report export. Searched application code for
filesystem writes, deletes, moves, renames and reads; inspected related ingestion,
upload, storage, dossier, processing and freshness tests.

The existing contract is **not cross-store atomic creation**:

- `docs/phase-7/gate-7.4/README.md` explicitly states that files precede DB commits
  and rollback/crash can leave orphan/partial files. It explicitly disclaims
  cross-store transactions and power-loss durability; there is no explicit fsync.
- That document says reports/snapshots are DB records, not a server PDF store,
  and recovery must account for orphans without silently deleting them.
- Storage promises contained opaque unique paths and exclusive creation, never
  overwriting existing evidence. Ingestion deduplicates by same-case DB hash.
- Artifact source identity and deletion are guarded by ORM immutability hooks.
  Dossier/snapshot/audit history is append-only. Gate 1 requires historical reports
  to be preserved and never falsely presented as current.
- P2 #1 guarantees bounded multipart spooling/closure, not application-storage
  rollback. Multipart spools are not durable artifact storage.

## Actual ordering

1. Identity/CSRF admission precedes multipart parsing. Ownership and namespace
   checks plus the existing case transaction lock precede ingestion.
2. Bounded application read, size/type/content validation, SHA-256 calculation,
   then same-case hash query. A duplicate returns its existing row immediately;
   it does not check physical existence, write bytes, or bump the case version.
3. For a new dossier artifact, read existing evidence and measure the candidate
   bundle before creating any new durable file. This preparation is in memory.
4. Generate `cases/<case>/<uuid>/<sanitized-name>`; resolve containment; mkdir;
   recheck containment; exclusive `open('xb')`; write; close. There is no
   application-owned temporary file, rename/finalization step or fsync.
5. Add Artifact, increment Case.version, flush. Artifact.case_id is the durable
   association; upload does not create a DossierRevision or derived evidence link.
6. Add `artifact_uploaded` audit (also for duplicates); function-scoped get_db
   commits before success headers. Any exception rolls back and closes the DB
   session. No filesystem compensation occurs.
7. Storage domain failures roll back the request and independently commit a
   sanitized `artifact_rejected` audit, then return 422. Generic DB errors escape
   through rollback and return generic HTTP 500, without domain rejection audit.
8. Processing reads original bytes when materializing uncached text and for
   multimodal review; derived text/evidence/runs are DB-backed, derivatives in
   memory. Stages commit independently. Snapshot/report rows and authority switch
   share the final DB transaction; failures retain previous derivation history.
   Report GET reads DB data; sample PDF is generated in memory; browser print/export
   does not create server filesystem state.

No artifact delete/replacement endpoint exists. Normal ORM artifact deletion is
forbidden. No supported DB-first/file-delete transaction exists to test.
No other application path writing both DB state and durable filesystem objects
was found. Preflight writes only its disposable probe and does not write DB rows.
Startup creates storage root/SQLite tables, but performs no inventory reconciliation.
Missing files are detected at read time; cached text/reused derivations do not
constitute a full storage integrity scan. No orphan scan or application-temp
cleanup/recovery utility was found. Rename and compensating unlink failures are
not applicable to the current upload algorithm; inventing those hooks would test
an implementation that does not exist.

## Classification before any production change

**VERIFIED BROKEN: none established against the existing contract.** This is not
an atomicity or operational-readiness claim. Observed incomplete cross-store state
is documented behavior; tests must not turn a desired new recovery policy into an
existing guarantee.

**VERIFIED WORKING (focused synthetic SQLite scope):**

- Artifact-insert flush failures and DBAPI commit failures roll back artifact,
  case version, dossier history and success audit. Existing file bytes survive.
- mkdir/open/write/close failures do not commit a new artifact row pointing to
  the incomplete/absent file, and do not advance case/dossier version.
- File failures produce sanitized 422 STORAGE_ERROR and independent rejection
  audit. DB commit failure returns generic `Internal Server Error` HTTP 500.
- Duplicate failures preserve the existing row/file/version and create no new
  durable object. Retry succeeds. Same filename/different bytes is additive.
- Exclusive-create collision rejects overwrite and preserves original bytes.
- Failed upload preserves current assessment/report and snapshot/report/run
  history. A later successful new upload makes the previous report historical.
- Missing original reads fail with StorageError; a missing prior dossier artifact
  blocks new-evidence preparation before any new file/row is created.
- All these API cases execute in both ACCOUNT and Demo using their actual shared
  handler, authenticated fixtures, real transaction lifecycle and temporary store.

**PARTIALLY VERIFIED / observed limitations:**

- New upload then flush/commit failure leaves a complete orphan; partial write
  leaves a three-byte orphan in the injected case; close failure leaves complete
  bytes with no row. No DB rollback deletes these files. This is the documented
  non-atomic ordering, not proof of an all-or-nothing contract violation.
- Retrying after DB or storage failure succeeds without manual cleanup because
  the next UUID is fresh; the old orphan remains. DB-based retry is not physical
  storage idempotency. Successful same-content duplicate reuse adds only an audit.
- After external loss, same-content upload returns 201/duplicate_of for the old
  row without restoring the missing object. Uncached processing then returns
  sanitized STORAGE_ERROR. This proves no automatic repair; it does not establish
  a repository promise that duplicate upload repairs storage.
- Report DB/filesystem atomicity is inapplicable: no durable server PDF exists.
  Existing report/freshness regressions cover DB authority; no artificial report
  filesystem boundary was introduced.

**AMBIGUOUS:** automatic orphan retention/removal, partial-file recovery,
missing-file duplicate repair/rejection, and handling/logging of hypothetical
compensating cleanup failure have no implemented/approved operational policy.
No compensating cleanup exists, so no primary error is masked by cleanup here.
The existing rejection audit records a fixed domain reason, not an orphan index.
Owner/operations decisions are needed before introducing recovery or retention
behavior. Do not silently delete evidence to make an atomicity assertion pass.

**NOT VERIFIED:** process kill/power loss, actual disk exhaustion, remote ambiguous
commit outcome (server commits then connection fails), PostgreSQL execution,
concurrent failure races, full filesystem corruption/hash reconciliation,
backup/restore, mounted storage, live services, real data or production recovery.
Injected commit failure occurs before the DBAPI commit; it does not model lost
acknowledgement after a successful commit. No schema migration is needed here.

## Failure injection and results

New file: `tests/regression_p2/test_filesystem_db_consistency.py` (23 cases).
Reuses regression_p2 fixtures and ACCOUNT/Demo upload context. Injects SQLAlchemy's
actual INSERT execution boundary and dialect DBAPI commit boundary; Path mkdir,
exclusive open, partial write and close; external missing-file loss; and an opaque
key collision. Assertions inspect a new DB session and disk snapshots, retry,
versions, audits and report authority/history. Orphan and missing-dedup assertions
are explicitly named/documented as characterization, not desired recovery policy.

All production code remains at baseline: there is **no production pre-fix/post-fix
pair**, no proven-defect root cause and no production change. Mechanisms behind
observed limitations are file-before-flush/commit with no compensation, direct
final-path writes, and DB-only hash dedup before any storage existence check.

Execution uses Linux Python 3.11 and
`PYTHONPYCACHEPREFIX=/tmp/dandoonjan-p2-consistency-pycache`.
Sandbox TestClient attempt stalled without a completed result and was interrupted
(exit 130); authorized runs outside the sandbox use synthetic disposable fixtures.

- Initial unchanged-production focused run: **19 passed, 3 warnings in 7.66s**.
- Expanded unchanged-production run: **2 failed, 21 passed, 3 warnings in 10.63s**.
  Both failures were test setup: the observer client ran startup DDL while its
  commit-failure injection was active. Corrected test setup to start the observer
  before injection; neither failure demonstrated a production defect.
- Final unchanged-production validation: **173 passed, 3 warnings in 67.00s**;
  includes all **23 focused consistency cases** and all **54 P2 #1 cases**.

Final command (with the bytecode prefix above):

```sh
python3 -m pytest tests/regression_p2/test_filesystem_db_consistency.py tests/regression_p2/test_upload_resource_boundaries.py tests/upload_management tests/test_ingestion.py tests/regression_p0/test_storage.py tests/next_phase/test_dossier.py tests/next_phase/test_demo.py tests/regression_p1/test_processing_retry.py tests/regression_p0/test_assessment_freshness.py -q --tb=short
```

The first two completed runs used only the new consistency file with `-q --tb=short`.
No post-fix result is asserted: production was never changed. Relevant existing
suites were rerun to validate the new test integration and preserve P2 #1 coverage;
these are results at this gate, not borrowed historical pass counts. Auth and
concurrency implementations were not touched; this selection includes existing
upload admission/CSRF controls and Demo behavior, not an exhaustive new auth or
concurrency audit. P0 concurrent text and P1 intake suites were not rerun because
no production code intersects them in this task.

The three warnings are existing Starlette TestClient/FastAPI lifespan deprecations.
No repository-wide suite, provider call or deployment was run.

## Task files and working-tree safety

Only task files:

1. `tests/regression_p2/test_filesystem_db_consistency.py` (added).
2. `docs/handoff/p2-filesystem-db-consistency.md` (added).

Baseline status captured before edits at `/tmp/dandoonjan-p2-baseline-status`;
SHA-256 manifest of all 988 pre-existing modified/untracked files captured at
`/tmp/dandoonjan-p2-baseline-hashes.json`. Final comparison recorded below.
Nothing staged, committed, pushed or deployed. Frontend visuals and all production
code remain unchanged. No credentials, paid services, clinical/product expansion,
hosted infrastructure or work requiring Mehdi was undertaken.

Final repository checks: **all 988 baseline file hashes match**; no original
status entry disappeared or changed. Exactly the two task files above were added
to status, both untracked. `git diff --check` passed; staged diff is empty.
Branch/HEAD remain the baseline values. No staging, commit, push or deployment
occurred. The frozen frontend and unrelated dirty/untracked evidence are preserved.
