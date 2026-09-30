"""Offline preflight regressions. Synthetic credentials; injected HTTP only."""
import json
import httpx
import pytest
from app.ai.providers import OpenRouterProvider
from app.ai.prompts import get_prompt
from app.errors import ProviderUnavailableError
from app.ai.review_schema import validate_review
from test_contract import candidate


def provider(handler, model='vendor/fixed-model'):
    return OpenRouterProvider('OFFLINE_TEST_ONLY', model,
        offline_handler=handler)


def envelope(value, **overrides):
    return {'model': 'vendor/fixed-model', 'choices': [{'finish_reason': 'stop',
        'message': {'content': json.dumps(value)}}], **overrides}


@pytest.mark.parametrize('model', ['', 'mock-evidence-v1', 'openrouter/auto',
    'openrouter/free', 'vendor/model:free', 'model', 'https://secret.invalid/model', 'vendor/ model'])
def test_invalid_model_rejected_without_transport(model):
    with pytest.raises(ProviderUnavailableError):
        provider(lambda r: pytest.fail('Transport called'), model)


@pytest.mark.parametrize('path', ['text', 'review'])
@pytest.mark.parametrize('failure', ['auth', 'timeout', 'rate', 'server', 'envelope',
    'json', 'truncated', 'refused', 'model', 'size'])
def test_transport_fails_closed(path, failure):
    calls = []
    def handler(request):
        calls.append(request)
        if failure == 'timeout':
            raise httpx.ReadTimeout('PRIVATE_CANARY')
        status = {'auth': 401, 'rate': 429, 'server': 503}.get(failure, 200)
        data = envelope({})
        if failure == 'envelope': data = {'choices': []}
        if failure == 'json': data['choices'][0]['message']['content'] = '```json\n{}\n```'
        if failure == 'truncated': data['choices'][0]['finish_reason'] = 'length'
        if failure == 'refused': data['choices'][0]['message']['refusal'] = 'PRIVATE_CANARY'
        if failure == 'model': data['model'] = 'other/model'
        if failure == 'size': return httpx.Response(200, content=b' ' * 256001)
        return httpx.Response(status, json=data)
    p = provider(handler)
    with pytest.raises(ProviderUnavailableError):
        if path == 'text': p.run(get_prompt('artifact_classifier'), '{}', {})
        else: p.review({'sources': [], 'text': [], 'images': []})
    assert 1 <= len(calls) <= 2


@pytest.mark.parametrize('text', ['Diagnostic confidence: 0.85', 'probability is 0.8',
    'confidence 9/10', 'اطمینان ۰٫۹', 'You have pulpitis', 'Start antibiotics',
    'Stop taking your medication', 'Take aspirin', '۹۰ درصد', 'definitive diagnosis'])
def test_safety_prose(text):
    value = candidate()
    value['patient_summary'] = [{'text': text, 'source_refs': ['s1'], 'insufficient_support': False}]
    with pytest.raises(ValueError): validate_review(value, ['s1'])


@pytest.mark.parametrize('path', ['text', 'review'])
def test_serialized_request_bound(path, monkeypatch):
    monkeypatch.setattr('app.ai.providers.MAX_REQUEST_BYTES', 100)
    p = provider(lambda request: pytest.fail('Oversized request was sent'))
    with pytest.raises(ProviderUnavailableError):
        if path == 'text': p.run(get_prompt('artifact_classifier'), 'x' * 101, {})
        else: p.review({'sources': [], 'text': [], 'images': []})


def test_aliases_are_request_scoped_and_only_resolved_after_validation():
    from app.ai.multimodal import provider_bundle, resolve_review
    local = {'sources': [{'source_ref': 'CASE_PRIVATE:v2:symptoms', 'kind': 'PATIENT_REPORTED',
        'artifact_id': None, 'page': None, 'label': 'symptoms', 'sha256': 'PRIVATE_HASH'}],
        'text': [{'source_ref': 'CASE_PRIVATE:v2:symptoms', 'text': 'Synthetic'}], 'images': []}
    first, mapping = provider_bundle(local)
    second, another = provider_bundle(local)
    assert not set(mapping) & set(another)
    assert 'PRIVATE' not in json.dumps(first)
    value = candidate()
    ref = next(iter(mapping))
    value['source_index'] = [{'source_ref': ref}]
    value['diagnostic_hypotheses'][0]['supporting_evidence_refs'] = [ref]
    output = validate_review(value, mapping)
    assert resolve_review(output, mapping)['source_index'] == [{'source_ref': 'CASE_PRIVATE:v2:symptoms'}]
    with pytest.raises(ProviderUnavailableError): validate_review(value, another)
    with pytest.raises(ProviderUnavailableError): validate_review(value, ['unknown'])


@pytest.mark.parametrize('mutation', ['duplicate', 'missing', 'extra', 'conflict', 'unsupported'])
def test_reference_contract(mutation):
    value = candidate()
    if mutation == 'duplicate': value['source_index'] *= 2
    if mutation == 'missing': value['source_index'] = []
    if mutation == 'extra': value['source_index'].append({'source_ref': 'foreign'})
    if mutation == 'conflict': value['diagnostic_hypotheses'][0]['contradicting_evidence_refs'] = ['s1']
    if mutation == 'unsupported': value['diagnostic_hypotheses'][0]['supporting_evidence_refs'] = []
    with pytest.raises(ProviderUnavailableError): validate_review(value, ['s1'])


@pytest.mark.parametrize('module,attribute', [('review_schema', 'VERSION'),
    ('multimodal', 'VERSION'), ('preflight', 'REVIEW_PROMPT_VERSION'), ('preflight', 'CONTRACT_VERSION')])
def test_processing_contract_invalidates_reuse(api_client, monkeypatch, module, attribute):
    import importlib
    from test_review_flow import create
    client, sessions, _ = api_client
    cid = create(client)
    first = client.post(f'/api/cases/{cid}/process').json()
    assert first['report']
    assert client.post(f'/api/cases/{cid}/process').json()['reused']
    monkeypatch.setattr(importlib.import_module('app.ai.' + module), attribute, 'synthetic-next-version')
    assert client.get(f'/api/cases/{cid}/report').status_code == 404
    second = client.post(f'/api/cases/{cid}/process').json()
    assert second['report'] and not second['reused'] and second['snapshot'] != first['snapshot']


@pytest.mark.parametrize('path', ['text', 'review'])
def test_total_elapsed_bound_even_for_stalled_transport(path, monkeypatch):
    import time
    import threading
    release = threading.Event()
    calls = []
    def handler(request):
        calls.append(request)
        release.wait(2)
        return httpx.Response(503)
    monkeypatch.setattr('app.ai.providers.MAX_DURATION', 0.05)
    p = provider(handler)
    start = time.monotonic()
    try:
        with pytest.raises(ProviderUnavailableError) as exc:
            if path == 'text': p.run(get_prompt('artifact_classifier'), '{}', {})
            else: p.review({'sources': [], 'text': [], 'images': []})
        assert exc.value.category == 'timeout'
        assert time.monotonic() - start < 0.5
    finally:
        release.set()
    assert len(calls) == 1


@pytest.mark.parametrize('status,category', [(401, 'authentication'), (403, 'authentication'),
    (429, 'rate_limit'), (500, 'provider'), (302, 'provider')])
def test_content_free_transport_categories(status, category):
    p = provider(lambda request: httpx.Response(status, text='PRIVATE_CANARY https://private.invalid'))
    with pytest.raises(ProviderUnavailableError) as exc:
        p.review({'sources': [], 'text': [], 'images': []})
    assert exc.value.category == category
    assert 'PRIVATE' not in str(exc.value) and 'https' not in str(exc.value)


def test_legacy_payload_renders_once_and_has_full_schema(db, monkeypatch):
    from app.ai.gateway import ModelGateway
    from app.ai.schemas import ExtractionOutput
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=envelope({'fields': [], 'treatment_items': []}))
    p = provider(handler)
    gateway = ModelGateway(db)
    gateway.provider = p
    gateway.run('invoice_extractor', ExtractionOutput,
        '{"filename":"PRIVATE_FILENAME.pdf","mime":"application/pdf"}\nSYNTHETIC_UNIQUE_TEXT')
    payload = json.dumps(seen[0])
    assert 'PRIVATE_FILENAME' not in payload
    assert payload.count('SYNTHETIC_UNIQUE_TEXT') == 1
    assert '$defs' in payload and 'treatment_items' in payload and 'same schema' not in payload


@pytest.mark.parametrize('key', ['', ' ', ' invalid ', 'invalid\nheader'])
def test_missing_or_invalid_dummy_key_never_calls_transport(key):
    with pytest.raises(ProviderUnavailableError) as exc:
        OpenRouterProvider(key, 'vendor/fixed-model',
            offline_handler=lambda request: pytest.fail('sent'))
    assert exc.value.category == 'configuration'


@pytest.mark.parametrize('environment', ['development', 'test', 'production'])
def test_disabled_live_mode_prevents_client_creation(environment, db, regression_settings, monkeypatch):
    from app.ai.gateway import ModelGateway
    monkeypatch.setattr(regression_settings, 'ai_provider', 'openrouter')
    monkeypatch.setattr(regression_settings, 'ai_model_name', 'vendor/fixed-model')
    monkeypatch.setattr(regression_settings, 'openrouter_api_key', 'OFFLINE_TEST_ONLY')
    monkeypatch.setattr(regression_settings, 'environment', environment)
    monkeypatch.setattr(regression_settings, 'live_provider_enabled', False)
    monkeypatch.setattr(httpx, 'Client', lambda *a, **kw: pytest.fail('Client created'))
    with pytest.raises(ProviderUnavailableError): ModelGateway(db)


def test_explicit_mock_is_available_offline(db, regression_settings):
    from app.ai.gateway import ModelGateway
    assert not regression_settings.live_provider_enabled
    assert ModelGateway(db).provider.name == 'mock'


@pytest.mark.parametrize('scope', ['case', 'revision'])
def test_foreign_scope_alias_replay_rejected(scope):
    from app.ai.multimodal import provider_bundle
    def local(ref):
        return {'sources': [{'source_ref': ref, 'kind': 'PATIENT_REPORTED',
            'page': None, 'label': 'symptoms'}], 'text': [], 'images': []}
    _, old = provider_bundle(local('CASE_A:v1:symptoms'))
    _, current = provider_bundle(local('CASE_B:v1:symptoms' if scope == 'case' else 'CASE_A:v2:symptoms'))
    value = candidate()
    ref = next(iter(old))
    value['source_index'] = [{'source_ref': ref}]
    value['diagnostic_hypotheses'][0]['supporting_evidence_refs'] = [ref]
    with pytest.raises(ProviderUnavailableError): validate_review(value, current)


def test_legacy_prompt_version_invalidates_processing_identity(db, case, monkeypatch):
    from dataclasses import replace
    from app.ai.prompts import PROMPTS
    from app.pipeline.orchestrator import effective_input_hash
    before = effective_input_hash(db, case)
    assert effective_input_hash(db, case) == before
    monkeypatch.setitem(PROMPTS, 'artifact_classifier', replace(PROMPTS['artifact_classifier'], version='synthetic-next'))
    assert effective_input_hash(db, case) != before
