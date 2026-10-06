"""Gate 7.4: finite proxy trust and unchanged production auth boundaries."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


@pytest.mark.parametrize('value', [None, '', ' ', '*', '127.0.0.1,*',
                                  'proxy.example', '127.0.0.0/8', '127.0.0.1,',
                                  'https://127.0.0.1', '999.1.1.1', '0.0.0.0',
                                  '::', '224.0.0.1', 'fe80::1%eth0'])
def test_invalid_proxy_trust_fails_before_preflight(value, monkeypatch, capsys):
    from app import deployment_serve as serve
    if value is None:
        monkeypatch.delenv('DJ_TRUSTED_PROXY_PEERS', raising=False)
    else:
        monkeypatch.setenv('DJ_TRUSTED_PROXY_PEERS', value)
    monkeypatch.setattr(serve, 'run_preflight', lambda: pytest.fail('preflight called'))
    monkeypatch.setattr(serve.os, 'execv', lambda *a: pytest.fail('serve called'))
    assert serve.main() == 1
    assert json.loads(capsys.readouterr().out) == {'status': 'FAIL', 'code': 'PROXY_TRUST_INVALID'}


@pytest.mark.parametrize('result', [0, 1])
def test_wrapper_preflight_gates_explicit_launch(result, monkeypatch):
    from app import deployment_serve as serve
    monkeypatch.setenv('DJ_TRUSTED_PROXY_PEERS', '127.0.0.1, ::1')
    monkeypatch.setenv('PORT', '8123')
    calls = []
    def preflight():
        calls.append('preflight')
        return result
    monkeypatch.setattr(serve, 'run_preflight', preflight)
    monkeypatch.setattr(serve.os, 'execv', lambda executable, argv: calls.append((executable, argv)))
    assert serve.main() == result
    if result:
        assert calls == ['preflight']
    else:
        executable, argv = calls[1]
        assert executable == sys.executable
        assert argv == [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0',
                        '--port', '8123', '--log-config', 'app/logging.json',
                        '--proxy-headers', '--forwarded-allow-ips', '127.0.0.1,::1']
        assert len(calls) == 2


@pytest.mark.parametrize('port', ['', '0', '65536', 'not-a-port', '9' * 5000])
def test_invalid_port_does_not_start_preflight(port, monkeypatch, capsys):
    from app import deployment_serve as serve
    monkeypatch.setenv('DJ_TRUSTED_PROXY_PEERS', '127.0.0.1')
    monkeypatch.setenv('PORT', port)
    monkeypatch.setattr(serve, 'run_preflight', lambda: pytest.fail('preflight called'))
    assert serve.main() == 1
    assert json.loads(capsys.readouterr().out)['code'] == 'PORT_INVALID'


def test_actual_wrapper_cli_preflight_failure_never_imports_http_app(tmp_path):
    root = Path(__file__).resolve().parents[2]
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DJ_', 'RC_POSTGRES'))}
    env.update(PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE='1',
               DJ_TRUSTED_PROXY_PEERS='127.0.0.1', DJ_ENVIRONMENT='development')
    # Preflight is configuration-invalid before any database/storage/provider I/O.
    script = '''
import importlib.abc, os, sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname in {'app.main', 'app.db', 'app.ai.providers'}: os._exit(97)
sys.meta_path.insert(0, Guard())
def forbidden(*a): os._exit(98)
os.execv = forbidden
from app.deployment_serve import main
raise SystemExit(main())
'''
    result = subprocess.run([sys.executable, '-B', '-c', script], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert json.loads(result.stdout) == {
        'status': 'FAIL', 'checks': {'configuration': 'PRODUCTION_REQUIRED'}}
    assert result.stderr == ''


def test_preflight_output_is_flushed_before_process_replacement(monkeypatch):
    from app import deployment_serve as serve
    import io
    calls = []
    class Output(io.StringIO):
        def flush(self):
            calls.append('flush')
            super().flush()
    monkeypatch.setenv('DJ_TRUSTED_PROXY_PEERS', '127.0.0.1')
    monkeypatch.setenv('PORT', '8000')
    monkeypatch.setattr(serve.sys, 'stdout', Output())
    monkeypatch.setattr(serve, 'run_preflight', lambda: 0)
    monkeypatch.setattr(serve.os, 'execv', lambda *args: calls.append('exec'))
    assert serve.main() == 0
    assert calls == ['flush', 'exec']


@pytest.mark.parametrize('peer,headers,expected', [
    ('127.0.0.1', {'X-Forwarded-Proto': 'https'}, 200),
    ('192.0.2.9', {'X-Forwarded-Proto': 'https'}, 503),
    ('127.0.0.1', {'Forwarded': 'proto=https'}, 503),
    ('127.0.0.1', {'X-Forwarded-Proto': 'https,http'}, 503),
    ('127.0.0.1', {'X-Forwarded-Proto': 'invalid'}, 503),
])
def test_production_scheme_uses_trusted_peer(raw_api_client, regression_settings, monkeypatch,
                                           peer, headers, expected):
    from app.main import app
    monkeypatch.setattr(regression_settings, 'environment', 'production')
    monkeypatch.setattr(regression_settings, 'auth_foundation_enabled', True)
    monkeypatch.setattr(regression_settings, 'auth_allowed_origins', ['https://synthetic.invalid'])
    proxy = ProxyHeadersMiddleware(app, trusted_hosts=['127.0.0.1'])
    with TestClient(proxy, base_url='http://synthetic.invalid', client=(peer, 1234)) as client:
        response = client.get('/api/auth/csrf', headers=headers)
        assert response.status_code == expected
        if expected == 200:
            assert '__Host-dandoonjan_preauth=' in response.headers['set-cookie']
            assert 'Secure' in response.headers['set-cookie']


def test_proxy_cookie_lifecycle(raw_api_client, regression_settings, monkeypatch):
    from app.main import app
    from tests.auth.helpers import register, login
    monkeypatch.setattr(regression_settings, 'environment', 'production')
    monkeypatch.setattr(regression_settings, 'auth_foundation_enabled', True)
    monkeypatch.setattr(regression_settings, 'auth_allowed_origins', ['https://synthetic.invalid'])
    # Public URL is HTTPS, backend ASGI transport is plaintext before middleware.
    proxy = ProxyHeadersMiddleware(app, trusted_hosts=['127.0.0.1'])
    async def backend(scope, receive, send):
        scope = dict(scope)
        if scope['type'] == 'http':
            scope['scheme'] = 'http'
        await proxy(scope, receive, send)
    with TestClient(backend, base_url='https://synthetic.invalid', client=('127.0.0.1', 1234),
                    headers={'X-Forwarded-Proto': 'https'}) as client:
        assert register(client).status_code == 201
        response = login(client)
        cookie = next(c for c in response.headers.get_list('set-cookie')
                      if c.startswith('__Host-dandoonjan_session='))
        for attribute in ['Secure', 'HttpOnly', 'Path=/', 'SameSite=lax']:
            assert attribute in cookie
        assert 'Domain=' not in cookie
        assert client.get('/api/auth/me').status_code == 200
        token = response.json()['csrf_token']
        assert client.post('/api/auth/logout', headers={
            'Origin': 'https://evil.invalid', 'X-CSRF-Token': token}).status_code == 403
        response = client.post('/api/auth/logout', headers={
            'Origin': 'https://synthetic.invalid', 'X-CSRF-Token': token})
        assert response.status_code == 204
        for cookie in response.headers.get_list('set-cookie'):
            assert 'Max-Age=0' in cookie and 'Secure' in cookie and 'HttpOnly' in cookie
            assert 'Path=/' in cookie and 'Domain=' not in cookie
        assert client.get('/api/auth/me').status_code == 401


@pytest.mark.parametrize('migration,preflight,steps', [
    (1, 0, ['migration']), (0, 1, ['migration', 'preflight']),
    (0, 0, ['migration', 'preflight', 'serve'])])
def test_fake_release_ordering(tmp_path, migration, preflight, steps):
    import shlex
    log = tmp_path / 'steps'
    for name, code in [('migration', migration), ('preflight', preflight), ('serve', 0)]:
        path = tmp_path / name
        path.write_text('#!/bin/sh\nprintf "%s\\n" ' + shlex.quote(name) +
                        ' >> ' + shlex.quote(str(log)) + '\nexit ' + str(code) + '\n')
        path.chmod(0o700)
    command = ' && '.join(shlex.quote(str(tmp_path / name)) for name in ['migration', 'preflight'])
    command += ' && exec ' + shlex.quote(str(tmp_path / 'serve'))
    result = subprocess.run(['sh', '-c', command], capture_output=True, timeout=5)
    assert result.returncode == (migration or preflight)
    assert log.read_text().splitlines() == steps


def test_liveness_does_not_check_dependencies(raw_api_client, monkeypatch):
    from app import deployment_preflight
    import app.db as database
    client, _, _ = raw_api_client
    def unavailable(*a, **kw):
        pytest.fail('liveness must not perform readiness checks')
    monkeypatch.setattr(database, 'SessionLocal', unavailable)
    monkeypatch.setattr(deployment_preflight, 'check_database', unavailable)
    monkeypatch.setattr(deployment_preflight, 'check_storage', unavailable)
    assert client.get('/health').json() == {'status': 'ok'}
    assert client.get('/api/health').json()['status'] == 'ok'


def test_empty_writable_store_does_not_prove_evidence(tmp_path, regression_settings, monkeypatch):
    from app.deployment_preflight import check_storage
    from app.security.ingestion import store_bytes, read_bytes
    from app.errors import StorageError
    import hashlib
    root = tmp_path / 'original'
    root.mkdir()
    monkeypatch.setattr(regression_settings, 'artifact_storage_dir', str(root))
    data = b'SYNTHETIC durable source'
    key = store_bytes('CASE-synthetic', 'source.txt', data)
    assert len(read_bytes(key)) == len(data)
    assert hashlib.sha256(read_bytes(key)).digest() == hashlib.sha256(data).digest()
    replacement = tmp_path / 'empty'
    replacement.mkdir()
    assert check_storage(replacement) == 'OK'
    monkeypatch.setattr(regression_settings, 'artifact_storage_dir', str(replacement))
    with pytest.raises(StorageError):
        read_bytes(key)


def test_container_uses_wrapper_without_migration():
    root = Path(__file__).resolve().parents[2]
    command = json.loads(next(line[4:] for line in (root / 'Dockerfile').read_text().splitlines()
                              if line.startswith('CMD ')))
    assert command == ['python', '-m', 'app.deployment_serve']
    assert 'alembic' not in (root / 'app/deployment_serve.py').read_text().lower()
