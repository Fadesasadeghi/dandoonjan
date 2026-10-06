# Gate 7.2 — current-head PostgreSQL runtime proof

2026-10-06 resumed gate. **PARTIAL: two reproduced defects block acceptance.**
Branch `agent/sadeghi-next-phase`; unchanged HEAD
`5bf2f8a56c1c86b0b00897d55291c9fcea8138bd`. No commit created or files staged.
[Previous attempt](PREVIOUS-ATTEMPT.md) preserves the 2026-10-05 environment blocker,
red/green harness repair, and Windows regression results as historical evidence.
[Owner status before](owner-status-before.txt) lists unrelated owner material.

## Environment and isolation

Native WSL/Linux conda `dandoonjan-wsl`, Python **3.11.16**, pytest **9.1.1**;
interpreter `/home/fadesasadeghi/miniforge3/envs/dandoonjan-wsl/bin/python`.
PostgreSQL **16.15** (Ubuntu 16.15-0ubuntu0.24.04.1).
New private cluster `/tmp/dandoonjan-g72-uja97leb`, private Unix socket directory
`socket/`, parent and socket mode 0700, Unix-socket port 55472. TCP disabled.
Only unique disposable `rc_synthetic_<uuid>` databases are created/dropped by tests.
Ubuntu `16/main` was neither used nor modified; no sudo was used.

Exact provisioning:

```text
/usr/lib/postgresql/16/bin/initdb -D /tmp/dandoonjan-g72-uja97leb/data --auth-local=trust --auth-host=reject --no-locale --encoding=UTF8
/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/dandoonjan-g72-uja97leb/data -l /tmp/dandoonjan-g72-uja97leb/server.log -o "-k /tmp/dandoonjan-g72-uja97leb/socket -p 55472 -c listen_addresses=''" -w start
```

The sandbox rejected socket binding/access; approved outside-sandbox commands
succeeded. The initial sandboxed focused attempt emitted fixture errors and was
interrupted (exit 130); it supplies no application acceptance evidence.

All resumed tests use this exact command prefix:

```text
RC_POSTGRES_SOCKET=/tmp/dandoonjan-g72-uja97leb/socket RC_POSTGRES_PORT=55472 /home/fadesasadeghi/miniforge3/envs/dandoonjan-wsl/bin/python verification/run_phase6_offline.py
```

The existing launcher disables dotenv before Settings initialization, including
migration subprocesses, disables live provider dispatch and forbids real httpx
transport. SQLite regressions use disposable temporary DB/storage only. Provider
lifecycle uses existing injected OfflineRouter, which forbids Mock fallback;
coordination probes reuse existing standalone offline fake-provider tests.
No production provider/model substitution occurred.
**No real patient data was used. No live AI/provider or external network request
was made. No production/shared database was contacted.** No API keys/credentials
were accessed or modified, no paid service or dependency download used, and no
normal SQLite development database touched. Gate 6.3 remains DEFERRED/BLOCKED.
No PR modification, staging, commit, push, merge, deployment or owner-file cleanup.

## PostgreSQL runtime evidence

VERIFIED WORKING (actual PostgreSQL assertions):

- Fresh zero-to-head migration, repeated upgrade, stored revision **e72b4c9a6102**.
  Populated predecessors `13cb12f30f53` and `a5716dc9a797`: findings/claim provenance
  and confidence, case question, legacy derivation state and processing authority
  preserved. Populated pre-auth upgrade preserves ownership and case version 9,
  disables legacy user, verifies account uniqueness and auth tables.
- Concurrent first knowledge-pack seeding is idempotent across five threads.
- Authenticated dossier/artifact metadata/ingestion/processing, immutable snapshot,
  authoritative report, reuse without more dispatch, restart/login/reuse, and
  injected provider failure preserving history while removing current report.
- Ownership isolation across all nine normal case read/write routes, foreign,
  legacy and demo cases; seven session-denial states; five CSRF rejection variants
  before processing; session hashing/revocation, relogin and bounded touch.
- Atomic PostgreSQL auth rate-limit ON CONFLICT under six concurrent requests:
  five 401 responses and one 429; normalized persistent budget and window reset.
  Session behavior uses conditional UPDATE/INSERT, not a separate session upsert.
- Five simultaneous same-case processing requests: four reconcile while one fake
  dispatch is held; exactly one successful ACTIVE pipeline/attempt and one shared
  pipeline ID. Runtime SQL capture confirms `FOR UPDATE OF cases` with case-ID
  filtering. Independent SHOW assertions confirm PostgreSQL 16.15, no TCP listener,
  and stored Alembic revision e72b4c9a6102.
- Same-case processing admission (simultaneous claim and during dispatch) produces
  one execution; different cases overlap; a dossier mutation during processing
  prevents obsolete result/snapshot activation.
- Upload capacity contention: one 201, one 422, exactly one stored artifact.
- Unknown unstamped schema refuses adoption; its synthetic table/row remain and
  no Alembic stamp/application tables are created.

## Reproduced defects — unchanged production code

**VERIFIED BROKEN: `alembic current`.** Upgrades succeed twice, but the current
command exits 1. `alembic/env.py:31` unconditionally calls
`context.get_revision_argument()`; current has no `destination_rev`, causing
`KeyError: 'destination_rev'`. Stored schema revision is independently asserted
at e72b4c9a6102. This is a migration-environment/CLI defect, not an upgrade failure.
The failing regression remains; no Alembic file was modified.

**VERIFIED BROKEN: concurrent dossier editing.** Two authenticated PUT requests
are synchronized after reading the same baseline; the harness changes scheduling
only. Initial case/revision version is 2. One edits duration, the other allergies;
both allocate version 3. PostgreSQL rejects one insert with UniqueViolation on
`dossier_revisions_case_id_case_version_key`, key `(1,3)`. Observed: one HTTP **200**,
one **500**, final case version **3**, stored revision versions **[2,3]**. Initial
history remains, the winner commits, and the rejected edit rolls back. Which edit
wins depends on scheduling. No duplicate revision/committed-history corruption
was observed. The regression expects two independently versioned successful edits
and remains failing. No schema/API/auth or dossier production change was made.

Proposed fixes require explicit owner approval before implementation:

1. Narrow Alembic environment guard: read destination revision only for commands
   supplying one, preserving unknown-schema adoption rejection. No migration
   revision/schema change proposed.
2. Serialize dossier read/merge/version allocation under the existing case-scoped
   DB lock, refreshing stale Case state before reading latest dossier fields.
   Preserve history, ownership/CSRF and API behavior. Confirm concurrent edit
   expectations with the owner before implementation.

## Tests run in the resumed gate

Append each scope below to the command prefix above:

| Scope | Result |
| --- | --- |
| `verification/test_rc_postgres.py tests/auth/test_postgres.py tests/next_phase/test_processing_postgres.py verification/test_gate72_harness.py -q -rs` | 11 passed, 0 failed/skipped; 3 warnings; 26.63s |
| Initial `tests/next_phase/test_gate72_postgres.py -q -rs` | 23 passed, 1 failed, 0 skipped; 3 warnings; 44.21s; dossier constraint error |
| Original focused files plus `tests/next_phase/test_gate72_postgres.py -q -rs --tb=short` | 39 passed, 2 failed, 0 skipped; 3 warnings; 83.19s; current command and dossier HTTP 500 |
| Final focused (same focused scope, with the two added proofs) | 41 passed, 2 failed, 0 skipped; 3 warnings; 83.90s; same two defects |
| `tests verification/test_gate72_harness.py -q -rs -k 'not test_concurrent_dossier_versions'` | 700 passed, 1 failed, 0 skipped, 1 deselected; 3 warnings; 328.90s; same Alembic current defect |

The broad run collected before the final two independent coordination/runtime tests
were added; those additions are covered in final focused retesting.
The broad regression explicitly deselects the already-reproduced dossier race;
it remains failed in focused acceptance. No PostgreSQL skip counts as a pass.
Warnings concern existing Starlette/httpx and FastAPI startup deprecations.
The previous attempt's results are historical and not counted as new executions.

## Limits and disposition

Full acceptance is blocked by the two defects. Arbitrary upgrade histories and
populated authoritative snapshots/reports across a predecessor upgrade are NOT
VERIFIED by these populated fixtures; current-head authoritative snapshot/history
behavior is verified separately. Wider upload/version contention is not exhausted.
Real provider acceptance is outside scope and was not run.

No production application code, Alembic files/revisions, schema, API/auth/security,
provider policy, storage/retention or deployment architecture changed.
## Cleanup and repository handoff

The final read-only private-cluster check returned **0** remaining
`rc_synthetic_*` databases, PostgreSQL **16.15**, and empty `listen_addresses`.
The disposable cluster stopped successfully:

```text
/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/dandoonjan-g72-uja97leb/data -m fast -w stop
```

Its postmaster PID file is absent. Temporary cluster files remain under /tmp;
no destructive filesystem cleanup was performed. `git diff --check` passed and
the staged diff is empty. Branch/HEAD remain unchanged. Owner status matches
[the recorded unrelated baseline](owner-status-before.txt).

All uncommitted Gate 7.2 files (including the previous attempt's changes):

- `verification/test_rc_postgres.py`
- `verification/test_gate72_harness.py`
- `tests/next_phase/test_gate72_postgres.py`
- `docs/phase-7/gate-7.2/README.md`
- `docs/phase-7/gate-7.2/PREVIOUS-ATTEMPT.md`
- `docs/phase-7/gate-7.2/owner-status-before.txt`

Recommendation: owner approval for the two narrow fixes described above, then
regression-first implementation and PostgreSQL retesting in another isolated
cluster. Gate 7.2 remains PARTIAL with full acceptance BLOCKED, not PASS.

