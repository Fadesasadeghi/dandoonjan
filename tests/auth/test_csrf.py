from datetime import timedelta
import pytest

from .helpers import csrf, register, login, PASSWORD


@pytest.mark.parametrize('endpoint', ['register', 'login'])
def test_preauth_csrf_required(api_client, endpoint):
    client, _, _ = api_client
    response = client.post('/api/auth/'+endpoint, json={'email':'valid@example.com','password':PASSWORD})
    assert response.status_code == 403


def test_logout_csrf_revokes_before_success_and_repeat_is_safe(api_client):
    from app.domain.models import AuthSession
    client, sessions, _ = api_client
    register(client); response = login(client)
    assert client.post('/api/auth/logout').status_code == 403
    assert client.get('/api/auth/me').status_code == 200
    headers = {'X-CSRF-Token': response.json()['csrf_token'], 'Origin':'http://testserver'}
    assert client.post('/api/auth/logout', headers=headers).status_code == 204
    with sessions() as db: assert db.query(AuthSession).one().revoked_at is not None
    assert client.get('/api/auth/me').status_code == 401
    assert client.post('/api/auth/logout', headers={'Origin':'http://testserver'}).status_code == 204


@pytest.mark.parametrize('origin', ['https://evil.example', 'null', 'http://testserver.evil', 'http://testserver/path'])
def test_untrusted_origin_rejected(api_client, origin):
    client, _, _ = api_client
    headers = csrf(client); headers['Origin'] = origin
    assert client.post('/api/auth/register', headers=headers, json={'email':'valid@example.com','password':PASSWORD}).status_code == 403


def test_referer_fallback_and_context_consumption(api_client):
    client, _, _ = api_client
    headers = csrf(client); headers.pop('Origin'); headers['Referer']='http://testserver/account'
    response = client.post('/api/auth/register', headers=headers, json={'email':'valid@example.com','password':PASSWORD})
    assert response.status_code == 201
    assert client.post('/api/auth/login', headers=headers, json={'email':'valid@example.com','password':PASSWORD}).status_code == 403


def test_context_expiry_and_authenticated_csrf_refresh(api_client):
    from app.domain.models import PreAuthContext, utcnow
    client, sessions, _ = api_client
    headers = csrf(client)
    with sessions() as db:
        db.query(PreAuthContext).one().expires_at = utcnow()-timedelta(seconds=1); db.commit()
    assert client.post('/api/auth/register', headers=headers, json={'email':'valid@example.com','password':PASSWORD}).status_code == 403
    register(client); login(client)
    headers = csrf(client)
    assert client.post('/api/auth/logout', headers=headers).status_code == 204


@pytest.mark.parametrize('header', [None, 'wrong', 'a'*10000], ids=['missing','wrong','oversized'])
def test_logout_bad_token_never_revokes(api_client, header):
    client, _, _ = api_client
    register(client); login(client)
    headers = {'Origin':'http://testserver'}
    if header: headers['X-CSRF-Token']=header
    assert client.post('/api/auth/logout', headers=headers).status_code == 403
    assert client.get('/api/auth/me').status_code == 200


def test_csrf_context_is_bound_to_browser_cookie(api_client):
    from fastapi.testclient import TestClient
    from app.main import app
    client, _, _ = api_client
    headers = csrf(client)
    with TestClient(app) as other:
        csrf(other)
        assert other.post('/api/auth/register', headers=headers, json={'email':'valid@example.com','password':PASSWORD}).status_code == 403


@pytest.mark.parametrize('method', ['POST','PUT','PATCH','DELETE'])
def test_mutation_guard_supports_multipart_and_all_methods(method):
    from types import SimpleNamespace
    from starlette.requests import Request
    from app.security.csrf import require_mutation_csrf
    from app.security.sessions import token_hash
    from fastapi import HTTPException
    request = Request({'type':'http','method':method,'headers':[(b'content-type',b'multipart/form-data; boundary=synthetic')]})
    with pytest.raises(HTTPException) as error:
        require_mutation_csrf(request, SimpleNamespace(csrf_token_hash=token_hash('b'*64)))
    assert error.value.status_code == 403
    request = Request({'type':'http','method':method,'headers':[
        (b'content-type',b'multipart/form-data; boundary=synthetic'),
        (b'origin',b'http://testserver'), (b'x-csrf-token', b'b'*64)]})
    require_mutation_csrf(request, SimpleNamespace(csrf_token_hash=token_hash('b'*64)))
