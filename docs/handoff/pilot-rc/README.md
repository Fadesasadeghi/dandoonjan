# Synthetic-data pilot Release Candidate

This RC is a controlled, synthetic-only decision-support demo. It is not a diagnosis
system or a clinical-ready product. No authentication, real patient data, hosted
deployment, paid services, provider credits or clinician-reviewed knowledge pack
were added. Stop after RC delivery for Product Owner review.

## Approved merge and branch

Live PR #2 was OPEN, unmerged and MERGEABLE, with base `agent/sadeghi` and exact
approved head `82ac9ccc4a91d1d450d7843d0cb34388954e43f8`. Its two commits were
`b835d5a4b8e970288bfc6f735578b49896875c11` and that approved head. The guarded
merge used `gh pr merge 2 --merge --match-head-commit 82ac9ccc4a91d1d450d7843d0cb34388954e43f8`.
GitHub verified MERGED at 2026-09-28T06:10:10Z, merge commit
`d3a6584d8b75a2dfb5f83f7c684bdab6dce65f28`. Its parents are the approved P0
base and P1 head; its tree equals the approved P1 tree. PR #2's source was unchanged.
`agent/sadeghi-pilot-rc` starts at that merge. The separate RC PR targets `agent/sadeghi`.

## Windows / PowerShell

Prerequisites: Python 3.11, Git, and a browser. From the repository root, in a new
PowerShell window, use a new `pilot-data` directory containing synthetic data only:

```powershell
git switch agent/sadeghi-pilot-rc
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
New-Item -ItemType Directory -Force .\pilot-data | Out-Null
$env:DJ_ENVIRONMENT = 'development'
$env:DJ_AI_PROVIDER = 'mock'
$env:DJ_AI_MODEL_NAME = 'mock-evidence-v1'
$env:DJ_OPENROUTER_API_KEY = ''
$env:DJ_OPENAI_API_KEY = ''
$env:DJ_REQUIRE_CLINICIAN_REVIEWED_KNOWLEDGE_PACK = 'false'
$env:DJ_CORS_ORIGINS = '[]'
$env:DJ_DATABASE_URL = 'sqlite:///./pilot-data/pilot.db'
$env:DJ_ARTIFACT_STORAGE_DIR = './pilot-data/artifact_store'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-config app/logging.json
```

Open <http://127.0.0.1:8000/>. Stop with Ctrl+C; repeat the final command to restart
with the same database and files. Do not bind this unauthenticated demo to a public
interface. No API key is needed. Do not change an existing unknown database's URL
or run migrations against it. A fresh clone or separate directory avoids mixing
this synthetic pilot with any existing data.

Linux/macOS equivalent: `python3.11 -m venv .venv`, `. .venv/bin/activate`,
`python -m pip install -r requirements.txt`, `mkdir -p pilot-data`; export the same
`DJ_*` values above, then run `python -m alembic upgrade head` and
`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-config app/logging.json`.

## Docker / PowerShell

These commands are supplied for review but **Docker build/runtime is NOT VERIFIED**:
`docker --version` returned exit 127, `docker: command not found` in the verification environment.
Docker Desktop / an available daemon is required. No cloud service is involved.

```powershell
docker build -t dandoonjan:pilot-rc .
docker volume create dandoonjan-pilot-rc-data
docker run --name dandoonjan-pilot-rc -p 127.0.0.1:8000:8000 --mount source=dandoonjan-pilot-rc-data,target=/app/data -e DJ_ENVIRONMENT=development -e DJ_AI_PROVIDER=mock -e DJ_AI_MODEL_NAME=mock-evidence-v1 -e DJ_DATABASE_URL=sqlite:////app/data/pilot.db -e DJ_ARTIFACT_STORAGE_DIR=/app/data/artifact_store -e DJ_CORS_ORIGINS=[] -e DJ_REQUIRE_CLINICIAN_REVIEWED_KNOWLEDGE_PACK=false dandoonjan:pilot-rc
```

In another terminal: `curl.exe --fail http://127.0.0.1:8000/health`. Exercise the
sample, then `docker stop dandoonjan-pilot-rc` and `docker start dandoonjan-pilot-rc`;
verify the saved case still opens. Keep the volume. Do not run `docker volume rm`
as a routine rollback. Docker startup preserves the SQLite convenience initialization;
PostgreSQL uses explicit Alembic migrations before application startup.

## Product Owner walkthrough

1. Home → “مشاهده پرونده نمونه”: real API creates a synthetic case, uploads its
   TXT evidence, processes it and loads the current-authoritative report.
2. Home → “بررسی پرونده”: enter a synthetic question and optional dentist recommendation.
3. Upload a TXT file containing `Treatment Plan` followed by `Tooth 46: RCT recommended`.
   Select an unsupported `.exe` too: its Persian rejection remains visible and the TXT succeeds.
4. Process and inspect material reviewed, separate sources, uncertainty and questions to ask.
   Recommendation remains distinct from necessity; uploaded images are not clinically analyzed.
5. Create another case without documents; after NEEDS_MORE_EVIDENCE, add the TXT and
   reprocess the same case. Edit the question and confirm a new current result.
6. Use “چاپ / ذخیره PDF”. Check print preview and save a PDF. Historical reports must
   never become current after a later blocked result.
7. Restart the app using the same storage paths and reopen the case URL in the same
   local environment. At 390, 768 and 1440 widths, verify readable RTL text and actions.

## Implementation boundaries

- OpenRouter now permits `claim_builder` through the existing schema and semantic
  validation boundaries. Offline production tests exercise valid, invalid-schema
  and invalid-ontology candidates with no real credentials or network.
- Production still refuses Mock/missing keys and does not fall back after provider
  failure or invalid output. Development/test retain deterministic Mock behavior.
- `psycopg` 3 supplies PostgreSQL support; SQLite local/demo behavior remains.
- PostgreSQL migration repairs create the required enum, add the current claim enum
  label without deleting historical labels, and backfill existing derived rows as
  NON_AUTHORITATIVE_LEGACY before removing temporary defaults. Legacy claims lacking
  a confidence column receive zero established confidence; existing confidence is retained.
- First-use pack seeding resolves a concurrent unique-constraint race with a savepoint.
  No pack content, clinical rules, queue or architecture redesign was introduced.
- API database dependencies commit before success headers. Response shapes and
  case/report authority rules are unchanged.
- `DJ_CORS_ORIGINS` is a JSON array of exact HTTP(S) origins; default `[]` grants no
  cross-origin access. Same-origin frontend/API works without a CORS grant. Credentials
  are not allowed, and CORS is not authentication.
- Logs contain only level/event and optional HTTP status. They omit URLs, client
  addresses, bodies, filenames, SQL parameters and exception contents. Diagnostic
  DB/audit errors use safe codes; evidence/provenance records remain intact.
  This intentionally limits diagnostics; do not enable SQL echo or raw HTTP debug logging.

## PostgreSQL rehearsal and rollback

Only a new PostgreSQL 16.15 cluster under `/tmp` was used. TCP listening was disabled;
its Unix socket directory and cluster were mode 0700. Local trust authentication
was restricted by those filesystem permissions; no password was entered or stored.
Never use this test-only trust configuration for a shared or production database.

The opt-in tests require `RC_POSTGRES_SOCKET` pointing to that private temporary
cluster. They create uniquely named `rc_synthetic_*` databases and remove only those
databases during cleanup. They never migrate an existing application database.

```bash
RC_POSTGRES_SOCKET=/tmp/dandoonjan-rc-socket python -m pytest verification/test_rc_postgres.py verification/test_rc_runtime.py -q --tb=short
```

Fresh upgrades and populated initial/pre-P0.1 upgrades are tested, including findings,
claims, provenance references, confidence, authority and the repaired FK. Repeating
`upgrade head` is checked. Runtime tests use migrated PostgreSQL and startup-created
SQLite, real HTTP, five overlapping cases, application restart, unchanged report
identities/content and unchanged evidence-file hashes.

Before any future known synthetic database upgrade: stop writes, retain the prior
code version, copy the SQLite database plus artifact directory together (or take a
PostgreSQL dump plus artifact backup), and rehearse on a separate copy. On failure,
keep the failed copy for diagnosis and restore the paired backup into a new location
with the previous code. Do not downgrade populated history or blindly stamp unknown
schemas. Backup/restore execution and real deployed database migration are NOT VERIFIED
in this checkpoint; no existing deployment/database was touched.

The production path remains separate: authenticated access design, approved hosting
and budget, PostgreSQL/persistent storage ownership and backups, approved provider/model
and secret handling, clinician-reviewed pack, and live deployment verification require
another Product Owner decision. Existing Netlify/Render files are not evidence of a
working hosted deployment and were not deployed here.

## Verification and evidence

See [verification record](VERIFICATION.md), [screenshots and PDF](screenshots/), and
[sanitized runtime evidence](evidence/). Historical Gate 1/P0/P1 handoffs remain history;
this record supersedes their readiness claims only for the checks explicitly rerun.
