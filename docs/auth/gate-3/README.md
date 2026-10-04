# AUTH Gate 3 — ACCOUNT frontend and session UX

Owner-approved implementation on branch `agent/sadeghi-next-phase`, based on
`9833b247078adf7ed4b9178282aeaffbdf7ea6ac`. No Git staging, commit, push, merge,
reset, restore or clean. No backend/schema/migration/deployment changes.

## Behavior and architecture

The Persian landing account entry opens a native RTL modal. Anonymous users can
register and explicitly log in. Registration displays the success message,
switches to login, clears the password and obtains fresh pre-auth CSRF; it never
authenticates. Authenticated users see account identity and logout, including an
account view in the dialog. There is no My Cases or account-switching UI.

`frontend/account.js` owns account restoration, safe metadata, auth transport,
dialog focus and independent pre-auth/ACCOUNT CSRF channels. `frontend/app.js`
continues to own workflow presentation and independent Demo CSRF. No new runtime
dependency or authentication architecture was introduced.

All credentials use existing same-origin HttpOnly cookies managed by the browser
and backend. JavaScript never reads/manufactures bearer cookies. CSRF is in
memory; credentials never enter storage/history/URLs/log state. Password inputs
allow paste and password managers, distinguish current/new-password autocomplete,
and clear on mode switch, close and successful action. Client length validation
counts Unicode code points and preserves spaces; backend validation is authoritative.

Structured request errors retain backend code, status and Retry-After. Empty
204 logout responses bypass JSON parsing. Unknown/wrong/disabled credentials
retain generic messaging; registration conflict remains generic. Rate guidance
is bounded and requires explicit retry. CSRF rejection refreshes the appropriate
channel and requires explicit resubmission. Ambiguous mutations/auth actions are
never automatically replayed.

## Restoration and boundaries

Startup enters restoring state and conceals ACCOUNT workflow material. `/me`
identifies the principal, `/csrf` refreshes ACCOUNT CSRF, then matching continuity
is validated through an owned Case GET before resume is offered. No account or
authenticated session is silently created. An ordinary anonymous 401 stays
anonymous; known-account continuity plus AUTH_REQUIRED shows ended-session UX.
Absent/expired/revoked/disabled sessions are indistinguishable on the backend;
the UI never claims a particular cause. Network/5xx leaves account work blocked
with explicit revalidation, rather than claiming logout. Disabled/unsafe auth
configuration fails closed while Demo remains independent.

ACCOUNT session epochs and workflow generations are separate. Account boundary
changes invalidate auth requests; workflow replacement/ACCOUNT–Demo transitions
invalidate workflow requests. Fetches have tracked AbortControllers; generation
checks also protect success, error, follow-up and finally paths when cancellation
is ignored. A late login after closing the dialog and starting Demo cannot replace
that workspace: its result is discarded and a fresh `/me` reconciles any cookie
the server actually committed.

Clearing releases case ID, report/authority/source DOM, export preparation and
title, dossier/intake values, File references and upload rows, processing/outcome
presentation, errors, audience selection and operation reports. Workflow identity
rotates; old Back/Forward entries cannot bind. Only the application-owned active
case key is removed; unrelated browser storage and server history are preserved.
Explicit transitions warn before discarding unsaved forms or pending local files.

Logout immediately locks/conceals ACCOUNT work and invalidates its requests.
Only backend 204 confirms success. Network/server/CSRF failure keeps old material
concealed, reports uncertain logout and offers explicit retry/revalidation. Demo
work can remain active while ACCOUNT logs out or changes.

Token-free BroadcastChannel messages contain only session-change type/phase.
Other tabs clear and lock on logout initiation, then revalidate on confirmed
change. BFCache pageshow revalidates; pagehide clears ACCOUNT presentation and
password inputs. No credentials, identity, case/report or clinical data are broadcast.

## Continuity and Demo

`dandoonjan_active_case` is now `{version:2,id,namespace,accountId}`. ACCOUNT binds
to the `/me` public ID. Unbound legacy hints and another account's metadata are
ignored; owned lookup denial removes invalid ACCOUNT continuity. History carries
namespace/account/workflow identity and presentation IDs only.

Demo metadata is namespace-specific and its existing visitor cookie remains the
server authority. Resume uses GET visitor validation, never a new POST visitor to
claim an old case. Lost visitor identity clears Demo material and offers a new
explicit Sample start. ACCOUNT and Demo may coexist; each case mutation attaches
only its namespace's CSRF token. No Demo case becomes an ACCOUNT case.

## Accessibility and visual preservation

Native dialog semantics, labelled inputs, aria-describedby/aria-invalid, live
status/error text, initial focus, Tab/Shift+Tab containment, Escape and focus return
are covered in Chrome. Keyboard-only registration/login is exercised. Responsive
dialog bounds/no overflow are checked at 390, 768 and 1440px under reduced motion;
screenshots are written to disposable pytest evidence directories.

Existing landing/workflow/print styles, tooth assets, typography and report/export
presentation code remain unchanged. The formerly desktop-only auth control is
available below the existing 1051px desktop breakpoint using scoped account CSS.
Known landing contrast debt was not changed or declared fixed. Screen-reader
semantics were checked through DOM/browser assertions; manual assistive-technology
testing and other browser engines are NOT VERIFIED.

## Exact implementation files

Added:

- `frontend/account.js`
- `frontend/account.css`
- `verification/auth_gate3_support.py`
- `verification/test_auth_gate3_browser.py`
- `docs/auth/gate-3/README.md`

Modified:

- `frontend/index.html`
- `frontend/app.js`
- `verification/test_demo_browser.py`
- `verification/test_navigation_browser.py`
- `verification/test_p1_browser.py`

The additional P1 fixture change removes obsolete injected ACCOUNT CSRF that
would override product token refresh. Existing tests use product restoration/
transport. Two direct backend-edit checks use the current product token; their
authority assertions remain unchanged. The storage-hint test now requires
rejection before any case GET instead of after a forbidden request.

## Test ledger

All pytest commands use `.venv/Scripts/python.exe verification/run_auth_gate2.py`
with the listed arguments and `-q --tb=line` (final regression adds `-ra`).
The launcher sets disposable global DB/storage before imports. Browser fixtures
use their own disposable SQLite/storage, Mock, empty provider keys and disabled
live dispatch. Gate 3 uses real UI registration/login with no injected transport;
its server installs live-provider construction/dispatch tripwires and checks that
passwords and tripwire failures never enter the server log.

| Run / arguments | Result |
| --- | --- |
| `verification/test_auth_gate3_browser.py`, tests first, before source implementation | **32 failed**, 113.46s; disabled landing entry/missing frontend behavior |
| Same, first implementation, `--maxfail=5` | 29 passed, 3 failed, 54.95s; responsive entry and report-resume test setup |
| Gate 3 + Demo + navigation + upload + professional PDF | 76 passed, 2 failed, 208.62s; hidden Demo expiry message and obsolete fixture token |
| Added stale-completion/hidden-reset/CSRF/owned/expired subset | 8 passed, 1 failed, 27 deselected, 22.37s; hidden completeness survived replacement |
| Added cross-tab logout-start/restoration subset | 3 passed, 1 failed, 36 deselected, 15.49s; other tab revalidated before logout completed |
| Gate 3, after boundary corrections | **40 passed**, 67.90s |
| Gate 3 + Demo + navigation retest | **62 passed**, 130.35s |
| Added account-view/keyboard/audience/Back subset, before polish fixes | 2 passed, 2 failed, 39 deselected, 18.92s; account view and audience reset |
| Added closed-login/new-Demo race, before correction | 1 failed, 43 deselected, 7.01s; late login cleared new Demo |
| Corrected closed-login/account-view/keyboard/audience subset | **4 passed**, 40 deselected, 10.45s |
| Full backend `tests -ra` | **571 passed, 3 skipped, 3 warnings**, 234.95s |
| Gate 3 + Demo + navigation + upload + professional PDF + P1, before closed-login addition | **106 passed**, 244.89s |
| Same combined suites including closed-login correction, before local color correction | **107 passed**, 250.76s |
| Added scoped-aqua surface test, before correction | 1 failed, 44 deselected, 5.27s; home-only CSS variables made dialog transparent |
| Final Gate 3 focused suite after scoped-color correction, `verification/test_auth_gate3_browser.py -ra` | **45 passed**, 73.24s |
| Final existing browser regression after focused pass: Demo + navigation + upload + professional PDF + P1, `-ra` | **63 passed**, 174.20s |

Final tested scope: VERIFIED WORKING for all 45 Gate 3 browser tests, 63 existing
browser regression tests and 571 executed backend tests. The three backend skips
are environmental limitations below. Earlier Auth Gate 1/2 results are historical
and are not counted as this gate's executions. Final screenshots at all three
widths were visually inspected after the scoped-color correction.

## Repository evidence

`git diff --check` passed; staged diff is empty. Branch and HEAD remain
`agent/sadeghi-next-phase` / `9833b247078adf7ed4b9178282aeaffbdf7ea6ac`.
No commit was created. No normal developer database was opened, migrated or used
by the explicit disposable launchers/fixtures; no local configuration was edited.

All 878 pre-existing dirty/untracked files were hashed before implementation and
again after verification (excluding only the exact Gate 3 additions/changes).
Count and aggregate SHA-256 match:
`afd2e38d72197fc4f3ae2727a2093934e33536788da5f3e19be7e7ec073c01eb`.
This includes the three unrelated modified landing screenshots and unrelated
assets, directories, fonts, scripts and archive. The protected tracked landing
styles/assets, typography, report/export and print files also have empty diffs.

PR #5 was verified OPEN with mergedAt=null and the correct head branch before
implementation. The first final read-only GraphQL request timed out. One read-only
retry succeeded: state=OPEN, mergedAt=null, headRefName=agent/sadeghi-next-phase.
PR #5 remains open/unmerged in that final verified response. No PR mutation was
attempted.

## Limits and deferred work

No server processing cancellation was added. Requests admitted before logout can
finish, as Gate 2 defines; their obsolete client results are rejected. There is
no current processing polling loop. Session loss is detected through requests/
restoration, not an invented client expiry timestamp. Another tab's CSRF refresh
can still require explicit retry.

Saved PDFs and an already-open browser print dialog cannot be recalled. Browser
history entries cannot be physically deleted, but their old workflow identity is
rejected. BroadcastChannel-dependent immediate cross-tab behavior needs browser
support; backend admission remains authoritative. Actual BFCache eligibility is
browser-controlled; verification covers native cross-document Back plus explicit
persisted-pageshow handling, without claiming every return used BFCache.

The backend skips remain private PostgreSQL socket availability and two existing
Windows directory-symlink privilege limitations. PostgreSQL/hosted HTTPS/proxy,
deployment/load, public rollout and clinical readiness remain NOT VERIFIED.

Deferred: My Cases, account switching, recovery/password change/email verification,
social login, production/deployment, abuse/housekeeping/credential hardening and
clinical/provenance/authority changes. No backend defect requiring expansion or
owner Stop Condition was encountered.
