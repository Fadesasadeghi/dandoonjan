"""Fixed free-model authorization; dummy credentials and owned offline transport only."""
import json

import httpx
import pytest

from app.ai.preflight import validate_configuration
from app.ai.providers import OpenRouterProvider
from app.config import Settings
from app.errors import ProviderUnavailableError

MODEL = 'qwen/qwen3.8-27b:free'
KEY = 'OFFLINE_TEST_ONLY'


def test_opt_in_defaults_off():
    assert Settings.model_fields['local_synthetic_acceptance_enabled'].default is False


@pytest.mark.parametrize('environment', ['development', 'test', 'production', 'local-synthetic'])
def test_default_rejects_free(environment):
    with pytest.raises(ProviderUnavailableError):
        validate_configuration(MODEL, KEY, True, environment=environment)


@pytest.mark.parametrize('environment', ['development', 'test', 'production', '', 'LOCAL-SYNTHETIC'])
def test_opt_in_requires_exact_local_environment(environment):
    with pytest.raises(ProviderUnavailableError):
        validate_configuration(MODEL, KEY, True, environment=environment,
                               local_synthetic_acceptance_enabled=True)


@pytest.mark.parametrize('model', ['openrouter/free', 'openrouter/auto', '/free', '/auto',
    'vendor/free', 'vendor/auto', 'openrouter/free:free', 'openrouter/auto:free',
    'vendor/router:free', 'vendor/model:free', 'vendor/paid-model',
    'qwen/qwen3.8-27b', MODEL + ':auto', MODEL.upper(), ''])
def test_opt_in_rejects_every_model_except_exact_allowlist(model):
    with pytest.raises(ProviderUnavailableError):
        validate_configuration(model, KEY, True, environment='local-synthetic',
                               local_synthetic_acceptance_enabled=True)


def test_fixed_free_model_accepted():
    validate_configuration(MODEL, KEY, True, environment='local-synthetic',
                           local_synthetic_acceptance_enabled=True)


@pytest.mark.parametrize('model', ['openrouter/free', 'openrouter/auto', '/free', '/auto',
    'vendor/free', 'vendor/auto', 'vendor/router', 'vendor/dynamic',
    'openrouter/auto:free', 'vendor/router:free'])
@pytest.mark.parametrize('enabled', [False, True])
def test_aliases_rejected_in_both_modes(model, enabled):
    with pytest.raises(ProviderUnavailableError):
        validate_configuration(model, KEY, True, environment='local-synthetic',
                               local_synthetic_acceptance_enabled=enabled)


@pytest.mark.parametrize('key,live', [('', True), (' invalid ', True), ('invalid\nkey', True),
                                     (KEY, False)])
def test_opt_in_preserves_key_and_live_gates(key, live):
    with pytest.raises(ProviderUnavailableError):
        validate_configuration(MODEL, key, live, environment='local-synthetic',
                               local_synthetic_acceptance_enabled=True)


@pytest.fixture
def local_mode(regression_settings, monkeypatch):
    monkeypatch.setattr(regression_settings, 'environment', 'local-synthetic')
    monkeypatch.setattr(regression_settings, 'local_synthetic_acceptance_enabled', True)
    return regression_settings


def test_adapter_transmits_exact_model_offline(local_mode):
    seen = []
    def handler(request):
        seen.append(json.loads(request.content)['model'])
        return httpx.Response(200, json={'model': MODEL, 'choices': [
            {'finish_reason': 'stop', 'message': {'content': '{}'}}]})
    provider = OpenRouterProvider(KEY, MODEL, offline_handler=handler)
    assert provider.review({'sources': [], 'text': [], 'images': []}) == {}
    assert seen == [MODEL]


@pytest.mark.parametrize('setting,value', [('environment', 'production'),
    ('local_synthetic_acceptance_enabled', False)])
def test_adapter_rechecks_authorization_before_dispatch(local_mode, monkeypatch, setting, value):
    provider = OpenRouterProvider(KEY, MODEL,
        offline_handler=lambda r: pytest.fail('Unauthorized dispatch'))
    monkeypatch.setattr(local_mode, setting, value)
    with pytest.raises(ProviderUnavailableError):
        provider.review({'sources': [], 'text': [], 'images': []})


def test_opt_in_does_not_authorize_live_client(local_mode, monkeypatch):
    monkeypatch.setattr(local_mode, 'ai_provider', 'openrouter')
    monkeypatch.setattr(httpx, 'Client', lambda *a, **kw: pytest.fail('Live client created'))
    with pytest.raises(ProviderUnavailableError):
        OpenRouterProvider(KEY, MODEL)


@pytest.mark.parametrize('failure', ['auth', 'rate', 'model', 'malformed'])
def test_free_model_transport_still_fails_closed(local_mode, failure):
    def handler(request):
        return httpx.Response({'auth': 401, 'rate': 429}.get(failure, 200), json={
            'model': 'vendor/other' if failure == 'model' else MODEL,
            'choices': [] if failure == 'malformed' else [
                {'finish_reason': 'stop', 'message': {'content': '{}'}}]})
    provider = OpenRouterProvider(KEY, MODEL, offline_handler=handler)
    with pytest.raises(ProviderUnavailableError):
        provider.review({'sources': [], 'text': [], 'images': []})
