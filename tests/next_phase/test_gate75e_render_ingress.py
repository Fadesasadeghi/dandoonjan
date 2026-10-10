"""Tests first: explicit Render staging TLS boundary, never caller header trust."""
import json

import pytest
from fastapi.testclient import TestClient

from app import deployment_preflight as preflight
from app.config import Settings

ORIGIN = 'https://dazzling-bombolone-90006d.netlify.app'
MODE = 'render-managed-tls'
FORGED = {
    'X-Forwarded-Proto': 'https', 'X-Forwarded-Host': ORIGIN.removeprefix('https://'),
    'Forwarded': f'for=127.0.0.1;proto=https;host={ORIGIN.removeprefix("https://")}',
    'X-Forwarded-For': '127.0.0.1', 'X-Forwarded-Port': '443',
    'X-Forwarded-Ssl': 'on', 'X-Url-Scheme': 'https',
}


@pytest.fixture
def boundary_settings(tmp_path):
    settings = Settings(_env_file=None, environment='staging',
        database_url='postgresql+psycopg:///synthetic', artifact_storage_dir=str(tmp_path),
        auth_foundation_enabled=True, auth_allowed_origins=[ORIGIN], cors_origins=[],
        ai_provider='mock', ai_model_name='mock-evidence-v1', live_provider_enabled=False,
        local_synthetic_acceptance_enabled=False,
        require_clinician_reviewed_knowledge_pack=True,
        openrouter_api_key='', openai_api_key='')
    # Before implementation this is deliberately an unknown setting, so tests
    # expose the ignored contract rather than failing at fixture construction.
    settings.__dict__['render_staging_https_boundary'] = MODE
    return settings


def test_explicit_boundary_starts_without_peers(monkeypatch):
    from app import deployment_serve as serve
    monkeypatch.setenv('DJ_ENVIRONMENT', 'staging')
    monkeypatch.setenv('DJ_RENDER_STAGING_HTTPS_BOUNDARY', MODE)
    monkeypatch.delenv('DJ_TRUSTED_PROXY_PEERS', raising=False)
    monkeypatch.setenv('PORT', '8123')
    calls = []
    monkeypatch.setattr(serve, 'run_preflight', lambda: calls.append('preflight') or 0)
    monkeypatch.setattr(serve.os, 'execv', lambda executable, argv: calls.append(argv))
    assert serve.main() == 0
    assert calls[0] == 'preflight'
    assert calls[1] == [serve.sys.executable, '-m', 'uvicorn', 'app.main:app',
        '--host', '0.0.0.0', '--port', '8123', '--log-config', 'app/logging.json',
        '--no-proxy-headers']


@pytest.mark.parametrize('environment', ['production', 'development', 'test', 'local-synthetic'])
def test_boundary_cannot_activate_outside_staging(environment, monkeypatch, capsys):
    from app import deployment_serve as serve
    monkeypatch.setenv('DJ_ENVIRONMENT', environment)
    monkeypatch.setenv('DJ_RENDER_STAGING_HTTPS_BOUNDARY', MODE)
    monkeypatch.setenv('DJ_TRUSTED_PROXY_PEERS', '127.0.0.1')
    monkeypatch.setattr(serve, 'run_preflight', lambda: pytest.fail('unsafe activation'))
    assert serve.main() == 1
    assert json.loads(capsys.readouterr().out)['code'] == 'RENDER_STAGING_HTTPS_BOUNDARY_INVALID'


@pytest.mark.parametrize('value', ['', 'true', '*', 'https', 'auto'])
def test_unknown_boundary_fails_closed(value, monkeypatch, capsys):
    from app import deployment_serve as serve
    monkeypatch.setenv('DJ_ENVIRONMENT', 'staging')
    monkeypatch.setenv('DJ_RENDER_STAGING_HTTPS_BOUNDARY', value)
    monkeypatch.setenv('DJ_TRUSTED_PROXY_PEERS', '127.0.0.1')
    monkeypatch.setattr(serve, 'run_preflight', lambda: pytest.fail('invalid mode accepted'))
    assert serve.main() == 1
    assert json.loads(capsys.readouterr().out)['code'] == 'RENDER_STAGING_HTTPS_BOUNDARY_INVALID'


@pytest.mark.parametrize('peers', ['', '*', '127.0.0.1', '10.0.0.0/8'])
def test_boundary_rejects_mixed_peer_configuration(peers, monkeypatch, capsys):
    from app import deployment_serve as serve
    monkeypatch.setenv('DJ_ENVIRONMENT', 'staging')
    monkeypatch.setenv('DJ_RENDER_STAGING_HTTPS_BOUNDARY', MODE)
    monkeypatch.setenv('DJ_TRUSTED_PROXY_PEERS', peers)
    monkeypatch.setattr(serve, 'run_preflight', lambda: pytest.fail('ambiguous trust mode'))
    assert serve.main() == 1
    assert json.loads(capsys.readouterr().out)['code'] == 'RENDER_STAGING_HTTPS_BOUNDARY_INVALID'


def test_preflight_rejects_boundary_in_production(boundary_settings):
    boundary_settings.environment = 'production'
    boundary_settings.ai_provider = 'openrouter'
    boundary_settings.ai_model_name = 'synthetic/approved-model'
    boundary_settings.live_provider_enabled = True
    assert preflight.check_configuration(boundary_settings, key_present=True) == 'RENDER_STAGING_HTTPS_BOUNDARY_INVALID'


def test_settings_reject_production_boundary():
    with pytest.raises(ValueError):
        Settings(_env_file=None, environment='production', render_staging_https_boundary=MODE)


@pytest.mark.parametrize('result', [0, 1])
def test_boundary_still_requires_successful_preflight(result, monkeypatch):
    from app import deployment_serve as serve
    monkeypatch.setenv('DJ_ENVIRONMENT', 'staging')
    monkeypatch.setenv('DJ_RENDER_STAGING_HTTPS_BOUNDARY', MODE)
    monkeypatch.delenv('DJ_TRUSTED_PROXY_PEERS', raising=False)
    monkeypatch.setattr(serve, 'run_preflight', lambda: result)
    launched = []
    monkeypatch.setattr(serve.os, 'execv', lambda *args: launched.append(args))
    assert serve.main() == result
    assert bool(launched) == (result == 0)


@pytest.mark.parametrize('environment', ['production', 'staging'])
def test_explicit_disabled_mode_keeps_literal_peers(environment, monkeypatch):
    from app import deployment_serve as serve
    monkeypatch.setenv('DJ_ENVIRONMENT', environment)
    monkeypatch.setenv('DJ_RENDER_STAGING_HTTPS_BOUNDARY', 'disabled')
    monkeypatch.setenv('DJ_TRUSTED_PROXY_PEERS', '127.0.0.1,::1')
    monkeypatch.setattr(serve, 'run_preflight', lambda: 0)
    launched = []
    monkeypatch.setattr(serve.os, 'execv', lambda executable, argv: launched.append(argv))
    assert serve.main() == 0
    assert launched[0][-3:] == ['--proxy-headers', '--forwarded-allow-ips', '127.0.0.1,::1']


def test_preflight_loads_explicit_boundary(monkeypatch):
    monkeypatch.setenv('DJ_ENVIRONMENT', 'staging')
    monkeypatch.setenv('DJ_RENDER_STAGING_HTTPS_BOUNDARY', MODE)
    assert preflight.load_configuration().render_staging_https_boundary == MODE


@pytest.mark.parametrize('field,value', [
    ('ai_provider', 'openrouter'), ('ai_model_name', 'other'),
    ('live_provider_enabled', True), ('local_synthetic_acceptance_enabled', True),
    ('require_clinician_reviewed_knowledge_pack', False),
    ('auth_foundation_enabled', False), ('cors_origins', [ORIGIN]),
])
def test_boundary_preserves_staging_guards(boundary_settings, field, value):
    setattr(boundary_settings, field, value)
    assert preflight.check_configuration(boundary_settings, key_present=False) != 'OK'


@pytest.mark.parametrize('key', ['openrouter', 'openai'])
def test_boundary_forbids_provider_credentials(boundary_settings, key):
    assert preflight.check_configuration(boundary_settings,
        key_present=key == 'openrouter', other_provider_key_present=key == 'openai') == 'STAGING_PROVIDER_CREDENTIALS_FORBIDDEN'


def test_boundary_keeps_unreviewed_pack_blocked(boundary_settings, raw_api_client, monkeypatch):
    from app.core.knowledge import pack
    from app.errors import KnowledgePackUnavailableError
    monkeypatch.setattr(pack, 'get_settings', lambda: boundary_settings)
    _, factory, _ = raw_api_client
    with factory() as db, pytest.raises(KnowledgePackUnavailableError):
        pack.get_active_pack(db)


@pytest.mark.parametrize('bad', ['missing', 'wrong'])
def test_boundary_csrf_token_is_still_required(boundary_api, bad):
    from tests.auth.helpers import PASSWORD
    client, _ = boundary_api
    assert client.get('/api/auth/csrf').status_code == 200
    headers = {'Origin': ORIGIN, **FORGED}
    if bad == 'wrong':
        headers['X-CSRF-Token'] = 'b' * 64
    response = client.post('/api/auth/register', headers=headers,
        json={'email': 'synthetic@example.com', 'password': PASSWORD})
    assert response.status_code == 403
    assert response.json()['detail']['code'] == 'CSRF_FAILED'


@pytest.fixture
def boundary_api(raw_api_client, regression_settings, monkeypatch):
    from app.main import app
    monkeypatch.setattr(regression_settings, 'environment', 'staging')
    monkeypatch.setitem(regression_settings.__dict__, 'render_staging_https_boundary', MODE)
    monkeypatch.setattr(regression_settings, 'auth_foundation_enabled', True)
    monkeypatch.setattr(regression_settings, 'auth_allowed_origins', [ORIGIN])
    monkeypatch.setattr(regression_settings, 'cors_origins', [])
    monkeypatch.setattr(regression_settings, 'require_clinician_reviewed_knowledge_pack', True)
    async def plaintext_backend(scope, receive, send):
        scope = dict(scope)
        if scope['type'] == 'http':
            scope['scheme'] = 'http'
        await app(scope, receive, send)
    # Browser URL is HTTPS; the platform's hop to the app is plaintext.
    with TestClient(plaintext_backend, base_url=ORIGIN, client=('192.0.2.9', 1234)) as client:
        yield client, plaintext_backend


@pytest.mark.parametrize('headers', [{}, FORGED, {
    'X-Forwarded-Proto': 'http', 'X-Forwarded-Host': 'evil.invalid',
    'Forwarded': 'proto=http;host=evil.invalid', 'X-Forwarded-For': '203.0.113.1'}])
def test_configured_boundary_not_headers_supplies_https(boundary_api, headers):
    client, _ = boundary_api
    response = client.get('/api/auth/csrf', headers=headers)
    assert response.status_code == 200
    cookie = response.headers['set-cookie']
    for value in ['__Host-dandoonjan_preauth=', 'Secure', 'HttpOnly', 'Path=/', 'SameSite=lax']:
        assert value in cookie
    assert 'Domain=' not in cookie


def test_forwarding_headers_cannot_enable_boundary(raw_api_client, regression_settings, monkeypatch):
    from app.main import app
    monkeypatch.setattr(regression_settings, 'environment', 'staging')
    monkeypatch.setattr(regression_settings, 'auth_foundation_enabled', True)
    monkeypatch.setattr(regression_settings, 'auth_allowed_origins', [ORIGIN])
    with TestClient(app, base_url='http://synthetic.invalid') as client:
        assert client.get('/api/auth/csrf', headers=FORGED).status_code == 503


@pytest.mark.parametrize('enabled', [False, True])
def test_boundary_changes_only_scheme_not_host_client_or_origin(regression_settings, monkeypatch, enabled):
    import asyncio
    from app.security.render_ingress import RenderStagingHTTPSBoundaryMiddleware
    monkeypatch.setattr(regression_settings, 'environment', 'staging')
    monkeypatch.setitem(regression_settings.__dict__, 'render_staging_https_boundary', MODE if enabled else 'disabled')
    captured = []
    async def downstream(scope, receive, send):
        captured.append(scope)
    original = {'type': 'http', 'scheme': 'http', 'server': ('backend.invalid', 8123),
        'client': ('192.0.2.9', 1234), 'headers': [(b'host', b'backend.invalid'),
        (b'origin', b'https://evil.invalid'),
        *[(k.lower().encode(), v.encode()) for k, v in FORGED.items()]]}
    asyncio.run(RenderStagingHTTPSBoundaryMiddleware(downstream)(original, None, None))
    assert captured[0] == {**original, 'scheme': 'https' if enabled else 'http'}
    assert original['scheme'] == 'http'


@pytest.mark.parametrize('headers,expected', [
    ({'Origin': ORIGIN}, 201), ({'Referer': ORIGIN + '/account'}, 201),
    ({}, 403), ({'Origin': 'https://evil.invalid'}, 403),
    ({'Referer': 'https://evil.invalid/account'}, 403),
    ({'Origin': 'null'}, 403), ({'Origin': ORIGIN + '/path'}, 403),
    ({'Origin': 'https://synthetic.onrender.com'}, 403),
    ({'Origin': 'https://evil.invalid', 'Referer': ORIGIN + '/account'}, 403),
])
def test_exact_origin_and_referer_with_spoofed_headers(boundary_api, headers, expected):
    from tests.auth.helpers import PASSWORD
    client, _ = boundary_api
    response = client.get('/api/auth/csrf')
    assert response.status_code == 200
    response = client.post('/api/auth/register',
        json={'email': 'synthetic@example.com', 'password': PASSWORD},
        headers={**FORGED, **headers, 'X-CSRF-Token': response.json()['csrf_token']})
    assert response.status_code == expected


def test_cookie_sessions_csrf_ownership_and_pack_boundary(boundary_api):
    from tests.auth.helpers import register, login
    client, backend = boundary_api
    assert register(client, 'owner@example.com').status_code == 201
    response = login(client, 'owner@example.com')
    assert response.status_code == 200
    session = next(c for c in response.headers.get_list('set-cookie')
                   if c.startswith('__Host-dandoonjan_session='))
    assert all(a in session for a in ['Secure', 'HttpOnly', 'Path=/', 'SameSite=lax'])
    assert 'Domain=' not in session
    headers = {'Origin': ORIGIN, 'X-CSRF-Token': response.json()['csrf_token']}
    assert client.post('/api/cases', data={'question': 'synthetic'}, headers=FORGED).status_code == 403
    response = client.post('/api/cases', data={'question': 'synthetic'}, headers=headers)
    assert response.status_code == 201
    cid = response.json()['case_id']
    assert client.get('/api/cases/' + cid).status_code == 200
    assert client.patch('/api/cases/' + cid, data={'question': 'edited synthetic'}, headers=headers).json()['changed']
    assert client.put('/api/cases/' + cid + '/dossier', json={'symptoms': 'synthetic'}, headers=headers).status_code == 200
    assert client.post('/api/cases/' + cid + '/process', headers=headers).status_code == 422
    with TestClient(backend, base_url=ORIGIN) as other:
        assert other.get('/api/cases/' + cid).status_code == 401
        assert register(other, 'other@example.com').status_code == 201
        response = login(other, 'other@example.com')
        other_headers = {'Origin': ORIGIN, 'X-CSRF-Token': response.json()['csrf_token'], **FORGED}
        for method, suffix, payload in [('GET', '', {}), ('PATCH', '', {'data': {'question': 'foreign'}}),
                ('PUT', '/dossier', {'json': {'symptoms': 'foreign'}}),
                ('POST', '/artifacts', {'files': {'file': ('synthetic.txt', b'synthetic', 'text/plain')}}),
                ('POST', '/process', {})]:
            assert other.request(method, '/api/cases/' + cid + suffix,
                headers=other_headers, **payload).status_code == 404
    assert client.options('/api/cases', headers={'Origin': 'https://evil.invalid',
        'Access-Control-Request-Method': 'POST'}).headers.get('Access-Control-Allow-Origin') is None
    assert client.post('/api/auth/logout', headers={**headers, 'Origin': 'https://evil.invalid', **FORGED}).status_code == 403
    assert client.get('/api/auth/me').status_code == 200
    assert client.post('/api/auth/logout', headers=headers).status_code == 204
    assert client.get('/api/auth/me').status_code == 401
