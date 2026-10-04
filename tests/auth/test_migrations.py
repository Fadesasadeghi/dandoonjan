"""Only disposable synthetic databases. Preserve all pre-auth table contents."""
import importlib.util
from pathlib import Path
import sqlite3
import pytest

spec = importlib.util.spec_from_file_location('auth_migration_helpers', Path(__file__).parents[1] / 'regression_p0/test_migrations.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
PREAUTH = '83b20cd5e702'


def capture(conn):
    names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('alembic_version','sqlite_sequence')")]
    return {name: conn.execute(f'SELECT * FROM "{name}" ORDER BY id').fetchall() for name in names}


def seed_remaining_history(conn):
    """Populate every pre-auth table, including linked reviews/extractions/audit.

    Typed synthetic values only; defer FK checks for circular extraction/provenance
    relationships, then check the complete graph before migration.
    """
    from app.db import Base
    from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, JSON
    conn.execute('PRAGMA defer_foreign_keys=ON')
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for name, table in Base.metadata.tables.items():
        if name not in tables or conn.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]:
            continue
        values = {}
        for column in table.columns:
            if column.foreign_keys or column.primary_key:
                value = 1
            elif column.nullable:
                value = None
            elif isinstance(column.type, Enum):
                value = column.type.enums[0]
            elif isinstance(column.type, Boolean):
                value = 1
            elif isinstance(column.type, Integer):
                value = 1
            elif isinstance(column.type, Float):
                value = 0.8
            elif isinstance(column.type, DateTime):
                value = '2026-01-01'
            elif isinstance(column.type, JSON):
                value = '[]' if column.name in {'source_index','supporting_evidence','contradicting_evidence','missing_evidence','reasons'} else '{}'
            else:
                value = f'{name}-synthetic' if column.name == 'public_id' else 'synthetic'
            values[column.name] = value
        names = ','.join(f'"{key}"' for key in values)
        placeholders = ','.join('?' for _ in values)
        conn.execute(f'INSERT INTO "{name}" ({names}) VALUES ({placeholders})', tuple(values.values()))
    assert conn.execute('PRAGMA foreign_key_check').fetchall() == []


@pytest.mark.parametrize('unstamped', [False, True])
def test_populated_preauth_preserved(tmp_path, unstamped):
    path = tmp_path/'populated.db'
    helpers._upgrade(path, PREAUTH)
    with sqlite3.connect(path) as conn:
        helpers._seed_case(conn)
        conn.execute("INSERT INTO processing_runs (id,public_id,case_id,module,status,attempt,input_version,input_hash,output_version,authority,created_at) VALUES (1,'RUN-synthetic',1,'pipeline','SUCCEEDED',1,'v1','hash','v1','ACTIVE','2026-01-01')")
        conn.execute("INSERT INTO artifacts (id,public_id,case_id,original_filename,safe_filename,mime_type,detected_mime_type,file_size,sha256,storage_key,category,subtype,immutable,created_at,document_role) VALUES (1,'ART-synthetic',1,'synthetic.txt','synthetic.txt','text/plain','text/plain',9,'source-hash','CASE-synthetic/source','UNKNOWN','UNKNOWN',1,'2026-01-01','unspecified')")
        from app.governance.immutability import snapshot_content_hash
        payload, versions = {'source_order':['ART-synthetic'],'synthetic':True}, {'case_version':1}
        import json
        conn.execute("INSERT INTO assessment_snapshots (id,public_id,case_id,case_version,payload,safety_state,immutable,versions,content_hash,created_at,derivation_run_id) VALUES (1,'SNP-synthetic',1,1,?,'NORMAL',1,?,?,'2026-01-01',1)", (json.dumps(payload),json.dumps(versions),snapshot_content_hash(payload,versions)))
        conn.execute("INSERT INTO reports (id,public_id,case_id,snapshot_id,schema_version,content,created_at,derivation_run_id) VALUES (1,'RPT-synthetic',1,1,'synthetic','{}','2026-01-01',1)")
        conn.execute("INSERT INTO provenance_records (id,public_id,artifact_id,truth_type,description,created_at) VALUES (1,'PRV-synthetic',1,'DOCUMENT_EXTRACTED','synthetic','2026-01-01')")
        conn.execute("INSERT INTO dossier_revisions (id,public_id,case_id,case_version,symptoms,duration,medical_history,medications,allergies,treatment_plan,previous_reports,previous_treatments,created_at) VALUES (1,'DSR-synthetic',1,1,'synthetic','','','','','','','','2026-01-01')")
        seed_remaining_history(conn)
        before = capture(conn)
        assert all(before.values())  # Preservation cannot pass with empty history tables.
        if unstamped: conn.execute('DROP TABLE alembic_version')
    helpers._upgrade(path); helpers._upgrade(path)
    with sqlite3.connect(path) as conn:
        for table, original in before.items():
            actual = conn.execute(f'SELECT * FROM "{table}" ORDER BY id').fetchall()
            if table == 'users': actual = [row[:4] for row in actual]
            assert actual == original, table
        assert conn.execute('SELECT kind,status,email,password_hash FROM users').fetchall() == [('LEGACY','DISABLED',None,None)]
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
        assert conn.execute('SELECT count(*) FROM auth_sessions').fetchone() == (0,)
    from app.db import make_engine
    from sqlalchemy.orm import Session
    from app.domain.models import AssessmentSnapshot
    from app.governance.immutability import verify_snapshot_integrity
    engine = make_engine(f'sqlite:///{path.as_posix()}')
    try:
        with Session(engine) as db:
            assert verify_snapshot_integrity(db.query(AssessmentSnapshot).one())
    finally: engine.dispose()


def test_preauth_startup_created_adoption(tmp_path):
    """Frozen committed schema, independently created without Alembic."""
    import subprocess
    from sqlalchemy.orm import DeclarativeBase
    import types, sys
    from sqlalchemy import create_engine
    class HistoricalBase(DeclarativeBase): pass
    module = types.ModuleType('frozen_preauth_models')
    module.__dict__['HistoricalBase'] = HistoricalBase
    sys.modules[module.__name__] = module
    source = subprocess.check_output(['git','show','a8a1ce7e534e6b2398780e1b5fd6c114eeb3ae79:app/domain/models.py']).decode('utf-8')
    source = source.split('# Register real-immutability')[0].replace('from app.db import Base', 'Base = HistoricalBase')
    exec(compile(source,'frozen_preauth_models','exec'),module.__dict__)
    path=tmp_path/'startup-preauth.db'
    engine=create_engine(f'sqlite:///{path.as_posix()}')
    try: HistoricalBase.metadata.create_all(engine)
    finally: engine.dispose()
    with sqlite3.connect(path) as conn: helpers._seed_case(conn)
    helpers._upgrade(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT user_id,version FROM cases').fetchone() == (1,1)
        assert conn.execute('SELECT kind FROM users').fetchone() == ('LEGACY',)


def test_fresh_migration(tmp_path, monkeypatch, regression_settings):
    path=tmp_path/'fresh.db'; helpers._upgrade(path)
    with sqlite3.connect(path) as conn:
        assert {'email','normalized_email','password_hash','kind','status','updated_at','email_verified_at'} <= {r[1] for r in conn.execute('PRAGMA table_info(users)')}
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    # Exercise the API on Alembic's schema, not only metadata.create_all.
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from app import db as database
    import app.main as main
    from .helpers import register, login
    engine = database.make_engine(f'sqlite:///{path.as_posix()}')
    monkeypatch.setattr(regression_settings, 'database_url', f'sqlite:///{path.as_posix()}')
    monkeypatch.setattr(database, 'SessionLocal', sessionmaker(bind=engine, autoflush=False, expire_on_commit=False))
    monkeypatch.setattr(main, 'engine', engine)
    try:
        with TestClient(main.app) as client:
            assert register(client, 'migrated@example.com').status_code == 201
            assert login(client, 'migrated@example.com').status_code == 200
            assert client.get('/api/auth/me').status_code == 200
    finally: engine.dispose()


def test_unknown_unstamped_shape_is_rejected(tmp_path):
    path=tmp_path/'unknown.db'; helpers._upgrade(path, PREAUTH)
    with sqlite3.connect(path) as conn:
        conn.execute('DROP TABLE alembic_version'); conn.execute('ALTER TABLE users ADD COLUMN unexpected TEXT')
    with pytest.raises(AssertionError, match='refusing Alembic adoption'):
        helpers._upgrade(path)
