from app.domain.models import User
from .helpers import register, login, PASSWORD


def test_login_me_and_safe_failures(api_client):
    client, sessions, _ = api_client
    assert client.get('/api/auth/me').status_code == 401
    assert register(client).status_code == 201
    wrong = login(client, password='incorrect synthetic passphrase').json()
    unknown = login(client, email='unknown@example.com').json()
    with sessions() as db:
        account = db.query(User).filter_by(kind='ACCOUNT').one()
        account.status = 'DISABLED'; db.commit()
    disabled = login(client).json()
    assert wrong == unknown == disabled
    with sessions() as db:
        db.query(User).filter_by(kind='ACCOUNT').one().status = 'ACTIVE'; db.commit()
    response = login(client, email='SYNTHETIC@example.COM')
    assert response.status_code == 200
    assert set(response.json()) == {'user', 'csrf_token'}
    me = client.get('/api/auth/me')
    assert me.status_code == 200
    assert set(me.json()) == {'public_id', 'email', 'email_verified'}
    assert PASSWORD not in me.text
    with sessions() as db:
        db.query(User).filter_by(kind='ACCOUNT').one().status = 'DISABLED'; db.commit()
    assert client.get('/api/auth/me').status_code == 401


def test_unknown_account_performs_dummy_verification(api_client, monkeypatch):
    from app.security import authentication
    client, _, _ = api_client
    calls = []
    original = authentication.verify_password
    def verify(encoded, password):
        calls.append(encoded)
        return original(encoded, password)
    monkeypatch.setattr(authentication, 'verify_password', verify)
    assert login(client, email='missing@example.com').status_code == 401
    assert len(calls) == 1 and calls[0].startswith('$argon2id$')


def test_foundation_is_disabled_by_default(api_client, regression_settings, monkeypatch):
    from app.config import Settings
    assert Settings.model_fields['auth_foundation_enabled'].default is False
    monkeypatch.setattr(regression_settings, 'auth_foundation_enabled', False)
    client, _, _ = api_client
    for route in ('csrf','me'):
        assert client.get('/api/auth/'+route).status_code == 404
    # Gate 2 fails closed even when account issuance is disabled.
    created = client.post('/api/cases', data={'question':'Synthetic Gate 1 boundary'})
    assert created.status_code == 401
    assert created.json()['detail']['code'] == 'AUTH_REQUIRED'
    assert client.get('/api/cases/CASE-unknown').status_code == 401


def test_database_failure_is_not_reported_as_bad_credentials(api_client, monkeypatch):
    from .helpers import csrf
    from fastapi.testclient import TestClient
    from app.main import app
    client, sessions, _ = api_client
    register(client)
    headers = csrf(client)
    def fail(*args, **kwargs):
        raise RuntimeError('SYNTHETIC_DATABASE_FAILURE')
    monkeypatch.setattr(sessions.class_, 'commit', fail)
    with TestClient(app, raise_server_exceptions=False) as failed:
        failed.cookies.update(client.cookies)
        response = failed.post('/api/auth/login', json={'email':'Synthetic@example.com','password':PASSWORD}, headers=headers)
    assert response.status_code == 500
    assert PASSWORD not in response.text and 'Set-Cookie' not in response.headers
