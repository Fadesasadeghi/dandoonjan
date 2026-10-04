"""Tests first: ACCOUNT and Demo admission before case-scoped work."""
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from tests.auth.helpers import register, login

READS = ['', '/dossier', '/status', '/assessment', '/report']
WRITES = [('PATCH', ''), ('PUT', '/dossier'), ('POST', '/artifacts'), ('POST', '/process')]
NOT_FOUND = {'detail': {'code': 'CASE_NOT_FOUND', 'message_fa': 'پرونده در دسترس نیست.'}}


def actor(client, email):
    assert register(client, email).status_code == 201
    response = login(client, email)
    assert response.status_code == 200
    return {'Origin': 'http://testserver', 'X-CSRF-Token': response.json()['csrf_token']}


def demo(client):
    response = client.post('/api/demo/session', headers={'Origin': 'http://testserver'})
    assert response.status_code == 200
    return {'Origin': 'http://testserver', 'X-CSRF-Token': response.json()['csrf_token']}


def create(client, headers, prefix='/api/cases'):
    response = client.post(prefix, data={'question': 'Synthetic question'}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()['case_id']


def request(client, method, path, headers=None):
    args = {'headers': headers or {}}
    if method == 'PUT': args['json'] = {'symptoms': 'synthetic'}
    if method == 'POST' and path.endswith('/cases'): args['data'] = {'question': 'synthetic'}
    if method == 'PATCH': args['data'] = {'question': 'synthetic edited'}
    if path.endswith('/artifacts'): args['files'] = {'file': ('synthetic.txt', b'Treatment Plan Tooth 46 RCT', 'text/plain')}
    return client.request(method, path, **args)


@pytest.mark.parametrize('method,suffix', [('GET', s) for s in READS] + WRITES)
def test_normal_route_isolation(api_client, method, suffix):
    from app.main import app
    from app.domain.models import Case, User, public_id
    client, factory, _ = api_client
    ah = actor(client, 'a@example.com'); a = create(client, ah)
    with TestClient(app) as b, TestClient(app) as anonymous:
        bh = actor(b, 'b@example.com'); bc = create(b, bh)
        with factory() as db:
            legacy = User(public_id=public_id('USR')); db.add(legacy); db.flush()
            old = Case(public_id=public_id('CASE'), user_id=legacy.id); db.add(old); db.commit(); oldid = old.public_id
            assert db.query(Case).filter_by(public_id=a).one().user_id == db.query(User).filter_by(normalized_email='a@example.com').one().id
            assert db.query(Case).filter_by(public_id=bc).one().user_id == db.query(User).filter_by(normalized_email='b@example.com').one().id
        dh = demo(anonymous); dc = create(anonymous, dh, '/api/demo/cases')
        for caller, headers, own, foreign in [(client, ah, a, bc), (b, bh, bc, a)]:
            responses = [request(caller, method, '/api/cases/'+cid+suffix, headers) for cid in (foreign, 'CASE-absent', oldid, dc)]
            assert all(r.status_code == 404 and r.json() == NOT_FOUND for r in responses)
            owner = request(caller, method, '/api/cases/'+own+suffix, headers)
            assert owner.status_code in ({200, 201} if suffix != '/report' else {404})
            if suffix == '/report': assert owner.json()['detail'] == 'REPORT_NOT_READY'
        denied = request(anonymous, method, '/api/cases/'+a+suffix, dh)
        assert denied.status_code == 401 and denied.json()['detail']['code'] == 'AUTH_REQUIRED'


@pytest.mark.parametrize('method,suffix', [('POST', None)] + WRITES)
@pytest.mark.parametrize('bad', ['missing','wrong','other','origin','referer'])
def test_csrf_before_case_work(api_client, method, suffix, bad):
    client, _, _ = api_client
    headers = actor(client, 'csrf@example.com')
    if bad == 'missing': headers.pop('X-CSRF-Token')
    if bad == 'wrong': headers['X-CSRF-Token'] = 'b'*64
    if bad == 'other':
        from app.main import app
        with TestClient(app) as other:
            headers['X-CSRF-Token'] = actor(other, 'othercsrf@example.com')['X-CSRF-Token']
    if bad == 'origin': headers['Origin'] = 'https://evil.example'
    if bad == 'referer': headers = {'Referer': 'https://evil.example/path', 'X-CSRF-Token': headers['X-CSRF-Token']}
    path = '/api/cases' if suffix is None else '/api/cases/CASE-absent'+suffix
    response = request(client, method, path, headers)
    assert response.status_code == 403 and response.json()['detail']['code'] == 'CSRF_FAILED'


@pytest.mark.parametrize('state', ['missing','invalid','expired','idle','revoked','disabled','logout'])
def test_session_denial(api_client, state):
    from app.domain.models import AuthSession, User, utcnow
    from app.security.sessions import cookie_name
    client, factory, _ = api_client
    headers = actor(client, 'session@example.com'); cid = create(client, headers)
    if state == 'missing': client.cookies.clear()
    elif state == 'invalid':
        client.cookies.clear(); client.cookies.set(cookie_name(), 'x')
    elif state == 'logout': assert client.post('/api/auth/logout', headers=headers).status_code == 204
    else:
        with factory() as db:
            row = db.query(AuthSession).one()
            if state == 'expired': row.expires_at = utcnow()-timedelta(seconds=1)
            if state == 'idle': row.last_seen_at = utcnow()-timedelta(minutes=31)
            if state == 'revoked': row.revoked_at = utcnow()
            if state == 'disabled': db.query(User).filter_by(kind='ACCOUNT').one().status = 'DISABLED'
            db.commit()
    response = client.get('/api/cases/'+cid)
    assert response.status_code == 401 and response.json()['detail']['code'] == 'AUTH_REQUIRED'


def test_creation_requires_session_even_flag_disabled(api_client, regression_settings, monkeypatch):
    client, _, _ = api_client
    monkeypatch.setattr(regression_settings, 'auth_foundation_enabled', False)
    response = client.post('/api/cases', data={'question':'synthetic'})
    assert response.status_code == 401 and response.json()['detail']['code'] == 'AUTH_REQUIRED'


@pytest.mark.parametrize('method,suffix', [('GET', s) for s in READS] + WRITES)
def test_demo_route_isolation(api_client, method, suffix):
    from app.main import app
    client, _, _ = api_client
    ah = demo(client); a = create(client, ah, '/api/demo/cases')
    with TestClient(app) as b, TestClient(app) as account:
        bh = demo(b); bc = create(b, bh, '/api/demo/cases')
        nh = actor(account, 'normal@example.com'); nc = create(account, nh)
        for caller, headers, own, foreign in [(client, ah, a, bc), (b, bh, bc, a)]:
            for cid in [foreign, nc, 'CASE-absent']:
                r = request(caller, method, '/api/demo/cases/'+cid+suffix, headers)
                assert r.status_code == 404 and r.json() == NOT_FOUND
            r = request(caller, method, '/api/demo/cases/'+own+suffix, headers)
            assert r.status_code in ({200,201} if suffix != '/report' else {404})
        assert request(account, method, '/api/demo/cases/'+a+suffix, nh).status_code == 401
        assert request(client, method, '/api/cases/'+nc+suffix, ah).status_code == 401


def test_denied_work_and_upload_touch(api_client, monkeypatch):
    from app.main import app
    from app.domain.models import Artifact, AuditEvent, AuthSession, Case, utcnow
    import app.api.routes as routes
    import app.security.ingestion as storage
    import app.pipeline.orchestrator as pipeline
    client, factory, store = api_client
    ah = actor(client, 'owner@example.com'); cid = create(client, ah)
    with TestClient(app) as b:
        bh = actor(b, 'foreign@example.com')
        with factory() as db:
            before = (db.query(Artifact).count(), db.query(AuditEvent).count(), db.query(Case).one().version)
        for name, module in [('run_case_pipeline', routes), ('effective_input_hash', pipeline), ('read_bytes', storage)]:
            monkeypatch.setattr(module, name, lambda *a, **kw: pytest.fail('Unauthorized clinical work'))
        for suffix in ['/artifacts','/process']:
            assert request(b, 'POST', '/api/cases/'+cid+suffix, bh).status_code == 404
        assert b.get('/api/cases/'+cid+'/report').json() == NOT_FOUND
        with factory() as db:
            assert before == (db.query(Artifact).count(), db.query(AuditEvent).count(), db.query(Case).one().version)
        assert not list(store.rglob('*'))
    with factory() as db:
        row = db.query(AuthSession).join(__import__('app.domain.models', fromlist=['User']).User).filter_by(normalized_email='owner@example.com').one()
        row.last_seen_at = utcnow()-timedelta(minutes=6); db.commit()
    assert request(client, 'POST', '/api/cases/'+cid+'/artifacts', ah).status_code == 201
    duplicate = request(client, 'POST', '/api/cases/'+cid+'/artifacts', ah)
    assert duplicate.status_code == 201 and duplicate.json()['duplicate_of']
