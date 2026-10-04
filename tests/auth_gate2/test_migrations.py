"""Synthetic migration preservation across exact stamped/unstamped shapes."""
import sqlite3
import pytest
from tests.auth.test_migrations import helpers, seed_remaining_history


def capture(conn):
    names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('alembic_version','sqlite_sequence')")]
    return {name: conn.execute(f'SELECT * FROM "{name}" ORDER BY 1').fetchall() for name in names}


@pytest.mark.parametrize('revision,unstamped', [
    ('83b20cd5e702', True), ('d81e27a9c401', False),
    ('d81e27a9c401', True), ('head', True), ('head', False)])
def test_additive_preservation(tmp_path, revision, unstamped):
    path = tmp_path/'preserve.db'
    helpers._upgrade(path, '83b20cd5e702')
    with sqlite3.connect(path) as conn:
        helpers._seed_case(conn)
        seed_remaining_history(conn)
    if revision != '83b20cd5e702':
        helpers._upgrade(path, revision)
    with sqlite3.connect(path) as conn:
        before = capture(conn)
        if unstamped:
            conn.execute('DROP TABLE alembic_version')
    helpers._upgrade(path)
    helpers._upgrade(path)
    with sqlite3.connect(path) as conn:
        after = capture(conn)
        for table, rows in before.items():
            actual = after[table]
            if table == 'users' and revision == '83b20cd5e702':
                actual = [row[:4] for row in actual]
            assert actual == rows, table
        assert after['demo_visitors'] == []
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
        assert conn.execute('SELECT user_id FROM cases').fetchall() == [(1,)]
        assert conn.execute('SELECT kind,status FROM users').fetchall() == [('LEGACY','DISABLED')]
        assert conn.execute('SELECT version_num FROM alembic_version').fetchone() == ('e72b4c9a6102',)


def test_fresh_and_unknown_fail_closed(tmp_path):
    path = tmp_path/'fresh.db'
    helpers._upgrade(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT count(*) FROM demo_visitors').fetchone() == (0,)
        helpers._seed_case(conn)
        conn.execute('DROP TABLE alembic_version')
        conn.execute('ALTER TABLE demo_visitors ADD COLUMN unknown TEXT')
        before = capture(conn)
    with pytest.raises(AssertionError, match='refusing Alembic adoption'):
        helpers._upgrade(path)
    with sqlite3.connect(path) as conn:
        assert capture(conn) == before
        assert not conn.execute("SELECT name FROM sqlite_master WHERE name='alembic_version'").fetchall()


def test_gate1_manifest_is_exact_unchanged_core():
    import json, importlib.util
    from pathlib import Path
    from app.db import Base
    spec = importlib.util.spec_from_file_location('gate2_schema_shape', Path('alembic/schema_adoption.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    actual = module.metadata_shape(Base.metadata)
    actual.pop('demo_visitors')
    frozen = json.loads(Path('alembic/gate1_schema.json').read_text(encoding='utf-8'))
    assert actual == frozen['shape']


def test_demo_api_on_alembic_schema(tmp_path, regression_settings, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from app import db as database
    import app.main as main
    from app.domain.models import DemoVisitor, Case, User
    from tests.auth_gate2.test_access import demo, create
    path = tmp_path/'migrated-api.db'; helpers._upgrade(path)
    url = f'sqlite:///{path.as_posix()}'
    engine = database.make_engine(url)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(regression_settings,'database_url',url)
    monkeypatch.setattr(database,'SessionLocal',factory)
    monkeypatch.setattr(main,'engine',engine)
    try:
        with TestClient(main.app) as client:
            headers = demo(client); cid = create(client,headers,'/api/demo/cases')
            assert client.get('/api/demo/cases/'+cid).status_code == 200
        with factory() as db:
            owner = db.query(Case).one().user_id
            assert db.query(DemoVisitor).one().user_id == owner
            assert db.get(User,owner).kind == 'LEGACY'
    finally:
        engine.dispose()
