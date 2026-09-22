"""H: populated synthetic SQLite migrations and the audited integrity gaps."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from sqlalchemy import inspect, text

from app.db import make_engine
from app.domain.models import Finding

REPO = Path(__file__).resolve().parents[2]
INITIAL = "13cb12f30f53"
PRE_P01 = "a5716dc9a797"


def _upgrade(path, revision="head"):
    env = {**os.environ, "DJ_DATABASE_URL": f"sqlite:///{path.as_posix()}",
           "DJ_AI_PROVIDER": "mock", "DJ_OPENAI_API_KEY": "",
           "DJ_OPENROUTER_API_KEY": ""}
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", revision],
                            cwd=REPO, env=env, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def _seed_case(conn):
    """Explicit predecessor-schema data; current ORM defaults cannot hide drift."""
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""INSERT INTO users (id, public_id, display_name, created_at)
                    VALUES (1, 'USR-synthetic', 'Synthetic', '2026-01-01')""")
    conn.execute("""INSERT INTO cases
        (id, public_id, user_id, status, version, question_text, context_text,
         dentist_recommendation_text, ontology_version, created_at, updated_at)
        VALUES (1, 'CASE-synthetic', 1, 'CREATED', 1, 'Synthetic question', '', '',
                'synthetic-v1', '2026-01-01', '2026-01-01')""")


def test_populated_initial_upgrade_preserves_finding(tmp_path):
    path = tmp_path / "initial.db"
    _upgrade(path, INITIAL)
    with sqlite3.connect(path) as conn:
        _seed_case(conn)
        conn.execute("""INSERT INTO findings
            (id, public_id, case_id, finding_type, statement, confidence, truth_type, created_at)
            VALUES (1, 'FND-synthetic', 1, 'TOOTH_REFERENCE', 'Tooth 46', 0.8,
                    'DOCUMENT_EXTRACTED', '2026-01-01')""")
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    # Isolate the audited first populated transition rather than masking it with
    # a later P0.1 failure. No test-only defaults or schema patches are installed.
    _upgrade(path, "d632177845ea")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT public_id, statement, confidence FROM findings").fetchall() == [
            ("FND-synthetic", "Tooth 46", 0.8)]
        assert conn.execute("SELECT predicate FROM findings").fetchone()[0] is not None
        assert conn.execute("SELECT question_text FROM cases").fetchone()[0] == "Synthetic question"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_populated_pre_p01_upgrade_preserves_processing_run(tmp_path):
    path = tmp_path / "pre_p01.db"
    _upgrade(path, PRE_P01)
    with sqlite3.connect(path) as conn:
        _seed_case(conn)
        conn.execute("""INSERT INTO processing_runs
            (id, public_id, case_id, module, status, attempt, input_version, input_hash,
             output_version, created_at)
            VALUES (1, 'RUN-synthetic', 1, 'pipeline', 'SUCCEEDED', 1, 'v1',
                    'synthetic-hash', 'v1', '2026-01-01')""")
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    _upgrade(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT public_id, status, input_hash, authority FROM processing_runs").fetchall() == [
            ("RUN-synthetic", "SUCCEEDED", "synthetic-hash", "NON_AUTHORITATIVE")]
        assert conn.execute("SELECT question_text FROM cases").fetchone()[0] == "Synthetic question"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_startup_created_database_can_enter_alembic_lifecycle(tmp_path, monkeypatch, regression_settings):
    import app.main as main
    from app.domain.models import User
    from sqlalchemy.orm import Session
    path = tmp_path / "startup.db"
    url = f"sqlite:///{path.as_posix()}"
    engine = make_engine(url)
    monkeypatch.setattr(regression_settings, "database_url", url)
    monkeypatch.setattr(main, "engine", engine)
    try:
        main.on_startup()
        with Session(engine) as db:
            db.add(User(public_id="USR-preserved", display_name="Synthetic"))
            db.commit()
    finally:
        engine.dispose()
    # Exercise the existing documented upgrade command. Do not blindly stamp
    # a startup-created schema or prescribe the future adoption implementation.
    _upgrade(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT public_id FROM users").fetchall() == [("USR-preserved",)]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_migrated_finding_treatment_item_fk_matches_model(tmp_path):
    path = tmp_path / "schema.db"
    _upgrade(path)
    engine = make_engine(f"sqlite:///{path.as_posix()}")
    try:
        migrated = {(tuple(fk["constrained_columns"]), fk["referred_table"],
                     tuple(fk["referred_columns"]))
                    for fk in inspect(engine).get_foreign_keys("findings")}
        expected = {((fk.parent.name,), fk.column.table.name, (fk.column.name,))
                    for fk in Finding.__table__.c.treatment_item_id.foreign_keys}
        assert expected and expected <= migrated, "migrated finding-to-treatment-item FK is missing"
    finally:
        engine.dispose()


def test_runtime_sqlite_connections_enforce_foreign_keys(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'runtime.db').as_posix()}")
    try:
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        engine.dispose()
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    finally:
        engine.dispose()
