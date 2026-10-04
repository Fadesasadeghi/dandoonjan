"""Narrow final-review regressions; synthetic data, no provider network access."""
from copy import deepcopy
from types import SimpleNamespace
import httpx
import pytest

from app.ai.providers import OpenRouterProvider
from app.ai.review_schema import validate_review
from app.errors import ProviderUnavailableError
from tests.next_phase.test_contract import candidate


@pytest.mark.parametrize('number', ['0.85', '.85', ',85', '85%', '85 percent',
    '۰٫۸۵', '٫۸۵', '،۸۵', '۸۵ درصد', '۸۵٪'])
@pytest.mark.parametrize('prefix', ['Diagnostic confidence: ', 'اطمینان: '])
def test_diagnostic_numeric_forms_rejected(number, prefix):
    value = candidate()
    value['patient_summary'] = [{'text': prefix + number,
        'source_refs': ['s1'], 'insufficient_support': False}]
    with pytest.raises(ProviderUnavailableError):
        validate_review(value, ['s1'])


@pytest.mark.parametrize('text', ['Symptoms lasted 3 days.', 'Tooth 46 is referenced.',
    'Document measurement: .85 mm.', 'مدت علائم ۳ روز است.'])
def test_nondiagnostic_numbers_remain_allowed(text):
    value = candidate()
    value['patient_summary'] = [{'text': text, 'source_refs': ['s1'], 'insufficient_support': False}]
    assert validate_review(value, ['s1']).patient_summary[0].text == text


def test_explicit_offline_handler_works(regression_settings):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={'model': 'synthetic/fixed', 'choices': [
            {'finish_reason': 'stop', 'message': {'content': '{}'}}]})
    provider = OpenRouterProvider('OFFLINE_TEST_ONLY', 'synthetic/fixed', offline_handler=handler)
    assert provider.review({'sources': [], 'text': [], 'images': []}) == {}
    assert len(seen) == 1 and not regression_settings.live_provider_enabled


@pytest.mark.parametrize('routing', ['ordinary', 'mock_default', 'mounted', 'proxy'])
def test_generic_client_cannot_authorize_offline(routing, regression_settings):
    def forbidden(request):
        pytest.fail('Generic client must be rejected before dispatch')
    transport = httpx.MockTransport(forbidden)
    kwargs = {}
    if routing != 'ordinary': kwargs['transport'] = transport
    if routing == 'mounted': kwargs['mounts'] = {'https://': httpx.MockTransport(forbidden)}
    if routing == 'proxy': kwargs['proxy'] = 'http://127.0.0.1:1'
    with httpx.Client(**kwargs) as client:
        # Construction must reject; no call that could use network is made here.
        with pytest.raises(ProviderUnavailableError):
            OpenRouterProvider('OFFLINE_TEST_ONLY', 'synthetic/fixed', client=client)


def test_offline_handler_cannot_be_combined_with_client():
    with httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('sent'))) as client:
        with pytest.raises(ProviderUnavailableError):
            OpenRouterProvider('OFFLINE_TEST_ONLY', 'synthetic/fixed', client=client,
                offline_handler=lambda r: pytest.fail('sent'))


@pytest.mark.parametrize('provider,model,key', [('mock', 'synthetic/fixed', 'OFFLINE_TEST_ONLY'),
    ('openrouter', '', 'OFFLINE_TEST_ONLY'), ('openrouter', 'mock-model', 'OFFLINE_TEST_ONLY'),
    ('openrouter', 'synthetic/fixed', '')])
def test_simulated_live_mode_still_requires_configuration(monkeypatch, provider, model, key):
    # Pure settings stand-in only; DJ_LIVE_PROVIDER_ENABLED stays false.
    monkeypatch.setattr('app.config.get_settings', lambda: SimpleNamespace(
        ai_provider=provider, live_provider_enabled=True))
    monkeypatch.setattr(httpx, 'Client', lambda *a, **kw: pytest.fail('Client created'))
    with pytest.raises(ProviderUnavailableError): OpenRouterProvider(key, model)


def test_running_retry_failure_recovery_and_normal_reuse(api_client, monkeypatch):
    from app.config import get_settings
    from app.ai.providers import MockProvider
    from app.domain.models import AssessmentSnapshot, ProcessingRun
    from tests.next_phase.test_review_flow import create
    client, sessions, _ = api_client
    cid = create(client)
    first = client.post(f'/api/cases/{cid}/process').json()
    assert first['report']
    with sessions() as db:
        historical = deepcopy(db.query(AssessmentSnapshot).one().payload)
    assert client.post(f'/api/cases/{cid}/process').json()['reused']
    # Invalid configuration prevents reusing the old success without changing inputs.
    monkeypatch.setattr(get_settings(), 'ai_provider', 'openrouter')
    assert client.post(f'/api/cases/{cid}/process').json()['status'] == 'FAILED'
    monkeypatch.setattr(get_settings(), 'ai_provider', 'mock')
    original = MockProvider.run
    observed = []
    def during_retry(*args):
        with sessions() as db:
            assert db.query(ProcessingRun).filter_by(module='pipeline').order_by(
                ProcessingRun.id.desc()).first().status.value == 'RUNNING'
        observed.append(client.get(f'/api/cases/{cid}/report').status_code)
        raise ProviderUnavailableError(category='timeout')
    monkeypatch.setattr(MockProvider, 'run', during_retry)
    failed = client.post(f'/api/cases/{cid}/process').json()
    assert observed == [404]
    assert failed['status'] == 'FAILED' and failed['report'] is None
    assert client.get(f'/api/cases/{cid}/report').status_code == 404
    monkeypatch.setattr(MockProvider, 'run', original)
    recovered = client.post(f'/api/cases/{cid}/process').json()
    assert recovered['report'] and not recovered['reused']
    assert recovered['snapshot'] != first['snapshot']
    assert client.get(f'/api/cases/{cid}/report').json()['snapshot_id'] == recovered['snapshot']
    assert client.post(f'/api/cases/{cid}/process').json()['reused']
    with sessions() as db:
        assert db.query(AssessmentSnapshot).order_by(AssessmentSnapshot.id).first().payload == historical
        assert db.query(AssessmentSnapshot).count() == 2
