"""Gate 7.3: offline preflight runtime; Docker assertions are source-level only."""
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import pytest
from sqlalchemy import create_engine, inspect, text

from verification.test_rc_postgres import ROOT, pg_url, migrate


@pytest.fixture
def preflight():
    from app import deployment_preflight
    return deployment_preflight


@pytest.fixture
def settings(tmp_path):
    from app.config import Settings
    store = tmp_path / 'artifacts'
    store.mkdir()
    return Settings(_env_file=None, environment='production',
        database_url='postgresql+psycopg:///synthetic', artifact_storage_dir=str(store),
        ai_provider='openrouter', ai_model_name='synthetic/approved-model',
        live_provider_enabled=True, auth_foundation_enabled=True,
        auth_allowed_origins=['https://synthetic.invalid'], cors_origins=[],
        require_clinician_reviewed_knowledge_pack=True,
        openrouter_api_key='', openai_api_key='')


def test_valid_configuration(preflight, settings):
    assert preflight.check_configuration(settings, key_present=True) == 'OK'


@pytest.mark.parametrize('field,value', [
    ('environment', 'development'), ('database_url', 'sqlite:///synthetic.db'),
    ('database_url', 'postgresql://localhost/synthetic'),
    ('database_url', 'not-a-url'), ('auth_foundation_enabled', False),
    ('auth_allowed_origins', []), ('auth_allowed_origins', ['http://synthetic.invalid']),
    ('cors_origins', ['https://other.invalid']), ('ai_provider', 'mock'),
    ('ai_provider', 'unknown'), ('ai_model_name', 'mock-evidence-v1'),
    ('ai_model_name', 'openrouter/auto'), ('ai_model_name', 'synthetic/model:free'),
    ('live_provider_enabled', False), ('local_synthetic_acceptance_enabled', True),
    ('require_clinician_reviewed_knowledge_pack', False),
    ('artifact_storage_dir', 'relative/path'), ('max_upload_bytes', 0),
])
def test_invalid_configuration(preflight, settings, field, value):
    setattr(settings, field, value)
    assert preflight.check_configuration(settings, key_present=True) != 'OK'


def test_missing_key(preflight, settings):
    assert preflight.check_configuration(settings, key_present=False) != 'OK'


def test_configuration_loader_excludes_secret_fields(preflight, settings, monkeypatch):
    from app.config import Settings
    for key, value in synthetic_env(settings).items():
        if key.startswith('DJ_'):
            monkeypatch.setenv(key, value)
    def forbidden(*args, **kwargs):
        raise AssertionError('Do not instantiate BaseSettings or scan dotenv/environment secrets')
    monkeypatch.setattr(Settings, '__init__', forbidden)
    observed = []
    original = preflight.os.environ.get
    def guarded(key, *args):
        observed.append(key)
        assert key not in {'DJ_OPENROUTER_API_KEY', 'DJ_OPENAI_API_KEY'}
        return original(key, *args)
    monkeypatch.setattr(preflight.os.environ, 'get', guarded)
    loaded = preflight.load_configuration()
    assert preflight.check_configuration(loaded, key_present=True) == 'OK'
    assert 'openrouter_api_key' not in loaded.model_dump()
    assert 'openai_api_key' not in loaded.model_dump()
    assert observed


def test_storage_probe_preserves_existing_files(preflight, settings):
    path = Path(settings.artifact_storage_dir)
    original = path / 'synthetic-evidence'
    original.write_bytes(b'synthetic unchanged')
    assert preflight.check_storage(path) == 'OK'
    assert list(path.iterdir()) == [original]
    assert original.read_bytes() == b'synthetic unchanged'


def test_missing_storage_is_not_created(preflight, tmp_path):
    path = tmp_path / 'absent'
    assert preflight.check_storage(path) != 'OK'
    assert not path.exists()


def test_unwritable_storage(preflight, settings, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError('SYNTHETIC_SECRET_DO_NOT_LOG')
    monkeypatch.setattr(preflight.tempfile, 'TemporaryFile', denied)
    assert preflight.check_storage(Path(settings.artifact_storage_dir)) != 'OK'


def test_unwritable_storage_runtime(preflight, settings):
    assert os.geteuid() != 0, 'Permission rehearsal requires an unprivileged test user'
    path = Path(settings.artifact_storage_dir)
    path.chmod(0o500)
    try:
        assert preflight.check_storage(path) == 'ARTIFACT_DIRECTORY_UNWRITABLE'
        assert list(path.iterdir()) == []
    finally:
        path.chmod(0o700)


def test_static_files(preflight, tmp_path):
    assert preflight.check_frontend(ROOT) == 'OK'
    assert preflight.check_frontend(tmp_path) != 'OK'


@pytest.mark.parametrize('asset', ['index.html', 'account.js', 'app.js', 'landing.css',
                                  'hero-tooth-aqua.png', 'report-export.js'])
def test_missing_required_asset(preflight, tmp_path, asset):
    import shutil
    shutil.copytree(ROOT / 'frontend', tmp_path / 'frontend')
    (tmp_path / 'frontend' / asset).unlink()
    assert preflight.check_frontend(tmp_path) != 'OK'


@pytest.mark.parametrize('version,valid', [(159999, False), (160000, True),
                                         (160015, True), (170000, False)])
def test_postgres_version_requirement(preflight, version, valid):
    assert preflight.postgres_version_supported(version) is valid


def test_unavailable_postgres_is_sanitized(preflight, settings, tmp_path):
    settings.database_url = f'postgresql+psycopg:///synthetic?host={tmp_path}/absent'
    assert preflight.check_database(settings, ROOT) == 'DATABASE_UNAVAILABLE'


def snapshot(url):
    engine = create_engine(url, hide_parameters=True)
    try:
        schema = inspect(engine)
        tables = sorted(schema.get_table_names())
        with engine.connect() as db:
            rows = {t: sorted((repr(tuple(r)) for r in db.execute(
                text('SELECT * FROM "' + t + '"')))) for t in tables}
        state = tables, rows, {t: (schema.get_columns(t), schema.get_pk_constraint(t),
            schema.get_foreign_keys(t), schema.get_indexes(t),
            schema.get_unique_constraints(t)) for t in tables}
        # SQLAlchemy type instances compare by identity; serialize their actual
        # definitions so separately reflected identical schemas compare equally.
        return json.dumps(state, default=str, sort_keys=True)
    finally:
        engine.dispose()


@pytest.mark.parametrize('schema_state', ['current', 'stale', 'missing', 'wrong', 'empty-version'])
def test_database_revision_and_no_mutation(preflight, settings, pg_url, schema_state):
    if schema_state in {'current', 'wrong', 'empty-version'}:
        migrate(pg_url)
    elif schema_state == 'stale':
        migrate(pg_url, 'd81e27a9c401')
    engine = create_engine(pg_url, hide_parameters=True)
    try:
        with engine.begin() as db:
            db.execute(text('CREATE TABLE gate73_preservation (id INTEGER PRIMARY KEY, note TEXT)'))
            db.execute(text("INSERT INTO gate73_preservation VALUES (1, 'synthetic preserved')"))
            if schema_state == 'wrong':
                db.execute(text("UPDATE alembic_version SET version_num='unknown-synthetic'"))
            elif schema_state == 'empty-version':
                db.execute(text('DELETE FROM alembic_version'))
            db.execute(text('ALTER DATABASE "' + engine.url.database +
                            '" SET default_transaction_read_only = on'))
    finally:
        engine.dispose()
    settings.database_url = pg_url
    before = snapshot(pg_url)
    result = preflight.check_database(settings, ROOT)
    assert (result == 'OK') is (schema_state == 'current')
    assert result == ('OK' if schema_state == 'current' else 'SCHEMA_REVISION_INVALID')
    assert snapshot(pg_url) == before


def synthetic_env(settings):
    # Never inherit provider keys or dotenv configuration into the standalone CLI.
    env = {k: v for k, v in os.environ.items() if not k.startswith('DJ_')}
    env.update({'DJ_ENVIRONMENT': 'production', 'DJ_DATABASE_URL': settings.database_url,
        'DJ_ARTIFACT_STORAGE_DIR': settings.artifact_storage_dir,
        'DJ_AUTH_FOUNDATION_ENABLED': 'true',
        'DJ_AUTH_ALLOWED_ORIGINS': '["https://synthetic.invalid"]', 'DJ_CORS_ORIGINS': '[]',
        'DJ_AI_PROVIDER': 'openrouter', 'DJ_AI_MODEL_NAME': 'synthetic/approved-model',
        'DJ_LIVE_PROVIDER_ENABLED': 'true', 'DJ_OPENROUTER_API_KEY': 'SYNTHETIC_SECRET_DO_NOT_LOG',
        'DJ_REQUIRE_CLINICIAN_REVIEWED_KNOWLEDGE_PACK': 'true'})
    return env


def test_cli_success_no_provider_dispatch(preflight, settings, pg_url, tmp_path):
    migrate(pg_url)
    settings.database_url = pg_url
    before = snapshot(pg_url)
    hook = tmp_path / 'hook'
    hook.mkdir()
    # Tripwires terminate even if a broad exception handler tries to conceal I/O.
    (hook / 'sitecustomize.py').write_text('import os, socket\n'
        'def forbidden(*a, **kw): os._exit(97)\n'
        'original = socket.socket.connect\n'
        'def connect(self, address):\n'
        ' if self.family != socket.AF_UNIX: forbidden()\n'
        ' return original(self, address)\n'
        'socket.socket.connect = connect\n'
        'import httpx\nhttpx.Client.send = forbidden\nhttpx.AsyncClient.send = forbidden\n'
        'from app.ai.providers import OpenRouterProvider, MockProvider\n'
        'OpenRouterProvider.__init__ = forbidden\nMockProvider.run = forbidden\n')
    env = synthetic_env(settings)
    env['PYTHONPATH'] = str(hook) + os.pathsep + str(ROOT)
    result = subprocess.run([sys.executable, '-B', '-m', 'app.deployment_preflight'],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)['status'] == 'PASS'
    assert 'SYNTHETIC_SECRET_DO_NOT_LOG' not in result.stdout + result.stderr
    assert result.stderr == ''
    assert snapshot(pg_url) == before


def test_cli_invalid_config_no_secret_or_dotenv(preflight, settings, tmp_path):
    env = synthetic_env(settings)
    env['DJ_MAX_UPLOAD_BYTES'] = 'SYNTHETIC_SECRET_DO_NOT_LOG'
    (tmp_path / '.env').write_text('DJ_ENVIRONMENT=production\nDJ_OPENROUTER_API_KEY=DOTENV_SECRET\n')
    result = subprocess.run([sys.executable, '-B', '-m', 'app.deployment_preflight'],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 1
    assert json.loads(result.stdout)['status'] == 'FAIL'
    assert 'SECRET' not in result.stdout + result.stderr
    assert result.stderr == ''


def test_cli_ignores_dotenv(preflight, tmp_path):
    (tmp_path / '.env').write_text('DJ_MAX_UPLOAD_BYTES=DOTENV_SECRET_INVALID_INTEGER\n')
    env = {k: v for k, v in os.environ.items() if not k.startswith('DJ_')}
    result = subprocess.run([sys.executable, '-B', '-m', 'app.deployment_preflight'],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 1
    assert json.loads(result.stdout)['checks']['configuration'] == 'PRODUCTION_REQUIRED'
    assert result.stderr == ''


def runtime_closure():
    todo = [Requirement(line) for line in (ROOT / 'requirements.txt').read_text().splitlines()
            if line.strip() and canonicalize_name(Requirement(line).name) != 'pytest']
    seen, resolved, extras = set(), {}, {}
    while todo:
        req = todo.pop()
        name = canonicalize_name(req.name)
        key = (name, tuple(sorted(req.extras)))
        if key in seen:
            continue
        seen.add(key)
        dist = metadata.distribution(name)
        assert dist.version in req.specifier
        resolved[name] = dist.version
        extras.setdefault(name, set()).update(req.extras)
        for raw in dist.requires or []:
            dep = Requirement(raw)
            if dep.marker is None or any(dep.marker.evaluate({'extra': e})
                    for e in set(req.extras) | {''}):
                todo.append(dep)
    return resolved, extras


def test_runtime_pins_are_declared_dependency_closure():
    pins = [Requirement(line) for line in (ROOT / 'requirements-runtime.txt').read_text().splitlines()
            if line.strip() and not line.startswith('#')]
    resolved, extras = runtime_closure()
    assert {canonicalize_name(p.name): str(p.specifier) for p in pins} == {
        name: '==' + version for name, version in resolved.items()}
    assert {canonicalize_name(p.name): p.extras for p in pins} == extras
    assert 'pytest' not in resolved


def docker_command():
    line = next(line for line in (ROOT / 'Dockerfile').read_text().splitlines() if line.startswith('CMD '))
    return json.loads(line[4:])


def test_docker_packaging_source():
    content = (ROOT / 'Dockerfile').read_text()
    assert 'USER 10001:10001' in content
    assert 'requirements-runtime.txt' in content
    assert 'DJ_ARTIFACT_STORAGE_DIR=/app/data/artifact_store' in content
    command = docker_command()
    assert command[:2] == ['sh', '-c']
    assert 'python -m app.deployment_preflight && exec uvicorn' in command[2]
    assert 'alembic' not in command[2] and 'upgrade' not in command[2]
    assert '--forwarded-allow-ips' not in command[2]  # Preserve existing proxy trust.


def test_docker_normalizes_source_permissions():
    content = (ROOT / 'Dockerfile').read_text()
    assert 'chmod -R go-w /app/app /app/frontend /app/alembic' in content
    assert 'chmod go-w /app/alembic.ini /app/README.md /app/.env.example /app/requirements-runtime.txt' in content


def test_packaged_migrations_missing(preflight, settings, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Database must not be opened without packaged migrations')
    monkeypatch.setattr(preflight, 'create_engine', forbidden)
    assert preflight.check_database(settings, tmp_path) == 'PACKAGED_MIGRATIONS_INVALID'


def test_postgres_version_rejection_in_database_check(preflight, settings, pg_url, monkeypatch):
    # Exercise the live DB check's version branch without provisioning another
    # PostgreSQL major. Real PostgreSQL 16 acceptance is tested separately.
    monkeypatch.setattr(preflight, 'postgres_version_supported', lambda value: False)
    settings.database_url = pg_url
    assert preflight.check_database(settings, ROOT) == 'POSTGRES_VERSION_INVALID'


def test_private_postgres_runtime(pg_url):
    engine = create_engine(pg_url)
    try:
        with engine.connect() as db:
            assert db.execute(text('SHOW listen_addresses')).scalar_one() == ''
            assert 160000 <= int(db.execute(text('SHOW server_version_num')).scalar_one()) < 170000
    finally:
        engine.dispose()


def test_cli_database_error_redaction(preflight, settings, tmp_path):
    env = synthetic_env(settings)
    env['DJ_DATABASE_URL'] = ('postgresql+psycopg://synthetic:SYNTHETIC_DB_SECRET@/'
                              'synthetic?host=' + str(tmp_path / 'absent'))
    result = subprocess.run([sys.executable, '-B', '-m', 'app.deployment_preflight'],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 1
    assert json.loads(result.stdout)['checks']['database'] == 'DATABASE_UNAVAILABLE'
    assert 'SECRET' not in result.stdout + result.stderr
    assert result.stderr == ''


@pytest.mark.parametrize('exit_code,served', [(0, True), (1, False)])
def test_startup_preflight_gates_serve(exit_code, served, tmp_path):
    command = docker_command()
    assert 'deployment_preflight' in command[2]
    marker = tmp_path / 'served'
    (tmp_path / 'python').write_text('#!/bin/sh\nexit ' + str(exit_code) + '\n')
    (tmp_path / 'uvicorn').write_text('#!/bin/sh\n: > ' + shlex.quote(str(marker)) + '\n')
    for name in ('python', 'uvicorn'):
        (tmp_path / name).chmod(0o700)
    result = subprocess.run(command, env={**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH']},
                            capture_output=True, timeout=5)
    assert marker.exists() is served
    assert result.returncode == exit_code


def test_build_context_excludes_owner_and_sensitive_material():
    exclusions = (ROOT / '.dockerignore').read_text().splitlines()
    for required in ('.tmp-*/', '*.zip', '.venv/', '.aws/', '.codex/', 'tools/', 'frontend-demo/'):
        assert required in exclusions


def test_templates_are_explicitly_incomplete():
    for name in ('render.yaml', 'netlify.toml'):
        assert 'NOT A PRODUCTION DEPLOYMENT RECIPE' in (ROOT / name).read_text()
