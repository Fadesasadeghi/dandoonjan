# Gate 7.3 — provider-neutral deployment packaging

Baseline: `agent/sadeghi-next-phase`,
`1c8c20a839f647237c904a234534cc393795dd0c`. This gate prepares packaging;
it does not deploy, select hosting/storage, authorize provider requests, or prove
production/clinical readiness. Synthetic data only. Gate 6.3 real-provider
acceptance remains DEFERRED/BLOCKED; no new attempt is authorized here.

## Runtime contract

- Linux CPython 3.11; PostgreSQL 16 using `postgresql+psycopg`.
- Explicit Alembic migration by a separate release operator/job before serving.
  Do not run migrations in each web worker. Unknown schema/adoption failures are
  stops, never reasons to stamp a database manually.
- Same-origin FastAPI HTML/static frontend and `/api` backend at an externally
  reachable HTTPS origin. Set `DJ_AUTH_ALLOWED_ORIGINS` to an explicit JSON array
  of approved exact HTTPS origins (no path, wildcard or credentials).
- `DJ_ENVIRONMENT=production`, `DJ_AUTH_FOUNDATION_ENABLED=true`,
  `DJ_CORS_ORIGINS=[]` for this same-origin layout. Preflight rejects CORS origins
  outside the auth allowlist; it does not change middleware behavior.
- Explicit `DJ_DATABASE_URL` and absolute `DJ_ARTIFACT_STORAGE_DIR`. The latter
  must already exist, be writable by runtime UID/GID 10001:10001, and be on
  owner-provisioned persistent storage. Default container path is
  `/app/data/artifact_store`, mode 0700. Image-layer storage is not persistent.
- Existing production policy requires `DJ_AI_PROVIDER=openrouter`, an explicitly
  approved model name, `DJ_LIVE_PROVIDER_ENABLED=true`, a present
  `DJ_OPENROUTER_API_KEY`, and `DJ_LOCAL_SYNTHETIC_ACCEPTANCE_ENABLED=false`.
  Mock, automatic/free routing and production local-synthetic mode are rejected.
  No model is selected or authorized by this document; placeholders cannot prove
  provider availability. Live-enabled configuration alone is not approval to
  dispatch requests during this gate.
- `DJ_REQUIRE_CLINICIAN_REVIEWED_KNOWLEDGE_PACK=true`. The shipped development
  pack is not reviewed; enforcing this flag does not supply an approved pack.
  Missing reviewed content remains a processing/release blocker, not permission
  to disable enforcement. The existing Demo provider path refuses production.
- Positive `DJ_MAX_UPLOAD_BYTES` (existing default 26214400); optional `PORT`
  (existing default 8000). Do not expose the backend directly over plaintext HTTP.

Inject required secrets into the process using an owner-approved secret mechanism.
Do not place them in build arguments, image layers, command arguments, source,
logs, or committed dotenv files. Preflight ignores `.env` and checks only provider
key presence; it never validates key contents remotely or instantiates a provider.
The app/Alembic retain their existing Settings loader: all three commands must use
the same injected environment, with no mounted/workspace dotenv file introducing
different settings. Database connection configuration is necessarily consumed by
the database driver; errors are reduced to fixed codes by preflight.

The current auth HTTPS scheme check requires a correctly configured reverse proxy
and trusted forwarded headers. This gate does not change Uvicorn proxy trust or
cookie/CSRF semantics. Trusted proxy topology and HTTPS cookie lifecycle must be
verified separately before hosted use. `/health` and `/api/health` remain liveness
responses, not database/storage/provider readiness.

## Separate migration, preflight and serve commands

Run from the packaged application root using the same release image/environment:

```sh
python -m alembic upgrade head
python -m app.deployment_preflight
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-config app/logging.json
```

Those three lines describe separate roles; do not paste them as an unconditional
sequence. A release controller must require migration exit 0 before starting the
application. For an explicitly authorized single-process rehearsal, fail-closed
ordering is:

```sh
python -m alembic upgrade head &&
python -m app.deployment_preflight &&
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-config app/logging.json
```

No migration against a production/shared database is authorized by this gate.
The default container CMD runs only `preflight && exec uvicorn`, honors `PORT`,
and never migrates. Preflight failure exits nonzero and prevents serving; restarting
the container repeats preflight. Directly overriding CMD can bypass this gate,
so deployment operators must preserve the documented ordering.

Preflight prints one JSON object containing PASS/FAIL and fixed check results.
It verifies configuration first; on configuration failure it does not connect to
the database. A plain Pydantic model reuses the application's non-secret field
definitions/defaults and origin validator, reading only their named environment
variables. It never constructs BaseSettings, scans all environment values, or
includes provider-key fields; only the separate key-presence check reads that key.
Otherwise it checks PostgreSQL major 16 and the packaged Alembic
head in a read-only transaction with connection/statement timeouts, existing
artifact-directory write/read access, and required nonempty readable UI assets.
It never runs Alembic env/adoption/migration code, creates schema, stamps a revision,
loads the HTTP app, or calls AI. The storage probe owns/removes only its temporary
file. A revision match does not prove every table is free of manual schema drift.

Success does not prove persistent mounting, complete artifact integrity, reviewed
pack availability, HTTPS/proxy operation, provider acceptance, backup restoration,
or clinical readiness. Readiness can also change after the startup check.

## Container and dependency derivation

The image retains `python:3.11-slim`, one stage and the existing application layout.
Code/static/migration files remain root-owned; the runtime user is 10001:10001.
Only the image artifact directory is made writable to that user. A mounted volume
replaces image permissions: its owner must provision matching access separately.
Do not solve permission failures by running as root or recursively modifying an
unknown populated store.

`requirements-runtime.txt` is derived from `requirements.txt`, excluding the
direct test-only `pytest` declaration. For each remaining PEP 508 requirement,
the derivation reads installed distribution `Requires-Dist` metadata, evaluates
markers for the Linux CPython 3.11 environment and the active extras, recursively
visits dependency/extras pairs, and pins each reached distribution's installed
version. It verifies each traversed requirement accepts that version. Extras are
retained, including `uvicorn[standard]` and `psycopg[binary]`.

Source environment: `/home/fadesasadeghi/miniforge3/envs/dandoonjan-wsl`,
Python 3.11.16, the Gate 7.2 verification environment. The closure has 39 packages;
it is not `pip freeze`. For example, `watchfiles`, `uvloop`, and `websockets` are
required by Uvicorn standard, not copied merely because installed. No pytest,
Conda tooling or unrelated distributions are included. The dependency-closure
regression recomputes this process against the installed metadata and requires
the exact names, extras and versions. Existing development requirements stay
unchanged; no package was upgraded, downgraded, installed or downloaded here.

This file targets Linux/Python 3.11, not Windows. Exact package versions constrain
resolution but are not a complete cryptographic lock: base-image digest, platform
wheels, package hashes and clean image installation remain unverified. The moving
base tag is deliberately retained rather than selecting an unverified digest.

Build only from a clean reviewed checkout. `.dockerignore` excludes dotenv,
credentials, DB/artifact paths, caches, temporary archives, owner tooling/evidence
and current untracked frontend variants. Exclusions are defense in depth, not a
complete guarantee against arbitrary future files. No build context was sent.

`render.yaml` and `netlify.toml` are labeled historical incomplete templates.
Their settings/routing are not converted into deployment recipes; Render's
SQLite/Mock/missing-auth configuration will fail preflight. Separate Netlify
asset/proxy/cookie behavior remains unverified. No provider is selected here.

## Startup, shutdown, restart and recovery

Before startup, verify migration success and matching release configuration,
mount ownership/capacity, paired backups, reviewed content and separately approved
HTTPS/proxy setup. Keep one application instance for a local artifact store;
independent replicas cannot assume access to the same files. Multi-instance/shared
storage topology is outside this gate. No new worker count or queue is introduced.

For shutdown, stop admission of new writes and allow active synchronous processing
to complete before sending SIGTERM. The CMD uses shell `exec` for Uvicorn;
actual container signal delivery and shutdown grace periods are NOT VERIFIED.
Several sequential provider stages can exceed one request timeout; operator/proxy
limits must be rehearsed without assuming a browser timeout cancels processing.

Restart with the same compatible code, PostgreSQL database, artifact directory and
configuration. Preserve session/audit/history records. Do not delete evidence,
reinitialize the database or silently switch storage paths. A missing mount can
look like an empty writable directory; preflight cannot distinguish that from a
new store. Operators must verify the mount and evidence inventory independently.

An interrupted durable RUNNING pipeline remains unresolved after restart. Existing
admission returns PROCESSING with no current report rather than replaying provider
work or promoting an older report. Never automatically retry, clear/stamp runs,
or mutate authority as an operational workaround. Preserve history and escalate
the case for an owner-approved recovery design. Completed synthetic report/reuse
restart behavior was verified in Gate 7.2; hard-kill recovery is not claimed.

## Paired backups and restoration

Quiesce application writes and finish in-flight work before taking a coordinated
PostgreSQL backup and artifact-directory backup. Record release SHA, schema head,
artifact inventory/hashes, backup time and permissions together, without secrets
or patient data. DB and filesystem do not share a transaction; an uncoordinated
pair can contain missing files or orphaned artifacts. Retention, encryption,
access controls and storage ownership require explicit owner decisions.

Rehearse restoration into new isolated locations using the matching code version,
database and artifact backup pair. Verify schema, provenance links, file hashes,
auth isolation and historical/current report semantics before any cutover. Preserve
the failed/current copy for investigation. Do not downgrade populated history or
blindly stamp unknown schemas. Backup/restore execution and real deployment state
are NOT VERIFIED in this gate.

## Gate evidence

2026-10-06, Linux Python 3.11.16, PostgreSQL 16.15. Private disposable cluster:
`/tmp/dandoonjan-g73-e037h5mt`, socket directory mode 0700, port 55473,
`listen_addresses=''`. No shared/production database is used. Tests create only
unique `rc_synthetic_*` databases and remove those fixtures afterward.

Initialization/start commands (local rehearsal only, never production settings):

```text
/usr/lib/postgresql/16/bin/initdb -D /tmp/dandoonjan-g73-e037h5mt/data --auth-local=trust --auth-host=reject --no-locale --encoding=UTF8
/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/dandoonjan-g73-e037h5mt/data -l /tmp/dandoonjan-g73-e037h5mt/server.log -o "-k /tmp/dandoonjan-g73-e037h5mt/socket -p 55473 -c listen_addresses=''" -w start
```

Sandbox denied Unix socket binding/connection; explicit execution approvals allowed
this private rehearsal. TCP stayed disabled. Do not copy test trust authentication
to a shared/production server. No external network access or dependency installation.

Test command prefix for PostgreSQL-enabled runs:

```text
RC_POSTGRES_SOCKET=/tmp/dandoonjan-g73-e037h5mt/socket RC_POSTGRES_PORT=55473 /home/fadesasadeghi/miniforge3/envs/dandoonjan-wsl/bin/python -B verification/run_phase6_offline.py
```

The existing offline launcher disables dotenv before app/DB imports, uses temporary
SQLite/storage for other regressions, and blocks real HTTPX transport. Standalone
CLI success additionally runs with hard-exit tripwires for provider construction,
Mock dispatch, HTTPX sends and Python non-Unix socket connections. Provider keys,
model identifiers, auth origins and data are synthetic; no real secret was read.

| Run | Result |
| --- | --- |
| New tests before implementation: `tests/next_phase/test_gate73_packaging.py -q --tb=short`, without PostgreSQL prefix | 6 failed, 43 setup errors, 0 passed/skipped; 1.29s. Errors are the absent preflight module; packaging files/features are missing as intended. |
| First implemented run in sandbox | 43 passed, 6 socket-permission setup errors; 2.41s. Infrastructure restriction, not a preflight failure. |
| First PostgreSQL-enabled implemented run | 43 passed, 6 failed; 13.36s. Schema capture compared SQLAlchemy type object identities; fixed test helper to serialize actual definitions. Application checks/CLI succeeded. |
| Targeted packaging, production-provider, auth/access, migrations and lifecycle: `tests/next_phase/test_gate73_packaging.py tests/regression_p0/test_packaging.py tests/regression_p1/test_production_provider.py tests/auth tests/auth_gate2 verification/test_rc_postgres.py verification/test_gate72_harness.py -q -rs --tb=short` | 216 passed, 0 failed/skipped/deselected, 3 existing warnings; 149.81s. Before the final five added checks/permission normalization. |
| Additional permission regression before Dockerfile normalization: `tests/next_phase/test_gate73_packaging.py -k normalizes_source_permissions -q --tb=short` | 1 failed, 54 intentionally deselected; 0.35s. Confirmed omission before fix. |
| Focused before loader refinement: `tests/next_phase/test_gate73_packaging.py tests/regression_p0/test_packaging.py -q -rs --tb=short` | 56 passed, 0 failed/skipped/deselected, 2 existing startup deprecation warnings; 15.32s. |
| First broad: `tests verification/test_gate72_harness.py -q -rs --tb=short` | 766 passed, 0 failed/skipped/deselected, 3 existing warnings; 344.87s. Before final loader regression/refinement. |
| Loader regression before refinement: `tests/next_phase/test_gate73_packaging.py -k configuration_loader_excludes_secret_fields -q --tb=short` | 1 failed, 55 intentionally deselected; 0.56s. Required dedicated non-secret loader absent. |
| Final focused: `tests/next_phase/test_gate73_packaging.py tests/regression_p0/test_packaging.py -q -rs --tb=short` | 57 passed, 0 failed/skipped/deselected, 2 existing startup deprecation warnings; 17.05s. |
| Final broad after loader refinement: `tests verification/test_gate72_harness.py -q -rs --tb=short` | 767 passed, 0 failed/skipped/deselected, 3 existing warnings; 340.80s. |

Final focused evidence covers valid production-like synthetic configuration;
invalid/missing settings; unavailable database; missing/stale/wrong/empty revision;
current revision; real PostgreSQL 16/TCP-disabled runtime; unit major-version
boundaries and forced runtime-check rejection (no actual PostgreSQL 15/17 server);
real writable/unwritable local storage and simulated OS failure; required assets;
dotenv exclusion; no Settings constructor or provider-key field reads by the
configuration loader; sanitized settings/DB errors; no provider dispatch; and unchanged
rows, table definitions, defaults, constraints and indexes. Schema checks are run
against PostgreSQL-enforced read-only databases with populated preservation rows.
No failed assertion was weakened or removed.

Dockerfile checks and fake-executable shell command gating are source/process-level
evidence only. They show preflight failure prevents the CMD's serve step and that
migrations/proxy-trust flags are absent; they do not build or execute an image.

Prior Gate 7.2 evidence remains historical: focused 50 passed and broader 711 passed.
Docker is unavailable: source-level packaging tests cannot establish image build,
runtime UID/volume permissions, signals or container lifecycle. No staging, commit,
push, PR change, deployment or provider request is authorized/performed.

Remaining NOT VERIFIED: clean image installation/build, immutable base-image/hash
locking, actual container UID/volume ownership/signals/replacement, durable mount
identity, hosted HTTPS/proxy/cookie behavior, paired backup restoration, successful
real-provider acceptance and reviewed knowledge-pack availability. These limitations
do not negate the bounded offline packaging/preflight checks and do not authorize
hosting, live dispatch, security changes or interrupted-run recovery changes.

## Final handoff

**PASS for the approved provider-neutral packaging/preflight scope**, supported
by the final 57-test focused and 767-test broad offline results. This is not a
production deployment/readiness or clinical acceptance claim.

Read-only cluster inspection confirmed PostgreSQL 16.15, TCP disabled and zero
remaining `rc_synthetic_*` databases. The cluster stopped successfully with:

```text
/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/dandoonjan-g73-e037h5mt/data -m fast -w stop
```

Cluster files and sanitized test logs remain under `/tmp`; no unrelated cleanup.
The postmaster PID file is absent. Final fingerprints match all 920 pre-existing
owner files, including filenames and SHA-256 contents. Owner dirty/untracked
status is unchanged. Repository status has only these nine additional approved
changes: Dockerfile, .dockerignore, render.yaml, netlify.toml, README.md,
requirements-runtime.txt, app/deployment_preflight.py,
tests/next_phase/test_gate73_packaging.py, docs/phase-7/gate-7.3/README.md.
Python syntax/template parsing and whitespace checks passed, including
`git diff --check`. Branch/HEAD remain the baseline above; index is empty.
No commit was created and nothing was staged or pushed.
