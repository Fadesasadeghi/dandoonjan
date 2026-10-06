# Gate 7.2 — PostgreSQL runtime proof and approved blocker fixes

2026-10-06. **VERIFIED WORKING for the approved two-blocker fix scope** on private
PostgreSQL 16.15. Focused acceptance and broad offline regression are green;
all synthetic databases were removed and the private cluster was stopped. Baseline/current branch `agent/sadeghi-next-phase`; unchanged HEAD
`5bf2f8a56c1c86b0b00897d55291c9fcea8138bd`. No commit was created.

Historical evidence is preserved separately:

- [Runtime before fixes](RUNTIME-BEFORE-FIX.md): reproduced Alembic/dossier defects,
  prior focused and broad results, and PostgreSQL acceptance boundaries.
- [Initial attempt](PREVIOUS-ATTEMPT.md): earlier Linux runtime blocker and initial
  red/green authentication harness repair; results are historical, not new checks.
- [Unrelated owner files](owner-status-before.txt): pre-existing dirty/untracked
  material, excluded from this gate.

## Approved production diff

[Exact production diff](production.diff) contains only two files:

- `alembic/env.py`: catch only `KeyError` whose arguments equal
  `('destination_rev',)` and treat it as no destination. All other errors
  propagate. Existing recognized-schema checks and upgrade-to-head adoption
  conditions remain unchanged.
- `app/core/cases/dossier.py`: import the existing `lock_case` helper, acquire it
  at update entry, then `db.refresh(case)` before reading fields/version. Merge,
  revision append, response, audit and commit remain in the existing transaction.
  No intermediate commit or new lock mechanism is introduced.

No migration revision/model/schema definition, API contract, auth/CSRF/ownership,
provider policy, storage/retention, or deployment architecture changed. The existing
unique dossier version constraint remains. No unrelated production code changed.

## Required regression-first sequence

Only the dossier test synchronization was adjusted first: both authenticated
requests must load the baseline Case version before crossing a barrier immediately
before `dossier.update`. Every original success/version/merge/history assertion is
retained. This permits valid lock serialization without a barrier inside the
critical section. The adjusted test was run against unchanged production files,
confirmed by saved SHA-256 hashes of both files. It failed as required: statuses
**[500,200]**, stored Case version **3**, stored revision versions **[2,3]**.

The approved fixes were applied afterward. The same test now passes, asserting
two 200 responses, distinct successive revision versions **[2,3,4]**, final Case
version **4**, and preservation/merge of both disjoint synthetic edits. No failing
regression was removed, weakened, xfailed or deselected in final testing.

## Private test environment and boundaries

Native WSL/Linux conda `dandoonjan-wsl`, Python **3.11.16**, pytest **9.1.1**.
PostgreSQL **16.15**, Ubuntu build `16.15-0ubuntu0.24.04.1`.
New unique cluster `/tmp/dandoonjan-g72-9alhojk0`; parent/socket directories mode
0700; Unix socket only, port 55472; `listen_addresses=''` (TCP disabled).
No sudo; Ubuntu `16/main` was not used or modified. Only unique disposable
`rc_synthetic_<uuid>` PostgreSQL databases were created/dropped.

```text
/usr/lib/postgresql/16/bin/initdb -D /tmp/dandoonjan-g72-9alhojk0/data --auth-local=trust --auth-host=reject --no-locale --encoding=UTF8
/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/dandoonjan-g72-9alhojk0/data -l /tmp/dandoonjan-g72-9alhojk0/server.log -o "-k /tmp/dandoonjan-g72-9alhojk0/socket -p 55472 -c listen_addresses=''" -w start
```

All tests use the existing offline launcher, which disables dotenv before Settings
initialization (including subprocesses), disables live dispatch, blocks real httpx
transport, and isolates SQLite regression DB/storage in temporary directories.
Injected OfflineRouter lifecycle forbids Mock fallback; coordination probes use
existing offline fake providers. No production model/provider substitution.
**No real patient data was used. No live AI/provider or external network request
was made. No production/shared database was contacted.** No real credentials/API keys
were accessed or modified. No paid service, dependency download, normal development
SQLite database access, PR modification, deployment, staging, commit, push or merge.
Gate 6.3 remains DEFERRED/BLOCKED and was not investigated.

## Tests executed in this blocker-fix sub-gate

Every scope below uses this exact command prefix:

```text
RC_POSTGRES_SOCKET=/tmp/dandoonjan-g72-9alhojk0/socket RC_POSTGRES_PORT=55472 /home/fadesasadeghi/miniforge3/envs/dandoonjan-wsl/bin/python verification/run_phase6_offline.py
```

| Scope after prefix | Result |
| --- | --- |
| `/mnt/c/users/admin/desktop/dandoonjan/tests/next_phase/test_gate72_postgres.py::test_concurrent_dossier_versions -q --tb=short` before production changes | 1 failed, 0 passed/skipped; 3 warnings; 5.21s |
| `tests/next_phase/test_gate72_postgres.py -q -rs --tb=short` after fixes, before correcting the new capture helper | 37 passed, 2 failed, 0 skipped; 3 warnings; 70.83s; both blocker tests passed; two new tests failed ordering JSON |
| `verification/test_rc_postgres.py tests/auth/test_postgres.py tests/next_phase/test_processing_postgres.py verification/test_gate72_harness.py tests/next_phase/test_gate72_postgres.py -q -rs --tb=short` | 50 passed, 0 failed/skipped/deselected; 3 warnings; 97.69s |
| `tests verification/test_gate72_harness.py -q -rs --tb=short` with PostgreSQL enabled and no exclusions | 711 passed, 0 failed/skipped/deselected; 3 warnings; 333.67s |

The initial relative pytest node path collected no tests (exit 4); correcting it
needed no launcher change. The new introspection capture helper initially sorted
by all columns, including PostgreSQL JSON; it was corrected to primary-key ordering.
This was test-only infrastructure, not another application defect or production
change. Existing warnings concern Starlette/httpx and FastAPI startup deprecations.

## Verified PostgreSQL behaviors and tested scope

- Fresh zero-to-head migration, repeat upgrade, `alembic current`, stored head
  **e72b4c9a6102**, and private PostgreSQL version/TCP settings.
- Unknown unstamped schema safely rejects upgrade/adoption with table/row intact.
- Six introspection combinations: empty, unknown, and recognized unstamped schemas,
  each using ordinary and PostgreSQL-enforced read-only connections. All remain
  unstamped with identical table rows, columns/defaults, constraints and indexes;
  no adoption, migration, or schema/data mutation. Recognized fixture includes a
  preserved synthetic legacy user. Unrelated revision-getter KeyError propagates.
- Populated existing predecessor fixtures preserve findings/claim provenance and
  confidence, case question, legacy derivation status and processing authority;
  populated pre-auth fixture preserves ownership/version 9 and legacy disablement.
- Authenticated account/session/CSRF/ownership behavior, nine case route isolation
  variants, seven session-denial states, five CSRF rejection variants, session
  hashing/revocation/relogin and bounded touch.
- Synthetic artifact ingestion/metadata, authenticated dossier processing,
  authoritative snapshot/report/reuse/restart, injected failure retaining history
  and removing current report, with no Mock fallback.
- Six concurrent login attempts prove PostgreSQL rate-limit ON CONFLICT atomicity
  (five 401, one 429), normalized persistence and budget-window reset. Session code
  uses existing conditional UPDATE/INSERT rather than a separate session upsert.
- Same-case admission with two contention schedules and five simultaneous requests
  produces one pipeline attempt/execution; four requests reconcile while one fake
  dispatch is held. Runtime SQL captures case-scoped `FOR UPDATE OF cases`.
  Different cases overlap; dossier edits prevent obsolete processing authority.
- Concurrent upload capacity admits one artifact and rejects the other coherently.
- Concurrent authenticated dossier edits preserve complete versioned history,
  merge disjoint fields, and avoid the former unique-constraint HTTP 500.

These are runtime PostgreSQL assertions, not compiler-only checks or SQLite inference.
The shared SQLite lifecycle is also covered in the focused and broad suites.

## Remaining limits

Arbitrary migration histories and populated authoritative snapshots/reports across
a predecessor upgrade remain NOT VERIFIED by the existing populated fixtures.
Current-head report/snapshot/history behavior is verified separately. Wider upload
and version contention is not exhaustively tested. No real provider acceptance or
production/deployment proof is claimed. These limits do not represent remaining
failures of the two approved blocker regressions.

## Final cleanup and repository handoff

Read-only private-cluster verification returned **0** remaining `rc_synthetic_*`
databases, PostgreSQL **16.15**, and an empty `listen_addresses`. The cluster
stopped successfully using:

```text
/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/dandoonjan-g72-9alhojk0/data -m fast -w stop
```

Its postmaster PID file is absent. Private cluster files remain under /tmp; no
unrelated filesystem cleanup was performed. Parent/socket permissions remain 0700.
`git diff --check` passed. The exact production diff was inspected and saved in
[production.diff](production.diff): **10 added lines, 1 removed line**, limited to
the two approved files. All migration revision files and schema definitions remain
unchanged. Branch/HEAD remain unchanged; the staged diff is empty.

Unrelated owner status matches [the baseline listing](owner-status-before.txt).
SHA-256 comparisons also confirm all three pre-existing modified owner screenshots
are byte-identical to the blocker-fix starting baseline. No owner material was
modified, staged, deleted, restored or cleaned.

All uncommitted Gate 7.2 files, including earlier gate work:

- `alembic/env.py`
- `app/core/cases/dossier.py`
- `tests/next_phase/test_gate72_postgres.py`
- `verification/test_rc_postgres.py`
- `verification/test_gate72_harness.py`
- `docs/phase-7/gate-7.2/README.md`
- `docs/phase-7/gate-7.2/RUNTIME-BEFORE-FIX.md`
- `docs/phase-7/gate-7.2/PREVIOUS-ATTEMPT.md`
- `docs/phase-7/gate-7.2/owner-status-before.txt`
- `docs/phase-7/gate-7.2/production.diff`

Assessment: **PASS for the approved blocker-fix sub-gate and executed PostgreSQL
acceptance scope**. Both reproduced defects are resolved; no tests were skipped or
deselected in final runs. The explicit NOT VERIFIED limits above remain. Recommend
owner review of the uncommitted diff/evidence before any separate Git gate.

