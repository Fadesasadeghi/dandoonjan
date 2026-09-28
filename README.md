# دندون‌جان — DANDOONJAN Evidence Core V0

Persian-first dental **evidence intelligence** application. NOT a chatbot, NOT an
autonomous diagnosis system. Purpose: a patient uploads their available documents,
states what the dentist recommended and what they want to understand, and the system
builds a structured, traceable evidence model before producing a patient-facing report.

> Architecture: **Evidence → Assessment → Explanation** (never Files → LLM → Answer)

Current synthetic-only Release Candidate: [execution and Product Owner handoff](docs/handoff/pilot-rc/README.md).
Use that handoff for Windows, local, Docker, migration and verification instructions.
This unauthenticated RC is for a controlled loopback demo, not public or patient use.

## Run locally (offline, mock AI)

```bash
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-config app/logging.json
```

- Presentation UI (Persian/RTL): http://127.0.0.1:8000/
- Legacy UI path redirects to the presentation: http://127.0.0.1:8000/ui
- API: http://127.0.0.1:8000/api
- Health: http://127.0.0.1:8000/health (also available at `/api/health`)

No AI credentials needed: `DJ_AI_PROVIDER=mock` is a deterministic offline provider.

## Presentation deployment

The repository contains Netlify proxy and Render configuration, but this is not
verification of a working hosted deployment. Do not publish the frontend without
a functional backend. The existing Render production/Mock configuration is refused
by production fail-closed policy; it is not an RC deployment recipe. Hosted work,
credentials and paid services require separate approval. The RC serves its frontend
and API from the same local origin.

## Tests

```bash
python -m pytest tests -q
```

Covers unit, integration, security/ingestion, state machine, provenance, snapshot
immutability, invariant (INV-01..08), adversarial, safety, and the evaluation
harness (golden + adversarial + safety cases in `evaluation/`).

## Database migrations

```bash
alembic upgrade head          # apply
alembic revision --autogenerate -m "..."   # after model changes
```

## Key guarantees (release blockers)

1. No raw file ever directly produces a patient answer.
2. All AI output passes strict schema + ontology validation before entering core state.
3. Every material fact carries provenance (artifact, page, span, model run, versions).
4. Patient/clinician-reported vs document-extracted vs model-inferred facts stay distinct.
5. Evidence requirements come only from the versioned Knowledge Pack
   (V0 pack: **NOT CLINICALLY VALIDATED** — development/demo only).
6. Reports are generated only from immutable Assessment Snapshots.
7. Safety gate can block or downgrade report delivery (fail closed).
8. Model/prompt/schema/ontology/knowledge-pack versions are recorded on every run.

See `docs/` and `DANDOONJAN_CURRENT_STATE_LOCK.md`.
