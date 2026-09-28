# P1 core checkpoint — ready for Product Owner review

Date: 2026-09-26. Source branch: `agent/sadeghi-p1-core`.
PR target: `agent/sadeghi`, never `main`.
Exact approved base: `b36036962a14397ebca0c6f1b7c23001409c93b3`.
Separate approved production correction: `b835d5a4b8e970288bfc6f735578b49896875c11`;
see [its evidence record](../p1-production-fail-closed.md).
The Product Owner will open the PR manually from the pushed branch. No GitHub CLI
installation or token was used. Stop here for review; no further P1 expansion.

## Delivered scope and evidence

| Requirement | Implementation / tested scope |
| --- | --- |
| Home | Exact supplied Persian Unicode strings; warm ivory, sage and terracotta editorial RTL composition; presentation/debug wording removed. |
| Create case | Short question + dentist recommendation form; real POST; optional editing uses existing PATCH/versioning. No authentication or profiles. |
| Evidence | Existing real upload API; additive file rows; uploading, uploaded, rejected, duplicate and attention states; safe backend Persian rejection text; mixed rejection/success continues. |
| Same-case recovery | NEEDS_MORE_EVIDENCE → add evidence → reprocess uses the same case. Processing and upload transport failures can retry that case. Lost creation responses are not automatically retried, preventing accidental duplicate POSTs. |
| Processing | Only observed coarse stages: creation, upload, server processing, result preparation. Waiting controls disable repeated submission. No percentages, token streams or clinical reasoning simulation. |
| Report | Read-only additive `presentation` field on the existing current-report endpoint; frozen snapshot relationships, human Persian source/claim labels and filenames. No raw internal IDs rendered. Recommendation/necessity and independent sources remain distinct. |
| Authority/safety | Existing current-report selection unchanged; snapshot integrity checked before presentation. No routine claims added to urgent/review-pending reports; blocked revisions never display an old report as current. Print action re-fetches the current authoritative report. |
| Sample | Explicitly synthetic; fetches the existing sample endpoint and uses the same real create/upload/process/report APIs as other cases. |
| Images | Upload/store only, explicit no-clinical-image-analysis wording; no OCR or image diagnosis added. |
| Export | Exact Print / Save PDF CTA; browser print action; print CSS and actual Chromium PDF output. |
| Responsive | Chrome at 1440px, 768px and 390px; no horizontal overflow in checked screens; keyboard focus, primary actions and reduced-motion behavior tested. |
| Deployment assets | Netlify rewrites retain matching `/ui/` CSS/JS paths for the same static frontend. Hosted deployment is not claimed verified. |

No schema/migration or architectural change. No deferred sharing/deep-link feature,
clinician-review workflow, auth, payments, queue or provider-platform expansion.

## Protected P0 confirmation

Protected P0 semantics remain intact within the tested scope: storage containment,
case isolation, historical/current isolation, current-report authority,
source-distinct provenance, processing identity, terminal reuse parity,
rejected-upload audit durability, migration integrity, snapshot immutability,
safety/report policy and deterministic tests. Existing P0 tests were not changed.
Pipeline, domain, storage and migration implementation files are unchanged from
the approved base. The only provider change is the separately approved correction.

## Exact verification

Interpreter used for all Python commands below:
`/mnt/c/Users/Admin/AppData/Local/Temp/dandoonjan-p0-regression-venv/Scripts/python.exe`
(Windows CPython 3.11.3). Commands abbreviate this path as `python`.
Default Linux Python 3.14.7 lacked pytest; WSL required escalation for Windows
interop. Playwright 1.63.0 was installed in the existing temporary test environment,
using installed Chrome. No application dependency was added; optional browser
requirements are in `verification/requirements.txt`. All data was synthetic,
SQLite temporary databases, local FastAPI and deterministic Mock; no live provider
or real credentials were used.

| Gate / command | Actual result |
| --- | --- |
| Prior baseline: `python -m pytest tests -q --tb=short -rfs` | 136 passed, 2 skipped, 4 warnings in 25.80s |
| Approved provider fix: `python -m pytest tests/regression_p1/test_production_provider.py -q --tb=short` | 19 passed in 0.46s |
| Provider-fix full suite: `python -m pytest tests -q --tb=short -rfs` | 155 passed, 2 skipped, 4 warnings in 24.85s |
| Before P1 implementation: `python -m pytest tests/regression_p1/test_report_presentation.py verification/test_p1_browser.py -q --tb=short` | 7 failed, 1 passed, 4 warnings in 32.63s; five missing presentation assertions and two reproduced browser upload defects |
| Focused P1 + Chrome, screenshot command below | 43 passed, 4 warnings in 19.27s |
| Protected P0: `python -m pytest tests/regression_p0 -q --tb=short -rfs` | 27 passed, 2 skipped, 4 warnings in 10.25s |
| **Final complete suite: `python -m pytest tests verification/test_p1_browser.py -q --tb=short -rfs`** | **181 passed, 2 skipped, 4 warnings in 42.79s** |
| `node --check frontend/app.js` | Passed |
| `git diff --check` | Passed |
| Direct comparison against all four supplied Unicode sequences | Passed; actual Persian text is stored in source |

Screenshot-producing command executed:

```bash
python -c "import os, pytest; os.environ['P1_SCREENSHOTS']='docs/handoff/p1-core/screenshots'; raise SystemExit(pytest.main(['tests/regression_p1','verification/test_p1_browser.py','-q','--tb=short']))"
```

The final full suite includes 16 Chrome tests (two were added after the 43-pass
focused run). Browser coverage includes the real sample flow, same-case evidence
addition/reprocess/edit/resume, rejected plus accepted files, duplicate upload,
image limitations, upload waiting/retry, process failure/retry, urgent and blocked
revisions, stale-print refusal, lost creation response, long untrusted text,
keyboard/reduced motion, and real coarse processing/result stages.

Review-pending browser rendering uses an explicitly labeled response fixture;
actual backend low-confidence review policy is separately tested through the API.
Transport-failure tests intentionally intercept browser requests. The normal
sample and same-case flows use the real local API with no response replacement.

The two skips are unchanged Windows directory-symlink privilege failures
(WinError 1314). Four warnings are the existing Starlette/httpx, AnyIO and two
FastAPI startup-event deprecations; none were suppressed.

## Screenshots and PDF

| View | Desktop 1440px | Tablet 768px | Mobile 390px |
| --- | --- | --- | --- |
| Home | [PNG](screenshots/home-1440.png) | [PNG](screenshots/home-768.png) | [PNG](screenshots/home-390.png) |
| Create | [PNG](screenshots/create-1440.png) | [PNG](screenshots/create-768.png) | [PNG](screenshots/create-390.png) |
| Report | [PNG](screenshots/report-1440.png) | [PNG](screenshots/report-768.png) | [PNG](screenshots/report-390.png) |

Additional evidence: [mobile evidence step](screenshots/evidence-390.png),
[urgent report](screenshots/urgent-report-1440.png),
[print layout](screenshots/print-layout.png),
[generated PDF](screenshots/sample-report.pdf), and
[rendered first PDF page](screenshots/pdf-page-1.png).

Actual screenshots were inspected for desktop/mobile/tablet layout and readable
Persian; the PDF's first page was visually reviewed. All PDF pages passed nonempty
text and page-boundary checks. The browser print action was exercised with a test
print stub; PDF generation used real Chromium printing. Native OS print-dialog
interaction and a physical printer were not tested.

## Remaining risks / NOT VERIFIED

- **Docker build/runtime: NOT VERIFIED — Docker CLI unavailable in Linux and Windows.**
- Windows directory-symlink enforcement remains NOT VERIFIED (two skipped tests).
- Native print dialog, physical printing, Firefox/Safari and physical mobile devices
  remain NOT VERIFIED. Viewport tests used desktop Chrome emulation.
- Real PostgreSQL, live AI provider, hosted Render/Netlify, HEIC decoding,
  five-request concurrency/load, backup/restore and clinical correctness/readiness
  remain NOT VERIFIED. Netlify routing was reviewed statically only.
- The Render template still selects production plus Mock. The approved fail-closed
  correction intentionally refuses that configuration; it is not a verified
  production deployment. Local demo checks explicitly use development + Mock.
- If a creation response is lost after server commit, the UI refuses automatic
  resubmission but cannot discover that unknown case ID. Server-side creation
  idempotency/recovery was not introduced in this checkpoint.
- Session continuity uses optional browser session storage. Unsent local files and
  rejected-file rows do not survive reload; persisted accepted artifacts do.
- Historical records are preserved; this work does not repair old derived data or
  certify clinical use. Knowledge-pack development content is not clinically validated.
