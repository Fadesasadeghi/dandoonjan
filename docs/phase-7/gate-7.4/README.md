# Gate 7.4 — local/offline operational contract

Approved baseline: `agent/sadeghi-next-phase`,
`43498523ea7c2911aa18c3d7371f166bd82bb8ad`. Only the seven owner-approved
files change. No staging, commit, push, PR modification, deployment, Docker,
installation, external network, credentials, live provider, patient data,
PostgreSQL startup or paired backup/restore is authorized/performed here.

This handoff supersedes Gate 7.3's serve command and implicit proxy trust only.
Its other production requirements and verification limits remain in force.
Gate 7.3's 57 focused/767 broad passes and PostgreSQL verification are historical
evidence, not new executions at this gate.

## Production launch and finite proxy trust

`python -m app.deployment_serve` reads `DJ_TRUSTED_PROXY_PEERS` and optional
`PORT` from the process environment, validates them, invokes the existing
deployment preflight, and replaces itself with Uvicorn only on success.
Docker CMD now invokes that wrapper directly. No shell, automatic migration,
provider construction/dispatch, retry, recovery, new endpoint or dependency
is introduced. Preflight retains its existing read-only DB check and temporary
storage write/read probe; the wrapper adds no database/storage writes.

`DJ_TRUSTED_PROXY_PEERS` is a required comma-separated list of literal IPv4/IPv6
addresses of the actual connecting proxy peers. Whitespace is trimmed, addresses
are normalized and duplicates removed. Missing/empty entries, wildcard, DNS
names, CIDR networks, URLs, ports, unspecified/multicast addresses and scoped
IPv6 are rejected. No DNS is used. A finite literal-peer contract deliberately
does not support dynamic provider networks; unresolved topology requires owner
approval rather than substituting `*`. `PORT` defaults to 8000 and must contain
one to five ASCII decimal digits representing 1–65535.

Validation failures return exit 1 and fixed JSON `PROXY_TRUST_INVALID` or
`PORT_INVALID`, without echoing inputs. Preflight nonzero prevents serve.
On success the wrapper flushes preflight stdout before process replacement,
preserving evidence even without unbuffered output, and executes the current
Python interpreter with:

```text
-m uvicorn app.main:app --host 0.0.0.0 --port <validated-port>
--log-config app/logging.json --proxy-headers
--forwarded-allow-ips <validated-peer-list>
```

The explicit CLI peer list overrides Uvicorn's `FORWARDED_ALLOW_IPS` default.
App/Alembic Settings still have their existing dotenv behavior. Inject one
matching release environment and do not mount workspace dotenv files. The
wrapper itself does not load Settings/dotenv or read/print secret values;
preflight retains its existing provider-key-presence check. Never put credentials
in command arguments, build layers, logs or this repository.

Installed Uvicorn 0.54.0 source, matching the runtime pin, handles
`X-Forwarded-Proto`/`X-Forwarded-For` only from trusted connecting peers.
It does not derive scheme/host from standardized `Forwarded`,
`X-Forwarded-Host` or `X-Forwarded-Port`. Comma-separated or invalid proto
values do not establish HTTPS. This gate does not change that library behavior.

Outside the application, the authorized infrastructure must:

- Terminate TLS at the approved exact HTTPS origin and manage certificate trust.
- Overwrite/sanitize forwarding headers, including duplicate input headers;
  a trusted peer must never relay attacker-controlled scheme assertions.
- Connect from an explicitly configured trusted IP peer.
- Preserve public Host, Origin/Referer, CSRF headers, cookies and Set-Cookie.
- Prevent direct public access to the plaintext backend and bypass routes.
- Preserve same-origin frontend/API routing, no-store responses, and appropriate
  request/body/time limits. Avoid caching authenticated responses.

No hosting provider is selected and no hosted HTTPS or browser TLS lifecycle is
verified. Historical Render/Netlify templates remain incomplete and unchanged.

## Preserved HTTPS/auth behavior

Production auth router admission requires ASGI request scheme `https` and exact
configured HTTPS auth origins. A trusted proxy with sanitized
`X-Forwarded-Proto: https` supplies that scheme. An untrusted spoof cannot.
Normal Case routes retain their existing session/ownership/CSRF checks without
a new scheme check, so external backend isolation remains mandatory.

Production session/preauth cookies retain `__Host-` names, Secure, HttpOnly,
SameSite=Lax, Path=/ and no Domain, including deletion. Exact origin/token CSRF
checks, authentication and ownership are unchanged. There is no app HTTPS
redirect or altered session security model. ASGI/TestClient evidence models the
public HTTPS URL with a plaintext backend scope; it is not a TLS proxy test.

## Serialized startup and failure contract

Use the same compatible release and injected configuration throughout:

1. Separate serialized release operator/job: `python -m alembic upgrade head`.
2. Require migration exit 0 before launching any application instance.
3. Application/container: `python -m app.deployment_serve`, which runs preflight
   and then serves only after PASS.

For an explicitly authorized single-process local release rehearsal the ordering
is equivalent to:

```sh
python -m alembic upgrade head && exec python -m app.deployment_serve
```

This is an operational contract, not permission to migrate a real/shared DB or
a general release controller. Do not run preflight redundantly before a wrapper
that already runs it. A failed migration must stop the release; a failed
preflight must stop serve. Preserve evidence and investigate, rather than
stamping unknown schemas, bypassing CMD, relaxing policy or retrying indefinitely.
No real Alembic invocation is used by the fake ordering tests.

## Shutdown, restart and interrupted state

Stop admission of new writes at the external boundary and finish in-flight
processing before replacement. Several synchronous provider stages may exceed
one request/proxy timeout; browser timeout does not prove cancellation. Set and
rehearse external drain/grace limits before hosted use. The production command
does not add a graceful-timeout policy; Uvicorn's current default is unbounded,
while an external supervisor may still terminate it forcibly.

The local harness uses a private Unix socket, disposable SQLite and artifacts,
no dotenv, and hard-exit tripwires for non-Unix socket connect/bind, HTTPX sends,
OpenRouter construction and Mock dispatch. It runs three process generations:
idle SIGTERM, restart plus a 1.5-second controlled in-flight health request,
then another restart/idle SIGTERM. It requires the response to finish, lifespan
shutdown-complete evidence, and exit within a bound. Uvicorn 0.54.0 re-raises
captured SIGTERM after graceful shutdown: Python reports `-15`, not exit 0.
The harness's five-second graceful timeout is test configuration only.

This proves local process/request draining only. It does not prove completion
of live synchronous provider/pipeline work, container PID/signal delivery,
supervisor behavior or hard-kill recovery.

Durable pipeline/stage/model/review RUNNING records can survive process death.
Existing admission returns PROCESSING with no current report before provider
construction; its existing pending branch assigns NON_AUTHORITATIVE and commits.
The latest non-successful pipeline prevents current report delivery; older
reports remain history. Existing separate-interpreter unresolved-run regression
is retained and rerun. No replay, automatic retry, authority/recovery change,
lease, worker, queue, cleanup or recovery endpoint is added. Preserve unresolved
history and stop for an owner-approved recovery design when needed.

## Persistent artifact identity

Restart/replacement must reuse the same database and durable artifact root.
Artifact rows reference relative `cases/<case>/<UUID>/<filename>` keys with size
and SHA-256. The harness ingests a synthetic original, then reads its same DB row
and verifies file size/hash in each of three process generations. A separate
test demonstrates an empty writable replacement directory passes the existing
storage probe while the referenced original is unavailable.

That probe proves access only. Operators must independently verify durable mount
identity, ownership, free capacity and inventory before serving. Startup can
create a missing root; image-layer storage or a new empty mount is insufficient.
Keep one application instance for the approved local filesystem contract.
Mounted ownership must support UID/GID 10001:10001; actual container ownership
has not been rehearsed. Do not repair unknown populated stores with recursive
permission changes or evidence deletion.

Files precede DB commits, so rollback/crash can leave orphan/partial files.
Exclusive creation and containment checks do not supply cross-store transactions
or power-loss durability; storage writes do not explicitly fsync files/directories.
These behaviors are documented, not changed by this gate.

## Liveness and startup readiness

`/health` and `/api/health` remain unchanged HTTP liveness responses. Tests replace
DB/session/storage readiness functions with failure tripwires and verify that
health still returns OK. They do not establish database, storage, provider,
knowledge-pack or processing readiness.

Preflight is an external startup readiness gate for its bounded configuration,
PostgreSQL-major/schema-head, artifact-access and frontend-asset checks. It is not
a continuous HTTP readiness endpoint, artifact integrity check, mount identity
check, real-provider acceptance or clinical readiness. Rehearse post-start failure
monitoring with authorized infrastructure; do not treat a green health route as
permission to accept work when those dependencies fail.

## Paired restoration acceptance contract — not executed

Back up the complete PostgreSQL application database, including `alembic_version`,
and the original files referenced by `artifacts.storage_key` as a coordinated pair.
Preserve all auth/demo/session records, cases/dossier revisions, artifacts,
classifications/quality, model/processing/review runs, provenance, extractions/
treatment items/fields/findings, claims/evidence links/gaps, knowledge packs,
assessments/safety, snapshots/reports, hypotheses/evidence and audit events.
Reports/snapshots are DB records, not a separate server PDF store.

Stop all writers and finish in-flight work before capturing both stores during
the same quiescent interval. Record release SHA, schema head, backup pair/time,
storage identity, complete key/size/hash inventory and permissions together.
DB snapshot consistency alone does not establish DB/filesystem consistency.

Restore into new isolated destinations with matching code/configuration.
Acceptance requires schema/revision compatibility, all referenced file sizes/
hashes, provenance/foreign-key relationships, authority/history preservation,
account isolation, report/current-versus-historical semantics, and a passing
bounded preflight. Account for orphans without silently deleting them. Preserve
the original/failed pair, and authorize cutover separately only after acceptance.
Restored auth state may revive sessions; no session-revocation policy is invented.
Retention, encryption/access policy and recovery objectives require owner decisions.
No PostgreSQL backup/restore or cluster is run here.

## Evidence and boundaries

Regression-first selected run: **17 failed, 11 deselected**, 0.75 seconds.
Sixteen failures were the absent wrapper; one was the old Docker CMD. An earlier
full attempt was interrupted after a sandbox TestClient startup stall and is not
a completed test result. A local Unix bind probe confirmed EPERM. Execution
approval allowed subsequent offline tests outside the sandbox.

First implemented focused run: **88 passed, 8 skipped, 1 failed**, 21.08 seconds.
The only failure was a harness expectation of exit 0; installed Uvicorn source
demonstrated deliberate post-drain SIGTERM re-raise. The corrected harness requires
both shutdown-complete evidence and the expected signal exit; no application
assertion was weakened. Next focused run: **94 passed, 8 skipped**, 25.09 seconds,
before the final real-wrapper CLI failure/import tripwire test was added.

Another regression-first check exposed buffered stdout loss across `exec`:
**1 failed, 34 deselected**, 0.60 seconds. The wrapper now explicitly flushes
preflight output before replacement. Before this correction, the first broad
run passed **750 tests, 52 skipped**, 262.41 seconds, three existing warnings.
This is intermediate evidence; the final broad run includes the flush regression.

Final focused command (installed Linux Python 3.11.16, no PostgreSQL socket):

```text
/home/fadesasadeghi/miniforge3/envs/dandoonjan-wsl/bin/python -B verification/run_phase6_offline.py tests/next_phase/test_gate74_operations.py verification/test_gate74_operations.py tests/next_phase/test_gate73_packaging.py tests/regression_p0/test_packaging.py tests/next_phase/test_processing_concurrency.py -q -rs --tb=short
```

Before the stdout correction: **95 passed, 8 skipped**, 25.22 seconds.
Final result: **96 passed, 8 skipped, 0 failed**, 26.08 seconds, three existing
deprecation warnings. Skips are Gate 7.3's five database-revision cases, CLI
success, database major-version rejection and private PostgreSQL runtime checks;
each reports the absent `RC_POSTGRES_SOCKET`. Proxy/cookies, actual wrapper CLI
failure/import tripwires, fake release ordering, local process/artifact rehearsal,
liveness limits, packaging and unresolved-RUNNING regressions passed.

Broader offline command:

```text
/home/fadesasadeghi/miniforge3/envs/dandoonjan-wsl/bin/python -B verification/run_phase6_offline.py tests verification/test_gate72_harness.py verification/test_gate74_operations.py -q -rs --tb=short
```

Final broad result: **751 passed, 52 skipped, 0 failed**, 264.63 seconds, three
existing deprecation warnings. All skips explicitly require the absent private
PostgreSQL socket: one auth test, 39 Gate 7.2 PostgreSQL cases, eight Gate 7.3
cases, and four processing PostgreSQL cases. No PostgreSQL server was started;
no production PostgreSQL success is inferred from SQLite or mocks.

The existing offline launcher disables
dotenv before app imports, uses disposable SQLite/storage, disables bytecode and
pytest cache writes, and rejects real HTTPX transport. The process rehearsal adds
its own hard-exit socket/provider tripwires. No package installation is needed.

Owner preservation baseline: 878 modified/untracked nonignored files, with paths,
modes, sizes and SHA-256 contents, captured outside the repository. This does not
cover ignored files or directory metadata and is not equivalent to Gate 7.3's
historical 920-file inventory. Final comparison verified every captured file's
path/mode/size/SHA-256 unchanged, and exactly seven allowlisted additional paths.
Branch/HEAD stayed at the approved baseline; index remained empty. Python AST
parsing of the four changed Python files and `git diff --check` passed. No commit
was created and nothing was staged/pushed.

Remaining NOT VERIFIED: clean image build/install, immutable base-image/hash
locking, actual container UID/mount ownership/signals/replacement, durable mount
identity, hosted HTTPS/TLS/proxy/browser cookies, paired PostgreSQL restoration,
successful real-provider acceptance and reviewed knowledge-pack availability.
No PostgreSQL runtime tests are claimed at this gate. Existing opt-in tests skip
explicitly when no private socket is supplied. No skipped infrastructure check
is converted into a pass.

Stop for owner approval before any change beyond the seven files, schema/API/auth/
CSRF/ownership/provider/recovery semantics, dependencies, PostgreSQL, Docker,
network/infrastructure/credentials, data-risking action, unresolved proxy topology,
backup/privacy policy, Git staging/commit/push, PR action or deployment.

Assessment: **PASS for the approved bounded LOCAL/OFFLINE implementation and
rehearsal scope**. Source/config contract and the listed local rehearsals are
verified; staging/production/clinical readiness remains unverified. Exactly these
seven files changed: `app/deployment_serve.py`, `Dockerfile`,
`tests/next_phase/test_gate74_operations.py`, `verification/test_gate74_operations.py`,
`tests/next_phase/test_gate73_packaging.py`, `docs/phase-7/gate-7.4/README.md`,
and `README.md`. Auth/ownership/CSRF/provider/pipeline/report authority and
interrupted-RUNNING implementation files remain unchanged. No new commit;
HEAD remains `43498523ea7c2911aa18c3d7371f166bd82bb8ad`, index empty,
implementation unstaged, pre-existing owner changes preserved. PR #4/#5 untouched.
