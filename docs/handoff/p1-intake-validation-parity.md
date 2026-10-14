# P1 intake validation parity investigation

Baseline: `agent/sadeghi-next-phase`, HEAD `7e2855f`. Work is uncommitted.
Scope: offline synthetic HTTP requests, temporary SQLite, Python 3.11.16,
FastAPI 0.142.2; Mock processing only. No frontend or migration changes.

## Boundaries inspected

| Boundary | Existing behavior and evidence |
| --- | --- |
| POST `/api/cases`, `/api/demo/cases` | FastAPI form strings; question required, recommendation defaults to empty. ACCOUNT context defaults to empty. Demo supplies the server marker instead. Both call `routes.create_owned_case`. |
| PATCH in both namespaces | Optional form strings; omission means unchanged. Demo delegates to the ACCOUNT handler with context forced to `None`. Exact stored-value comparisons determine changes after the existing case lock/refresh. |
| Domain/service | Creation writes text directly and transitions CREATED to INTAKE_COMPLETE. The state machine validates status transitions, not text content. No case-text trimming or min/max length rule was found. PATCH increments version once for a material change and records an audit event. |
| Dossier PUT in both namespaces | Shared `DossierPatch` schema: eight optional string/null fields, unknown keys forbidden, maximum 10,000 characters before trimming. `dossier.update` strips submitted non-null values, ignores omission/null, and preserves revisions. This is a separate structured contract, not another spelling of question/recommendation. |
| Persistence | Case text columns are non-null SQL Text columns with empty ORM defaults; no text length/nonblank check. Inspected ORM and initial migration, without modifying either. |
| Admission | Existing route admission checks identity/CSRF before parsing; dependencies enforce ownership and mode isolation. No changes. |
| Browser boundary (read only) | `frontend/app.js:createOrUpdate` trims question/recommendation and sends both fields on create and edit, including explicit empty recommendation on clearing. Backend does not otherwise share that normalization. |

Contract evidence: Gate 1 decisions require case editing/versioning; the approved
`docs/next-phase/CONTRACT.md` allows incomplete intake and requires changes to
invalidate current reports while retaining history. Optional recommendation is
also documented in `docs/handoff/pilot-rc/README.md`. Existing API defaults allow
empty recommendation/context at creation. Existing dossier, Demo, case concurrency,
freshness and admission tests were inspected before implementation.

## VERIFIED BROKEN before the fix

1. **Recommendation clearing, ACCOUNT and Demo:** create with empty recommendation
   succeeds and stores empty. Populate it, then PATCH an explicit empty string:
   HTTP 200 reports `changed: false`, version remains 2 instead of 3, and the
   handler treats the field as omitted. Both URL-encoded and multipart forms fail.
2. **ACCOUNT context clearing:** the same create/edit mismatch, in both encodings.
   Demo context is intentionally server-owned and is not a parity defect.

Root cause: FastAPI's form extraction replaces an empty string with the declared
default. POST uses `Form("")`; PATCH used `Form(None)`, so the handler could not
distinguish a clear operation from omission. No field comparison, version change,
or freshness invalidation happened for that operation.

Tests were added and run before production edits:

```text
python3 -m pytest tests/regression_p1/test_intake_validation.py -q --tb=short
Initial: 6 failed, 32 passed.
Expanded before production edits: 8 failed, 40 passed.
```

The extra two failures exercised the same recommendation clear on already
assessed ACCOUNT/Demo cases: version stayed 3 instead of becoming 4. Those tests
also require current assessment/report invalidation and preservation of historical
records after the fix. The pre-fix assertions stopped at the version mismatch;
they did not reach the later freshness assertions.

## Fix and verification

Two small request dependencies retain FastAPI string validation and inspect the
cached form only to recover an explicit empty recommendation or ACCOUNT context.
The existing locked mutation handler receives `""` for a clear and `None` for
omission. Demo shares the recommendation dependency and still ignores client
context. No normalization, length limit, requiredness, response shape, or database
rule was introduced. The generated OpenAPI document matches the pre-edit document
exactly (comparison captured outside the repository under `/tmp`).

The first post-fix focused run passed 48 tests. A subsequent schema check caught
an intermediate dependency-factory naming collision in generated OpenAPI; explicit
named dependencies removed it. One redundant ACCOUNT test case that returned
without testing Demo context was removed, leaving 47 focused cases.

Final runs on the final production code:

```text
python3 -m pytest tests/regression_p1/test_intake_validation.py tests/next_phase/test_dossier.py tests/regression_p0/test_case_text_concurrency.py tests/regression_p0/test_assessment_freshness.py::test_only_current_assessments_are_returned -q --tb=short
82 passed, 3 warnings (47 new focused cases; 35 existing cases).

python3 -m pytest tests/auth_gate2/test_access.py -k PATCH -q --tb=short
7 passed, 45 deselected, 3 warnings.
```

**VERIFIED WORKING — 89 selected tests:** empty optional text now persists on PATCH,
increments version once, repeated empty recommendation is a no-op, omission leaves
values alone, and valid nonempty text keeps its existing behavior. Current results
become unavailable after recommendation clearing; historical assessment/snapshot/
run/report rows and uploaded artifacts are retained. Existing concurrent edits,
dossier revisions, freshness, ownership, mode isolation and CSRF checks pass.
Both commands reported the same existing Starlette TestClient and FastAPI startup
deprecations. Prior full-suite handoff counts are historical and are not claimed
as testing at this gate. `git diff --check` passed; final status review shows only
the four task files added/modified beyond the pre-existing dirty/untracked files.

## Remaining policy questions and limits

- **PARTIALLY VERIFIED:** missing/empty question produces 422 at creation and is a
  no-op on PATCH; whitespace-only and one-character questions are accepted and
  persisted unchanged. Tests characterize this behavior rather than declare a
  new policy. The contract does not settle whether clearing a question should be
  rejected or supported for incomplete intake. Changing that needs a product decision.
- No supported backend question/recommendation minimum or maximum was found.
  The tests cover 1 and 10,001 characters, surrounding whitespace and Persian text;
  they do not establish unlimited HTTP payload support. Enforcing trimming or new
  limits requires a product decision. Browser trimming alone does not establish
  a universal API normalization contract.
- **VERIFIED WORKING in tested scope:** dossier trimming, omission/null vs clear,
  10,000/10,001 length boundary, rejection of numeric/list/unknown fields, and
  ACCOUNT/Demo parity. Multipart files supplied as text fields are rejected;
  Demo's ignored creation context remains the documented intentional exception.
- **NOT VERIFIED:** PostgreSQL runtime, browser execution, live providers,
  deployment, clinical behavior and the full repository suite. None were run.
- Initial sandboxed pytest attempts stalled during TestClient setup and were
  interrupted; they are not counted as test results. Completed runs used approved
  execution outside that sandbox with the same offline synthetic fixtures.

Changed files for this task only: `app/api/routes.py`, `app/api/demo.py`,
`tests/regression_p1/test_intake_validation.py`, and this handoff.
Pre-existing modified images and unrelated untracked artifacts were left alone.
No commit or push was performed.
