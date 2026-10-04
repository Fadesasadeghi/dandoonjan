# Auth Gate 2 — ownership and visitor-scoped Demo

Implementation baseline: `aef36d710e3ff466e3cba3f8661f81203c882855` on
`agent/sadeghi-next-phase`. All changes remain unstaged. No commit, push, merge,
reset, restore, clean, or migration against the normal developer database occurred.
The three pre-existing screenshot modifications and all pre-existing untracked
artifacts were preserved.

Status: implementation verified and ready for owner review in the executed
synthetic scope. PR #5 was verified OPEN and UNMERGED by the final read-only GitHub
REST query (`merged=false`, `merged_at=null`), after earlier CLI timeouts and a
failed web fallback. No merge action was performed. PostgreSQL runtime is NOT
VERIFIED because the existing private synthetic socket was not supplied.

## Architecture and ordering

`app/security/case_access.py` centralizes normal ACCOUNT and Demo admission.
`CaseAdmissionRoute` checks identity and mutation CSRF before FastAPI reads/parses
JSON or multipart. This preliminary check uses a separate read-only session,
touches no identity rows, and resolves no Case. Function-scoped dependencies repeat
credential validation and own the authoritative Case lookup/write transaction.

Normal queries filter directly by public ID, authenticated user ID, ACTIVE ACCOUNT
owner, and absence of a Demo visitor association. Demo queries filter directly by
public ID, visitor user ID, persistent visitor association and non-authenticating
LEGACY/DISABLED principal. Failed queries never perform another existence query.
They access no artifacts, dossier, report authority, snapshot, source material,
effective hash, provider, or processing pipeline.

Both namespaces call the existing clinical route handlers with an already
authorized Case. Creation shares only the existing clinical creation operation.
`_ensure_user()` and the unrestricted `_case_or_404()` were removed.

`Case.user_id` remains the only canonical ownership relationship. Case gained only
a view-only ORM relationship to Demo visitors, with no new database column. No
artifact/report/snapshot/derivation/provenance owner field was added. Pipeline,
reporting, authority, source presentation and provider implementation files were
not changed. Only `sample.is_demo()` changed its classification source.

SQLite uploads still acquire `BEGIN IMMEDIATE` before capacity measurement and
insertion. Authentication is read-only until that lock is established; monotonic
session touching occurs afterwards. PostgreSQL locks the authorized Case row.
Duplicate, capacity and durable rejection-audit behavior remains in existing code.

Requests admitted before concurrent logout may finish. Requests authenticated after
revocation commits fail. No pipeline cancellation behavior was introduced.

## Route matrix and fixed contracts

Every normal operation requires a valid session for an ACTIVE ACCOUNT. Missing,
invalid, expired, idle-expired, revoked or disabled-account identity returns
`401 AUTH_REQUIRED`. Every normal mutation additionally uses Gate 1 synchronizer
CSRF and exact Origin/Referer validation before ownership lookup.

| Method | Normal path | Required boundary |
| --- | --- | --- |
| POST | `/api/cases` | ACCOUNT + CSRF; create with that ACCOUNT user ID |
| GET | `/api/cases/{id}` | ACCOUNT + owned Case |
| PATCH | `/api/cases/{id}` | ACCOUNT + CSRF + owned Case |
| GET | `/api/cases/{id}/dossier` | ACCOUNT + owned Case |
| PUT | `/api/cases/{id}/dossier` | ACCOUNT + CSRF + owned Case |
| POST | `/api/cases/{id}/artifacts` | ACCOUNT + CSRF + locked owned Case |
| POST | `/api/cases/{id}/process` | ACCOUNT + CSRF + owned Case |
| GET | `/api/cases/{id}/status` | ACCOUNT + owned Case |
| GET | `/api/cases/{id}/assessment` | ACCOUNT + owned Case |
| GET | `/api/cases/{id}/report` | ACCOUNT + owned Case before hashes/authority/sources |

All ten operations also exist under `/api/demo/cases` with Demo visitor admission.
Missing/invalid/expired/revoked Demo identity returns `401 DEMO_AUTH_REQUIRED`.
All Demo mutations require that visitor's CSRF token and trusted origin.

With a valid principal and, for mutations, valid CSRF, foreign, nonexistent,
historical LEGACY and wrong-namespace cases return exactly the same response:

```json
{"detail":{"code":"CASE_NOT_FOUND","message_fa":"پرونده در دسترس نیست."}}
```

Status is 404. Invalid mutation CSRF returns `403 CSRF_FAILED` independently of
case existence. Authorized callers retain existing domain responses, including
`REPORT_NOT_READY`. Protected case/auth/Demo session responses and errors use
`Cache-Control: no-store`. Matching lookup shapes, one fixed error body, and no
existence-dependent child queries reduce avoidable enumeration differences; no
claim of constant-time database execution is made.

Public synthetic fixture reads remain `/api/demo/sample`, `/sample-image` and
`/sample-plan`. They issue no credentials and adopt no cases. `/case/{id}` remains
an identical static HTML shell without a Case lookup. Source/presentation material
is returned inside the protected report endpoint; there is no separate artifact
download, report-ID, snapshot-ID or PDF API/storage mount. Route declarations were
re-audited after implementation.

## Demo visitor and classification

New `demo_visitors` stores a unique RESTRICT user FK, unique opaque-token hash,
independent CSRF-token hash, creation/last-seen/absolute-expiration timestamps,
revocation timestamp and expiration index. Tokens use the existing 32-random-byte
Gate 1 primitives; bearer tokens appear only in HttpOnly cookies. No bearer token
is returned in JSON.

Each bootstrap creates a new LEGACY/DISABLED User with no credentials, unless a
valid visitor already exists. It never selects or associates an existing User.
ACCOUNT sessions and `auth_sessions` remain unchanged in principal semantics.

`POST /api/demo/session` requires a trusted exact origin, creates/reuses a visitor,
and issues/refreshes its CSRF token. `GET /api/demo/session` requires a valid visitor
and refreshes CSRF for navigation/resume. Issuance requires explicit allowed origins
and, outside development/test/local-synthetic, HTTPS configuration.

Demo lifetime is 12 hours absolute / 30 minutes idle, with bounded monotonic touches.
Development cookie: `dandoonjan_dev_demo`; production cookie:
`__Host-dandoonjan_demo`, Secure, HttpOnly, SameSite=Lax, Path=/, no Domain.

The persistent visitor-to-User association controls classification even after
expiry/revocation. There is no expiry deletion or principal reuse. A fresh session
after expiry creates a fresh principal; previous cases remain unavailable.

Demo creation writes the synthetic context marker server-side. Client `sample`
flags, stored hints and context markers grant no authorization or Demo processing
mode. Demo PATCH retains server synthetic context. ACCOUNT cases with the marker
remain normal cases; historical marker-bearing LEGACY cases remain quarantined.

The existing Mock provider, `mock-evidence-v1`, `demo-review-v2`, safety and source
rules remain. The production Demo processing prohibition remains. Demo tests fail
if a real provider is constructed or dispatched. Credentials, visitor/user IDs,
expiry and revocation never enter clinical payloads, effective hashes, derivation
identity or report authority. Credential changes preserve existing hashes,
snapshots, reports and authority in the tested scope.

With both cookies present, the namespace selects the principal. Neither cookie
authorizes the other namespace. Visitors cannot access each other's cases.

## LEGACY quarantine and rollout

Historical Gate 1 LEGACY users remain DISABLED with null credentials and unchanged
Case ownership. No reassignment, email/public-ID/browser-ID claiming, first-user
adoption or historical Demo backfill occurs. Registration inserts a new ACCOUNT.
Only newly minted Demo principals receive visitor associations.

`auth_foundation_enabled` still defaults to false. Disabling account issuance
does not disable normal ownership checks or restore anonymous access. Existing
valid sessions, if any, still pass the ownership boundary. Normal anonymous
frontend creation intentionally fails closed until Gate 3; no fake compatibility
or ACCOUNT UI was added. Public auth rollout/deployment remains outside this gate.

## Minimal frontend Demo compatibility

Only `frontend/app.js` changed; no HTML/CSS/visual redesign. Sample obtains a
visitor after all fixture assets load, keeps Demo CSRF in memory, and sends Sample
creation/mutations through the Demo namespace. The shared request helper also
routes Sample resume, history report revalidation and printing through Demo APIs.
Stored `sample` is a routing hint only. Resume never bootstraps a new principal to
recover an old case. A 401 clears Demo CSRF and cached report/export material;
starting a new Sample can establish a fresh visitor/case.

Browser regression fixtures obtain a real synthetic ACCOUNT and add its CSRF only
to normal-case mutations. This is test-only transport, not product ACCOUNT auth.
Demo browser tests cover refresh/resume, lost credential recovery, storage-hint
forgery, namespace isolation, retries, navigation and Professional PDF behavior.

## Additive migration and exact adoption

Revision `e72b4c9a6102`, predecessor `d81e27a9c401`, creates only `demo_visitors`
and its expiration index. No Case/User rebuild, clinical table alteration or data
backfill occurs. SQLite checks FK integrity before/after. PostgreSQL uses additive
transactional DDL. Downgrade refuses destructive removal of visitor history.

`gate1_schema.json` was frozen from Gate 1 metadata before model changes and
includes required checks. A test compares the unchanged core schema against it.
`preauth_schema.json` was not modified. Adoption now recognizes exact RC, pre-auth,
Gate 1 and complete new-head schemas, preserving both known knowledge-pack unique
constraint variants. Unknown/partial shapes fail before adoption/application-data
changes. Startup `create_all()` is not an upgrade mechanism; migrate existing
databases before startup.

Disposable migration tests cover fresh SQLite, populated stamped Gate 1, unstamped
pre-auth, unstamped Gate 1, unstamped new head, repeated upgrade, unknown rejection,
all-table history preservation, FK integrity, legacy ownership, snapshot hashes,
and Demo API execution on Alembic-created schema. No developer migration ran.
PostgreSQL runtime/migration/adoption remains NOT VERIFIED: private socket absent.

## Tests and execution ledger

No real patient data, live provider request or paid service was used. Test inputs
are synthetic; provider-adapter tests use explicit injected offline transports.
Demo tests install real-provider construction/dispatch tripwires. Browser servers
use disposable SQLite/storage, Mock, disabled live dispatch and empty provider keys.

The existing Windows Python executable is `.venv/Scripts/python.exe` (Python 3.11).
The first sandbox launch failed with WSL `UtilBindVsockAnyPort`; the existing
approved executable was then used outside that sandbox. Source edits and pytest
runs were separate after the owner's targeted-edit instruction. No source rewrite
script was used after that instruction; targeted patches modified the routes.

`verification/run_auth_gate2.py` sets offline environment inside Windows Python
before imports, with fresh temporary global DB/storage defaults. This avoids WSL
shell assignments being lost and `.env` local acceptance mode contaminating tests.
It changes no product settings. It clears real provider keys, disables live and
local-synthetic acceptance, selects Mock and keeps account issuance disabled by
default; individual disposable fixtures explicitly enable account verification.

| Execution | Exact result |
| --- | --- |
| Initial `tests/auth_gate2`, before implementation | 52 failed, 3 warnings, 24.74s; intended absent ownership/Demo/CSRF defects reproduced |
| First focused implementation run | 52 passed, 3 warnings, 28.48s |
| Auth/Gate 2/Demo/upload combined run | 7 failed, 164 passed, 1 skipped, 3 warnings, 101.07s; six new capture-helper errors and production-cookie test setup corrected |
| New malformed-body admission tests, before route wrapper | 2 failed, 3 warnings, 1.38s; FastAPI returned 422 before authentication |
| Expanded targeted run with shell environment | 3 failed, 243 passed, 1 skipped, 6 errors, 3 warnings, 167.81s; direct-handler argument, fixture discovery, inherited provider mode corrected |
| First four-suite browser run | 8 failed, 38 passed, 2 warnings, 327.57s; global test ACCOUNT CSRF header interfered with Demo; fixture corrected |
| Separate Demo browser retest | 8 passed, 1 warning, 17.24s; subsequent raw-string edit removed that warning |
| First full backend run with shell environment | 44 failed, 525 passed, 3 skipped, 3 warnings, 198.85s; 40 existing local-mode provider failures plus four authenticated regression setups corrected |
| Targeted run through initial offline launcher | 248 passed, 1 skipped, 6 fixture errors, 3 warnings, 162.42s; explicit review-flow fixture imports corrected |
| Browser collection through initial launcher | 3 collection errors, 0.43s; launcher repository import path corrected |
| Final complete backend suite | **571 passed, 3 skipped, 3 warnings, 206.91s** |
| Final four browser suites | **46 passed, 129.13s** |
| Final standalone Gate 2 + auth suites | **139 passed, 1 skipped, 3 warnings, 97.46s** |

Final full backend command:

```text
.venv/Scripts/python.exe verification/run_auth_gate2.py tests -q --tb=line -ra
```

Final browser arguments:

```text
verification/test_demo_browser.py verification/test_upload_management_browser.py
verification/test_navigation_browser.py verification/test_professional_pdf_browser.py
-q --tb=line
```

The final full run includes focused Gate 2/auth/migration, existing Demo/upload,
report/provenance/authority/invariant and all other backend suites. Security tests
cover A/B ownership, all route methods, fixed denied responses, session states,
CSRF failures, malformed-body ordering, no clinical work/second lookup on denial,
upload idle-touch/duplicates, historical LEGACY, both-cookie separation, spoofed
markers, visitor expiry/revocation, credential-independent identity, parallel
bootstrap/uploads, five concurrent processing requests and logout admission.

The three final backend skips are unchanged environmental limitations: private
PostgreSQL socket absent and two existing Windows directory-symlink privilege
checks. No thresholds, skips or safety assertions were weakened/added to hide
regressions. Final suites have no remaining executed test failures.

Historical Gate 1's 495 backend passes and 43 browser passes are prior results,
not Gate 2 results. Earlier failed local-mode runs are superseded by the explicit
Windows-local offline verification; product/provider safety code was not weakened.

## Remaining limits and deferred work

NOT VERIFIED: PostgreSQL runtime/adoption/concurrency, hosted HTTPS/proxy forwarding,
deployment/multiworker operation and the two platform symlink cases.
No deployment, production migration, live-provider verification or clinical-ready
claim is made. Bootstrap abuse limits, visitor retention/housekeeping and longer
visitor recovery are later hardening decisions; expired rows currently persist.
CSRF refresh in another tab can invalidate older tokens, requiring user retry.

Gate 3: ACCOUNT UI/transport, authenticated resume/history binding, account cache
clearing, My Cases and session-expiry UX. Gates 4–5: recovery/verification and
credential hardening, abuse/housekeeping policy, hosted/PostgreSQL/deployment
verification under their approved scope. No recovery, verification UI, account
switching, visual redesign, clinical change or public auth rollout was implemented.

## Exact Gate 2 files

Added:

- `alembic/gate1_schema.json`
- `alembic/versions/e72b4c9a6102_demo_visitors.py`
- `app/api/demo.py`
- `app/security/case_access.py`
- `app/security/demo_sessions.py`
- `tests/auth_gate2/__init__.py`
- `tests/auth_gate2/conftest.py`
- `tests/auth_gate2/test_access.py`
- `tests/auth_gate2/test_boundary.py`
- `tests/auth_gate2/test_migrations.py`
- `tests/next_phase/__init__.py`
- `verification/run_auth_gate2.py`
- `docs/auth/gate-2/README.md`
- `docs/auth/gate-2/worktree-status.txt`

Modified:

- `alembic/schema_adoption.py`
- `app/api/routes.py`
- `app/core/cases/sample.py`
- `app/domain/models.py`
- `app/main.py`
- `app/security/sessions.py`
- `frontend/app.js`
- `tests/auth/conftest.py`
- `tests/auth/test_login.py`
- `tests/next_phase/conftest.py`
- `tests/next_phase/test_demo.py`
- `tests/next_phase/test_openrouter_e2e.py`
- `tests/next_phase/test_preflight.py`
- `tests/next_phase/test_preflight_remediation.py`
- `tests/next_phase/test_review_budget.py`
- `tests/next_phase/test_review_flow.py`
- `tests/regression_p0/conftest.py`
- `tests/regression_p0/test_derivation.py`
- `tests/regression_p1/conftest.py`
- `tests/regression_rc/conftest.py`
- `tests/regression_rc/test_commit_before_response.py`
- `tests/regression_rc/test_provider_privacy.py`
- `tests/test_api.py`
- `tests/upload_management/conftest.py`
- `tests/upload_management/test_upload.py`
- `verification/test_demo_browser.py`
- `verification/test_navigation_browser.py`
- `verification/test_p1_browser.py`
- `verification/test_professional_pdf_browser.py`
- `verification/test_rc_postgres.py`

Test changes supply real synthetic authenticated actors, namespace-specific CSRF,
explicit authorized Case arguments, production cookie naming, package-qualified
shared helpers, the new fixed 404 contract and new migration head. Existing
clinical/safety/PDF/upload assertions remain effective.

Final status is captured in [worktree-status.txt](worktree-status.txt). Pre-existing
unrelated files are listed there but are not part of this implementation. HEAD
remains the Gate 1 commit; there is no Gate 2 commit. Staged diff is empty.

## Closure evidence

| Invariant | Evidence / result |
| --- | --- |
| Every normal operation requires ACTIVE ACCOUNT | Route matrix, all-route A/B tests, session-state tests and pre-body admission tests passed |
| Every normal mutation requires CSRF | All five routes reject missing/wrong/other-session tokens and invalid Origin/Referer before lookup |
| Clinical work follows ownership | Handler dependencies; denial tripwires and SQL-query recording passed |
| Foreign/nonexistent/LEGACY/Demo share one normal 404 | Parameterized read/mutation tests passed |
| ACCOUNT/Demo and visitors cannot cross | Separate-cookie namespace and A/B visitor tests passed |
| No historical reassignment or browser authorization | Migration preservation, registration, marker and storage-hint tests passed |
| Identity/provenance excludes auth data | Credential-independent hash/snapshot/report/authority tests and existing provenance suites passed |
| Demo cannot construct/dispatch real provider | Existing/new Mock tripwires and production prohibition tests passed |
| Authority, provenance and safety remain intact | Final full offline suite passed without weakening existing assertions |
| Additive migration preserves history | Eight Gate 2 schema/adoption tests plus existing migration suites passed on disposable SQLite |
| Disabled auth does not restore anonymous cases | Dedicated flag-disabled 401 assertions passed |
| PR #5 remains unmerged | Read-only `gh api .../pulls/5`: state=open, merged=false, merged_at=null |

Final `git diff --check` passed; `git diff --cached --quiet` passed. Branch and HEAD
remain the baseline above. All closure invariants are satisfied in the tested
offline SQLite/browser scope, with PostgreSQL limitations reported as instructed.
