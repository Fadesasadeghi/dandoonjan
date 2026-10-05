"""Real ACCOUNT admission, file-backed disposable SQLite, synchronized requests."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import timedelta
from threading import Barrier, Event, Lock

import pytest
from fastapi.testclient import TestClient

from tests.next_phase.test_review_flow import create


def peer(client):
    from app.main import app
    result = TestClient(app)
    result.cookies.update(client.cookies)
    result.headers.update(client.headers)
    return result


@pytest.mark.parametrize('contention', ['simultaneous_claim', 'during_dispatch'])
def test_same_case_has_one_execution_and_reconciles(api_client, monkeypatch, contention):
    from app.ai.providers import MockProvider
    from app.ai.gateway import ModelGateway
    from app.domain.models import ProcessingRun
    client, factory, _ = api_client
    cid = create(client)
    admitted, release, second_dispatch = Event(), Event(), Event()
    start = Barrier(2)
    mutex = Lock()
    count = 0
    entrants = 0
    original = MockProvider.run
    constructor = ModelGateway.__init__
    def instrument(self, db, *args, **kwargs):
        constructor(self, db, *args, **kwargs)
        self.provider._test_session = db
    monkeypatch.setattr(ModelGateway, '__init__', instrument)
    def held(self, prompt, *args):
        nonlocal count
        if prompt.prompt_id == 'artifact_classifier':
            # Remove incidental SQLite stage locks from the baseline probe. A DB
            # writer lock must not be the mechanism that protects provider work;
            # PostgreSQL does not globally serialize these independent writes.
            self._test_session.commit()
            with mutex:
                count += 1
                if count > 1: second_dispatch.set()
            admitted.set()
            assert release.wait(10)
        return original(self, prompt, *args)
    monkeypatch.setattr(MockProvider, 'run', held)
    # Synchronize both authenticated requests just before the pipeline.
    import app.api.routes as routes
    pipeline = routes.run_case_pipeline
    def synchronized(db, case):
        nonlocal entrants
        start.wait(10)
        with mutex:
            entrants += 1
            position = entrants
        if contention == 'during_dispatch' and position == 2:
            assert admitted.wait(10)
        return pipeline(db, case)
    monkeypatch.setattr(routes, 'run_case_pipeline', synchronized)
    with peer(client) as other, ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(actor.post, f'/api/cases/{cid}/process') for actor in (client, other)]
        try:
            assert admitted.wait(10)
            # Safe implementation returns the second response while the first is held.
            done = wait(futures, timeout=2, return_when=FIRST_COMPLETED).done
            assert done, f'Second request did not reconcile; classifier dispatches={count}'
            response = next(iter(done)).result()
            assert response.status_code == 200
            pending = response.json()
            assert pending['status'] == 'PROCESSING' and pending['report'] is None
            assert not pending['reused']
            assert not second_dispatch.is_set()
        finally:
            release.set()
        responses = [f.result(timeout=15) for f in futures]
    assert count == 1
    with factory() as db:
        runs = db.query(ProcessingRun).filter_by(module='pipeline').all()
        assert len(runs) == 1 and runs[0].attempt == 1
        assert runs[0].status.value == 'SUCCEEDED' and runs[0].authority.value == 'ACTIVE'
    assert len({r.json()['pipeline_run_id'] for r in responses}) == 1
    monkeypatch.setattr(routes, 'run_case_pipeline', pipeline)
    assert client.post(f'/api/cases/{cid}/process').json()['reused']
    assert count == 1


def test_different_cases_overlap(api_client, monkeypatch):
    from app.ai.providers import MockProvider
    client, _, _ = api_client
    ids = [create(client), create(client)]
    barrier = Barrier(2)
    original = MockProvider.run
    def held(self, prompt, *args):
        if prompt.prompt_id == 'artifact_classifier': barrier.wait(10)
        return original(self, prompt, *args)
    monkeypatch.setattr(MockProvider, 'run', held)
    with peer(client) as other, ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(actor.post, f'/api/cases/{cid}/process')
                   for actor, cid in zip((client, other), ids)]
        assert all(f.result(timeout=20).json()['report'] for f in futures)


@pytest.mark.parametrize('mutation', ['dossier', 'case', 'artifact'])
def test_mutation_cannot_activate_obsolete_result(api_client, monkeypatch, mutation):
    from app.ai.providers import MockProvider
    from app.domain.models import ProcessingRun, AssessmentSnapshot
    client, factory, _ = api_client
    cid = create(client)
    entered, release = Event(), Event()
    original = MockProvider.run
    def held(self, prompt, *args):
        if prompt.prompt_id == 'artifact_classifier':
            entered.set()
            assert release.wait(10)
        return original(self, prompt, *args)
    monkeypatch.setattr(MockProvider, 'run', held)
    with peer(client) as other, ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, f'/api/cases/{cid}/process')
        try:
            assert entered.wait(10)
            if mutation == 'dossier':
                response = other.put(f'/api/cases/{cid}/dossier', json={'duration': '4 synthetic days'})
            elif mutation == 'case':
                response = other.patch(f'/api/cases/{cid}', data={'question': 'Changed synthetic question'})
            else:
                response = other.post(f'/api/cases/{cid}/artifacts', files={
                    'file': ('synthetic-note.txt', b'SYNTHETIC note only', 'text/plain')})
            assert response.status_code in (200, 201)
        finally:
            release.set()
        result = future.result(timeout=20).json()
    assert result['status'] == 'FAILED' and result['report'] is None
    assert result['error_code'] == 'PROCESSING_INPUT_CHANGED'
    with factory() as db:
        run = db.query(ProcessingRun).filter_by(module='pipeline').one()
        assert run.status.value == 'FAILED' and run.authority.value == 'NON_AUTHORITATIVE'
        assert db.query(AssessmentSnapshot).count() == 0
    assert client.get(f'/api/cases/{cid}/report').status_code == 404


def test_interrupted_running_blocks_replay_and_preserves_history(api_client, monkeypatch):
    from app.ai.providers import MockProvider
    from app.domain.models import Case, ProcessingRun, utcnow, public_id, AssessmentSnapshot
    from app.domain.enums import ProcessingRunStatus, RunAuthority
    client, factory, _ = api_client
    cid = create(client)
    assert client.post(f'/api/cases/{cid}/process').json()['report']
    with factory() as db:
        case = db.query(Case).filter_by(public_id=cid).one()
        old = db.query(ProcessingRun).filter_by(case_id=case.id, module='pipeline').one()
        frozen = db.query(AssessmentSnapshot).one().content_hash
        pending = ProcessingRun(public_id=public_id('RUN'), case_id=case.id, module='pipeline',
            input_hash=old.input_hash, input_version=old.input_version, attempt=2,
            status=ProcessingRunStatus.RUNNING, authority=RunAuthority.NON_AUTHORITATIVE,
            started_at=utcnow()-timedelta(days=2))
        db.add(pending); db.commit()
        pending_id = pending.public_id
    monkeypatch.setattr(MockProvider, 'run', lambda *a: pytest.fail('Interrupted work replayed'))
    result = client.post(f'/api/cases/{cid}/process').json()
    assert result['status'] == 'PROCESSING' and result['pipeline_run_id'] == pending_id
    assert result['report'] is None and not result['reused']
    assert client.get(f'/api/cases/{cid}/report').status_code == 404
    with factory() as db:
        assert db.query(ProcessingRun).filter_by(module='pipeline').count() == 2
        assert db.query(AssessmentSnapshot).one().content_hash == frozen
        assert db.query(ProcessingRun).filter_by(public_id=pending_id).one().authority.value == 'NON_AUTHORITATIVE'
    # A separate interpreter has no knowledge of the previous execution. Durable
    # records must still block replay without assuming timeout means cancellation.
    import json
    import os
    import subprocess
    import sys
    script = '''
import json, sys
from app.db import SessionLocal
from app.domain.models import Case
from app.ai.gateway import ModelGateway
from app.pipeline.orchestrator import run_case_pipeline
def forbidden(*a, **kw): raise AssertionError('PROVIDER_CONSTRUCTION_FORBIDDEN')
ModelGateway.__init__ = forbidden
with SessionLocal() as db:
    case = db.query(Case).filter_by(public_id=sys.argv[1]).one()
    value = run_case_pipeline(db, case)
    print(json.dumps({k:value[k] for k in ('status','reused','report')}))
'''
    result = subprocess.run([sys.executable, '-c', script, cid], capture_output=True,
        text=True, timeout=15, env={**os.environ, 'DJ_DATABASE_URL': regression_url(factory)})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'status': 'PROCESSING', 'reused': False, 'report': None}


def regression_url(factory):
    return factory.kw['bind'].url.render_as_string(hide_password=True)


def test_postgresql_lock_statement_is_case_scoped():
    from types import SimpleNamespace
    from sqlalchemy.dialects.postgresql import dialect
    from sqlalchemy.orm import Query
    from app.pipeline.runs import lock_case
    statements = []
    class Capture(Query):
        def one(self):
            statements.append(self.statement.compile(dialect=dialect()))
            return (23,)
    db = SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name='postgresql')),
                         query=lambda *entities: Capture(entities))
    lock_case(db, 23)
    assert 'FOR UPDATE OF cases' in str(statements[0])
    assert 'WHERE cases.id =' in str(statements[0])
    assert list(statements[0].params.values()) == [23]


def test_edit_at_snapshot_boundary_never_commits_authority(api_client, monkeypatch):
    from app.pipeline import reporting
    from app.domain.models import ProcessingRun, AssessmentSnapshot
    client, factory, _ = api_client
    cid = create(client)
    original = reporting.create_snapshot
    with peer(client) as other:
        def changed(db, case, *args):
            assert other.put(f'/api/cases/{cid}/dossier', json={'duration': 'late synthetic edit'}).status_code == 200
            return original(db, case, *args)
        monkeypatch.setattr(reporting, 'create_snapshot', changed)
        result = client.post(f'/api/cases/{cid}/process').json()
    assert result['status'] == 'FAILED' and result['error_code'] == 'PROCESSING_INPUT_CHANGED'
    with factory() as db:
        assert db.query(AssessmentSnapshot).count() == 0
        run = db.query(ProcessingRun).filter_by(module='pipeline').one()
        assert run.authority.value == 'NON_AUTHORITATIVE'
        assert not db.query(ProcessingRun).filter_by(status='RUNNING').all()
    assert client.get(f'/api/cases/{cid}/report').status_code == 404


def test_attempts_after_failure_are_serial_and_current(api_client, monkeypatch):
    from app.ai.providers import MockProvider
    from app.errors import ProviderUnavailableError
    from app.domain.models import ProcessingRun
    client, factory, _ = api_client
    cid = create(client)
    original = MockProvider.run
    def fail(*a): raise ProviderUnavailableError(category='authentication')
    monkeypatch.setattr(MockProvider, 'run', fail)
    failed = client.post(f'/api/cases/{cid}/process').json()
    assert failed['status'] == 'FAILED'
    monkeypatch.setattr(MockProvider, 'run', original)
    assert client.post(f'/api/cases/{cid}/process').json()['report']
    with factory() as db:
        runs = db.query(ProcessingRun).filter_by(module='pipeline').order_by(ProcessingRun.id).all()
        assert [r.attempt for r in runs] == [1, 2]
        assert [r.authority.value for r in runs] == ['NON_AUTHORITATIVE', 'ACTIVE']


def test_auth_denial_before_gateway(raw_api_client, regression_settings, monkeypatch):
    from app.ai.gateway import ModelGateway
    from tests.auth.helpers import register, login
    client, factory, _ = raw_api_client
    monkeypatch.setattr(regression_settings, 'auth_foundation_enabled', True)
    monkeypatch.setattr(regression_settings, 'auth_allowed_origins', ['http://testserver'])
    assert register(client, 'synthetic-a@example.com').status_code == 201
    logged = login(client, 'synthetic-a@example.com')
    client.headers.update({'Origin': 'http://testserver', 'X-CSRF-Token': logged.json()['csrf_token']})
    cid = create(client)
    monkeypatch.setattr(ModelGateway, '__init__', lambda *a, **kw: pytest.fail('Denied provider construction'))
    with peer(client) as other:
        other.cookies.clear()
        assert other.post(f'/api/cases/{cid}/process').status_code == 401
        assert register(other, 'synthetic-b@example.com').status_code == 201
        logged = login(other, 'synthetic-b@example.com')
        other.headers.update({'X-CSRF-Token': logged.json()['csrf_token']})
        assert other.post(f'/api/cases/{cid}/process').status_code == 404
    from app.domain.models import AuthSession, utcnow
    with factory() as db:
        for row in db.query(AuthSession): row.expires_at = utcnow()-timedelta(seconds=1)
        db.commit()
    assert client.post(f'/api/cases/{cid}/process').status_code == 401
