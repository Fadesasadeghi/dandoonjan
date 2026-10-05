# Phase 6 Gate 6.1 — provider reliability and processing admission

Date: 2026-10-05. Owner-authorized offline implementation only.
Baseline branch: `agent/sadeghi-next-phase`.
Baseline and final HEAD: `55cdcf2e0fd7e5e7590da1a5609ee5dd21c66b48`.
No staging, commit, push, merge, deployment, live AI, paid service, patient data,
provider-secret access, or normal developer database access.

## Evidence and scope

VERIFIED OFFLINE: SQLite same-case admission/reconciliation, different-case
overlap, serialized attempt allocation, input mutation invalidation, immutable
history/current-report protection, single HTTP dispatch, safe failure categories,
sanitized dispatch accounting, and ACCOUNT admission. Existing Demo, upload,
report/provenance, auth and selected browser regressions passed.

PARTIALLY VERIFIED: PostgreSQL uses a Case-scoped `FOR UPDATE OF cases` statement,
checked through the PostgreSQL SQL compiler. Private synthetic runtime tests exist
but are NOT VERIFIED because no `RC_POSTGRES_SOCKET` was supplied. No PostgreSQL
installation or server startup was attempted. Live compatibility, real remote
cancellation, clinical accuracy, deployment and actual service billing are NOT
VERIFIED. The review output budget remains 1200 tokens.

## Tests first and confirmed causes

All commands use `.venv/Scripts/python.exe verification/run_phase6_offline.py`.
The launcher sets empty provider-key variables and disabled live dispatch before
imports, changes cwd to a disposable directory, disables dotenv in child
interpreters, and blocks real HTTPX transport in the pytest process. Existing
synthetic fixtures own their databases/storage. Existing migration scripts/config
are copied into the disposable directory for cwd-dependent integrity checks;
no migration revision was added or altered.

Initial focused arguments:

```text
tests/next_phase/test_processing_concurrency.py tests/next_phase/test_provider_replay.py -q --tb=line
```

Before application changes: **25 failed, 5 passed, 1 teardown error, 3 warnings,
35.73s**. Failures demonstrated absent reconciliation, write locks spanning provider
work, failed input-edit requests, immediate timeout/network/429/5xx replay, missing
Retry-After/accounting, lost pipeline categories and collapsed refusal/truncation/
model mismatch. Baseline interrupted-run dispatch reached the intentional provider
tripwire (`pytest.fail`), causing an additional TestClient teardown error. This
teardown artifact is not counted as an independent product defect.

The first launcher attempt also had Windows temporary-directory cleanup trouble
because cwd was still inside it; restoration of cwd fixed that harness issue before
the reported red rerun. No product assertion was removed to obtain green.

Two supplementary baseline probes used a disposable `git archive` of exact HEAD,
overlaid only with the new test/launcher. The test releases incidental SQLite
stage writes at the synthetic provider boundary; this removes the broad writer
lock that can otherwise mask admission defects. Simultaneous admission reproduced
the ProcessingRun identity UNIQUE violation. Contention after first dispatch
reproduced **two classifier dispatches for the same case** (one failed test,
9 deselected, 3 warnings, 3.83s). This is controlled baseline evidence, not a
PostgreSQL runtime claim. Both contention variants pass on the implementation.

## Admission and interrupted-run reconciliation

Ownership and CSRF admission remain in the unchanged Auth Gate 2 dependencies,
before the pipeline is called. The pipeline commits the bounded admission/session
touch, then takes a short database coordination lock:

- SQLite: `UPDATE cases SET id=id WHERE id=:case_id`, reserving the writer without
  altering input/version/timestamps or relying on ignored FOR UPDATE.
- PostgreSQL: lock only the requested Case row with `FOR UPDATE OF cases` under
  the normal READ COMMITTED transaction behavior.

Within that transaction it refreshes inputs, checks all RUNNING pipeline records,
materializes artifact text, resolves eligible exact-identity reuse, or allocates
and commits one NON_AUTHORITATIVE/RUNNING attempt. `max(attempt)+1` now runs under
this admission lock. Module attempts belong to that single pipeline execution.

The lock is released before provider execution. ModelRun and module RUNNING audit
records are committed before provider calls, so SQLite writes do not serialize
different cases across provider work. Caught model/module failures are durable;
unfinished candidate writes are rolled back and pipeline-derived rows are marked
NON_AUTHORITATIVE.

An unresolved same-case request returns HTTP 200 with existing response keys:

```json
{
  "case_public_id": "<owned case>",
  "status": "PROCESSING",
  "pipeline_run_id": "<existing unresolved run>",
  "reused": false,
  "snapshot": null,
  "report": null,
  "report_kind": null
}
```

PROCESSING here means durable unresolved processing, not proof a worker remains
alive. No new provider is constructed or dispatched. No older report is returned.
A RUNNING claim is non-authoritative regardless of its age or current input hash.
It is not deleted, promoted or automatically reclaimed. Reconciliation survives
a separate interpreter restart with provider construction forbidden. Completed
current authoritative results still reuse with zero additional dispatch.

Without leases/heartbeats/worker identity, automatic safe liveness recovery is
not possible. An interrupted RUNNING claim can therefore block the case indefinitely,
including after an input edit. This is the intentionally conservative no-migration
subset, not a recovery mechanism or a claim of provider cancellation.

## Input consistency and authority

The admitted ProcessingRun freezes the effective input hash/version. Artifact
role and detected MIME now participate alongside identity/hash/text. Pipeline and
provider contract versions advance to `pipeline-v4` and `real-provider-v4`, so
old stored identities are not silently reused; no historical hash is rewritten.

Fresh independent read transactions check identity before and after provider work
including after bundle preparation, and before report creation. Review intake
provenance binds to the dossier revision
used to prepare input. Changes produce `PROCESSING_INPUT_CHANGED`, a failed,
non-authoritative attempt and no current report.

The final input check runs under the database coordination lock. Snapshot/report
persistence and authority activation now share their final commit rather than
committing a report-ready result before activation. An edit arriving at the
snapshot boundary cannot activate the obsolete result. Edits committed after
activation change case identity/version and remain subject to existing report
retrieval checks. Prior snapshots and successful history remain immutable.

Edits/uploads are not newly prohibited. Obsolete work may already have transmitted
old synthetic input before detection; checks invalidate it, not erase transmission.
There is no new copy/retention model or server cancellation behavior.

## Provider replay and failure mapping

One logical provider invocation permits **at most one adapter HTTP dispatch**.
No connection/timeout/5xx replay is attempted: HTTPX errors are not treated as
proof that the remote application received nothing. No provider/model substitution
or Mock fallback was added. Owned clients retain `trust_env=False`, no redirects,
existing payload/response bounds, deadlines and strict completion validation.

Retry-After delta seconds and HTTP dates become bounded integer advisory metadata
(0–86400 seconds); invalid/oversized headers become None. Only safe category/delay
scalars cross the transport worker boundary. There is no automatic sleep or retry,
and no raw header, exception traceback or body is retained in that boundary.

| Detectable cause | Safe classification |
| --- | --- |
| Invalid/disabled configuration | REAL_PROVIDER_CONFIGURATION |
| 401/403 | REAL_PROVIDER_AUTHENTICATION |
| 429 | REAL_PROVIDER_RATE_LIMIT |
| Caller/HTTP timeout | REAL_PROVIDER_TIMEOUT; remote outcome may be ambiguous |
| Transport errors or 5xx | REAL_PROVIDER_AMBIGUOUS_REMOTE_OUTCOME |
| 400/404/405/413/415/422 | REAL_PROVIDER_INCOMPATIBLE_REQUEST |
| Other provider rejection/local transport capacity | REAL_PROVIDER_PROVIDER |
| Bad envelope | REAL_PROVIDER_MALFORMED_ENVELOPE |
| Invalid content JSON/object | REAL_PROVIDER_SCHEMA |
| Local Pydantic failure | SCHEMA_VALIDATION_FAILED |
| Refusal/content_filter | REAL_PROVIDER_REFUSAL |
| length | REAL_PROVIDER_TRUNCATION |
| cancelled | REAL_PROVIDER_CANCELLED |
| Returned model mismatch | REAL_PROVIDER_MODEL_MISMATCH |
| Invalid sources/unsafe candidates | REAL_PROVIDER_REFERENCE / REAL_PROVIDER_SAFETY |

Gateway/review wrappers preserve safe cause codes internally and the existing
processing `error_code` carries them. No public field or endpoint was added;
caught processing failure remains HTTP 200 with FAILED/null report. Raw provider
error bodies/messages/URLs/prompts are never exposed. Existing generic Persian
failure UI is unchanged; cause-specific messages/cooldowns belong to Gate 6.4.

Explicit resubmission after a durably FAILED local attempt remains possible under
existing retry behavior. It is a new requested execution, not an automatic adapter
replay, and does not establish the previous remote request was cancelled. Retry-After
is internal advisory metadata; a cross-request/deployment cooldown is not enforced.
Browser network ambiguity wording/polling remains deferred. While a claim is
RUNNING, server reconciliation prevents the resubmission from dispatching again.

## Dispatch accounting

Each OpenRouter adapter has an in-memory DispatchAccounting object; trusted
verification code can supply one shared object across adapter instances. Events
contain exactly `event`, `provider`, `model`, `kind`, `image_bearing`.
`event` distinguishes logical invocation from adapter HTTP dispatch. Kinds are
the allowlisted classification/extraction/claim/review prompt identities.

The recorder never receives headers, text, images, case/account/session IDs,
raw prompts/responses or URLs. No accounting is logged, persisted or exposed
through the API. Offline end-to-end tests assert exact classification/review
counts, image-part presence and zero further events on authoritative reuse.
An HTTP dispatch event proves the adapter invoked its transport, not remote
receipt/interpretation or absence of retries inside an externally supplied client.

## Verification ledger

Results below are executions at this gate, not historical Auth/Phase 5 counts.

| Execution | Result |
| --- | --- |
| Corrected-launcher tests-first red | 25 failed, 5 passed, 1 teardown error, 3 warnings; 35.73s |
| First implementation focused | 1 failed, 29 passed; missing-model envelope classification corrected |
| Corrected initial focused | 30 passed, 3 warnings; 6.88s |
| First relevant regression selection | 446 passed, 2 harness-path failures, 3 warnings; 132.06s |
| Expanded focused plus affected migration/provenance tests | 55 passed, 3 warnings; 57.41s |
| Relevant selection after launcher correction | 452 passed, 3 warnings; 156.62s |
| Expanded focused with both contention variants | 35 passed, 3 warnings; 10.86s |
| Full backend `tests -q --tb=line -ra` | 606 passed, 3 skipped, 3 warnings; 230.14s |
| Auth Gate 3 + Demo + navigation browser suites | 71 passed; 136.53s |
| Focused plus PostgreSQL compiler/opt-in checks | 36 passed, 4 skipped, 3 warnings; 11.04s |
| Final audit-state/provider/pipeline/report regression selection | 314 passed, 4 skipped, 3 warnings; 73.70s |
| Full backend after audit-state corrections, before final preparation guard | 608 passed, 7 skipped, 3 warnings; 217.96s |
| Final affected regression selection including preparation guard | 315 passed, 4 skipped, 3 warnings; 77.89s |
| Final focused concurrency/replay/PostgreSQL-boundary suites | 38 passed, 4 skipped, 3 warnings; 12.36s |

Relevant selection arguments:

```text
tests/next_phase tests/regression_p1/test_production_provider.py
tests/regression_rc/test_provider_privacy.py tests/regression_p0/test_api_state.py
tests/regression_p0/test_derivation.py tests/upload_management tests/auth_gate2
tests/test_invariants.py tests/test_p0_provenance.py tests/test_pipeline.py
tests/test_p0_orchestration.py tests/test_p01_reconciliation.py -q --tb=line -ra
```

Browser arguments:

```text
verification/test_auth_gate3_browser.py verification/test_demo_browser.py
verification/test_navigation_browser.py -q --tb=line -ra
```

Full backend skips: one private PostgreSQL socket not supplied; two existing Windows
directory-symlink privilege limitations. Warnings are the three existing
FastAPI/Starlette deprecations. No skip/threshold/auth/provenance/safety assertion
was weakened. Existing tests that required two automatic provider attempts now
require exactly one; budget tests assert the more precise completion failure codes.

The later full backend run also includes four added PostgreSQL admission tests,
all skipped without a private socket (seven skips in total). The final two-line
preparation guard and its new test were verified by the final affected selection;
the 608 full-suite count and 71 browser count are earlier gate checkpoints, not
executions repeated after that last guard. No frontend file or public response
shape changed in the final correction.

The subsequent PostgreSQL SQL/compiler and private-runtime test additions are
verified separately in the final focused command, not included in the 606 count:

```text
tests/next_phase/test_processing_concurrency.py tests/next_phase/test_provider_replay.py
tests/next_phase/test_processing_postgres.py -q --tb=line -ra
```

Final review added two stronger audit-state assertions. Each reproduced one failure
before correction: snapshot-stage RUNNING after a late input rejection (1.68s),
and ModelRun RUNNING after a semantic-stage rollback (1.28s). Authority/report
exposure checks already passed; these additional defects affected audit truthfulness.
Activation now stays inside the snapshot stage's failure boundary. A request-local
set of model-run IDs lets rollback close only that stage's own unresolved records,
without retaining rejected candidate output or touching another case's records.
An explicit mixed-file retest had 118 passes/4 skips and six fixture setup errors
(`api_client` discovery in the existing E2E module); directory-based collection is
used for the final regression check. No fixture/assertion was weakened.

Final affected regression arguments (after the two audit-state corrections):

```text
tests/next_phase tests/test_pipeline.py tests/test_p0_orchestration.py
tests/test_p01_reconciliation.py tests/regression_p0/test_api_state.py
tests/regression_p0/test_derivation.py tests/test_invariants.py
tests/test_p0_provenance.py -q --tb=line -ra
```

A further input-race regression reproduced one unnecessary review dispatch after
an edit committed during bundle preparation (1 failed, 26 deselected, 3 warnings;
1.48s). An additional identity check after preparation now rejects that obsolete
bundle before provider invocation, while retaining the existing post-call check.

## Files and rollback boundary

Modified: `app/ai/{gateway,preflight,providers,review}.py`, `app/errors.py`,
`app/pipeline/{orchestrator,runs}.py`, `app/safe_logging.py`, and
`tests/next_phase/{test_preflight,test_review_budget,test_review_flow}.py`.
Added: `app/ai/dispatch.py`, three focused processing/provider test modules,
`verification/run_phase6_offline.py`, and this handoff.

No frontend, auth implementation, routes, domain models, migration, dependency,
knowledge-pack, clinical ontology, visual/export or environment file changed.
No new schema/API migration is necessary for this limited gate. Reverting the
gate's source changes is independent of historical data: no snapshot/result/hash
was rewritten and no cleanup is required. Rolling back admission loses its
protections; unresolved persisted RUNNING claims must not be arbitrarily promoted
or deleted as a rollback shortcut.

## Repository integrity and next decisions

Initial/final staged diff is empty. PR #5 read-only verification: OPEN, unmerged,
head equals baseline. No PR #4/#5 mutation occurred. All 878 pre-existing
dirty/untracked owner files match their pre-implementation SHA-256 records;
aggregate fingerprint `2da3bd4a9b606854eca803d1ecc1faafbabd22049e88443f67809dc80095fd87`.
The three unrelated screenshot modifications remain unrelated and untouched.
Final `git diff --check` and new-file syntax/whitespace checks pass. The index
remains empty, branch/HEAD match baseline, and only the gate files plus pre-existing
owner material appear in status. No commit was created.

No Gate 6.1 owner Stop Condition was required. Future automatic interrupted-run
recovery may need approved leases/schema design; cause-specific public retry UX,
provider/model changes, live acceptance, paid usage, patient data and deployment
still require their respective owner approvals. Gate 6.2 Persian/output hardening
and Gate 6.4 operational UX are not claimed implemented here.
