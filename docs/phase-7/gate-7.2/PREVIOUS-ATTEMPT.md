# Gate 7.2 — PostgreSQL runtime proof (partial; acceptance blocked)

2026-10-05. Baseline branch `agent/sadeghi-next-phase`, HEAD
`5bf2f8a56c1c86b0b00897d55291c9fcea8138bd`. No commit was created.
The staged diff was empty. Pre-existing owner files are listed separately in
[owner-status-before.txt](owner-status-before.txt) and remain outside this gate.
The approved Gate 1 handoff and existing Phase 6 PostgreSQL/provider-isolation
instructions were read. No repository Phase 7.1 document was found; the owner's
Gate 7.1 audit statement supplied the obsolete-harness finding.
Gate 6.3 remains DEFERRED/BLOCKED; this gate does not revisit its authentication.

## Environment and boundaries

VERIFIED WORKING: PostgreSQL **16.15**, Ubuntu build
`16.15-0ubuntu0.24.04.1`, in a local/private disposable synthetic cluster.
The cluster and socket are under `/tmp/dandoonjan-g72-i31fst6y/` and both parent
and socket directory have mode **0700**. Port **55472** identifies the Unix socket;
`SHOW listen_addresses` returned an empty value, so PostgreSQL TCP is disabled.
`SELECT version()` succeeded through this socket. A uniquely named
`rc_synthetic_<uuid>` database was created, verified to have zero public tables,
and dropped successfully. These checks prove environment provisioning only,
not application migration or lifecycle correctness.

The cluster was initialized with the owner-approved command:

```text
/usr/lib/postgresql/16/bin/initdb -D /tmp/dandoonjan-g72-i31fst6y/data --auth-local=trust --auth-host=reject --no-locale --encoding=UTF8
/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/dandoonjan-g72-i31fst6y/data -l /tmp/dandoonjan-g72-i31fst6y/server.log -o "-k /tmp/dandoonjan-g72-i31fst6y/socket -p 55472 -c listen_addresses=''" -w start
```

The sandbox initially rejected Unix socket binding; the approved retry outside
that sandbox succeeded. No sudo was used. `16/main` was neither used nor changed;
read-only cluster listing reported it down and its default socket did not answer.
No production/shared database was contacted. No real patient data was used.
No live AI/provider request or external network request was made. No credentials
were accessed or modified. No dependency download or paid service was used.
The normal SQLite development database was not accessed or changed.
PR #4 and PR #5 were not modified or merged. No deployment occurred.

## Reproduced infrastructure defect and repair

VERIFIED BROKEN before repair: the shared PostgreSQL lifecycle verifier used an
unauthenticated TestClient. A new regression executes that exact shared lifecycle
against a disposable SQLite database and initially failed with `KeyError: case_id`
at the unauthenticated case-creation response.

The repair is confined to verification/test infrastructure:

- `verification/test_rc_postgres.py`: synthetic ACCOUNT registration/login, rotated
  CSRF header, explicit 401/403 assertions, authenticated login after restart, and
  an asserted successful dossier update. No authentication bypass is installed.
- The private socket fixture accepts validated `RC_POSTGRES_PORT` (default 5432)
  and propagates it to both administrative connection and generated test URL,
  allowing the approved 55472 private socket. This port path has not yet been
  exercised by a real psycopg test fixture.
- `verification/test_gate72_harness.py`: regression of the shared lifecycle on
  disposable SQLite. This is explicitly not PostgreSQL runtime evidence.

VERIFIED WORKING on SQLite after repair: account/login, session-backed case
creation, missing-auth/invalid-CSRF rejection, dossier edit, synthetic artifact
metadata/ingestion, processing, authoritative snapshot/report, reuse without new
provider dispatch, restart/login/reuse, and offline injected provider failure
with no current report and preserved historical snapshot. The existing
`OfflineRouter` uses its injected synthetic HTTP handler and forbids Mock fallback.
Its synthetic model is the existing harness fixture, not a production substitution.
The existing offline launcher disables dotenv before Settings initialization,
uses disposable DB/storage, blanks credential environment inputs without reading
values, disables live dispatch, and rejects real httpx network transport.

No production application code changed. No migrations/schema, public API,
auth/security semantics, provider policy, retention policy, or architecture changed.
The only CREATE/DROP DATABASE operations affected this gate's disposable database.

## Current-gate test executions

All pytest commands use `.venv/Scripts/python.exe verification/run_phase6_offline.py`
and run from disposable directories, with dotenv disabled in migration subprocesses.
The available repository Python is Windows 3.11; it cannot use the WSL private
Unix socket as a Linux backend runtime. Inspected Linux interpreters (3.12/3.14)
lack backend dependencies; cached wheels do not form a compatible environment.
No Linux environment was provisioned through network access.

| Execution | Exact scope | Result |
| --- | --- | --- |
| Initial PostgreSQL collection | `verification/test_rc_postgres.py tests/auth/test_postgres.py tests/next_phase/test_processing_postgres.py -q` | 0 passed, 0 failed, 10 skipped; 1 warning; 0.74s |
| Pre-repair reproducer | `verification/test_gate72_harness.py -q` | 0 passed, 1 failed, 0 skipped; 3 warnings; 3.51s |
| Post-repair shared lifecycle | `verification/test_gate72_harness.py -q` | 1 passed, 0 failed, 0 skipped; 3 warnings; 3.56s |
| Final focused | `verification/test_gate72_harness.py verification/test_rc_postgres.py tests/auth/test_postgres.py tests/next_phase/test_processing_postgres.py -q` | 1 passed, 0 failed, 10 skipped; 3 warnings; 3.60s |
| Offline backend regression | `tests verification/test_gate72_harness.py -q` | 665 passed, 0 failed, 7 skipped; 3 warnings; 231.71s |

The backend regression skips comprise five PostgreSQL opt-in cases and two
Windows directory-symlink cases. No offline httpx network tripwire was triggered.

PostgreSQL skips explicitly indicate no `RC_POSTGRES_SOCKET` supplied to the
Windows process. They are not acceptance passes. PostgreSQL focused verification
is not green; the authorized offline regression runs independently to validate
that the harness repair preserves current SQLite behavior. Earlier gate test
results are historical and are not counted here. Warnings concern existing
Starlette/httpx and FastAPI startup deprecations.

## PostgreSQL acceptance status and remaining work

Expected/source Alembic head: **e72b4c9a6102**. This is not a PostgreSQL runtime
migration result. No application migration was run on PostgreSQL.

| Required behavior | Current PostgreSQL evidence |
| --- | --- |
| Fresh upgrade, repeat upgrade, `alembic current` | NOT VERIFIED |
| Unknown unstamped schema rejection | NOT VERIFIED |
| Account/login/session/CSRF and owner isolation | NOT VERIFIED |
| Dossier/artifact/processing/report/snapshot/reuse | NOT VERIFIED |
| Same-case admission, different-case overlap, FOR UPDATE | NOT VERIFIED |
| Session/rate-limit upserts; upload accounting contention | NOT VERIFIED |
| Concurrent dossier versions | NOT VERIFIED; no race reproduced or ruled out |
| Populated predecessor upgrade and preservation | NOT VERIFIED |
| PostgreSQL provider isolation | NOT VERIFIED; shared SQLite injected lifecycle verified |

Assessment: PARTIAL environment/harness evidence; PostgreSQL application acceptance
BLOCKED on a compatible, already-provisioned Linux backend environment. Next action:
provide its path (official Python 3.11 preferred), then run the final focused scopes
with `RC_POSTGRES_SOCKET` pointing only to a new approved private gate socket and
`RC_POSTGRES_PORT=55472`, using the offline launcher. Do not reuse arbitrary/shared
URLs or infer PostgreSQL behavior from SQLite. Follow with missing PostgreSQL
acceptance tests and focused offline regressions; stop for owner approval if an
application/schema/migration/API/security change is required.

The private cluster was stopped successfully with:

```text
/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/dandoonjan-g72-i31fst6y/data -m fast -w stop
```

Its postmaster PID file is absent. Its isolated temporary files are retained under
/tmp; no owner files or other clusters were cleaned up. `git diff --check` passed.
The staged diff remains empty. Branch and HEAD remain unchanged; no stage, commit,
push, merge, or deployment occurred. All Gate 7.2 changes are the shared verifier,
the added SQLite regression, this README, and the owner baseline listing. Final
status comparison confirms no additional dirty paths outside that allowlist.

