# Phase 6 Gate 6.2 — multimodal transport and candidate validation

Date: 2026-10-05. Owner-approved tests-first/offline implementation.
Baseline: `agent/sadeghi-next-phase`,
`a7ce462fec9938b0b97d8efbd9390173f5ef5a60`.
No stage, commit, push, PR mutation, deployment, live AI, paid usage, secret
inspection, real patient data or normal developer database access is authorized.

## Scope and authority

This gate verifies transport, bounded representations, references, structured
output and deterministic safety rules. It does not verify clinical accuracy.
DANDOONJAN remains Persian evidence explanation/decision support requiring
clinician judgment. Gate 6.1 admission, input identity, single-dispatch policy,
internal categories, immutable history and request-local Demo isolation remain.

No endpoint, public response field, database column, migration, dependency,
provider/model configuration, output budget, retention policy or frontend file
changes. Internal contract versions invalidate reuse across validation versions;
existing snapshots/derivation records are never rewritten or deleted. Existing
public `source_index` fields remain unchanged. Coverage descriptors are transient
provider input; coverage limitations are frozen through the existing assertions.

## Transport matrix

| Accepted input | Review input | Separate extraction | Bounds and identity |
| --- | --- | --- | --- |
| JPEG / PNG | Actual JPEG data-URI image parts, with preceding alias | No clinical image extraction | Single frame, 20M source pixels, longest side 1600; original/page and derivative hashes remain local |
| PDF | One actual JPEG part per rendered page | Bounded PDF text for legacy document extraction | All pages, 1–8; over-limit/encrypted/corrupt input fails rather than silently omitting pages; page numbers map to artifact refs |
| UTF-8 TXT | Bounded actual text | Bounded text extraction | Review 20,000 characters/source; newly derived extraction 20,001 including truncation sentinel; original immutable bytes retained |
| Other MIME / animated PNG | No new support | Existing upload restrictions | Rejected/fails closed |

Combined visual bounds remain 16 derivatives / 12 MiB JPEG bytes; review text
100,000 characters and inventory 100 sources. Base64 increases HTTP wire size;
12 MiB is the derivative-byte budget, not the serialized request-byte budget.
PDF review consumes visual pages, not duplicated extracted text. Original SHA256
is checked before deriving/grounding. Fresh RGB copies omit EXIF, ICC and comments;
EXIF orientation is applied before resizing. Derivatives exist only in memory.
The source's `document_role`, deterministic artifact ordering and page remain
traceable. No filename/path/account/session identifier or local hash is added to
review input; semantic dossier/evidence text itself is still sent. This is not
identifier redaction inside user-authored text.

## Reference and observation contract

Application-owned local sources become fresh random request aliases. Duplicate
local sources/alias collisions fail; candidate index must equal the exact supplied
inventory. Unknown, cross-case, duplicate, contradictory or omitted references
fail. Model ordering is replaced with application ordering. Aliases are resolved
only after validation. IDs in narrative prose cannot masquerade as references.

`kind` identifies source provenance, not clinical truth. Every paraphrase or
interpretation must retain `insufficient_support=true`, displayed by the existing
web/export renderers. A sufficient-support assertion is restricted to an exact
quote from matching supplied text with one fixed attribution: `به گفته شما`,
`به روایت`, or `در متن سند`. No extra conclusion may be appended. Hypotheses
retain `MODEL_INFERRED`, qualitative confidence and required missing information
and checks; they do not become document findings.

Legacy text-only extraction additionally grounds tooth/treatment/price locators
against bounded immutable source text. It checks page/span validity, line-level
ontology matching and explicit modality markers, rejects known negation and
fabricated image bounding boxes, and confines claim candidates to supplied atomic
facts. These are conservative lexical/co-occurrence checks, not clinical semantic
entailment. Complex phrasing can fail closed and needs clinician review.

The canonical application-owned Demo PNG is recognized by pixels, including
metadata variants, and described as `NON_CLINICAL`. It cannot support/contradict
a diagnostic hypothesis or be described as clinical evidence. This is not a
general detector for arbitrary synthetic images. No radiograph-accuracy claim.

## Persian, completeness and safety

All model assertion narratives and hypothesis labels must pass deterministic
Persian checks. References, enums, codes, numeric units, established short dental
tokens and abbreviations are exempt. Narratives require sufficient Arabic-script
letters, a majority script ratio, distinct words and a Persian function-word
anchor. Labels have a shorter minimum. English-only/Arabic-only fixtures fail;
mixed Persian/RCT/OPG/CBCT/FDI text passes. No automatic translation. This heuristic
does not prove full linguistic quality or distinguish every Arabic/Persian phrase.

Both audiences and limitations must be substantive and nonempty; boilerplate-only
summaries fail. Limitations must state that this is not diagnosis and requires a
dentist. Hypotheses need uncertainty/check entries. Existing prescription,
definitive-language and numeric-confidence checks remain; narrow added forms
cover direct disease assertions, guaranteed outcomes and replacing the dentist.
Ordinary tooth numbers and cautious clinical terminology have false-positive
regressions. These checks are defense in depth, not exhaustive natural-language
safety proof. Structured output never grants autonomous clinical authority.

Malformed/partial JSON, envelope failures, refusal, content filtering, cancelled,
length truncation and model mismatch keep their Gate 6.1 classifications and
single-dispatch policy. Persian/completeness failures use `schema`, safety uses
`safety`, references use `reference`; no raw exception/provider content is exposed.

## Missing evidence and frozen audiences

Only processable artifacts enter review. Omitted/rejected inputs cannot be cited.
The application appends deterministic limitations for partial TXT, canonical
nonclinical PNG, omitted artifacts and actually empty/unknown dossier fields.
Missing dossier text is explicitly not a judgment about separately uploaded
documents. PDF limits fail the run; there is no silently reviewed page subset.
Existing materials/quality lists may show submitted files independently of model
source inventory; the frozen review inventory identifies model input.

Review output is validated before persistence and again after application notes.
Both audience sections/limitations in reports equal the frozen validated output.
Export uses that same authoritative, revalidated report and existing support-gap
warnings. Neither audience has a separate model/diagnosis channel.
Mock remains deterministic, marks its interpretations as insufficiently supported,
and uses Persian templates for missing fields. Demo retains isolated Mock and no
clinical interpretation of its PNG. Production Mock restrictions are unchanged.

## Budget

Review budget remains **1200 tokens**. A minimal safe output with both audiences,
limitations and three random aliases fits below 1200 UTF-8 bytes in a deterministic
fixture. This is conservative compact-output evidence, not an approved-model
tokenizer measurement or successful live result. Maximum 100-source outputs and
provider reasoning consumption are NOT VERIFIED within 1200. Truncation fails
closed; sources are never silently dropped and the budget was not increased.

## Tests-first ledger

All commands use `.venv/Scripts/python.exe verification/run_phase6_offline.py`.
The existing launcher uses disposable DB/storage/cwd, disables dotenv and live
provider execution before imports, empties key variables without inspecting them,
and trips on real HTTPX transport. Only injected synthetic HTTP responses are used.

Initial command:

```text
tests/next_phase/test_gate62_output.py tests/next_phase/test_gate62_transport.py -q --tb=line -ra
```

Before application changes: **26 failed, 10 passed, 3 warnings (2.42s)**.
Confirmed gaps: semantic emptiness, English-only acceptance, missing uncertainty,
unsupported sufficient claims, aliases, silent TXT truncation, integrity checking,
nonclinical evidence support and additional definitive forms; a cautious RCT phrase
also exposed a numeric-confidence false positive. Initial green: **36 passed**.

Additional tests-first grounding command:
`tests/next_phase/test_gate62_grounding.py -q --tb=line -ra`.
Initial **3 failures** demonstrated invented ontology items/pages/claims becoming
report-ready. Follow-up output/grounding checks exposed **4 failures / 42 passes**
including character spans, partial completeness and language. Explicit diagnosis/
nonclinical-category assertions then produced **3 failures** before added safety
checks; fabricated bounding-box regression produced **1 failure** before rejection.

Regression failures were fixed without weakening assertions: synthetic clinical
support formerly linked to the nonclinical PNG now links to intake; a new positive
real text-artifact FK/frozen audience test preserves artifact-evidence coverage.
Existing English success fixtures now emit valid Persian narratives. Numeric
safety tests assert the exact safety category and retain their rejected scores.
An incomplete Demo template regression was corrected, not exempted from validation.

The last regression, `test_label_exemption_cannot_be_reused_for_narrative`,
produced **1 failure** (`DID NOT RAISE`) before its fix. Validation had inferred
field role from text equality with a hypothesis label. It now validates assertion
fields as full narratives and label fields separately; no language rule is relaxed.
Focused final command adds `test_gate62_grounding.py` and
`test_gate62_authority.py` to the initial output/transport command: **55 passed,
3 warnings (8.81s)**.

## Files changed

- `app/ai/multimodal.py`: integrity, bounded truthful coverage, derivative handling,
  aliases and canonical nonclinical pattern.
- `app/ai/review_schema.py`, `review.py`: validation and frozen limitation notes,
  deterministic Mock/Demo wording.
- `app/ai/providers.py`, `prompts.py`, `preflight.py`: instructions, internal
  contract versions and corrected Mock price offsets.
- `app/ai/grounding.py`: source/locator/atomic candidate validation.
- `app/ai/gateway.py`, `app/pipeline/orchestrator.py`: processable-artifact review
  scope and identity versions.
- `app/core/artifacts/ingestion.py`, `app/pipeline/stages.py`, `claims.py`: bounded
  extraction and grounding before authoritative facts.
- Four new `tests/next_phase/test_gate62_{output,transport,grounding,authority}.py`
  modules; existing contract/preflight/remediation/replay fixtures updated while
  retaining or strengthening assertions.
- `verification/offline_openrouter.py`: valid synthetic candidate fixture and
  nonclinical evidence separation; this handoff.

No frontend, auth/session, database model/migration, knowledge pack, report visual,
environment, dependency or owner-material files changed.

## Remaining limitations / next gate

NOT VERIFIED: live provider capability/service/free-tier availability, provider
image interpretation, clinical accuracy, actual approved-model tokenization,
maximum-budget sufficiency, deployed PostgreSQL runtime and arbitrary synthetic
image detection. No live execution is authorized. Page parsing itself is not a
complete CPU/memory sandbox even though extracted/outbound representations are
bounded. Gate 6.1 heartbeat/lease recovery and Gate 6.4 retry UX remain deferred.
No owner decision was needed to change API, schema, model, privacy or budget here.
Gate 6.3 live synthetic acceptance requires separate owner authorization.

## Final verification

Focused Gate 6.2: **55 passed, 3 warnings (8.81s)**.

Relevant backend command:

```text
tests/next_phase tests/regression_p1 tests/regression_rc/test_provider_privacy.py tests/upload_management tests/auth_gate2 tests/test_p0_provenance.py tests/test_p0_orchestration.py tests/test_p0_claims_extraction.py tests/test_p01_reconciliation.py tests/test_ingestion.py tests/test_invariants.py -q --tb=line -ra
```

Result: **521 passed, 4 skipped, 3 warnings (181.47s)**. The four existing
PostgreSQL processing runtime tests require `RC_POSTGRES_SOCKET`; no skip or
threshold was changed. This covers Gate 6.1 contention/replay/identity/reuse,
provider/preflight/review, Demo, Auth Gate 2, uploads and report/provenance authority.

Browser command:
`verification/test_demo_browser.py verification/test_professional_pdf_browser.py -q --tb=line -ra`.
Result: **22 passed (53.18s)** with disposable SQLite/storage and local Mock.
Both audiences, source distinction, support warnings, revalidated export, stale
authority and Demo continuity are covered. No frontend change.

Full final backend command: `tests -q --tb=line -ra`.
Result: **664 passed, 7 skipped, 3 warnings (231.17s)**. Five PostgreSQL runtime
checks require the unavailable private cluster; two existing Windows symlink tests
require an unavailable OS privilege. Skips were neither added nor weakened.
Warnings are existing Starlette TestClient/FastAPI lifespan deprecations.
An earlier full run (before the last label regression/fix) had 663 passes and is
prior evidence only. An earlier browser run started before the incomplete-Demo
template correction was interrupted; the fresh complete 22-test run above is
the browser acceptance result.

GitHub was initially unreachable inside the network sandbox. The authorized
read-only retry succeeded: PR #5 is **OPEN**, `mergedAt=null`, base
`agent/sadeghi-pilot-rc`, head `agent/sadeghi-next-phase` at the exact baseline
commit. No PR write occurred. Provider network execution remains prohibited.

## Repository integrity

Final branch/HEAD remain the exact baseline. Staged diff is empty;
`git diff --check` passes. New Python files parse and new-file whitespace checks
pass. All **878** pre-existing unrelated owner files match their original SHA256
fingerprints (aggregate baseline
`2da3bd4a9b606854eca803d1ecc1faafbabd22049e88443f67809dc80095fd87`).
The pre-existing landing PNG changes and owner untracked directories/assets remain
untouched. Gate changes are uncommitted and unstaged; no cleanup was performed.
No schema/API/budget/provider/retention owner decision remains for this offline
gate. Live execution still needs separate approval.
