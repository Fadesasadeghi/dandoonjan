# Real multimodal preflight — offline gate

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
| JSON envelope | `model`, `temperature` (0), `max_tokens` (2000 legacy / 6000 review), `response_format` (`type: json_object`), `messages` |
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
