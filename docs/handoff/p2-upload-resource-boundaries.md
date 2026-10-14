# P2 #1 — Upload resource-boundary hardening

Baseline and final branch: `agent/sadeghi-next-phase`.
HEAD: `c194f40de6673292ae3c478b54e6db54daea9f31` (unchanged).
Scope: local synthetic ACCOUNT and Demo uploads; disposable SQLite/storage,
Mock only. No schema, frontend, provider, hosting or deployment changes.

## Existing contract and inspection

- ACCOUNT: `POST /api/cases/{case_public_id}/artifacts`,
  `app/api/routes.py::upload_artifact`. Demo:
  `POST /api/demo/cases/{case_public_id}/artifacts`,
  `app/api/demo.py::upload_artifact`, delegates to the ACCOUNT handler.
- One required `UploadFile` named `file`; optional enumerated `document_role`.
  This is not a batch API. Repeated `file` parts select the last completed part;
  other parts are parsed but ignored by ingestion. This observed framework
  behavior is preserved, not declared a newly approved product policy.
- `app/config.py::Settings.max_upload_bytes`: **26,214,400 bytes / 25 MiB**,
  configurable through `DJ_MAX_UPLOAD_BYTES`. Deployment preflight requires it
  to be positive. `routes.read_upload_bounded` already reads at most limit+1,
  with reads of at most 65,536 bytes. Ingestion rejects `len(data) > limit`.
  Exactly the configured limit is accepted if other validation succeeds.
- `app/core/artifacts/ingestion.py`: PDF, JPEG/JPG, PNG, TXT only; extension
  matching is case-insensitive. Signature/content must match extension. Missing
  or generic `application/octet-stream` MIME is allowed; other declared MIME
  must match detected MIME (parameters stripped). Zero-byte, blank/BOM-only/NUL
  TXT, invalid UTF-8, malformed PDF/image, and encrypted PDF are rejected.
- `app/security/ingestion.py`: original filename is a label (stored up to 500
  characters); sanitized storage filename is at most 180 characters. Keys use
  case/UUID/name, resolved containment, and exclusive creation. Path-like labels
  cannot select an external destination. Same filename/different bytes adds a
  new artifact; same-case/same-content hash returns the existing artifact with
  `duplicate_of`, HTTP 201, without a version bump. No replacement endpoint.
- New evidence increments case version once. Dossier revision, evidence history,
  report/snapshot authority and independent source provenance remain unchanged.
  `app/ai/multimodal.py` enforces existing dossier processing capacities:
  8 PDF pages, 20 million image pixels, 16 derived images, 12 MiB derived bytes,
  100,000 aggregate text characters and 100 sources. Non-dossier uploads do not
  acquire a new dossier or these dossier-specific checks.
- `app/security/case_access.py`: identity/CSRF admission precedes body parsing;
  ownership and ACCOUNT/Demo isolation are checked by dependencies; upload
  capacity is measured while holding the existing case transaction lock.
- Domain failures: sanitized 422 with code/Persian message and independent
  durable `artifact_rejected` audit. Missing/wrong form metadata: framework 422;
  parser failures: 400. Missing identity/CSRF and foreign-case behavior remain
  unchanged. Not every framework error has the domain error envelope.
- Inspected `app/main.py`, `app/db.py`, artifact/audit models, installed parser
  source, Gate 1 README/decisions/roadmap, storage-containment handoff, phase 7.3
  configuration and phase 7.4 ingress limits guidance, plus upload-management,
  ingestion, storage, auth Gate 2, Demo, dossier and prior P0/P1 regressions.
- Starlette defaults: 1 MiB spool rollover (not a file rejection boundary),
  1 MiB non-file part limit, 1,000 files and 1,000 fields. No repository-defined
  aggregate HTTP request byte maximum was found. Phase 7.4 delegates appropriate
  body/time limits to infrastructure without choosing numerical values.

## VERIFIED BROKEN before the fix

1. **Configured per-file limit did not bound pre-handler temporary storage.**
   FastAPI parsed multipart before calling the bounded application reader.
   Starlette checked `max_part_size` only for non-file parts and wrote all file
   bytes to the spool. With the existing configurable limit set to 128 bytes,
   a 4,224-byte file wrote all 4,224 bytes before returning 422. Ignored/repeated
   file parts also spooled their entire contents. Both namespaces reproduced it.
   The 128-byte test override exercises existing configuration; it is not a new
   production size policy. Application `read_upload_bounded` itself was working.
2. **Unfinished multipart spool was not deterministically closed.** A request
   ending inside a file part returned a form without that unfinished file.
   FastAPI closed returned form entries, but that omitted spool stayed open
   after the 422 response. Instrumented tests retain the stream reference to
   distinguish explicit closure from eventual garbage collection. Both
   namespaces reproduced this; permanent artifact files/rows were not created.

## Minimal production changes

- Added `app/security/upload_form.py`. A small subclass of the existing multipart
  parser retains at most the configured file limit plus the existing one-byte
  oversize sentinel for **each** file part, including ignored parts. Remaining
  bytes are consumed without retaining them. Existing ingestion still rejects
  the selected oversized file, with the same ownership/status/audit behavior.
- The helper closes every allocated spool in `finally`, including incomplete
  files omitted from the returned form. Existing parser error messages/statuses
  and generic sanitized parsing failure behavior are preserved.
- Added a three-line hook in `CaseAdmissionRoute` for POST artifact routes only,
  after existing identity/CSRF admission. Other routes are unchanged.
- No new numerical limit, quota, MIME/extension/filename rule or retention policy.
  No ingestion/storage schema, case lifecycle, replacement or processing changes.

## Tests and results at this gate

New tests: `tests/regression_p2/test_upload_resource_boundaries.py`, with fixture
reuse in `tests/regression_p2/conftest.py`. Final focused selection: 54 cases.
They cover configured exact/over boundaries, malformed/empty/unusable inputs,
path-like/long names, duplicate/additive behavior, deterministic rejection,
DB/filesystem preservation, multipart metadata, incomplete/ignored/repeated
parts, CSRF-before-spooling, fragmented input, disconnect cleanup, and disk
rollover with unchanged dossier/report/artifacts after rejection.

Authoritative runtime: Linux Python 3.11.16, FastAPI 0.142.2, Starlette 1.7.0,
python-multipart 0.0.32. Framework versions match runtime pins. Commands used
`PYTHONPYCACHEPREFIX=/tmp/dandoonjan-p2-pycache` to avoid Windows/Linux shared
bytecode interference. Synthetic API tests used approved execution outside the
sandbox after sandboxed TestClient setup stalled (two attempts interrupted;
no completed result from those attempts).

| Execution | Exact result |
| --- | --- |
| Initial Windows exploratory focused run (44 cases), unchanged production | 4 failed, 40 passed, 3 warnings in 24.79s |
| Expanded Windows exploratory run (48 cases), unchanged production | 8 failed, 40 passed, 3 warnings in 26.84s |
| Linux pre-fix focused run (48 cases), unchanged production | **6 failed, 42 passed, 3 warnings in 29.62s** |
| Same Linux focused selection immediately after fix | **48 passed, 3 warnings in 27.38s** |
| Broader relevant regression selection, including 52 focused cases | **211 passed, 3 warnings in 136.76s** |
| ACCOUNT/Demo auth/admission selection | **52 passed, 16 deselected, 3 warnings in 42.93s** |
| Final focused selection, including disk-spool/report preservation | **54 passed, 3 warnings in 38.75s** |

Pre-fix Linux failures: `test_configured_boundary_before_spooling` with
`extra=4096`, `test_repeated_parts_characterization`, and
`test_incomplete_multipart_closes_spool`, each for ACCOUNT and Demo. Exact and
just-over boundary response behavior already passed. Windows additionally failed
both long-filename acceptance cases; Linux passed them without a filename change.
The Windows failure's precise OS/storage cause was not independently established;
portable long-path acceptance is PARTIALLY VERIFIED, not a new policy requirement.
Windows was exploratory and was not rerun after the production fix.

Commands (all with the bytecode prefix above):

```sh
python3 -m pytest tests/regression_p2/test_upload_resource_boundaries.py -q --tb=short
python3 -m pytest tests/regression_p2/test_upload_resource_boundaries.py tests/upload_management tests/test_ingestion.py tests/regression_p0/test_storage.py tests/regression_p0/test_api_state.py tests/regression_p0/test_assessment_freshness.py tests/regression_p0/test_case_text_concurrency.py tests/next_phase/test_dossier.py tests/next_phase/test_demo.py tests/regression_p1/test_intake_validation.py tests/regression_p1/test_processing_retry.py -q --tb=short
python3 -m pytest tests/auth_gate2/test_access.py tests/auth_gate2/test_boundary.py -k 'artifacts or malformed or csrf or isolation or mixed_cookies or denied_work_and_upload_touch or parallel_demo' -q --tb=short
```

The broader selection includes the existing real 25 MiB exact/+1 tests and
capacity/duplicate/concurrent upload tests. All three warnings per run are
existing TestClient/lifespan deprecations. No repository-wide suite was run.
These are executions at this gate, not copied historical pass counts.

## VERIFIED WORKING within tested scope

ACCOUNT/Demo shared validation, exact/default/configured size handling,
limit+1 spool retention, fragmented input, explicit temporary file closure,
filename containment on Linux, content duplicate awareness and additive evidence,
unchanged prior bytes/versions/dossier/report after rejection, durable rejection
audit, ownership/visitor isolation and CSRF-before-body admission. Existing
capacity, history/freshness, concurrent text update, intake PATCH and retry
regressions pass. Rejected validation uploads leave no new permanent artifact
files or artifact rows; intentional audit rows remain. Completed and incomplete
multipart spools close. No claim of global filesystem/DB transactional atomicity.

## AMBIGUOUS / PARTIALLY VERIFIED / NOT VERIFIED

- **AMBIGUOUS / decision boundary:** aggregate HTTP bytes, multipart header/name
  lengths, upload duration, aggregate non-dossier storage, concurrent resource
  budgets and user quotas have no approved numerical boundary here. Extra-file
  rejection versus current last-field selection is also not product-defined.
  No arbitrary values or new batch policy were introduced.
- **PARTIALLY VERIFIED resource protection:** per-file retained bytes are bounded;
  the request is still consumed and parsed. This does not limit transport traffic,
  parsing time, upstream ASGI chunk allocation, headers, or aggregate concurrent
  usage. Existing multipart counts can still admit a large total spool footprint.
  The 1 MiB rollover threshold is not an aggregate memory guarantee.
- **PARTIALLY VERIFIED malformed input:** tested missing boundary/name/filename,
  empty filename, truncation and disconnect. Not an exhaustive multipart fuzzer.
  Framework validation messages can differ from domain messages.
- **PARTIALLY VERIFIED platform support:** Linux long filenames pass; exploratory
  Windows acceptance failures remain documented above.
- **NOT VERIFIED:** hosted ingress/body/time configuration, PostgreSQL execution,
  live providers, real data, disk exhaustion, filesystem write/DB commit failure
  atomicity, and exhaustive decoder CPU/memory adversarial inputs. Storage write
  precedes DB flush/commit; no filesystem rollback guarantee was added. Existing
  prior-artifact reads and dossier derivative preparation are unchanged.
- The parser adapter uses Starlette internals (`_current_part`, allocated spool
  list) and Request's form cache. Pinned versions are tested; framework upgrades
  must retain these regression checks.

Remaining total request/time/quota policy needs owner/operations/infrastructure
approval in a later authorized task. Nothing requiring Mehdi, hosted access,
credentials, clinical approval or paid services was undertaken.

## Task files and repository safety

Exactly five task files:

1. `app/security/case_access.py` (modified)
2. `app/security/upload_form.py` (added)
3. `tests/regression_p2/conftest.py` (added)
4. `tests/regression_p2/test_upload_resource_boundaries.py` (added)
5. `docs/handoff/p2-upload-resource-boundaries.md` (added)

Initial dirty state: three modified landing screenshots; existing untracked
`.tmp-*` trees, archive, UI evidence, `frontend-demo/`, `tools/` and verification
scripts. All **988** constituent pre-existing dirty/untracked file SHA-256 hashes
were checked and preserved. No original status entry was removed or staged.
`git diff --check`: passed. Working tree retains original dirt plus
these five task files. Nothing was staged, committed, pushed or deployed.
