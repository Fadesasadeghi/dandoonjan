# Gate 6.3 — preflight only

2026-10-05. No live AI/provider request was executed. This document and the
standalone verification runner prepare one future owner-authorized attempt.
Baseline: `agent/sadeghi-next-phase`,
`7670771f96adcc07d5be254b9e2fc4acc6f11721`. Gates 6.1/6.2 are closed.
PR #5 read-only check: OPEN, unmerged, same head, base `agent/sadeghi-pilot-rc`.

## Configuration and credential handling

Source allowlist: OpenRouter, exactly `qwen/qwen3.8-27b:free`, environment
`local-synthetic`, explicit local-synthetic opt-in. Review output remains 1200
tokens; each legacy text request remains at the existing 2000-token maximum.
No paid routing, provider/model substitution, Mock fallback or replay is added.
Source defaults are Mock/live-disabled; only the disposable future instance opts
into the existing approved real-provider path. No environment file is edited.

The backend Settings prefix is `DJ_`; the key is `DJ_OPENROUTER_API_KEY` through
the backend process environment, otherwise the existing `.env` Settings loader.
A configuration-only boolean check returned **key present: true**. No key value,
prefix, suffix, length, representation, validity or remote authorization was
inspected/displayed. Do not paste a key or put it on a command line. Presence does
not prove validity. The live-only runner loads the configured key without printing
it; the offline runner uses a dummy credential and disables dotenv before loading
application settings. App/DB imports occur only after disposable DB/storage flags.

## Exact synthetic case

One normal authenticated ACCOUNT in a new disposable SQLite database/storage.
The fixture uses synthetic credentials internally; account/session IDs never enter
published results. This is not a Demo case and not an admission bypass.

Question:
`این پرونده آزمون نرم‌افزار است؛ منابع ساختگی و محدودیت آن‌ها را توضیح دهید.`

Dossier:

- symptoms: `حساسیت فرضی به سرما برای آزمون نرم‌افزار؛ این شرح حال متعلق به بیمار واقعی نیست.`
- duration: `سه روز — کاملاً ساختگی`
- remaining optional history/recommendation fields: absent, represented as missing.

Artifacts reuse `app.core.cases.sample`:

- `image_pattern()`: 512×384 PNG with bars and visible text
  `SYNTHETIC TRANSPORT PATTERN - NOT A RADIOGRAPH`, role `dental_image`.
  Canonical pixels are explicitly NON_CLINICAL. No realistic radiograph.
- `plan_pdf()`: one synthetic text page, role `treatment_plan`, containing exactly
  `SYNTHETIC Treatment Plan`, `Tooth 46: RCT recommended`, and
  `For software testing only; not clinical evidence.` It represents an invented
  proposal for extraction/traceability testing, never actual treatment necessity.

Actual bounded text reaches classification/extraction (PDF text, <=20k) and review
(Persian dossier). Actual PNG and rendered PDF-page JPEG parts reach review. No
separate TXT artifact is needed for this minimal case. TXT truncation/large-source
limits remain the Gate 6.2 offline evidence; this live case does not test truncation.

## Dispatch budget and commands

The planned successful path is exactly **five logical calls / five HTTP attempts**:
two `artifact_classifier`, one `treatment_plan_extractor`, one `claim_builder`, one
`review`. This is the minimum path for these existing PNG/PDF fixtures with the
PDF's explicit atomic treatment proposal and unchanged orchestrator. A PNG-only
two-call test would omit PDF/text extraction and document provenance coverage.

Provider output can select a different legal stage path (for example empty
extraction). Therefore five is the exact PASS-path plan, not a guarantee that a
failed run reaches five calls. The guard stops on unexpected stage ordering or a
sixth call; it never forces/fabricates extraction or silently expands the budget.
Failures stop with 0–5 attempts. No automatic retry, model change or paid escalation.

From repository root, offline readiness command (executed):

```text
.venv/Scripts/python.exe -B verification/gate63_synthetic_acceptance.py
```

Future live command — **NOT EXECUTED; separate owner authorization required**:

```text
.venv/Scripts/python.exe -B verification/gate63_synthetic_acceptance.py --live --owner-authorized
```

Use a fresh one-shot process, never import this runner into the normal app/server.
No key is an argument. The command uses a temporary SQLite DB and artifact store,
normal ACCOUNT registration/ownership/processing admission, existing provider
adapter and validation, and no live local web server. The runner clears its live
flag/key references on completion and exits. Temporary resources are disposed.
Caller timeout cannot guarantee remote cancellation; no retry is permitted after
an ambiguous outcome. Published evidence must not copy the disposable database.

## Acceptance categories

PASS (live only): all five expected calls succeed with the exact model; actual
review payload has two JPEG image parts, one mapped PDF page and bounded text;
existing Persian/completeness/safety/reference validators succeed; both audience
sections and limitations equal frozen ReviewRun/snapshot content; snapshot integrity
and case-local artifact/page mapping hold; nonclinical limitation exists; a repeated
process request reuses that snapshot with **zero** additional dispatches. No
definitive diagnosis/treatment authority is granted. Existing validation is defense
in depth, not proof of clinical correctness or exhaustive language semantics.

FAIL: configuration/authentication, unsupported request/model, malformed/truncated/
refused/schema/Persian/safety/reference failure, report/snapshot/authority mismatch,
plan deviation, replay, unexpected routing, leakage or harness assertion failure.
No result may be repaired, translated, substituted with Mock or promoted afterward.

RATE_LIMITED: 429/internal rate-limit category; stop immediately without sleep/retry.
INCONCLUSIVE: timeout/ambiguous transport/provider availability outcome; do not
infer remote cancellation or safe replay. These are not PASS or clinical findings.
Unavailable model/unsupported multimodal capability requires owner review before
any model change; no capability discovery request is part of this preflight.

## Safe evidence and cost

The runner prints only result/category, provider/model, budget, sanitized logical/
HTTP counts, plan-deviation boolean, visual-part/page counts and bounded-text
boolean. Existing accounting never receives request content. Provider input is
inspected transiently only to verify representation; no new raw payload/response,
Authorization/header, prompt, evidence, data URI, case/account/session ID or key
is persisted/logged/exported. Existing structured records exist only in the
disposable database. Both report sections are checked in memory.

Cost category is **free-intended** from the exact `:free` identifier and strict
allowlist only. No pricing/model discovery or billing request occurred. Service
availability, actual provider image support and actual billing are NOT VERIFIED;
this runner does not impose a provider-account monetary ceiling. Any paid-routing
requirement is a stop condition, not permission to continue.

## Offline evidence at this preflight

- Successful runner: `OFFLINE_PASS`, five logical calls/five injected dispatches,
  two visual parts/one PDF page, bounded text true; ordinary reuse adds zero calls.
- `--offline-failure rate_limit`: RATE_LIMITED, exact internal rate-limit code,
  one dispatch, no replay (expected nonzero exit).
- `--offline-failure authentication`: FAIL, exact internal authentication code,
  one dispatch, no replay (expected nonzero exit).
- Existing focused source-contract suites:
  `test_local_synthetic_free.py`, `test_gate62_transport.py`,
  `test_review_budget.py`, `test_provider_replay.py` through
  `verification/run_phase6_offline.py`: **99 passed, 3 existing warnings (7.54s)**.
  All real HTTPX transport was prohibited. No app/validation tests were weakened.

Only this preflight document and `verification/gate63_synthetic_acceptance.py`
were added. No application/API/schema/migration/environment or existing fixture
file changed. The 878 pre-existing unrelated owner files match their fingerprints;
staging remains empty and branch/HEAD remain baseline. No stage/commit/push/merge,
deployment, patient data, paid service or developer DB use occurred.

Owner decision outstanding: authorize one execution of the exact five-call plan
and command above. Preflight readiness itself is not that authorization. Stop here.

## One owner-authorized live execution — 2026-10-05

The owner subsequently explicitly authorized ONE execution of the exact live
command above. It was executed once and exited nonzero. Sanitized result:

```json
{"result":"FAIL","failure_code":"REAL_PROVIDER_AUTHENTICATION","logical_calls":1,"http_dispatches":1,"provider":"openrouter","model":"qwen/qwen3.8-27b:free","review_budget":1200,"plan_deviation":false,"visual_parts":0,"pdf_pages":0,"bounded_text":false}
```

The first classification dispatch failed with the adapter's authentication category
(its 401/403 mapping; the summary does not distinguish those statuses). This does
not establish why authentication was rejected. No credential inspection, repair,
capability discovery, retry, model change, paid fallback or Mock substitution was
performed. The one-execution authorization has been consumed.

Multimodal review was not reached. No successful acceptance, authoritative final
report/snapshot, or live zero-dispatch report reuse was verified. Zero visual parts
here means no review transport evidence, not failure of the offline image contract.
The runner used only disposable synthetic resources and cleared live/key settings
on exit; no raw provider content, key, Authorization, prompt, evidence, case/account/
session identifier or unnecessary payload was recorded in this handoff.

Outcome: **LIVE ACCEPTANCE DID NOT PASS — OWNER REVIEW REQUIRED**. Any future live
attempt requires a new explicit authorization; none is planned automatically.
Branch/HEAD remain baseline and staging is empty. Existing owner-file fingerprints
remain unchanged. Only this sanitized handoff entry was changed after execution.
