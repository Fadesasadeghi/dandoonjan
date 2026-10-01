# Real multimodal preflight — offline gate

## 2026-10-01 — two synthetic live attempts and offline budget remediation

The operator reports two distinct live attempts with the same fixed model,
`qwen/qwen3.8-27b:free`, and the same small synthetic text-only bundle. No real
patient data was used in either attempt:

1. **First attempt:** accepted by the provider and generated tokens, then
   cancelled/timed out before a successful complete response, as detailed below.
2. **Post-remediation retry:** the one separately authorized LOCAL SYNTHETIC live
   retry was performed and failed with `rate_limit` before successful completion.
   The exact operator-supplied result is:

   ```text
   LIVE PROVIDER FAILED
   error_type: ProviderUnavailableError
   category: rate_limit
   ```

The 1200-token remediation remains **VERIFIED OFFLINE but NOT VERIFIED LIVE**
because the retry was rate-limited. This result does not establish that the
remediation solved the timeout. No successful live completion or validated report
is established by either attempt. The retry evidence is operator-supplied, not
an execution or independent provider-log inspection performed during this update.

The operator supplied the following evidence from the separately authorized LOCAL
SYNTHETIC live-provider test. These are operator observations, not a new execution
or independently retrieved provider logs:

| Observation | Exact supplied evidence |
| --- | --- |
| Fixed model | `qwen/qwen3.8-27b:free` |
| Cost | $0.00 |
| Data policy shown by OpenRouter | No data training |
| Input | 957 tokens |
| Generated before cancellation | 1,785 tokens |
| Throughput | 45.3 tok/s |
| Generation time | 39.4s |
| OpenRouter finish reason | `cancelled` |
| Provider response | ModelRun 499 |
| DANDOONJAN result | `ProviderUnavailableError category=timeout` |
| Data | No real patient data was used |

**Final live response: NOT VERIFIED because the request was cancelled.** No accepted
complete JSON, schema-valid review, resolved provenance, or successful live report
is established. The displayed policy/cost are evidence for that attempt only.

Root cause analysis (PARTIALLY VERIFIED): the old review request allowed 6,000
generated tokens, approximately 132.5 seconds at the observed rate, despite a
45-second caller deadline. Small input does not bound output. The schema permits
six patient assertions, twenty professional assertions, eight nested hypotheses,
twenty safety flags, twenty limitations and one hundred source entries; those are
maxima, not required counts. The old prompt did not discourage filling these limits
or repeating evidence. Generation alone consumed 39.4s before cancellation; queueing,
prefill, network and response delivery also consume the deadline. Their individual
durations and the reasoning/final-output token split were not supplied. Therefore
reasoning overhead is a plausible contributor, not a verified model-specific cause.

The 45-second contract bounds each `_request` caller (including up to two attempts),
not an entire pipeline or guaranteed remote cancellation. The default HTTP operation
timeout is 30 seconds, bounded further by remaining caller time. Late worker results
are discarded; transport cleanup can outlast the caller. ModelRun 499/cancelled does
not establish the precise local timeout/cancellation sequence.

Offline inspection found only `max_tokens`, temperature and JSON-object formatting
in the existing request contract. There is no local capability record proving this
exact model/provider supports disabling or budgeting reasoning. No web/model discovery
was performed. No speculative `reasoning`, `enable_thinking`, or alternative token
parameter was added; hiding reasoning would not itself prove reduced computation.
Provider enforcement of the existing token parameter remains NOT VERIFIED live.

Narrow changes: review `max_tokens` is now 1,200 (legacy remains 2,000); schema display
titles and JSON whitespace are removed from the review prompt/data serialization.
All schema validation keywords, required fields, source data and image parts remain.
The prompt asks for short, nonrepetitive assertions, treats array limits as ceilings,
and explicitly forbids omitting safety concerns or source references to save space.
`REVIEW_PROMPT_VERSION` is now `review-instructions-v3`, invalidating old review reuse.
No ReviewOutput schema, validator, fixed-model equality, privacy authorization,
deterministic safety, deadline, retry or fail-closed rule changed.

At the observed rate, 1,200 tokens correspond to approximately 26.5 seconds of
generation. This is a conservative trial budget, not a measured completion requirement
or latency guarantee. Large source inventories or reasoning may exhaust it. A `length`
or `cancelled` completion is rejected even if its content is valid JSON; no truncation
repair, field deletion, source dropping or automatic budget escalation is allowed.

Prior offline remediation verification: the new regression first produced **1 failed, 2 passed**
(6,000-token budget reproduced). Focused offline suite: **219 passed, 3 warnings**.
Full offline suite: **382 passed, 7 skipped, 3 warnings in 60.50s**. Skips were two
Windows symlink privilege checks and five PostgreSQL checks without a private cluster.
Warnings were existing FastAPI/Starlette deprecations. Commands run with the existing
Windows virtual environment (sandbox WSL bridge failed, then approved execution):

```text
.venv/Scripts/python.exe -m pytest tests/next_phase/test_review_budget.py -q
.venv/Scripts/python.exe -m pytest tests/next_phase tests/regression_p1/test_production_provider.py tests/regression_rc/test_provider_privacy.py -q
.venv/Scripts/python.exe -m pytest tests verification/test_rc_postgres.py -q -ra
```

The first command is the pre-fix reproduction; the latter two include the post-fix
regressions, deadline tests, validation/provenance/safety tests and lifecycle tests.
`git diff --check` passed. No supplemental browser or process-runtime suite was rerun.
Tests use owned injected
HTTP transport and synthetic credentials; test setup clears provider credentials and
disables live authorization. Existing historical evidence files below are unchanged.

The separately authorized single retry has now been performed by the operator,
with the rate-limit failure recorded above. Stop after this documentation update;
no further live request is authorized. Do not access/read/print/log the API key,
change models, use paid services, increase the deadline, weaken fail-closed behavior,
deploy, modify PR #4/#5, or commit. This update changes documentation only; prior
offline test results above are historical and pytest is not rerun for this update.
Live completion, reasoning controls, token-cap enforcement, output adequacy for larger
bundles, clinical correctness, PostgreSQL runtime, deployment and OpenRouter process
restart remain NOT VERIFIED. No key was accessed/read/printed/logged; no live request,
paid service, commit, push, deploy, or PR #4/#5 modification was performed in this task.
Existing unrelated working-tree changes are preserved.
No commit was created. Current HEAD is `c6a1cea3ba7652a1b74f09515d21ba5af3d3e90f`;
the working tree remains dirty with this remediation and pre-existing local changes.

## Historical offline gate (2026-09-30)

Date: 2026-09-30. Backend-only, pending manual review. Base/HEAD remains
`eb837e1f0dcda3d1d0c88b951726123e148f51ce` (approved Gate 1 Landing).
No staging, commit, push, PR modification, deployment, dependency installation,
provider discovery, real credentials, real patient data, or external AI calls.
`DJ_LIVE_PROVIDER_ENABLED` remains false. Existing ZIP/WebP/tools artwork is excluded.
Older acceptance documents and evidence are historical and unchanged.

## Implementation and tested scope

Explicit `mock` remains deterministic in development/test. Production retains its
existing prohibition on Mock. Explicit `openrouter` never substitutes Mock in any
environment. Unknown providers fail configuration. `strict_real` remains accepted
for caller compatibility; fail-closed behavior no longer depends on that flag.

The real adapter has local configuration validation, one bounded HTTP path for
legacy text and multimodal review, strict completion-envelope checks, no fenced-JSON
repair, and authoritative local schema/reference/safety validation. Financial and
claim prompts receive complete schemas; untrusted text is a separate user message
and is not rendered recursively into instructions. Review instructions are versioned.

Review source aliases are fresh random `src_` + 32 hexadecimal characters for every
request. Only the request's mapping can resolve them. Validation precedes resolution;
unknown, old-request, cross-case and cross-revision aliases fail. Local source IDs,
original/derivative hashes and artifact relationships remain authoritative locally.

Successful review output supplies both patient and professional sections of the same
immutable snapshot. Failed reviews retain no output/source index. Content-free failure
codes distinguish configuration, authentication, timeout, rate limit, provider/server,
malformed envelope, schema, reference and safety failures. Unexpected internal review
failures remain `REVIEW_FAILED`; Pydantic schema failures use `SCHEMA_VALIDATION_FAILED`.
Configuration failures before review create a failed review audit for dossier cases,
using `unconfigured` metadata rather than persisting rejected configuration values.

Processing identity includes review schema, review prompt, derivative, provider-contract
and legacy prompt versions. Meaningful changes invalidate reuse. Report retrieval
requires the latest processing attempt itself to have succeeded under the current
processing identity. RUNNING and FAILED attempts hide older results; prior snapshots
remain stored as history. Recovery after failure requires a fresh successful attempt.
No schema migration or architecture change was required.

## Exact outbound inventory

The adapter emits only the following application fields. HTTP libraries additionally
supply protocol headers such as Host and Content-Length.

| Layer | Fields / values |
| --- | --- |
| HTTP | POST to the fixed OpenRouter chat-completions URL; Authorization: backend bearer secret; Content-Type: application/json; Accept-Encoding: identity. No redirects. |
| JSON envelope | `model`, `temperature` (0), `max_tokens` (2000 legacy / 1200 review after 2026-10-01 remediation), `response_format` (`type: json_object`), `messages` |
| Message | `role`, `content`; system instructions plus JSON schema; user data |
| Review first text part | `type: text`, `text`: serialized object containing `sources`, `documents` |
| Review source | `source_ref` (opaque alias), `kind`, `page`, `label`; `document_role` when present |
| Review document | `source_ref` (alias), `text` (dossier field or bounded extracted document text) |
| Review image marker | `type: text`, `text: Source: <alias>` |
| Review image | `type: image_url`, `image_url: {url: data:image/jpeg;base64,<derivative>}` |
| Legacy classification/extraction user content | Metadata `mime`, `filename` replaced with constant `document`; bounded extracted document text |
| Legacy claim user content | `treatment_items`: `tooth`, `treatment`, `predicate`, `confidence`; `price_facts`: `subject`, `object_value`, `confidence` |

No application-generated internal case IDs, artifact IDs, local paths, original
filenames or provenance hashes are needed or included in source metadata. Local source
inventory is retained only in the database/snapshot. Images are re-encoded JPEG pixel
copies; PDFs become bounded page images. Original files are preserved.

This is metadata minimization, **not de-identification**: supplied text and visible image
pixels may themselves contain sensitive content. The future acceptance test must use
synthetic data. Source references establish traceability, not factual/clinical truth.

## Bounds and failure behavior

Both paths allow at most two attempts, 18 MiB serialized UTF-8 request bytes, 256,000
response-envelope bytes, and a 45-second caller deadline. Individual HTTP operations
also have finite timeouts. Output token limits are additional bounds, not validation.
401/403 fail immediately; 429/5xx and transport timeouts/errors may retry within the
same deadline. Redirects, compressed responses, malformed envelopes/JSON, refusals,
non-`stop` completions, extra/missing choices, and returned-model mismatch fail closed.
A returned model must exactly equal the requested model; no discovery or name repair.

A bounded daemon transport worker enforces the caller deadline even for an injected
stalled transport. At most eight workers can be outstanding. Late results are discarded;
workers have no database/report access and cannot initiate another attempt after the
deadline. Python cannot forcibly cancel an already-blocked synchronous socket or injected
handler: it may finish cleanup after the caller fails. Actual network cancellation and
provider timing remain NOT VERIFIED. Owned clients close on completion. Offline handlers receive an adapter-owned
MockTransport/client with environment routing disabled and no mounts or proxy. Generic
clients belong to live callers and never authorize offline execution.

## Structured output and safety limits

Required review keys: `patient_summary`, `professional_report`,
`diagnostic_hypotheses`, `safety_red_flags`, `limitations`, `source_index`.
Hypotheses preserve label, LOW/MEDIUM/HIGH confidence only, MODEL_INFERRED truth type,
supporting/contradicting refs, missing information, recommended checks and
insufficient-support indication. Local strict schemas reject extra fields.

Regressions cover numeric diagnostic confidence in prose, known definitive-diagnosis
and prescription/treatment directives, unsupported assertions, invalid source indexes,
unknown aliases and conflicting support/contradiction. Deterministic safety can be
escalated by model flags but never downgraded. Provider-side strict schema support is
not required: the request uses `json_object` and supplies the full schema in instructions.
These are bounded lexical/structural safeguards, **not comprehensive semantic or
clinical validation**; supported-looking assertions can still be incorrect.

## Configuration and secret handling

A later authorized real execution requires all four backend settings:

```dotenv
DJ_AI_PROVIDER=openrouter
DJ_AI_MODEL_NAME=<owner-approved-fixed-vendor/model-id>
DJ_LIVE_PROVIDER_ENABLED=true
DJ_OPENROUTER_API_KEY=<backend-secret-injected-outside-source-control>
```

This block is documentation only. No live setting was enabled by this gate.
The template defaults to Mock and `DJ_LIVE_PROVIDER_ENABLED=false` with empty key fields.
No model is approved/discovered by this gate. Local checks reject empty/malformed/Mock
IDs, automatic/free routing selectors, invalid/empty key shape and disabled live mode.
A syntactically valid identifier does not prove provider availability, immutability,
multimodal capability, cost, or owner approval. Those must be established separately.

Only the explicit keyword-only `offline_handler` argument authorizes the trusted
synthetic test path. The adapter wraps that callable in its own MockTransport/client
with `trust_env=false`; combining a handler with a client is rejected. Generic clients,
mocked defaults, mounts and proxies never grant offline authorization. No HTTPX private
attributes are inspected. Tests use a nonsecret dummy marker; no real key is accessed.
The handler is injected by trusted backend test code, never by HTTP input or environment.
Configuration checks for simulated live mode use an isolated settings stand-in;
`DJ_LIVE_PROVIDER_ENABLED` remains false throughout this gate.
Never place keys in browser state, UI, reports, fixtures, logs, commits or test evidence.
Failure audit stores category codes only, not exception text, prompt, raw response,
case/dossier text, images, connection URL or secret. Validated successful output and
local provenance retain their existing persistence semantics.

### Controlled local synthetic fixed-free exception (2026-10-01)

The original validator rejected every `:free` identifier along with automatic/free
routing selectors. This conservative policy enforced the fixed-model preflight
boundary but also excluded explicitly selected fixed free variants. The narrow
exception now requires both backend settings `DJ_ENVIRONMENT=local-synthetic` and
`DJ_LOCAL_SYNTHETIC_ACCEPTANCE_ENABLED=true` and accepts exactly
`qwen/qwen3.8-27b:free`. The opt-in defaults false and has no HTTP request/UI control.
It does not change the configured model or enable live execution.

With the opt-in enabled, any other model (including paid models and other fixed
free models), or any other environment (including production), fails configuration.
Without it, `:free` remains rejected. `/free`, `/auto`, and model components named
`free`, `auto`, `router`, or `dynamic` (including suffixed variants) are rejected.
The exception's exact allowlist also excludes all other dynamic selectors.
Existing normal-mode syntactic validation is not a complete provider model registry.

The separate `DJ_LIVE_PROVIDER_ENABLED` and provider/key checks remain required for
live execution. Validation runs at construction and before dispatch. Offline handlers
retain their existing trusted test-only boundary; response-model equality, bounded
retries, schema validation, sanitized failures, and no Mock fallback remain unchanged.
No live request is authorized by this documentation or implementation gate.

This is an operator-declared local synthetic mode, not detection of synthetic data
or network binding. Any later separately authorized execution must use an isolated,
loopback-only backend and fresh synthetic database/storage. Never enable it on a
deployed service or submit patient data. The exact ID is the owner's supplied choice;
availability, provider pricing, modality support, and live response compatibility
are NOT VERIFIED. No provider lookup or live call was performed for this change.

Verification uses dummy credentials and injected offline HTTP only. The new
regression-first suite initially reported 30 failures and 8 setup errors because
the new configuration interface did not exist. After implementation and additional
alias coverage, the focused command
`.venv/Scripts/python.exe -m pytest tests/next_phase/test_local_synthetic_free.py tests/next_phase/test_preflight.py tests/next_phase/test_preflight_remediation.py -q --tb=short`
passed **162 tests**, with three FastAPI/Starlette deprecation warnings.
The expanded command `.venv/Scripts/python.exe -m pytest tests -q -ra --tb=short`
passed **379 tests**, with **2 skipped** (Windows directory-symlink privilege
unavailable) and the same **3 warnings**. These are new offline results for this
change, not live acceptance. PostgreSQL, browser/runtime acceptance, and the two
skipped symlink cases were not verified at this gate. `git diff --check` passed.
No commit, push, PR modification, or deployment was performed.

## Verification

Historical pre-remediation checkpoints are listed below. Older acceptance evidence
outside this gate is unchanged. The current JUnit files are refreshed by the remediation
runs and sanitized: hostnames/timestamps and user-specific skip paths are removed,
while case identities, counts, outcomes and skip categories are preserved. PostgreSQL
inspection paths are replaced with descriptive environment/location labels.

- Baseline focused scope: 48 passed, 3 warnings.
- New regression reproduction before fixes: 34 failed, 23 passed.
- First focused retest: 86 passed, 3 warnings.
- Expanded next-phase lifecycle checkpoint: 77 passed, 3 warnings.
- First full protected checkpoint: 274 passed, 2 skipped, 3 warnings.
- Recovery edge case: reproduced (1 failed), then focused retest 75 passed.
- Prior final combined protected suite: **286 passed, 7 skipped, 3 warnings** in 104.86s
  (historical pre-remediation result; current XML is replaced by the new run). Skips: two Windows symlink privilege checks and five
  private-cluster PostgreSQL checks. Warnings: existing FastAPI/Starlette deprecations.
- Prior supplemental SQLite loopback HTTP runtime: **1 passed** in 10.74s
  (historical pre-remediation result; runtime evidence is refreshed below). Five concurrent synthetic
  cases, actual server-process restart, report/file equality, reuse, production
  misconfiguration refusal and log canary checks. This uses explicit Mock, not OpenRouter.
- PostgreSQL-only collection: 5 skipped; no private cluster supplied.

### Final-review remediation results

- Before fixes: 7 failed, 17 passed; the running retry exposed HTTP 200, a leading
  decimal passed the guard, and generic mocked/mounted/proxy clients obtained offline
  authorization. The new explicit-injection API tests also failed before implementation.
- Focused three-fix suite: **35 passed, 3 warnings**.
- Requested expanded suite: **158 passed, 3 warnings**.
- Final protected suite: **321 passed, 7 skipped, 3 warnings**; current
  `evidence/offline-junit.xml`. The same two symlink and five PostgreSQL checks skipped.
- SQLite loopback concurrency/process-restart rerun: **1 passed**; current
  `evidence/runtime-junit.xml` and `evidence/runtime/`. No provider network calls.
- Commands and categorical results: [remediation-results.json](evidence/remediation-results.json).

The report endpoint now requires the latest attempt itself to be successful and current;
older successful output cannot reappear while recovery is RUNNING or after failure.
Reuse rejects older successes behind newer RUNNING/FAILED attempts. Tests observe the
committed running attempt through another session, then verify failure, fresh successful
recovery, unchanged history and ordinary reuse. No historical data is deleted.

The confidence guard handles leading dot/comma and Persian decimal forms and the
Persian percent glyph. This applies the existing numeric diagnostic-confidence and
percentage rules; it does not ban ordinary tooth numbers, durations or measurements.
Those permitted examples have regressions. Review/provider contract versions were
bumped so previously accepted results cannot be reused under the revised contract.

The Windows project `.venv` is usable through approved execution outside the sandbox.
Inside the sandbox the WSL bridge failed with `UtilBindVsockAnyPort: socket failed 1`.
No previously authorized Linux verification environment was found; no environment or
package was installed. Tests force live authorization false and credential variables
empty before application import. All OpenRouter calls use injected transport.

The offline end-to-end test exercises synthetic dossier + evidence → exact serialized
sanitized payload → injected structured completion → local validation → durable
ReviewRun/evidence links → immutable shared snapshot → patient/professional sections →
connection disposal/fresh application client and session lifecycle → reuse without HTTP.
It also proves provider/validation failure cannot create or expose a current report.
This restart test is application/session restart in-process, not an OS process restart.

PostgreSQL preparation extends the existing opt-in fresh/populated migration suite
with this injected-provider dossier/review/restart/failure lifecycle. It runs only when
`RC_POSTGRES_SOCKET` points to a private temporary cluster; it creates and drops only
uniquely named synthetic databases. No live-provider PostgreSQL execution occurred.
The subsequent [local PostgreSQL inspection](evidence/postgres/README.md) found no
available executable or compatible prior Linux test environment. No cluster was created,
no server started, and no PostgreSQL tests executed. PostgreSQL remains NOT VERIFIED;
historical PostgreSQL 16.15 evidence is not a current runtime result.

## Exact next procedure — separately authorized live test

1. Review this uncommitted diff and authorize any desired commit separately. Approve a
   specific fixed multimodal model identifier, provider use, synthetic-only payload,
   credential handling, cost ceiling and one-case acceptance scope. Do not discover
   models automatically. This gate grants none of those live permissions.
2. In an isolated backend instance with a fresh local synthetic database/storage,
   rerun the protected offline suite and injected full-pipeline test. If PostgreSQL is
   required, first run the injected lifecycle against a private disposable cluster.
3. Have the operator inject the secret through an approved backend-only secret store
   without printing it. Set the four required settings above only for that instance.
   Set a provider/account spending limit externally; the code does not enforce a
   monetary ceiling. One pipeline may call classification, extraction, claims and
   multimodal review, with at most two attempts per request.
4. Create one synthetic dossier using `POST /api/cases`, update its fields using
   `PUT /api/cases/{case_id}/dossier`, and attach a nonclinical synthetic pattern or
   synthetic PDF using `POST /api/cases/{case_id}/artifacts`. Do not upload patient data.
5. Invoke `POST /api/cases/{case_id}/process` once. Inspect only content-free status,
   failure category, requested/returned model identity and elapsed duration. On any
   failure stop; do not change routing, weaken validation, repair output, or fall back.
6. On success, verify `GET /api/cases/{case_id}/report`, both report sections, local
   source resolution, durable successful ReviewRun and shared immutable snapshot.
   Confirm repeat processing reuses that snapshot without another provider request.
   Do not describe this as clinical validation.
7. Immediately restore `DJ_LIVE_PROVIDER_ENABLED=false`, remove the injected secret
   from the isolated process environment/secret mount and stop that instance. Record
   only sanitized counts/status/timing and NOT VERIFIED limits; no prompt, raw provider
   output, dossier text, images, key or connection URL in published evidence.

Live provider behavior/model compatibility, cost, clinical correctness, actual network
cancellation, PostgreSQL runtime for the new flow, real deployment, and OS-process
restart with OpenRouter remain NOT VERIFIED.

## Review boundary

See [changed-file inventory](CHANGED_FILES.md) and
[repository/secret-pattern checks](evidence/repository-checks.json).
`git diff --check` passes, the index is empty, and HEAD remains the approved landing
commit. The prior gate recorded matching fingerprints for five excluded ZIP/WebP/artwork
files. Remediation did not open or modify them; they remain excluded. No frontend
files changed. The refreshed scope scan covers secrets, machine/user paths, hostnames/usernames and
evidence metadata; synthetic fixtures are also reviewed for patient-data provenance.
Synthetic dummy markers and documented placeholders are intentional. This is not an
exhaustive secret-detection claim. Stop for manual review; no commit is authorized.
