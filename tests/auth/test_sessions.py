from datetime import timedelta
import hashlib

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.models import utcnow
from .helpers import register, login


def test_hash_only_storage_fixation_and_revocation(api_client):
    from app.domain.models import AuthSession
    from app.security.sessions import cookie_name, revoke_all
    client, sessions, _ = api_client
    register(client)
    client.cookies.set(cookie_name(), 'a'*64)
    response = login(client)
    raw = client.cookies.get(cookie_name(), domain='testserver.local')
    assert raw and raw != 'a'*64 and len(bytes.fromhex(raw)) == 32
    with sessions() as db:
        session = db.query(AuthSession).one()
        assert session.token_hash == hashlib.sha256(raw.encode()).hexdigest()
        assert session.csrf_token_hash == hashlib.sha256(response.json()['csrf_token'].encode()).hexdigest()
        assert raw not in str(session.__dict__)
        db.add(AuthSession(user_id=session.user_id, token_hash=session.token_hash, csrf_token_hash='b'*64,
                           expires_at=utcnow()+timedelta(hours=1)))
        with pytest.raises(IntegrityError): db.flush()
        db.rollback()
        revoke_all(db, session.user_id); db.commit()
    client.cookies.clear(); client.cookies.set(cookie_name(), raw)
    assert client.get('/api/auth/me').status_code == 401


@pytest.mark.parametrize('field,age', [('expires_at', timedelta(seconds=1)), ('last_seen_at', timedelta(minutes=31)), ('revoked_at', timedelta(seconds=1))])
def test_expiration_and_revocation(api_client, field, age):
    from app.domain.models import AuthSession
    client, sessions, _ = api_client
    register(client); login(client)
    with sessions() as db:
        setattr(db.query(AuthSession).one(), field, utcnow()-age); db.commit()
    assert client.get('/api/auth/me').status_code == 401


def test_last_seen_is_bounded(api_client):
    from app.domain.models import AuthSession
    client, sessions, _ = api_client
    register(client); login(client)
    with sessions() as db: before = db.query(AuthSession).one().last_seen_at
    assert client.get('/api/auth/me').status_code == 200
    with sessions() as db: assert db.query(AuthSession).one().last_seen_at == before
    with sessions() as db:
        db.query(AuthSession).one().last_seen_at = utcnow()-timedelta(minutes=6); db.commit()
    assert client.get('/api/auth/me').status_code == 200
    with sessions() as db:
        from app.security.sessions import as_utc
        assert as_utc(db.query(AuthSession).one().last_seen_at) > utcnow()-timedelta(minutes=1)


@pytest.mark.parametrize('token', ['x'*10000, 'wrong', 'g'*64, 'a'*63], ids=['oversized','short','invalid-hex','wrong-length'])
def test_malformed_token_rejected_before_lookup(api_client, token):
    from app.security.sessions import cookie_name
    from sqlalchemy import event
    client, sessions, _ = api_client
    statements = []
    engine = sessions.kw['bind']
    def record(conn, cursor, statement, parameters, context, executemany): statements.append(statement)
    event.listen(engine, 'before_cursor_execute', record)
    try:
        client.cookies.set(cookie_name(), token)
        assert client.get('/api/auth/me').status_code == 401
        assert not statements
    finally: event.remove(engine, 'before_cursor_execute', record)


def test_development_cookie_flags(api_client):
    client, _, _ = api_client
    register(client)
    cookie = login(client).headers['set-cookie']
    assert 'dandoonjan_dev_session=' in cookie
    assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie and 'Path=/' in cookie
    assert 'Secure' not in cookie and 'Domain=' not in cookie


def test_production_cookie_and_fail_closed(api_client, regression_settings, monkeypatch):
    from app.security.sessions import set_session_cookie
    from fastapi import Response
    monkeypatch.setattr(regression_settings, 'environment', 'production')
    response = Response()
    set_session_cookie(response, 'a'*64)
    cookie = response.headers['set-cookie']
    assert '__Host-dandoonjan_session=' in cookie and 'Secure' in cookie
    assert 'HttpOnly' in cookie and 'Path=/' in cookie and 'Domain=' not in cookie
    client, _, _ = api_client
    assert client.get('/api/auth/csrf').status_code == 503


def test_production_https_lifecycle(api_client, regression_settings, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.security.sessions import cookie_name
    monkeypatch.setattr(regression_settings, 'environment', 'production')
    monkeypatch.setattr(regression_settings, 'auth_allowed_origins', ['https://testserver'])
    with TestClient(app, base_url='https://testserver') as client:
        assert register(client).status_code == 201
        response = login(client)
        assert response.status_code == 200
        cookie = response.headers['set-cookie']
        assert '__Host-dandoonjan_session=' in cookie and 'Secure' in cookie
        assert client.get('/api/auth/me').status_code == 200
        from .helpers import csrf
        assert client.post('/api/auth/logout', headers=csrf(client)).status_code == 204
        assert not client.cookies.get(cookie_name())


def test_relogin_issues_fresh_session_and_revokes_previous(api_client):
    from app.domain.models import AuthSession
    from app.security.sessions import cookie_name
    client, sessions, _ = api_client
    register(client); login(client)
    old = client.cookies.get(cookie_name())
    assert login(client).status_code == 200
    assert client.cookies.get(cookie_name()) != old
    with sessions() as db:
        rows = db.query(AuthSession).order_by(AuthSession.id).all()
        assert len(rows) == 2 and rows[0].revoked_at is not None and rows[1].revoked_at is None
    client.cookies.clear(); client.cookies.set(cookie_name(), old)
    assert client.get('/api/auth/me').status_code == 401


def test_session_and_logout_commit_before_success_headers(api_client):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.domain.models import AuthSession
    client, sessions, _ = api_client
    register(client)
    events = []
    async def observed(scope, receive, send):
        async def checked_send(message):
            if message['type'] == 'http.response.start':
                if scope['path'] == '/api/auth/login' and message['status'] == 200:
                    with sessions() as db: assert db.query(AuthSession).count() == 1
                    events.append('login committed')
                if scope['path'] == '/api/auth/logout' and message['status'] == 204:
                    with sessions() as db: assert db.query(AuthSession).one().revoked_at is not None
                    events.append('logout committed')
            await send(message)
        await app(scope, receive, checked_send)
    with TestClient(observed) as checked:
        assert login(checked).status_code == 200
        from .helpers import csrf
        assert checked.post('/api/auth/logout', headers=csrf(checked)).status_code == 204
    assert events == ['login committed','logout committed']
