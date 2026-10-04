"""Opt-in rehearsal. Creates only uniquely named databases on a private test socket."""
import os
from pathlib import Path
import subprocess
import sys
import uuid
from urllib.parse import quote

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def pg_url():
    socket = os.environ.get("RC_POSTGRES_SOCKET")
    if not socket:
        pytest.skip("NOT VERIFIED: RC_POSTGRES_SOCKET private temporary cluster not supplied")
    path = Path(socket)
    assert path.is_dir() and path.stat().st_mode & 0o077 == 0
    import psycopg
    from psycopg import sql
    name = "rc_synthetic_" + uuid.uuid4().hex
    with psycopg.connect(dbname="postgres", host=socket, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            # Percent encoding also exercises Alembic's ConfigParser escaping.
            yield f"postgresql+psycopg:///{name}?host={quote(socket, safe='')}"
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def migrate(url, revision="head"):
    env = {**os.environ, "DJ_DATABASE_URL": url, "DJ_AI_PROVIDER": "mock",
        "DJ_ENVIRONMENT": "test", "DJ_OPENROUTER_API_KEY": "", "DJ_OPENAI_API_KEY": ""}
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("predecessor", [None, "13cb12f30f53", "a5716dc9a797"])
def test_postgres_fresh_and_populated_migrations(pg_url, predecessor):
    from sqlalchemy import create_engine, inspect, text
    engine = create_engine(pg_url, hide_parameters=True)
    try:
        if predecessor:
            migrate(pg_url, predecessor)
            with engine.begin() as conn:
                conn.execute(text("""INSERT INTO users (id, public_id, display_name, created_at)
                    VALUES (1, 'USR-synthetic', 'Synthetic', '2026-01-01')"""))
                conn.execute(text("""INSERT INTO cases
                    (id,public_id,user_id,status,version,question_text,context_text,
                    dentist_recommendation_text,ontology_version,created_at,updated_at)
                    VALUES (1,'CASE-synthetic',1,'CREATED',1,'Synthetic question','','',
                    'synthetic','2026-01-01','2026-01-01')"""))
                extra = ", predicate" if predecessor != "13cb12f30f53" else ""
                value = ", 'MENTIONED'" if extra else ""
                conn.execute(text(f"""INSERT INTO findings
                    (id,public_id,case_id,finding_type,statement,confidence,truth_type,created_at{extra})
                    VALUES (1,'FND-synthetic',1,'TOOTH_REFERENCE','Tooth 46',0.8,
                    'DOCUMENT_EXTRACTED','2026-01-01'{value})"""))
                conn.execute(text("""INSERT INTO processing_runs
                    (id,public_id,case_id,module,status,attempt,input_version,input_hash,output_version,created_at)
                    VALUES (1,'RUN-synthetic',1,'pipeline','SUCCEEDED',1,'v1','synthetic','v1','2026-01-01')"""))
                confidence_column = ", confidence" if predecessor == "a5716dc9a797" else ""
                confidence_value = ", 0.7" if confidence_column else ""
                conn.execute(text(f"""INSERT INTO claims
                    (id,public_id,case_id,claim_type,subject,predicate,object_value,
                    source_type,source_reference,status,created_at{confidence_column})
                    VALUES (1,'CLM-synthetic',1,'OTHER','TOOTH_46','MENTIONED','synthetic',
                    'DOCUMENT_EXTRACTED','synthetic source','ACTIVE','2026-01-01'{confidence_value})"""))
        migrate(pg_url)
        migrate(pg_url)  # idempotent upgrade
        inspector = inspect(engine)
        assert any(fk["constrained_columns"] == ["treatment_item_id"] and
            fk["referred_table"] == "treatment_items" for fk in inspector.get_foreign_keys("findings"))
        enums = {e["name"]: e["labels"] for e in inspector.get_enums()}
        assert "TREATMENT" in enums["claimtype"]
        with engine.connect() as conn:
            # The next-phase migrations extend the protected RC schema.
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "e72b4c9a6102"
            if predecessor:
                assert conn.execute(text("SELECT statement, derivation_status FROM findings")).one() == ("Tooth 46", "NON_AUTHORITATIVE_LEGACY")
                assert conn.execute(text("SELECT authority FROM processing_runs")).scalar_one() == "NON_AUTHORITATIVE"
                assert conn.execute(text("SELECT question_text FROM cases")).scalar_one() == "Synthetic question"
                assert conn.execute(text("SELECT source_reference, derivation_status FROM claims")).one() == ("synthetic source", "NON_AUTHORITATIVE_LEGACY")
                assert conn.execute(text("SELECT confidence FROM claims")).scalar_one() == (0.7 if predecessor == "a5716dc9a797" else 0.0)
    finally:
        engine.dispose()


def test_concurrent_first_pack_seed_is_idempotent(pg_url):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.core.knowledge.pack import seed_knowledge_pack
    migrate(pg_url)
    engine = create_engine(pg_url, hide_parameters=True)
    barrier = threading.Barrier(5)
    def seed(_):
        try:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                pack = seed_knowledge_pack(session)
                identity = pack.id
                session.commit()
                return identity
        except Exception as exc:
            return type(exc).__name__
    try:
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(seed, range(5)))
        assert all(isinstance(item, int) for item in results), results
        assert len(set(results)) == 1
    finally:
        engine.dispose()


def test_postgres_injected_openrouter_dossier_lifecycle(pg_url, tmp_path, monkeypatch):
    """Opt-in database rehearsal only. The provider transport is always synthetic."""
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from app.config import get_settings
    import app.db as database
    import app.main as main
    from verification.offline_openrouter import OfflineRouter, verify_success
    from app.domain.models import ReviewRun, AssessmentSnapshot
    migrate(pg_url)
    settings = get_settings()
    monkeypatch.setattr(settings, 'database_url', pg_url)
    monkeypatch.setattr(settings, 'artifact_storage_dir', str(tmp_path / 'store'))
    monkeypatch.setattr(settings, 'environment', 'test')
    monkeypatch.setattr(settings, 'require_clinician_reviewed_knowledge_pack', False)
    router = OfflineRouter(monkeypatch)
    engine = database.make_engine(pg_url)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(database, 'SessionLocal', sessions)
    monkeypatch.setattr(main, 'engine', engine)
    try:
        with TestClient(main.app) as client:
            cid, report, frozen = verify_success(client, sessions, router)
        engine.dispose()
        with TestClient(main.app) as client:
            count = len(router.requests)
            assert client.get(f'/api/cases/{cid}/report').json() == report
            assert client.post(f'/api/cases/{cid}/process').json()['reused']
            assert len(router.requests) == count
            client.put(f'/api/cases/{cid}/dossier', json={'duration': '4 days'})
            router.failure = 'authentication'
            assert client.post(f'/api/cases/{cid}/process').json()['report'] is None
            assert client.get(f'/api/cases/{cid}/report').status_code == 404
        with sessions() as db:
            assert db.query(AssessmentSnapshot).one().payload == frozen
            failed = db.query(ReviewRun).order_by(ReviewRun.id.desc()).first()
            assert failed.status == 'FAILED' and failed.output is None
    finally:
        engine.dispose()
