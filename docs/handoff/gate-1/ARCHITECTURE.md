# ARCHITECTURE

DANDOONJAN is a Python/FastAPI modular monolith.

Main flow:

Intake → file ingestion → classification → quality checks → structured extraction
→ findings/claims → evidence links → knowledge-pack gaps → assessment/safety
→ snapshot → Persian report.

Main technologies and components:

- FastAPI / Uvicorn.
- SQLAlchemy, Alembic, and Pydantic.
- SQLite currently used locally; PostgreSQL is configurable and selected as the deployment target.
- Plain HTML/CSS/JavaScript Persian RTL frontend.
- ModelGateway, deterministic Mock AI for development/testing, and an OpenRouter adapter.
- pytest / TestClient.
- Docker / Render / Netlify deployment-related configuration.

The architecture uses ProcessingRun, authority state, snapshots, provenance, and
audit records. Their presence is not proof that every isolation or safety invariant
holds; see [AUDIT](AUDIT.md).

No rewrite from scratch is approved or currently justified. Preserve this modular
monolith unless a Stop Condition requires reconsideration. The official runtime is
Python 3.11; deployment and provider verification remain bounded by the audit.
