# P1 #2 processing / retry investigation

Baseline: `agent/sadeghi-next-phase` at
`c5572220436bb032fc42f0c5a78b49d90e63d8b4`. Uncommitted investigation only.
No production defect was demonstrated. No production code, frontend, API shape,
schema, retry policy, or deployment configuration was changed.

## Existing contract and evidence

Both namespaces delegate processing, status, assessment and report handling to
the same handlers. ACCOUNT uses authenticated ownership and configured execution
identity; Demo uses visitor ownership and fixed Mock identity in allowed local
environments. Demo is not a fallback for ACCOUNT provider failure.

| Scenario | Finding and tested scope |
| --- | --- |
| Never processed | VERIFIED WORKING: no pipeline rows, report 404, assessments empty in both modes. Created intake is INTAKE_COMPLETE; status is not a promise that a report exists. |
| Starts | VERIFIED WORKING: durable RUNNING pipeline, NON_AUTHORITATIVE, case PROCESSING; concurrent reads have no current report/assessment. |
| Succeeds | VERIFIED WORKING: terminal SUCCEEDED/ACTIVE, current report and assessments available; snapshots and reports persist. Case normally reaches REPORT_READY; restricted/evidence outcomes have separate existing terminal semantics. |
| Fails | VERIFIED WORKING: caught execution failures return HTTP 200 with FAILED, null report/snapshot, sanitized error and run identity. Run is FAILED/NON_AUTHORITATIVE and remains history. Admission/pre-execution HTTP errors need not create a run. |
| Retry after failure | VERIFIED WORKING in both modes: same case, new run ID, next attempt for the same input hash; successful retry restores current results. |
| Retry also fails | VERIFIED WORKING in both modes: distinct durable failed attempts, no current result, later successful retry works. |
| Repeat after success | VERIFIED WORKING: unchanged effective inputs reuse the successful run/report/snapshot without Mock dispatch or another pipeline row. There is no force-rerun API contract. |
| Inputs change after success | VERIFIED WORKING: report/assessment immediately cease to be current. A new input hash starts its own attempt numbering. Failure does not resurrect old results; subsequent success creates a new report and preserves old snapshots/reports. |
| Close requests | VERIFIED WORKING on disposable SQLite: the second same-case request observes PROCESSING and the same run ID, without duplicate provider execution. Existing tests also cover simultaneous admission, different-case overlap and mutations during execution. |
| Interrupted worker | Existing regression verifies an old RUNNING record blocks replay, including in a separate interpreter. This can remain unresolved indefinitely. It is explicit existing behavior, not evidence that timeout-based retry is safe. No recovery/lease/cancellation policy was introduced. |
| Browser reload | VERIFIED WORKING: success reload returns home, then explicit resume fetches the current report in both modes without mutation replay. Existing refresh test also prohibits fabricated processing. PARTIALLY VERIFIED for reload during durable RUNNING/FAILED: source tracing shows explicit resume reads case/dossier/report and displays the persisted status when report is 404; actual browser crash during backend execution was not exercised. |
| Frontend/backend disagreement | VERIFIED WORKING: process start clears cached report; report history revalidates identity and print rechecks freshness. No polling exists. A PROCESSING response ends the local request animation and offers manual status/retry interaction; it does not mean the backend execution completed. |
| HTTP versus durable failure UI | VERIFIED WORKING in browser fixtures: aborted transport, HTTP 503 and HTTP 200 FAILED all release controls and permit same-case retry in ACCOUNT and Demo. Real Mock retry succeeds. Failure responses in these browser probes are intercepted fixtures, not persisted failures; actual durable failures are covered separately by API tests. |

Effective identity includes case version and text, dossier, source artifacts,
provider/model, pack identity/version, prompt/module/schema versions, and Demo
version when applicable. Attempt numbers are scoped to case/module/input hash,
not a global counter. Current reads require the latest pipeline to be successful,
ACTIVE and match current identity; reports additionally match snapshot case version.
Previous ACTIVE authority may remain stored after a failed retry as history, but
the latest-run/current-input filters prevent presenting that history as current.
Successful replacement supersedes previous authority without deleting snapshots.

Frontend controls disable during the local request. Retry calls the same process
handler after saving current intake/dossier and pending uploads. Local navigation
does not replay mutations. Session continuity is namespaced; it grants no ownership.
No automatic retry, forced new successful attempt, or polling requirement was found.

## Files inspected

Read targeted implementation/test sections and relevant documentation:

- `AGENTS.md`; `docs/handoff/gate-1/{README,DECISIONS,ROADMAP,AUDIT}.md`;
  `docs/next-phase/CONTRACT.md`; `docs/handoff/p1-core/README.md`;
  `docs/handoff/p1-intake-validation-parity.md` and processing-identity references.
- `app/api/routes.py`, `app/api/demo.py`, `app/pipeline/orchestrator.py`,
  `app/pipeline/runs.py`, `app/domain/models.py`, `app/domain/enums.py`,
  `app/core/cases/state_machine.py`, `app/core/cases/sample.py`,
  `app/security/case_access.py`, `app/ai/gateway.py`, `app/ai/dispatch.py`.
- `frontend/app.js` processing, outcome, busy controls, API, navigation, printing
  and continuity functions; targeted `frontend/account.js` error references.
- `tests/conftest.py`, regression P0/P1 and next-phase fixture files;
  `tests/next_phase/test_processing_concurrency.py`, `test_demo.py`;
  `tests/regression_p0/test_assessment_freshness.py`, `test_api_state.py`;
  `tests/test_pipeline.py`, `test_p01_reconciliation.py`;
  processing admission references in `tests/auth_gate2/test_access.py` and
  `test_boundary.py`; `verification/test_p1_browser.py` and
  `verification/test_navigation_browser.py`.

## Tests added and execution

- `tests/regression_p1/test_processing_retry.py`: four parameterized ACCOUNT/Demo
  API checks, exercising repeated failure/retry/reuse, input change/failure/new
  success, exact historical snapshot/report preservation and running reconciliation.
- `tests/regression_p1/test_processing_retry_browser.py`: six ACCOUNT/Demo browser
  checks for network/HTTP/durable-response-shape failure, same-case retry, released
  controls and successful reload/resume without mutation replay.

All tests ran against unchanged production code. There is no red/green production
fix cycle or defect root cause to report. Initial sandboxed Linux invocations
stalled during TestClient setup and were interrupted (exit 130, no results).
The subsequent API invocation used approved execution outside that sandbox.

Completed commands (all new results from this investigation, not prior handoffs):

```text
python3 -m pytest tests/regression_p1/test_processing_retry.py tests/next_phase/test_processing_concurrency.py tests/test_pipeline.py tests/test_p01_reconciliation.py tests/regression_p0/test_assessment_freshness.py tests/regression_p0/test_api_state.py tests/next_phase/test_demo.py -q --tb=short
68 passed, 7 fixture-setup errors, 3 warnings (48.63s).

PYTHONPYCACHEPREFIX=/tmp/dandoonjan-p1-retry-pycache python3 -m pytest tests/next_phase/test_demo.py tests/auth_gate2/test_access.py tests/auth_gate2/test_boundary.py -k 'test_demo or process' -q --tb=short
36 passed, 43 deselected, 3 warnings (33.10s).

.venv/Scripts/python.exe -m pytest verification/test_p1_browser.py verification/test_navigation_browser.py -k 'processing or refresh_has_no_fabricated or resume' -q --tb=short
7 passed, 28 deselected (32.20s).

.venv/Scripts/python.exe -m pytest tests/regression_p1/test_processing_retry_browser.py -q --tb=short
6 passed (35.85s).

.venv/Scripts/python.exe -m pytest verification/test_p1_browser.py::test_print_refuses_stale_report verification/test_navigation_browser.py::test_report_history_revalidates_exact_result -q --tb=short
6 passed (27.11s).
```

All four new API cases passed in the first completed API command. Its seven errors
were missing `api_client` fixture discovery in Demo tests, with Windows source
paths reported by Linux. Windows/Linux shared bytecode interference was suspected;
using a separate Linux bytecode cache resolved all seven on rerun without changing
fixtures or production code. The API warnings concern existing Starlette TestClient
and FastAPI startup deprecations. The second API command also passed the existing
five-parallel-request test and selected processing admission checks. Browser tests
used local Chrome/FastAPI, disposable SQLite, synthetic data and Mock only.

Pre-fix results are these unchanged-production results; post-fix results are not
applicable because no fix was made. `git diff --check` passed. Final status comparison
preserved every original dirty/untracked status entry and added only the three
task files; nothing was staged and branch/HEAD remained unchanged.

## Remaining boundaries

**AMBIGUOUS / PRODUCT DECISION:** recovery of genuinely abandoned RUNNING work,
automatic polling, automatic retries and force-rerun of unchanged successful inputs
would extend the established contract. No speculative rule was implemented.

**PARTIALLY VERIFIED:** visible content in an already-open idle tab is not pushed
updates when another tab edits inputs. History navigation and print revalidate;
continuous cross-tab synchronization is not implemented. Actual browser reload
during a durable failed/running backend attempt remains untested end to end.

**NOT VERIFIED:** PostgreSQL runtime/locking, real process kill during provider I/O,
live providers, credentials, production deployment, infrastructure, clinical
correctness and the entire repository suite. SQLite concurrency evidence does not
establish PostgreSQL acceptance. No migrations were needed or attempted.

Task files are exactly the two new test files and this handoff. Unrelated tracked
image changes and untracked artifacts were left alone. Nothing was staged,
committed, pushed or deployed; no live or paid provider was used.
