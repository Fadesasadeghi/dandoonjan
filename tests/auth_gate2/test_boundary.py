"""Ordering, identity preservation and concurrent admissions; synthetic only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from tests.auth_gate2.test_access import actor, demo, create, request, NOT_FOUND, WRITES
from tests.auth.helpers import register


@pytest.mark.parametrize('prefix,code', [('/api/cases','AUTH_REQUIRED'),('/api/demo/cases','DEMO_AUTH_REQUIRED')])
def test_auth_before_malformed_body(api_client, prefix, code):
    client, _, _ = api_client
    r = client.put(prefix+'/CASE-any/dossier', content='{broken', headers={'Content-Type':'application/json'})
    assert r.status_code == 401 and r.json()['detail']['code'] == code


@pytest.mark.parametrize('method,suffix', WRITES)
def test_demo_csrf_before_lookup(api_client, method, suffix):
    client, _, _ = api_client
    headers = demo(client)
    for bad in [{}, {**headers,'X-CSRF-Token':'a'*64}, {**headers,'Origin':'https://evil.example'},
                {'X-CSRF-Token':headers['X-CSRF-Token'],'Referer':'https://evil.example/path'}]:
        response = request(client, method, '/api/demo/cases/CASE-missing'+suffix, bad)
        assert response.status_code == 403 and response.json()['detail']['code'] == 'CSRF_FAILED'


@pytest.mark.parametrize('state', ['expired','idle','revoked','invalid'])
def test_demo_expiration_never_claims(api_client, state):
    from app.domain.models import DemoVisitor, Case, utcnow
    from app.security.demo_sessions import cookie_name
    client, factory, _ = api_client
    headers = demo(client); cid = create(client, headers, '/api/demo/cases')
    with factory() as db:
        row = db.query(DemoVisitor).one(); olduser = row.user_id
        if state == 'expired': row.expires_at = utcnow()-timedelta(seconds=1)
        if state == 'idle': row.last_seen_at = utcnow()-timedelta(minutes=31)
        if state == 'revoked': row.revoked_at = utcnow()
        db.commit()
    if state == 'invalid':
        client.cookies.clear(); client.cookies.set(cookie_name(), 'bad')
    assert client.get('/api/demo/cases/'+cid).status_code == 401
    new = demo(client)
    assert client.get('/api/demo/cases/'+cid).json() == NOT_FOUND
    assert create(client, new, '/api/demo/cases') != cid
    with factory() as db:
        assert db.query(Case).filter_by(public_id=cid).one().user_id == olduser
        assert db.query(DemoVisitor).count() == 2


def test_mixed_cookies_marker_spoof_and_legacy(api_client, monkeypatch):
    from app.domain.models import Case, User, public_id
    from app.core.cases.sample import DEMO_MARKER, is_demo
    import app.ai.gateway as gateway
    client, factory, _ = api_client
    nh = actor(client, 'mixed@example.com'); nc = create(client, nh)
    dh = demo(client); dc = create(client, dh, '/api/demo/cases')
    with factory() as db:
        legacy = User(public_id=public_id('USR')); db.add(legacy); db.flush()
        old = Case(public_id=public_id('CASE'), user_id=legacy.id, context_text=DEMO_MARKER)
        db.add(old); db.commit(); oldid, owner = old.public_id, old.user_id
    for prefix, headers, allowed, denied in [('/api/cases',nh,nc,dc),('/api/demo/cases',dh,dc,nc)]:
        assert client.get(prefix+'/'+allowed).status_code == 200
        for cid in [denied, oldid, 'CASE-missing']:
            assert client.get(prefix+'/'+cid).json() == NOT_FOUND
    assert client.patch('/api/cases/'+nc, headers=nh, data={'context':DEMO_MARKER,'sample':'true'}).status_code == 200
    assert client.patch('/api/demo/cases/'+dc, headers=dh, data={'context':'escape'}).status_code == 200
    with factory() as db:
        assert not is_demo(db.query(Case).filter_by(public_id=nc).one())
        assert is_demo(db.query(Case).filter_by(public_id=dc).one())
        assert not is_demo(db.query(Case).filter_by(public_id=oldid).one())
    assert register(client,'fresh@example.com').status_code == 201
    with factory() as db:
        assert db.query(Case).filter_by(public_id=oldid).one().user_id == owner


def test_demo_provider_hash_and_authority_independent_of_credentials(api_client, regression_settings, monkeypatch):
    from app.domain.models import Case, DemoVisitor, AssessmentSnapshot, Report, ProcessingRun
    from app.pipeline.orchestrator import effective_input_hash
    from app.governance.immutability import verify_snapshot_integrity
    import app.ai.gateway as gateway
    client, factory, _ = api_client
    headers = demo(client); cid = create(client, headers, '/api/demo/cases'); path = '/api/demo/cases/'+cid
    assert client.put(path+'/dossier', json={'symptoms':'Synthetic cold sensitivity'}, headers=headers).status_code == 200
    assert request(client,'POST',path+'/artifacts',headers).status_code == 201
    monkeypatch.setattr(regression_settings,'ai_provider','openrouter')
    monkeypatch.setattr(gateway,'OpenRouterProvider',lambda **kw: pytest.fail('Real provider constructed for Demo'))
    result = client.post(path+'/process',headers=headers).json()
    assert result['report']
    before = client.get(path+'/report').json()
    with factory() as db:
        case = db.query(Case).one(); h = effective_input_hash(db,case)
        snap = db.query(AssessmentSnapshot).one(); frozen = deepcopy(snap.payload)
        versions = deepcopy(snap.versions); identity = (snap.public_id, snap.derivation_run_id, snap.content_hash)
        report = deepcopy(db.query(Report).one().content)
        visitor = db.query(DemoVisitor).one()
        visitor.token_hash = 'c'*64; visitor.csrf_token_hash = 'd'*64
        visitor.revoked_at = __import__('app.domain.models',fromlist=['utcnow']).utcnow()
        db.commit()
    with factory() as db:
        assert effective_input_hash(db,db.query(Case).one()) == h
        snap = db.query(AssessmentSnapshot).one()
        assert (snap.public_id,snap.derivation_run_id,snap.content_hash) == identity
        assert snap.payload == frozen and snap.versions == versions and verify_snapshot_integrity(snap)
        assert db.query(Report).one().content == report
        assert db.query(ProcessingRun).filter_by(module='pipeline').one().authority.value == 'ACTIVE'
        assert not any(key in str(frozen) for key in ['user_id','token_hash','csrf_token_hash','visitor_id'])
    assert before['review']['run']['provider'] == 'mock'
    assert client.get(path+'/report').status_code == 401


def test_no_second_case_or_child_query_on_denial(api_client):
    client, factory, _ = api_client
    headers = actor(client,'queries@example.com'); create(client,headers)
    statements = []
    engine = factory.kw['bind']
    def record(conn,cursor,statement,parameters,context,executemany): statements.append(statement.lower())
    event.listen(engine,'before_cursor_execute',record)
    try:
        assert client.get('/api/cases/CASE-missing/report').json() == NOT_FOUND
    finally:
        event.remove(engine,'before_cursor_execute',record)
    assert len([s for s in statements if 'from cases' in s]) == 1
    assert not any(any(t in s for t in ['assessment_snapshots','processing_runs','artifacts','dossier_revisions','reports']) for s in statements)


def test_parallel_demo_bootstrap_and_account_uploads(api_client):
    from app.main import app
    from app.domain.models import DemoVisitor, Artifact, Case
    client, factory, _ = api_client
    def bootstrap(n):
        with TestClient(app) as visitor:
            headers = demo(visitor)
            return create(visitor,headers,'/api/demo/cases')
    with ThreadPoolExecutor(max_workers=2) as pool:
        cases = list(pool.map(bootstrap,range(2)))
    with factory() as db:
        assert len({r.user_id for r in db.query(DemoVisitor)}) == 2
    def upload(n):
        with TestClient(app) as account:
            headers = actor(account,f'parallel{n}@example.com'); cid = create(account,headers)
            response = request(account,'POST','/api/cases/'+cid+'/artifacts',headers)
            assert response.status_code == 201
            return cid,response.json()['artifact_id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(upload,range(2)))
    with factory() as db:
        for cid,aid in results:
            assert db.query(Artifact).filter_by(public_id=aid).one().case_id == db.query(Case).filter_by(public_id=cid).one().id


def test_five_parallel_processing_requests(api_client):
    from contextlib import ExitStack
    from app.main import app
    from app.domain.models import ProcessingRun
    _, factory, _ = api_client
    with ExitStack() as stack:
        actors = []
        for n in range(5):
            client = stack.enter_context(TestClient(app))
            headers = actor(client,f'processing{n}@example.com')
            cid = create(client,headers)
            assert request(client,'POST','/api/cases/'+cid+'/artifacts',headers).status_code == 201
            actors.append((client,headers,cid))
        def process(item):
            client,headers,cid = item
            response = client.post('/api/cases/'+cid+'/process',headers=headers)
            assert response.status_code == 200 and response.json()['report']
            assert client.get('/api/cases/'+cid+'/report').json()['case_id'] == cid
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(process,actors))
        for n,(client,_,_) in enumerate(actors):
            assert client.get('/api/cases/'+actors[(n+1)%5][2]+'/report').json() == NOT_FOUND
    with factory() as db:
        assert db.query(ProcessingRun).filter_by(module='pipeline',status='SUCCEEDED').count() == 5


def test_logout_after_admission_may_finish_but_new_request_fails(api_client, monkeypatch):
    from threading import Event
    from app.main import app
    import app.api.routes as routes
    client, _, _ = api_client
    headers = actor(client,'admission@example.com'); cid = create(client,headers)
    admitted, release = Event(), Event()
    original = routes.run_case_pipeline
    def held(db,case):
        admitted.set()
        assert release.wait(15)
        return original(db,case)
    monkeypatch.setattr(routes,'run_case_pipeline',held)
    with TestClient(app) as logout, ThreadPoolExecutor(max_workers=1) as pool:
        logout.cookies.update(client.cookies)
        future = pool.submit(client.post,'/api/cases/'+cid+'/process',headers=headers)
        try:
            assert admitted.wait(15)
            assert logout.post('/api/auth/logout',headers=headers).status_code == 204
            assert client.get('/api/cases/'+cid).status_code == 401
        finally:
            release.set()
        assert future.result(timeout=30).status_code == 200
