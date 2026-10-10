# Gate 7.5E — local Render staging ingress remediation

Baseline: `3dd5b2c94b02e56a0182b9b0eddc1f97f491b259` on
`agent/sadeghi-next-phase`. Local implementation and offline tests only. No
deployment, resource creation, hosted migration, provider credential, staging,
commit, push or frontend change is authorized or performed by this gate.

## Explicit security boundary

One setting is added: `DJ_RENDER_STAGING_HTTPS_BOUNDARY`. It defaults to
`disabled`; its only enabling value is `render-managed-tls`, permitted only with
`DJ_ENVIRONMENT=staging`. This is an operator assertion of the Render-managed TLS
boundary, not hostname detection or information from an incoming request.

Render documents automatic HTTP-to-HTTPS redirection, managed TLS and an
application listener that is not directly publicly reachable:
[TLS](https://render.com/docs/tls),
[Web Services](https://render.com/docs/web-services).
This mode must not be enabled on an exposed plaintext listener or another
platform. Actual hosted ingress behavior remains NOT VERIFIED locally. Stop if
the listener can be reached outside the approved TLS ingress boundary.

The launcher requires `DJ_TRUSTED_PROXY_PEERS` to be absent in this mode (even an
empty value is rejected) and starts Uvicorn with `--no-proxy-headers`. There is
no wildcard or guessed IP. An HTTP middleware copies the ASGI scope and sets
only its scheme to `https`; it leaves Host, client address, Origin, Referer and
headers unchanged. Forwarding headers are ignored, not consumed or interpreted.
Caller-supplied headers cannot select the mode or change trusted host/client
semantics. The middleware does not verify encryption by itself; its justification
is the explicit platform boundary. Use the launcher, not an independently
configured Uvicorn process that could re-enable proxy-header interpretation.

Configuration loading, deployment preflight and launcher reject activation
outside staging. Without this mode, the middleware is inactive and the original
finite-literal-peer launcher behavior is retained, including production's
existing trusted-peer interpretation. Invalid normal-mode peers still fail
before preflight. The offline launcher resets the new setting to `disabled`,
preventing inherited staging configuration from contaminating isolated tests.

Secure `__Host-` session/preauth cookies, HttpOnly, Path `/`, SameSite=Lax, exact
Origin/Referer checks, synchronizer CSRF tokens, authentication, account ownership
and empty staging CORS are unchanged. The Render origin is not added to allowed
browser origins. A spoofed forwarded host does not become an allowed origin;
missing Origin still requires a valid allowed Referer. Staging remains mock-only,
provider credentials forbidden, and reviewed Knowledge Pack enforcement required.
Clinical processing remains expected-blocked, not clinical acceptance.

## Intended future Render environment

This table is configuration for a separately authorized future deployment, not
an instruction to apply the template or create any resource now.

| Name | Intended value |
| --- | --- |
| `DJ_ENVIRONMENT` | `staging` |
| `DJ_RENDER_STAGING_HTTPS_BOUNDARY` | `render-managed-tls` |
| `DJ_DATABASE_URL` | Protected Render internal PostgreSQL 16 URL using `postgresql+psycopg://`; no credential value documented |
| `DJ_AUTH_ALLOWED_ORIGINS` | `["https://dazzling-bombolone-90006d.netlify.app"]` |
| `DJ_AUTH_FOUNDATION_ENABLED` | `true` |
| `DJ_CORS_ORIGINS` | `[]` |
| `DJ_AI_PROVIDER` | `mock` |
| `DJ_AI_MODEL_NAME` | `mock-evidence-v1` |
| `DJ_LIVE_PROVIDER_ENABLED` | `false` |
| `DJ_LOCAL_SYNTHETIC_ACCEPTANCE_ENABLED` | `false` |
| `DJ_REQUIRE_CLINICIAN_REVIEWED_KNOWLEDGE_PACK` | `true` |
| `DJ_ARTIFACT_STORAGE_DIR` | `/app/data/artifact_store` |
| `DJ_MAX_UPLOAD_BYTES` | `26214400` |
| `PORT` | Render-supplied; no fixed override |
| `DJ_TRUSTED_PROXY_PEERS` | Absent in this mode |
| `DJ_OPENROUTER_API_KEY`, `DJ_OPENAI_API_KEY` | Absent |

Normal/production mode uses `DJ_RENDER_STAGING_HTTPS_BOUNDARY=disabled` (or leaves
it unset) and still requires verified finite literal `DJ_TRUSTED_PROXY_PEERS`.
Production provider/preflight requirements are unchanged. Startup never migrates;
PostgreSQL must already be version 16 and at packaged head `e72b4c9a6102`.

## Tests-first evidence

Before implementation, focused ingress tests plus existing Gate 7.4/staging
tests yielded **32 failed, 82 passed, 3 warnings**, 15.85 seconds. Failures
reproduced `PROXY_TRUST_INVALID` without peers, ignored new configuration,
plaintext auth rejection and missing boundary middleware. Existing tests passed.
Two scope-isolation cases also failed in a separate pre-implementation run.
They are included in the complete 32-failure baseline, not additional failures.

The initial sandbox run stalled before requests in Starlette TestClient's AnyIO
portal startup. A bounded diagnostic confirmed the stall and timed out; the
original stalled run was interrupted. Completed API tests use the same existing
isolated offline launcher outside the sandbox. It creates disposable local test
storage and blocks real HTTP provider dispatch. No safety guard was relaxed.

## Retesting and review

Final focused command (existing isolated offline launcher):

```bash
/home/fadesasadeghi/miniforge3/envs/dandoonjan-wsl/bin/python -B verification/run_phase6_offline.py tests/next_phase/test_gate75e_render_ingress.py tests/next_phase/test_gate74_operations.py tests/test_staging_integration_contract.py tests/auth tests/auth_gate2 tests/next_phase/test_gate73_packaging.py tests/regression_p0/test_packaging.py -q --tb=short
```

**309 passed, 9 skipped, 0 failed, 3 existing deprecation warnings**, 134.75
seconds. This includes 49 new ingress cases, unchanged production proxy tests,
preflight, staging, auth, session/cookie, CSRF, account isolation and packaging/
routing coverage. The nine skips require an unsupplied private disposable
PostgreSQL cluster. No hosted database was used.

An earlier focused run passed 302 tests with nine skips before seven additional
cases were collected. A separate single-file run then exposed a test-only missing
`db` fixture dependency (48 passed, one setup error); it was corrected to use the
existing disposable API session fixture. The final focused result above includes
all additional cases and the correction; no application guard was changed for it.

Broad command:

```bash
/home/fadesasadeghi/miniforge3/envs/dandoonjan-wsl/bin/python -B verification/run_phase6_offline.py tests -q --tb=short
```

**835 passed, 52 skipped, 0 failed, 3 existing deprecation warnings**, 266.29
seconds. All 52 skips require an unsupplied private disposable PostgreSQL cluster.
The offline launcher returned success without a network-tripwire failure. No
provider dispatch, hosted database, deployment or resource creation occurred.

**VERIFIED WORKING:** local ingress contract, the focused scope above and the
isolated offline broad suite. **PARTIALLY VERIFIED:** deployment compatibility
through local/source tests only. **NOT VERIFIED:** actual provider ingress, hosted
PostgreSQL/schema, Netlify proxy/cookies, cold starts and durable storage.
Technically ready for owner local manual review; this is not deployment approval.

HEAD remains `3dd5b2c94b02e56a0182b9b0eddc1f97f491b259`; index empty. Gate files:
`.env.example`, `app/config.py`, `app/deployment_preflight.py`,
`app/deployment_serve.py`, `app/main.py`, `app/security/render_ingress.py`,
`render.yaml`, `verification/run_phase6_offline.py`,
`tests/next_phase/test_gate75e_render_ingress.py`, the Gate 7.5B README and this
README. No frontend file changed. Owner-state hash/inventory checks preserve all
928 pre-existing modified/untracked files. No staging, commit or push performed.

## Local manual review

The exact offline review command, from the repository root, is:

```bash
/home/fadesasadeghi/miniforge3/envs/dandoonjan-wsl/bin/python -B verification/run_phase6_offline.py tests/next_phase/test_gate75e_render_ingress.py -q --tb=short
```

These tests emulate the plaintext backend hop behind an HTTPS browser URL and
exercise the actual app with disposable SQLite test storage. They do not claim
deployment preflight acceptance with SQLite.

There is no ready live manual staging application in this gate: no existing
approved local migrated PostgreSQL 16 target/TLS ingress was established, and no
database or TLS listener is created. Once those local prerequisites are separately
established, use an isolated clean source export with no `.env`, not the dirty
owner checkout. Supply the safe staging environment above with a local synthetic
database/storage target. From that export's root, the launcher command is:

```bash
/home/fadesasadeghi/miniforge3/envs/dandoonjan-wsl/bin/python -B -m app.deployment_serve
```

Do not enable the Render boundary merely to browse a local HTTP port. A local
emulation must provide an actual HTTPS ingress and shield its backend listener;
otherwise use the normal finite-peer contract. The offline command above is the
applicable review command now. Do not bypass preflight or use owner data.

## Remaining limitations

Hosted Render/Netlify TLS, proxy forwarding, cookies, cold starts and PostgreSQL
migrations remain NOT VERIFIED. Render and Netlify production remain public;
application authentication is not whole-environment privacy. Synthetic testers
only; the application cannot identify arbitrary uploads as synthetic. Artifact
bytes are ephemeral, with durable uploads, restart/redeploy recovery, preserved
artifact history, backup/restore and clinical acceptance excluded. Knowledge Pack
remains pending. No Netlify routing files or frontend visuals were changed.
