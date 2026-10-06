"""Local process rehearsal only: private Unix socket, disposable synthetic state.

No Docker/TLS/provider/production readiness claims. The worker wraps the existing
health request with a bounded delay solely to observe Uvicorn request draining.
It does not change application routes or pipeline behavior.
"""
from pathlib import Path
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def worker(folder):
    import asyncio
    import hashlib
    import socket
    folder = Path(folder)
    os.chdir(folder)
    sys.path.insert(0, str(ROOT))
    for name in tuple(os.environ):
        if name.startswith('DJ_'):
            del os.environ[name]
    os.environ.update(DJ_ENVIRONMENT='test', DJ_DATABASE_URL='sqlite:///' + str(folder / 'state.db'),
                      DJ_ARTIFACT_STORAGE_DIR=str(folder / 'artifacts'), DJ_AI_PROVIDER='mock',
                      DJ_LIVE_PROVIDER_ENABLED='false', DJ_OPENROUTER_API_KEY='', DJ_OPENAI_API_KEY='')
    from app.config import Settings
    Settings.model_config['env_file'] = None
    original_connect, original_bind = socket.socket.connect, socket.socket.bind
    def connect(sock, address):
        if sock.family != socket.AF_UNIX:
            os._exit(97)
        return original_connect(sock, address)
    def bind(sock, address):
        if sock.family != socket.AF_UNIX:
            os._exit(97)
        return original_bind(sock, address)
    socket.socket.connect, socket.socket.bind = connect, bind
    import httpx
    def forbidden(*a, **kw):
        os._exit(97)
    httpx.Client.send = forbidden
    httpx.AsyncClient.send = forbidden
    from app.ai.providers import MockProvider, OpenRouterProvider
    MockProvider.run = forbidden
    OpenRouterProvider.__init__ = forbidden
    from app.db import Base, engine, SessionLocal
    from app.domain.models import User, Case, Artifact
    from app.core.artifacts.ingestion import ingest_artifact
    from app.security.ingestion import read_bytes
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        artifact = db.query(Artifact).one_or_none()
        if artifact is None:
            user = User(public_id='USR-g74-synthetic')
            db.add(user)
            db.flush()
            case = Case(public_id='CASE-g74-synthetic', user_id=user.id)
            db.add(case)
            db.flush()
            artifact = ingest_artifact(db, case, 'synthetic.txt', 'text/plain',
                                      b'SYNTHETIC source retained across restart').artifact
            db.commit()
        data = read_bytes(artifact.storage_key)
        assert len(data) == artifact.file_size
        assert hashlib.sha256(data).hexdigest() == artifact.sha256
        (folder / 'verified').write_text(artifact.storage_key + '\n' + artifact.sha256)
    from app.main import app
    shutdown = folder / 'shutdown-complete'
    shutdown.unlink(missing_ok=True)
    async def controlled(scope, receive, send):
        if scope['type'] == 'http' and (b'x-g74-hold', b'yes') in scope['headers']:
            (folder / 'inflight').write_text('synthetic request admitted')
            await asyncio.sleep(1.5)
        async def observed(message):
            if message['type'] == 'lifespan.shutdown.complete':
                shutdown.write_text('application lifespan shutdown completed')
            await send(message)
        await app(scope, receive, observed)
    import uvicorn
    uvicorn.run(controlled, uds=str(folder / 'http.sock'), log_level='warning',
                proxy_headers=False, timeout_graceful_shutdown=5)


def request(folder, hold=False):
    import socket
    from http.client import HTTPResponse
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(10)
        sock.connect(str(folder / 'http.sock'))
        headers = b'X-G74-Hold: yes\r\n' if hold else b''
        sock.sendall(b'GET /health HTTP/1.1\r\nHost: synthetic.invalid\r\n' + headers +
                     b'Connection: close\r\n\r\n')
        response = HTTPResponse(sock)
        response.begin()
        return response.status, response.read()


def wait_until(predicate, process, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        assert process.poll() is None, 'worker exited before readiness; inspect worker log'
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError('local rehearsal deadline exceeded')


def test_idle_sigterm_restart_and_inflight_drain(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import hashlib
    import signal
    # Sanitized subprocess environment; worker never reads workspace dotenv.
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DJ_', 'RC_POSTGRES'))}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    fingerprints = []
    for attempt in range(3):
        with (tmp_path / ('worker-' + str(attempt) + '.log')).open('wb') as log:
            process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                                        '--worker', str(tmp_path)], cwd=tmp_path,
                                       env=env, stdout=log, stderr=log)
            try:
                def ready():
                    try:
                        return request(tmp_path)[0] == 200
                    except (OSError, ConnectionError):
                        return False
                try:
                    wait_until(ready, process)
                except AssertionError:
                    log.flush()
                    raise AssertionError((tmp_path / ('worker-' + str(attempt) + '.log')).read_text())
                fingerprints.append((tmp_path / 'verified').read_text())
                if attempt == 1:
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        pending = pool.submit(request, tmp_path, True)
                        wait_until(lambda: (tmp_path / 'inflight').exists(), process)
                        process.terminate()
                        assert pending.result(timeout=10) == (200, b'{"status":"ok"}')
                else:
                    process.terminate()
                # Uvicorn 0.54.0 restores/re-raises captured SIGTERM after draining.
                assert process.wait(timeout=10) == -signal.SIGTERM
                assert (tmp_path / 'shutdown-complete').read_text() == 'application lifespan shutdown completed'
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
    assert len(set(fingerprints)) == 1
    key, expected = fingerprints[0].splitlines()
    source = tmp_path / 'artifacts' / key
    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
    assert source.read_bytes() == b'SYNTHETIC source retained across restart'


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
    else:
        raise SystemExit('Use offline pytest launcher; worker requires a disposable root.')
