"""DANDOONJAN_EVIDENCE_CORE_V0 — FastAPI app shell."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import get_settings
from app.db import Base, engine
from app.errors import DandoonjanError
from app.safe_logging import configure_logging

configure_logging()

app = FastAPI(title="DANDOONJAN Evidence Core V0", version="0.1.0")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins,
                   allow_methods=["GET", "POST", "PATCH"],
                   allow_headers=["Content-Type"], allow_credentials=False)


@app.exception_handler(DandoonjanError)
async def domain_error_handler(request: Request, exc: DandoonjanError):
    # Never leak stack traces to the frontend.
    return JSONResponse(status_code=422,
                        content={"code": exc.code, "message_fa": exc.user_message_fa})


@app.on_event("startup")
def on_startup() -> None:
    settings = get_settings()
    Path(settings.artifact_storage_dir).mkdir(parents=True, exist_ok=True)
    # SQLite is the release-safe single-instance presentation store.  Keep
    # clean-instance startup deterministic even when the service is marked
    # production; PostgreSQL deployments continue to use Alembic migrations.
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)  # dev convenience; prod uses migrations


app.include_router(router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": get_settings().app_name}


@app.get("/health")
def public_health():
    return {"status": "ok"}


@app.get("/")
def presentation_home():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/case/{case_public_id}")
def presentation_case(case_public_id: str):
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/ui")
def legacy_ui_redirect():
    return RedirectResponse(url="/", status_code=307)


# Keep the old static path available for bookmarked assets/routes.
app.mount("/ui/", StaticFiles(directory=FRONTEND_DIR, html=True), name="ui")
