"""Current-contract acceptance on private disposable synthetic PostgreSQL only."""
from concurrent.futures import ThreadPoolExecutor, wait
from contextlib import ExitStack
from threading import Barrier, Event, Lock
import os
import subprocess
import sys

import pytest
from sqlalchemy import MetaData, create_engine, inspect, select, text

from verification.test_rc_postgres import ROOT, pg_url, migrate
from tests.next_phase.test_processing_postgres import pg_api
from tests.next_phase.test_processing_concurrency import peer
from tests.auth.test_rate_limits import (
    test_concurrent_limit_is_atomic as check_atomic_limit,
    test_persistent_normalized_limit_and_no_permanent_lockout as check_limit_reset,
)
from tests.auth.test_sessions import (
    test_hash_only_storage_fixation_and_revocation as check_session,
    test_relogin_issues_fresh_session_and_revokes_previous as check_relogin,
    test_last_seen_is_bounded as check_touch,
)
from tests.auth_gate2.test_access import (
    READS, WRITES, test_normal_route_isolation as check_isolation,
    test_session_denial as check_denial,
    test_csrf_before_case_work as check_csrf,
)
from tests.upload_management.test_upload import test_concurrent_capacity as check_capacity


@pytest.fixture()
def pg_raw_api(pg_url, regression_settings, monkeypatch, request):
    migrate(pg_url)
    monkeypatch.setattr(regression_settings, 'database_url', pg_url)
    monkeypatch.setattr(regression_settings, 'auth_foundation_enabled', True)
    monkeypatch.setattr(regression_settings, 'auth_allowed_origins', ['http://testserver'])
    return request.getfixturevalue('raw_api_client')


def test_unknown_unstamped_schema_rejected(pg_url):
    engine = create_engine(pg_url, hide_parameters=True)
    try:
        with engine.begin() as db:
            db.execute(text('CREATE TABLE gate72_unknown (id INTEGER PRIMARY KEY, note TEXT)'))
            db.execute(text("INSERT INTO gate72_unknown VALUES (1, 'synthetic preservation probe')"))
        with pytest.raises(AssertionError, match='refusing Alembic adoption'):
            migrate(pg_url)
        assert inspect(engine).get_table_names() == ['gate72_unknown']
        with engine.connect() as db:
            assert db.execute(text('SELECT note FROM gate72_unknown')).scalar_one() == 'synthetic preservation probe'
    finally:
        engine.dispose()


def test_current_head_and_private_runtime(pg_url):
    migrate(pg_url)
    migrate(pg_url)
    result = subprocess.run([sys.executable, '-m', 'alembic', 'current'],
        cwd=ROOT, env={**os.environ, 'DJ_DATABASE_URL': pg_url},
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'e72b4c9a6102 (head)' in result.stdout
    engine = create_engine(pg_url, hide_parameters=True)
    try:
        with engine.connect() as db:
            assert db.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'e72b4c9a6102'
            assert db.execute(text('SHOW server_version')).scalar_one().startswith('16.15')
            assert db.execute(text('SHOW listen_addresses')).scalar_one() == ''
    finally:
        engine.dispose()


@pytest.mark.parametrize('schema', ['empty', 'unknown', 'recognized'])
@pytest.mark.parametrize('read_only', [False, True])
def test_current_never_adopts_unstamped_database(pg_url, schema, read_only):
    if schema == 'recognized':
        migrate(pg_url)
    engine = create_engine(pg_url, hide_parameters=True)
    try:
        with engine.begin() as db:
            if schema == 'unknown':
                db.execute(text('CREATE TABLE gate72_unknown (id INTEGER PRIMARY KEY, note TEXT)'))
                db.execute(text("INSERT INTO gate72_unknown VALUES (1, 'synthetic preserved row')"))
            elif schema == 'recognized':
                db.execute(text('DROP TABLE alembic_version'))
                db.execute(text("""INSERT INTO users (id, public_id, display_name, created_at,
                    kind, status) VALUES (1, 'USR-gate72-introspection', 'Synthetic',
                    '2026-01-01', 'LEGACY', 'DISABLED')"""))
        def capture():
            with engine.connect() as db:
                metadata = MetaData()
                metadata.reflect(bind=db)
                rows = {name: db.execute(select(table).order_by(*table.primary_key.columns)).all()
                        for name, table in metadata.tables.items()}
                columns = db.execute(text("""SELECT table_name, column_name, data_type,
                    is_nullable, column_default FROM information_schema.columns
                    WHERE table_schema='public' ORDER BY table_name, ordinal_position""")).all()
                constraints = db.execute(text("""SELECT c.relname, p.conname,
                    pg_get_constraintdef(p.oid) FROM pg_constraint p
                    JOIN pg_class c ON c.oid=p.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='public' ORDER BY c.relname, p.conname""")).all()
                indexes = db.execute(text("""SELECT tablename, indexname, indexdef
                    FROM pg_indexes WHERE schemaname='public' ORDER BY tablename, indexname""")).all()
                return rows, columns, constraints, indexes
        before = capture()
        url = pg_url + ('&options=-c%20default_transaction_read_only%3Don' if read_only else '')
        result = subprocess.run([sys.executable, '-m', 'alembic', 'current'],
            cwd=ROOT, env={**os.environ, 'DJ_DATABASE_URL': url},
            capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == ''
        assert capture() == before
        assert 'alembic_version' not in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_current_propagates_unrelated_revision_error(pg_url):
    migrate(pg_url)
    script = """
from alembic import command, context
from alembic.config import Config
def unrelated():
    raise KeyError('gate72_unrelated_revision_error')
context.get_revision_argument = unrelated
command.current(Config('alembic.ini'))
"""
    result = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
        env={**os.environ, 'DJ_DATABASE_URL': pg_url},
        capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert "KeyError: 'gate72_unrelated_revision_error'" in result.stderr


@pytest.mark.parametrize('method,suffix', [('GET', s) for s in READS] + WRITES)
def test_owner_isolation(pg_raw_api, method, suffix):
    check_isolation(pg_raw_api, method, suffix)


@pytest.mark.parametrize('state', ['missing', 'invalid', 'expired', 'idle', 'revoked', 'disabled', 'logout'])
def test_session_denial(pg_raw_api, state):
    check_denial(pg_raw_api, state)


@pytest.mark.parametrize('bad', ['missing', 'wrong', 'other', 'origin', 'referer'])
def test_csrf_precedes_processing(pg_raw_api, bad):
    check_csrf(pg_raw_api, 'POST', '/process', bad)


def test_atomic_rate_limit(pg_raw_api):
    check_atomic_limit(pg_raw_api)


def test_rate_limit_reset(pg_raw_api):
    check_limit_reset(pg_raw_api)


def test_session_hashes_and_revocation(pg_raw_api):
    check_session(pg_raw_api)


def test_relogin_revokes_previous(pg_raw_api):
    check_relogin(pg_raw_api)


def test_session_touch(pg_raw_api):
    check_touch(pg_raw_api)


def test_upload_capacity_contention(pg_api, monkeypatch):
    check_capacity(pg_api, monkeypatch)


def test_runtime_revision_and_tcp_disabled(pg_url):
    migrate(pg_url)
    engine = create_engine(pg_url, hide_parameters=True)
    try:
        with engine.connect() as db:
            assert db.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'e72b4c9a6102'
            assert db.execute(text('SHOW server_version')).scalar_one().startswith('16.15')
            assert db.execute(text('SHOW listen_addresses')).scalar_one() == ''
    finally:
        engine.dispose()


def test_five_same_case_requests_one_execution(pg_api, monkeypatch):
    from sqlalchemy import event
    from app.ai.providers import MockProvider
    from app.ai.gateway import ModelGateway
    from app.domain.models import ProcessingRun
    from tests.next_phase.test_review_flow import create
    import app.api.routes as routes
    client, sessions, _ = pg_api
    cid = create(client)
    started, release, barrier, mutex = Event(), Event(), Barrier(5), Lock()
    dispatches = []
    locks = []
    engine = sessions.kw['bind']
    def record(conn, cursor, statement, parameters, context, executemany):
        if 'FOR UPDATE OF cases' in statement:
            locks.append(statement)
    event.listen(engine, 'before_cursor_execute', record)
    original = MockProvider.run
    constructor = ModelGateway.__init__
    def instrument(self, db, *args, **kwargs):
        constructor(self, db, *args, **kwargs)
        self.provider._test_session = db
    def held(self, prompt, *args):
        if prompt.prompt_id == 'artifact_classifier':
            self._test_session.commit()  # Same offline probe as the established two-request test.
            with mutex:
                dispatches.append(True)
            started.set()
            assert release.wait(10)
        return original(self, prompt, *args)
    pipeline = routes.run_case_pipeline
    def synchronized(db, case):
        barrier.wait(10)
        return pipeline(db, case)
    monkeypatch.setattr(ModelGateway, '__init__', instrument)
    monkeypatch.setattr(MockProvider, 'run', held)
    monkeypatch.setattr(routes, 'run_case_pipeline', synchronized)
    try:
        with ExitStack() as stack, ThreadPoolExecutor(max_workers=5) as pool:
            actors = [client] + [stack.enter_context(peer(client)) for _ in range(4)]
            futures = [pool.submit(actor.post, f'/api/cases/{cid}/process') for actor in actors]
            try:
                assert started.wait(10)
                done = wait(futures, timeout=3).done
                assert len(done) == 4
                assert all(f.result().status_code == 200 and
                           f.result().json()['status'] == 'PROCESSING' for f in done)
                assert len(dispatches) == 1
            finally:
                release.set()
            responses = [f.result(timeout=20) for f in futures]
        assert all(r.status_code == 200 for r in responses)
        assert len({r.json()['pipeline_run_id'] for r in responses}) == 1
        assert len(dispatches) == 1
        assert locks and all('WHERE cases.id =' in statement for statement in locks)
        with sessions() as db:
            run = db.query(ProcessingRun).filter_by(module='pipeline').one()
            assert run.attempt == 1 and run.status.value == 'SUCCEEDED'
            assert run.authority.value == 'ACTIVE'
    finally:
        event.remove(engine, 'before_cursor_execute', record)


def test_concurrent_dossier_versions(pg_api, monkeypatch):
    """Two requests read the same baseline; both edits must remain versioned."""
    from app.core.cases import dossier
    from app.domain.models import Case, DossierRevision
    from app.main import app
    from fastapi.testclient import TestClient
    client, sessions, _ = pg_api
    response = client.post('/api/cases', data={'question': 'Synthetic race probe'})
    assert response.status_code == 201
    cid = response.json()['case_id']
    initial = client.put(f'/api/cases/{cid}/dossier', json={'duration': 'baseline'})
    assert initial.status_code == 200
    baseline = initial.json()['case_version']
    barrier = Barrier(2)
    original = dossier.update
    def synchronized(db, case, patch):
        # Both authenticated dependencies have loaded the same Case version.
        # Synchronize before the critical section so a valid row lock can work.
        assert case.version == baseline
        barrier.wait(timeout=10)
        return original(db, case, patch)
    monkeypatch.setattr(dossier, 'update', synchronized)
    # Observe the real HTTP error instead of re-raising the server exception in
    # the test thread. Never publish session cookies or response token values.
    with TestClient(app, raise_server_exceptions=False) as a, \
            TestClient(app, raise_server_exceptions=False) as b, \
            ThreadPoolExecutor(max_workers=2) as pool:
        for actor in (a, b):
            actor.cookies.update(client.cookies)
            actor.headers.update(client.headers)
        futures = [pool.submit(actor.put, f'/api/cases/{cid}/dossier', json=patch)
                   for actor, patch in [(a, {'duration': 'synthetic edit A'}),
                                        (b, {'allergies': 'synthetic edit B'})]]
        responses = [f.result(timeout=20) for f in futures]
    with sessions() as db:
        case = db.query(Case).filter_by(public_id=cid).one()
        revisions = db.query(DossierRevision).filter_by(case_id=case.id).order_by(DossierRevision.id).all()
        observed = {'statuses': [r.status_code for r in responses],
                    'response_versions': [r.json()['case_version'] for r in responses if r.status_code == 200],
                    'stored_version': case.version,
                    'revision_versions': [r.case_version for r in revisions],
                    'history': [(r.duration, r.allergies) for r in revisions]}
        assert observed['statuses'] == [200, 200], observed
        assert observed['revision_versions'] == [baseline, baseline + 1, baseline + 2], observed
        assert case.version == baseline + 2, observed
        assert revisions[-1].duration == 'synthetic edit A', observed
        assert revisions[-1].allergies == 'synthetic edit B', observed
