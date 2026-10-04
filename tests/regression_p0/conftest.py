"""Isolated synthetic resources for the Gate 1 audit regressions."""
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.config import get_settings


@pytest.fixture(autouse=True)
def regression_settings(tmp_path, monkeypatch):
    settings = get_settings()
    for name, value in {
        "artifact_storage_dir": str(tmp_path / "store"),
        "database_url": f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        "ai_provider": "mock",
        "ai_model_name": "mock-evidence-v1",
        "openai_api_key": "",
        "openrouter_api_key": "",
        "require_clinician_reviewed_knowledge_pack": False,
        "environment": "development",
    }.items():
        monkeypatch.setattr(settings, name, value)
    return settings


@pytest.fixture()
def ingest_plan():
    # Same PDF/ingestion pattern as test_p01_reconciliation, with explicit text
    # so source proposition and confidence regressions control their inputs.
    import pymupdf
    from app.core.artifacts.ingestion import ingest_artifact

    def ingest(db, case, text="Treatment Plan\nTooth 46: RCT"):
        with pymupdf.open() as doc:
            doc.new_page().insert_text((72, 72), text)
            data = doc.tobytes()
        return ingest_artifact(db, case, "plan.pdf", "application/pdf", data).artifact

    return ingest


@pytest.fixture()
def raw_api_client(regression_settings, monkeypatch):
    """Real get_db commit/rollback lifecycle, with a temporary database only."""
    from fastapi.testclient import TestClient
    import app.db as database
    import app.main as main

    engine = database.make_engine(regression_settings.database_url)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(main, "engine", engine)
    try:
        with TestClient(main.app) as client:
            yield client, sessions, Path(regression_settings.artifact_storage_dir)
    finally:
        engine.dispose()


@pytest.fixture()
def api_client(raw_api_client, regression_settings, monkeypatch):
    """Existing behavior suites run as a real authenticated synthetic ACCOUNT."""
    from tests.auth.helpers import register, login
    client, sessions, storage = raw_api_client
    monkeypatch.setattr(regression_settings, 'auth_foundation_enabled', True)
    monkeypatch.setattr(regression_settings, 'auth_allowed_origins', ['http://testserver'])
    assert register(client, 'regression@example.com').status_code == 201
    response = login(client, 'regression@example.com')
    assert response.status_code == 200
    client.headers.update({'Origin': 'http://testserver', 'X-CSRF-Token': response.json()['csrf_token']})
    yield client, sessions, storage
