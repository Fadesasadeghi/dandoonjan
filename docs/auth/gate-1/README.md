# AUTH Gate 1 — account and session foundation

Implemented on 2026-10-04 against `a8a1ce7e534e6b2398780e1b5fd6c114eeb3ae79`.
No Git staging, commit, push, merge, restore, reset, or clean was performed.

**This is backend foundation, not an authenticated product release. Normal case
routes remain unprotected. Knowing a case ID still permits access. Gate 2 must
enforce ownership across every case route before authenticated product use.**

`DJ_AUTH_FOUNDATION_ENABLED` defaults to false; the auth endpoints return 404
until explicitly enabled for isolated backend verification. No frontend, Landing,
Demo, upload, navigation, export, clinical pipeline, report-authority, snapshot,
provenance, or Case implementation was modified. `_ensure_user()` remains unchanged
and remains unsuitable for real account-owned case creation.

## Files

Added:

- `app/api/auth.py`
- `app/security/authentication.py`
- `app/security/sessions.py`
- `app/security/csrf.py`
- `app/security/rate_limits.py`
- `alembic/versions/d81e27a9c401_auth_foundation.py`
- `alembic/schema_adoption.py`
- `alembic/preauth_schema.json`
- `tests/auth/__init__.py`
- `tests/auth/conftest.py`
- `tests/auth/helpers.py`
- `tests/auth/test_registration.py`
- `tests/auth/test_login.py`
- `tests/auth/test_sessions.py`
- `tests/auth/test_csrf.py`
- `tests/auth/test_credentials.py`
- `tests/auth/test_rate_limits.py`
- `tests/auth/test_migrations.py`
- `tests/auth/test_postgres.py`
- This document.
- `docs/auth/gate-1/worktree-status.txt`: exact final `git status --short` snapshot.

Modified:

- `app/domain/models.py`: extend User; add auth-only tables.
- `app/config.py`: disabled-by-default foundation flag and validated exact auth origins.
- `app/main.py`: mount auth router, auth-only safe validation errors/no-store headers.
- `alembic/env.py`: select explicit recognized unstamped revision.
- `requirements.txt`: two direct dependencies.
- `verification/test_rc_postgres.py`: expected head changes to `d81e27a9c401`.

Existing test fixtures outside `tests/auth` were not weakened or changed. The
PostgreSQL verification change updates a schema-head assertion, not an acceptance
condition. Unrelated modified screenshots and untracked files remain untouched.

## Schema

Existing User `id`, `public_id`, `display_name`, `created_at`, and all Case.user_id
references remain unchanged. Case.user_id remains non-null; its existing
non-cascading foreign key remains unchanged.

Added User fields:

| Field | Type / nullability | Purpose |
| --- | --- | --- |
| email | String(320), nullable | Validated display/delivery address |
| normalized_email | String(320), nullable, UNIQUE | Portable login/uniqueness key |
| password_hash | String(512), nullable | Encoded Argon2id hash |
| kind | String(16), non-null, default LEGACY | ACCOUNT or LEGACY |
| status | String(16), non-null, default DISABLED | ACTIVE or DISABLED |
| updated_at | UTC DateTime, nullable | ORM account updates; preserved legacy rows are not backfilled |
| email_verified_at | UTC DateTime, nullable | Actual verification state; no verification flow yet |

Database checks require ACCOUNT credentials and an Argon2id-format hash prefix.
LEGACY requires DISABLED, null email/normalized-email/hash/verification timestamp.
No roles, usernames, profile fields, last-login field, or DEMO behavior were added.
New account public IDs use `secrets.token_hex(16)` (128 random bits). Existing
public IDs and the Case public-ID generator are unchanged.

AuthSession (`auth_sessions`): integer PK; indexed `user_id` FK with RESTRICT;
unique `token_hash` String(64); `csrf_token_hash` String(64); UTC `created_at`,
`last_seen_at`, indexed `expires_at`; nullable `revoked_at`.

PreAuthContext (`preauth_contexts`): integer PK; unique token hash; CSRF-token hash;
creation/expiration timestamps; nullable consumed timestamp. No user relationship.

AuthRateLimit (`auth_rate_limits`): hash key PK; indexed window start; positive
attempt counter. No raw email, IP, password, session, or CSRF credential is stored.

## Credential contract

Email: trim surrounding whitespace; validate using email-validator without DNS;
canonicalize domain through IDNA ASCII/lowercase for the login key; NFC/casefold
the local part under an explicit case-insensitive account policy. Preserve dots
and plus-tags. Bound canonical keys to 320 characters. Database uniqueness handles
concurrent registrations on SQLite/PostgreSQL without citext. Null legacy emails
do not conflict with other null legacy emails.

Passwords: 15–128 code points, exact supplied content; spaces, Persian, Unicode,
passphrases and at least 64 characters supported. No composition/periodic-change
rules, trimming, truncation, or implicit Unicode normalization. Invalid UTF-8
surrogate input is rejected safely. Hash/verify with argon2-cffi Argon2id defaults
(installed release uses 64 MiB, 3 iterations, parallelism 4), independently salted;
rehash on successful login when maintained parameters change. Dummy Argon2
verification reduces the obvious unknown-account timing fast path.

The compromised/common-password blocklist is explicitly **deferred**. No weak
handwritten substitute, large dataset, external lookup, or unrelated dependency
was introduced. It remains a hardening requirement before broader rollout.

Direct dependencies added: `argon2-cffi>=25.1,<26`, installed 25.1.0;
`email-validator>=2.3,<3`, installed 2.3.0. The former supplies maintained password
cryptography absent from stdlib/current dependencies; the latter avoids handwritten
email/IDNA parsing. Newly installed transitives: argon2-cffi-bindings 26.1.0,
cffi 2.1.1, pycparser 3.0, dnspython 2.8.0. DNS capability is not invoked.
No JWT/OAuth/auth framework/Redis/email SDK was added.

## Backend endpoint contracts

All require the foundation flag and explicit `DJ_AUTH_ALLOWED_ORIGINS`.

| Endpoint | Success | Contract |
| --- | --- | --- |
| GET /api/auth/csrf | 200 `{csrf_token}` | Issue 10-minute pre-auth context; if authenticated, refresh its CSRF hash too |
| POST /api/auth/register | 201 account | Pre-auth CSRF; insert a new ACCOUNT only; no login/session issuance |
| POST /api/auth/login | 200 `{user, csrf_token}` | Pre-auth CSRF; generic credential verification; fresh authenticated cookie/session |
| POST /api/auth/logout | 204, empty | Valid session requires CSRF; revoke before success; clear session/pre-auth cookies |
| GET /api/auth/me | 200 account | Require active ACCOUNT and valid session |

Account response is exactly `{public_id, email, email_verified}`. No internal
database ID, password/hash, raw session token, or token/CSRF hash is exposed.

Errors use `detail: {code, message_fa}` where applicable:
401 AUTH_REQUIRED; generic 401 INVALID_CREDENTIALS for unknown/wrong/disabled;
403 CSRF_FAILED; generic 400 REGISTRATION_FAILED for normalized-email conflict;
422 INVALID_CREDENTIAL_INPUT for malformed credentials/JSON; 429 AUTH_RATE_LIMITED
with Retry-After. Disabled foundation gives 404 AUTH_NOT_ENABLED; unsafe auth
configuration gives 503 AUTH_CONFIGURATION_INVALID.

Only recognized email-uniqueness violations become registration errors. Other
database failures propagate as errors and cannot become authentication success or
ordinary credential failure. Auth validation strips Pydantic input details;
auth responses/errors have no-store. Existing case error handling is unchanged.
Registration/session/revocation use the existing function-scoped commit-before-
response dependency; registration failure rolls back both account and CSRF
consumption. Auth code writes no credentials into logs or audit event details.

Repeated logout with no valid session returns 204 for a trusted origin; it changes
no authenticated state and needs no now-invalid CSRF token. Untrusted/missing
Origin/Referer is rejected. Disabled accounts cannot use existing sessions.

## Session/cookie/CSRF policy

Session and CSRF tokens are independently generated from 32 random bytes each,
lowercase hex encoded. Persist only SHA-256 hashes. Malformed/oversized session
credentials are rejected before any session query. Passwords never use SHA-256.

12-hour absolute expiration; 30-minute idle expiration; UTC server validation.
Last-seen writes occur at most approximately every 5 minutes and use a monotonic
conditional update. Idle expiry is conservative between touches. No per-request
session rotation. Login creates a fresh credential and revokes the current valid
session rather than upgrading pre-auth identity. `revoke_all` supports future
password-change/reset invalidation. Re-enabling a disabled account must accompany
an appropriate session-revocation policy in any future account-management flow.

Production/nondevelopment: `__Host-dandoonjan_session`, Secure, HttpOnly,
SameSite=Lax, Path=/, no Domain. Pre-auth uses equivalently protected
`__Host-dandoonjan_preauth`. Only development/test/local-synthetic uses differently
named `dandoonjan_dev_session` / `dandoonjan_dev_preauth` without Secure; HttpOnly,
SameSite and CSRF remain. Production auth refuses HTTP requests or non-HTTPS
configured origins. Proxy HTTPS/cookie forwarding is NOT VERIFIED here.

Pre-auth context does not create authenticated identity. Login/registration require
cookie-bound synchronizer CSRF and trusted exact Origin, or trusted Referer-origin
fallback. Successful context consumption is atomic and single-use. `/csrf` issues
a new context and token; previously issued CSRF tokens become obsolete on refresh.
The authenticated mutation helper checks X-CSRF-Token for POST/PUT/PATCH/DELETE,
without reading multipart bodies. Logout integrates it now; Gate 2 must integrate
it with all protected case mutations. SameSite alone is not the defense.

CSRF tokens may appear in the narrow JSON response; the bearer session credential
appears only in HttpOnly cookies, never frontend storage, JSON, forms, or URLs.
There is no frontend integration yet. Default cross-origin credentialed CORS is
unchanged; this Gate's verification uses same-origin requests.

## Rate-limit foundation

Five attempts per normalized email per action (login/register), per fixed 15-minute
window. SQLite/PostgreSQL native atomic upsert/RETURNING coordinates workers;
no per-process-only counters or permanent lockout. Counter commit precedes
credential/account work so failed attempts cannot roll it back. Login/register
budgets are separate; successes also consume attempts. Retry-After is a conservative
900 seconds. Expired windows reset on next attempt.

IP/body/global abuse limits, account flooding, Argon2 deployment load benchmarking,
and expired-context/session/counter housekeeping remain deployment/later-Gate work.
No cleanup/deletion job was introduced. Foundation disabled by default is essential
while those deployment controls and Gate 2 ownership remain incomplete.

## Migration/adoption preservation

Handwritten revision `d81e27a9c401`, predecessor `83b20cd5e702`. No autogeneration
or migration against the normal developer database was run.

The frozen pre-auth manifest records all 25 committed tables' columns/type
affinities/lengths/nullability, primary keys, foreign-key/delete relationships,
uniqueness and indexes. Unstamped recognition chooses the actual complete known
schema: RC at `4f2c9d7e1a10`, pre-auth at `83b20cd5e702`, or complete auth at head
with its required checks. It rejects unknown/partial schemas. Both exact known
knowledge-pack uniqueness variants are preserved: initial migrations retained
single-ID uniqueness; startup-created schemas did not have that historical extra
constraint. Nothing removes that constraint or rewrites knowledge-pack data.

Users gain nullable credential fields, legacy/default status/kind, and constraints.
SQLite batch rebuilds only users to add checks on a dedicated Alembic connection;
FK integrity is checked before/after and runtime FK enforcement is never disabled.
An externally FK-enabled SQLite migration connection is refused rather than
silently disabling it. PostgreSQL uses ALTER operations. No clinical table is
altered, no case is claimed, no snapshot/hash is rewritten. Downgrade refuses to
discard accounts/history; forward repair or an approved paired backup is required.

**Migration must precede starting the new app against an existing pre-auth
database.** Existing create_all startup is not an upgrade mechanism. This Gate did
not migrate, rebuild, inspect rows in, or start against the developer database.

Preservation tests populate every pre-auth table, preserve all old users/clinical
rows byte-for-byte through stamped and unstamped upgrades, check unchanged
Case.user_id/version, artifact identity/storage/hash, dossier/reviews/derivations,
report/snapshot/provenance/audit relationships and ordering, FK integrity, and
snapshot hash integrity. Fresh, populated, old startup-created, current
startup-created, recognized RC adoption, repeated upgrade and unknown-shape
rejection are exercised. PostgreSQL tests are opt-in/private synthetic only.

## Verification and command ledger

All Python executions used the existing `.venv/Scripts/python.exe` (Python 3.11.3).
The first sandbox launch failed with WSL `UtilBindVsockAnyPort` socket error; the
approved executable prefix was then used outside that sandbox. No live provider,
real patient data, shared database, or production database was used.

Test command prefix: `.venv/Scripts/python.exe -m pytest`.
Final offline subprocess environment explicitly set DJ_DATABASE_URL to
`sqlite:///./test_global.db`, DJ_AI_PROVIDER=mock, DJ_LIVE_PROVIDER_ENABLED=false,
both provider keys empty, DJ_ENVIRONMENT=test, and
DJ_LOCAL_SYNTHETIC_ACCEPTANCE_ENABLED=false. API/migration/browser fixtures use
their own disposable synthetic databases/storage. Local settings were not edited.

| Execution (pytest arguments unless stated) | Exact result |
| --- | --- |
| `tests/auth -q --tb=short`, tests first | 44 setup errors: missing Settings auth fields; test fixture corrected |
| `tests/auth/test_registration.py tests/auth/test_login.py tests/auth/test_migrations.py -q --tb=no`, corrected tests first | 14 failed, 3 warnings, 13.77s; missing foundation reproduced |
| pip install `'argon2-cffi>=25.1,<26' 'email-validator>=2.3,<3'` | Success; installed versions above |
| `tests/auth -q --tb=short`, first implementation | 20 failed, 24 passed, 3 warnings, 38.98s; UTC ORM synchronization and adoption mismatch fixed |
| `tests/auth/test_migrations.py -q --tb=short` | 1 failed, 3 passed, 10.17s; historical uniqueness variant isolated |
| `tests/auth --ignore=tests/auth/test_migrations.py -q --tb=line` | 1 failed, 39 passed, 3 warnings, 16.93s; test compared naive/aware representations, corrected to persisted timestamp |
| `tests/auth tests/regression_p0/test_migrations.py tests/next_phase/test_dossier_migration.py -q --tb=line`, first combined collection | 7 collection errors, 0.32s; auth test package/helpers isolated to avoid conftest/name collisions |
| Same combined command after isolation | 67 passed, 1 skipped, 3 warnings, 61.30s |
| `tests --ignore=tests/auth -q --tb=line`, inherited local config | 40 failed, 392 passed, 2 skipped, 3 warnings, 103.96s |
| Committed baseline copy: five failing provider test modules, without local mode | 121 passed, 3 warnings, 9.77s |
| Committed baseline copy: `tests --ignore=tests/auth -q --tb=line`, same local mode enabled | Same 40 failed, 392 passed, 2 skipped, 3 warnings, 87.49s |
| Current tree: `tests --ignore=tests/auth -q --tb=line`, explicit offline environment | 432 passed, 2 skipped, 3 warnings, 90.69s |
| `tests/auth -q --tb=line`, after adoption/Unicode strengthening | 60 passed, 1 skipped, 3 warnings, 35.74s |
| `tests -q --tb=line -ra`, first consolidated final collection | 1 failed, 493 passed, 3 skipped, 3 warnings, 120.38s; HTTPX rejected lone surrogate before sending it; test transport corrected to escaped JSON |
| `tests/auth -q --tb=line -ra`, corrected Unicode + commit-before-header assertion | 63 passed, 1 skipped, 3 warnings, 35.75s |
| Final separate migration group | 12 passed, 2 warnings, 28.90s |
| Final separate Demo group | 11 passed, 3 warnings, 6.87s |
| Final separate Upload Management group | 39 passed, 3 warnings, 14.93s |
| Final separate report/provenance group | 58 passed, 3 warnings, 26.68s |
| `tests/auth/test_migrations.py::test_fresh_migration -q --tb=line`, additional API-on-migrated-schema assertions | 1 passed, 3 warnings, 2.53s |
| Final clean consolidated `tests -q --tb=line -ra`, explicit offline environment | **495 passed, 3 skipped, 3 warnings, 120.28s** |

Browser command: `verification/test_professional_pdf_browser.py
verification/test_upload_management_browser.py verification/test_demo_browser.py
verification/test_navigation_browser.py -q --tb=line` — **43 passed, 143.80s**,
local real Chrome, offline synthetic server. No Landing contrast failure was
observed in this tested scope; the full Landing accessibility suite was not run.

Migration group: `tests/auth/test_migrations.py tests/regression_p0/test_migrations.py
tests/next_phase/test_dossier_migration.py -q --tb=line`.

Report/provenance group: `tests/test_invariants.py tests/test_p0_provenance.py
tests/regression_p0/test_derivation.py tests/regression_p0/test_api_state.py
tests/next_phase/test_review_flow.py tests/next_phase/test_contract.py
tests/regression_p1/test_report_presentation.py -q --tb=line`.

The 40 local-mode provider failures are **proven unrelated** by reproduction of the
same failed tests/counts in a disposable `git archive` of committed HEAD. That
mode intentionally rejects the other injected fixed models. No provider code,
test assertion, local configuration, or safety guard was weakened to fix them.

Read-only inspection/check commands included cat/sed/rg of AGENTS, all approved
handoff documents, requirements, models, config, main, migration adoption and
existing tests; git status/diff/stat/ls-files; executable/version/module probes;
schema-only comparison in a new disposable database (identified the historical
unique constraint); and `git diff --check` (passed). The frozen manifest was
generated from committed model source, then strengthened from the disposable
committed archive. Both generation commands succeeded and opened no real DB.
`RC_POSTGRES_SOCKET`/available local executables were checked; no private cluster
was available. Installed dependency versions and Argon2 parameters were checked
through Python metadata/PasswordHasher properties; they exactly match the values
above. No Git mutation command was executed.
Final repository checks: `git diff --check` passed; `git diff --cached --quiet`
passed (nothing staged); `git log -1 --format='%H %s'` confirmed unchanged HEAD;
`git diff --name-only` confirmed only the six Gate 1 tracked changes plus the three
pre-existing screenshot modifications. The full working-tree status is recorded
in [worktree-status.txt](worktree-status.txt).

NOT VERIFIED: PostgreSQL runtime/migration/adoption; hosted HTTPS/proxy cookie
forwarding; multiworker PostgreSQL rate-limit execution; deployment Argon2 load;
two existing Windows directory-symlink regressions (OS privilege unavailable).
Recovery, verification delivery, password change, roles, Demo authorization, My
Cases, frontend account state and server-side case ownership are later Gates.

## Gate boundary / remaining decisions

No stop condition requiring a risky change was encountered. The blocklist is an
explicit deferral, not a claim of compromised-password detection. PostgreSQL and
deployment checks remain bounded by environment availability. Existing auth-free
case routes are deliberately tested as still public with foundation disabled.
Public/production rollout is not approved. Gate 2 ownership and CSRF integration
must precede authenticated product use. Review/migrate a synthetic database first;
do not start the new schema against an unmigrated normal database.

Final tested scope: VERIFIED WORKING for the 495 executed backend assertions and
43 browser tests, including the account/session foundation and existing workflow
regressions. The three backend skips are the private PostgreSQL auth check and two
existing Windows directory-symlink checks. PostgreSQL/hosted deployment remains
NOT VERIFIED; ownership remains VERIFIED ABSENT in the unchanged case API.
