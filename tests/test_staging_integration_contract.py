"""Offline staging preparation: no hosted resources or provider dispatch."""
import ast
import importlib.util
import json
from pathlib import Path
import tomllib

import pytest
from starlette.responses import Response

from app import deployment_preflight as preflight
from app.config import Settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def staging(tmp_path):
    return Settings(_env_file=None, environment='staging',
        database_url='postgresql+psycopg:///synthetic',
        artifact_storage_dir=str(tmp_path), auth_foundation_enabled=True,
        auth_allowed_origins=['https://synthetic.invalid'], cors_origins=[],
        ai_provider='mock', ai_model_name='mock-evidence-v1',
        live_provider_enabled=False, local_synthetic_acceptance_enabled=False,
        require_clinician_reviewed_knowledge_pack=True,
        openrouter_api_key='', openai_api_key='')


def test_staging_accepts_mock_without_key(staging):
    assert preflight.check_configuration(staging, key_present=False) == 'OK'


@pytest.mark.parametrize('field,value', [
    ('ai_provider', 'openrouter'), ('live_provider_enabled', True),
    ('local_synthetic_acceptance_enabled', True), ('ai_model_name', 'other'),
    ('auth_foundation_enabled', False), ('auth_allowed_origins', []),
    ('auth_allowed_origins', ['http://synthetic.invalid']),
    ('cors_origins', ['https://synthetic.invalid']),
    ('require_clinician_reviewed_knowledge_pack', False),
    ('database_url', 'sqlite:///synthetic.db'), ('artifact_storage_dir', './relative'),
])
def test_staging_rejects_contract_violations(staging, field, value):
    setattr(staging, field, value)
    assert preflight.check_configuration(staging, key_present=False) != 'OK'


def test_staging_rejects_openrouter_presence(staging):
    assert preflight.check_configuration(staging, key_present=True) != 'OK'


@pytest.mark.parametrize('key', ['DJ_OPENROUTER_API_KEY', 'DJ_OPENAI_API_KEY'])
def test_cli_rejects_credentials_before_database(staging, monkeypatch, capsys, key):
    for name, value in staging.model_dump().items():
        if name not in {'openrouter_api_key', 'openai_api_key'}:
            monkeypatch.setenv('DJ_' + name.upper(), json.dumps(value) if isinstance(value, list) else str(value))
    monkeypatch.setenv(key, 'SYNTHETIC_FORBIDDEN_DO_NOT_LOG')
    def forbidden(*args):
        pytest.fail('Must reject configuration before opening database')
    monkeypatch.setattr(preflight, 'check_database', forbidden)
    assert preflight.main() == 1
    output = capsys.readouterr().out
    assert 'SYNTHETIC_FORBIDDEN' not in output
    assert json.loads(output)['checks']['configuration'] == 'STAGING_PROVIDER_CREDENTIALS_FORBIDDEN'


def test_production_requirements_unchanged(staging):
    staging.environment = 'production'
    assert preflight.check_configuration(staging, key_present=False) != 'OK'
    staging.ai_provider = 'openrouter'
    staging.ai_model_name = 'synthetic/approved-model'
    staging.live_provider_enabled = True
    assert preflight.check_configuration(staging, key_present=False) != 'OK'
    assert preflight.check_configuration(staging, key_present=True) == 'OK'
    staging.require_clinician_reviewed_knowledge_pack = False
    assert preflight.check_configuration(staging, key_present=True) == 'REVIEWED_PACK_ENFORCEMENT_REQUIRED'


def test_secure_staging_cookies(staging, monkeypatch):
    from app.security import sessions, demo_sessions
    monkeypatch.setattr(sessions, 'get_settings', lambda: staging)
    response = Response()
    for name in (sessions.cookie_name(), sessions.preauth_cookie_name(), demo_sessions.cookie_name()):
        assert name.startswith('__Host-')
        sessions.set_cookie(response, name, 'synthetic', 60)
    for key, value in response.raw_headers:
        if key == b'set-cookie':
            assert b'Secure' in value and b'HttpOnly' in value and b'SameSite=lax' in value
            assert b'Domain=' not in value


def test_development_pack_remains_blocked(staging, db, monkeypatch):
    from app.core.knowledge import pack
    from app.errors import KnowledgePackUnavailableError
    from app.domain.enums import KnowledgePackStatus
    monkeypatch.setattr(pack, 'get_settings', lambda: staging)
    seeded = pack.seed_knowledge_pack(db)
    assert seeded.status == KnowledgePackStatus.DEVELOPMENT
    assert seeded.review_status == 'NOT_CLINICALLY_VALIDATED'
    with pytest.raises(KnowledgePackUnavailableError):
        pack.get_active_pack(db)


def declared_routes(path):
    tree = ast.parse(path.read_text())
    return {(d.func.attr.upper(), d.args[0].value)
        for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for d in node.decorator_list if isinstance(d, ast.Call)
        and isinstance(d.func, ast.Attribute) and d.args and isinstance(d.args[0], ast.Constant)}


def test_health_and_dossier_routes_and_relative_fetches():
    health = declared_routes(ROOT / 'app/main.py')
    assert {('GET', '/health'), ('GET', '/api/health')} <= health
    for name in ('routes.py', 'demo.py'):
        routes = declared_routes(ROOT / 'app/api' / name)
        assert {('GET', '/cases/{case_public_id}/dossier'), ('PUT', '/cases/{case_public_id}/dossier')} <= routes
    source = (ROOT / 'frontend/app.js').read_text()
    assert 'api(`/api/cases/${state.caseId}/dossier`' in source
    assert "path.replace('/api/cases','/api/demo/cases')" in source
    for name in ('app.js', 'account.js'):
        source = (ROOT / 'frontend' / name).read_text()
        assert "credentials:'same-origin'" in source
        assert 'https://' not in source and 'DANDOONJAN_BACKEND_URL' not in source


def test_storage_probe_is_writable_only(staging, tmp_path, monkeypatch):
    assert preflight.check_storage(tmp_path) == 'OK'
    assert list(tmp_path.iterdir()) == []
    def denied(*args, **kwargs):
        raise PermissionError()
    monkeypatch.setattr(preflight.tempfile, 'TemporaryFile', denied)
    assert preflight.check_storage(tmp_path) == 'ARTIFACT_DIRECTORY_UNWRITABLE'
    assert not preflight.postgres_version_supported(170000)
    assert preflight.postgres_version_supported(160000)


def generator():
    spec = importlib.util.spec_from_file_location('netlify_redirects', ROOT / 'scripts/generate_netlify_redirects.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_redirect_generation_and_order(tmp_path):
    module = generator()
    target = tmp_path / '_redirects'
    module.generate('https://synthetic.onrender.com', target)
    lines = target.read_text().splitlines()
    assert lines == ['/api/* https://synthetic.onrender.com/api/:splat 200!',
                     '/ui/* /:splat 200', '/case/* /index.html 200']
    assert not any(line.startswith('/* ') for line in lines)
    config = tomllib.loads((ROOT / 'netlify.toml').read_text())
    assert config['build']['publish'] == 'frontend'
    assert 'generate_netlify_redirects.py' in config['build']['command']
    assert 'redirects' not in config
    assert 'sed' not in config['build']['command']
    import re
    html = (ROOT / 'frontend/index.html').read_text()
    for asset in re.findall(r'(?:src|href)="/ui/([^"]+)"', html):
        assert (ROOT / 'frontend' / asset).is_file()


@pytest.mark.parametrize('origin', ['', 'http://synthetic.invalid', 'https://synthetic.invalid/api',
    'https://user:pass@synthetic.invalid', 'https://synthetic.invalid?x=1',
    'https://synthetic.invalid\n/api/* https://evil.invalid 200', 'https://synthetic.invalid#x',
    'https://synthetic.invalid:bad'])
def test_invalid_redirect_origin_preserves_output(tmp_path, origin):
    target = tmp_path / '_redirects'
    target.write_text('preserved')
    with pytest.raises(ValueError):
        generator().generate(origin, target)
    assert target.read_text() == 'preserved'


def test_staging_preflight_runs_all_bounded_checks(staging, monkeypatch, capsys):
    monkeypatch.setattr(preflight, 'load_configuration', lambda: staging)
    monkeypatch.delenv('DJ_OPENROUTER_API_KEY', raising=False)
    monkeypatch.delenv('DJ_OPENAI_API_KEY', raising=False)
    calls = []
    for name in ('check_database', 'check_storage', 'check_frontend'):
        def check(*args, _name=name):
            calls.append(_name)
            return 'OK'
        monkeypatch.setattr(preflight, name, check)
    assert preflight.main() == 0
    assert calls == ['check_database', 'check_storage', 'check_frontend']
    output = json.loads(capsys.readouterr().out)
    assert output == {'status': 'PASS', 'checks': {'configuration': 'OK', 'database': 'OK',
                                                'artifacts': 'OK', 'frontend': 'OK'}}
    assert 'durable' not in output


@pytest.mark.parametrize('peers', [None, '', '*', '10.0.0.0/8', 'proxy.invalid'])
def test_staging_launcher_rejects_unbounded_proxy_trust(peers):
    from app.deployment_serve import trusted_peers
    with pytest.raises(ValueError):
        trusted_peers(peers)


def test_staging_launcher_accepts_finite_literal_peers():
    from app.deployment_serve import trusted_peers
    assert trusted_peers('127.0.0.1, ::1') == '127.0.0.1,::1'


def test_preflight_blocks_noncurrent_schema(staging, monkeypatch):
    class Result:
        def scalar_one(self):
            return 160000
    class Connection:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def begin(self):
            return self
        def execute(self, statement):
            assert str(statement) in {'SET TRANSACTION READ ONLY',
                "SET LOCAL statement_timeout = '10000'", 'SHOW server_version_num'}
            return Result()
    class Engine:
        def connect(self):
            return Connection()
        def dispose(self):
            pass
    class Migration:
        def get_current_heads(self):
            return ('stale-synthetic',)
    monkeypatch.setattr(preflight, 'create_engine', lambda *a, **kw: Engine())
    monkeypatch.setattr(preflight.MigrationContext, 'configure', lambda *a: Migration())
    assert preflight.check_database(staging) == 'SCHEMA_REVISION_INVALID'
