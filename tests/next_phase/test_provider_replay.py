"""Synthetic HTTP only: conservative replay, classifications and safe accounting."""
import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest

from app.ai.providers import OpenRouterProvider
from app.errors import ProviderUnavailableError


@pytest.mark.parametrize('failure,category', [
    (401, 'authentication'), (403, 'authentication'), (429, 'rate_limit'),
    (503, 'ambiguous_remote_outcome'), (400, 'incompatible_request'),
    ('timeout', 'timeout'), ('network', 'ambiguous_remote_outcome'),
    ('connect', 'ambiguous_remote_outcome'),
    ('envelope', 'malformed_envelope'), ('json', 'schema'),
    ('refusal', 'refusal'), ('length', 'truncation'), ('cancelled', 'cancelled'),
    ('model', 'model_mismatch'),
])
def test_single_dispatch_and_exact_classification(failure, category):
    seen = []
    def handler(request):
        seen.append(request)
        if failure == 'timeout': raise httpx.ReadTimeout('PRIVATE_EVIDENCE')
        if failure == 'network': raise httpx.WriteError('PRIVATE_EVIDENCE')
        if failure == 'connect': raise httpx.ConnectError('PRIVATE_EVIDENCE')
        if isinstance(failure, int):
            return httpx.Response(failure, headers={'Retry-After': '37'}, text='PRIVATE_EVIDENCE')
        value = {'model': 'synthetic/fixed', 'choices': [{'finish_reason': 'stop',
            'message': {'content': '{}'}}]}
        if failure == 'envelope': value = {}
        if failure == 'json': value['choices'][0]['message']['content'] = 'not JSON'
        if failure == 'refusal': value['choices'][0]['message']['refusal'] = 'PRIVATE_EVIDENCE'
        if failure in ('length', 'cancelled'): value['choices'][0]['finish_reason'] = failure
        if failure == 'model': value['model'] = 'other/fixed'
        return httpx.Response(200, json=value)
    provider = OpenRouterProvider('OFFLINE_TEST_ONLY', 'synthetic/fixed', offline_handler=handler)
    with pytest.raises(ProviderUnavailableError) as caught:
        provider.review({'sources': [], 'text': [], 'images': []})
    assert len(seen) == 1
    assert caught.value.category == category
    assert 'PRIVATE' not in str(caught.value)
    if failure == 429: assert caught.value.retry_after == 37


@pytest.mark.parametrize('header,expected', [('17', 17), ('-1', None),
    ('private.invalid', None), ('9' * 1000, None), ('86401', 86400)])
def test_retry_after_is_bounded_metadata(header, expected):
    provider = OpenRouterProvider('OFFLINE_TEST_ONLY', 'synthetic/fixed',
        offline_handler=lambda r: httpx.Response(429, headers={'Retry-After': header}))
    with pytest.raises(ProviderUnavailableError) as caught:
        provider.review({'sources': [], 'text': [], 'images': []})
    assert caught.value.retry_after == expected


def test_retry_after_http_date():
    date = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=50), usegmt=True)
    provider = OpenRouterProvider('OFFLINE_TEST_ONLY', 'synthetic/fixed',
        offline_handler=lambda r: httpx.Response(429, headers={'Retry-After': date}))
    with pytest.raises(ProviderUnavailableError) as caught:
        provider.review({'sources': [], 'text': [], 'images': []})
    assert 48 <= caught.value.retry_after <= 50


def test_dispatch_accounting_is_content_free():
    provider = OpenRouterProvider('OFFLINE_TEST_ONLY', 'synthetic/fixed',
        offline_handler=lambda r: httpx.Response(200, json={'model': 'synthetic/fixed',
            'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}))
    provider.review({'sources': [], 'text': [{'source_ref': 'PRIVATE_ACCOUNT', 'text': 'PRIVATE_EVIDENCE'}],
        'images': [{'source_ref': 'PRIVATE_IMAGE', 'data': 'PRIVATE_BYTES'}]})
    assert provider.dispatch_accounting.snapshot() == [
        {'event': 'logical_call', 'provider': 'openrouter', 'model': 'synthetic/fixed',
         'kind': 'review', 'image_bearing': True},
        {'event': 'http_dispatch', 'provider': 'openrouter', 'model': 'synthetic/fixed',
         'kind': 'review', 'image_bearing': True}]
    assert 'PRIVATE' not in json.dumps(provider.dispatch_accounting.snapshot())


@pytest.mark.parametrize('stage', ['classification', 'review'])
def test_failure_survives_pipeline_without_mock(api_client, monkeypatch, stage):
    from verification.offline_openrouter import OfflineRouter, create_dossier
    from app.domain.models import ProcessingRun, ReviewRun
    client, factory, _ = api_client
    router = OfflineRouter(monkeypatch)
    original = router.handle
    def handler(request):
        payload = json.loads(request.content)
        review = 'review-instructions-' in payload['messages'][0]['content']
        if review == (stage == 'review'):
            return httpx.Response(429, headers={'Retry-After': '41'})
        return original(request)
    monkeypatch.setattr('app.ai.gateway.OpenRouterProvider', lambda **kw:
        OpenRouterProvider('OFFLINE_TEST_ONLY', 'synthetic/fixed-model', offline_handler=handler))
    cid = create_dossier(client)
    result = client.post(f'/api/cases/{cid}/process').json()
    assert result['status'] == 'FAILED' and result['report'] is None
    assert result['error_code'] == 'REAL_PROVIDER_RATE_LIMIT'
    with factory() as db:
        run = db.query(ProcessingRun).filter_by(module='pipeline').one()
        assert run.error == 'REAL_PROVIDER_RATE_LIMIT'
        if stage == 'review': assert db.query(ReviewRun).one().error_code == run.error


def test_gateway_schema_failure_is_durable_without_replay(db, regression_settings):
    from app.ai.gateway import ModelGateway
    from app.ai.schemas import ClassificationOutput
    from app.domain.models import ModelRun
    from app.errors import ExtractionValidationError
    from app.safe_logging import safe_error_code
    provider = OpenRouterProvider('OFFLINE_TEST_ONLY', 'synthetic/fixed',
        offline_handler=lambda r: httpx.Response(200, json={'model': 'synthetic/fixed',
            'choices': [{'finish_reason': 'stop', 'message': {'content': '{"invalid":true}'}}]}))
    gateway = ModelGateway(db)
    gateway.provider = provider
    with pytest.raises(ExtractionValidationError) as caught:
        gateway.run('artifact_classifier', ClassificationOutput, 'PRIVATE_EVIDENCE')
    assert safe_error_code(caught.value) == 'SCHEMA_VALIDATION_FAILED'
    db.rollback()
    run = db.query(ModelRun).one()
    assert run.status == 'FAILED' and run.validated_output is None
    assert len(provider.dispatch_accounting.snapshot()) == 2


def test_pipeline_accounting_and_reuse(api_client, monkeypatch):
    from verification.offline_openrouter import OfflineRouter, create_dossier
    from app.ai.dispatch import DispatchAccounting
    client, _, _ = api_client
    router = OfflineRouter(monkeypatch)
    accounting = DispatchAccounting()
    monkeypatch.setattr('app.ai.gateway.OpenRouterProvider', lambda **kw:
        OpenRouterProvider('OFFLINE_TEST_ONLY', 'synthetic/fixed-model',
            offline_handler=router.handle, dispatch_accounting=accounting))
    cid = create_dossier(client)
    assert client.post(f'/api/cases/{cid}/process').json()['report']
    events = accounting.snapshot()
    assert [(e['event'], e['kind'], e['image_bearing']) for e in events] == [
        ('logical_call', 'artifact_classifier', False), ('http_dispatch', 'artifact_classifier', False),
        ('logical_call', 'review', True), ('http_dispatch', 'review', True)]
    assert client.post(f'/api/cases/{cid}/process').json()['reused']
    assert accounting.snapshot() == events
    assert all(set(e) == {'event', 'provider', 'model', 'kind', 'image_bearing'} for e in events)


def test_semantic_stage_failure_does_not_leave_running_model(api_client, monkeypatch):
    from app.ai.providers import MockProvider
    from app.domain.models import ModelRun, ProcessingRun
    from tests.next_phase.test_review_flow import create
    client, factory, _ = api_client
    cid = create(client)
    monkeypatch.setattr(MockProvider, '_classify', lambda *a:
        {'category': 'INVALID_SYNTHETIC_CATEGORY', 'subtype': 'INTRAORAL', 'confidence': 0.8})
    result = client.post(f'/api/cases/{cid}/process').json()
    assert result['status'] == 'FAILED' and result['report'] is None
    with factory() as db:
        run = db.query(ModelRun).one()
        assert run.status == 'FAILED' and run.validated_output is None
        assert not db.query(ProcessingRun).filter_by(status='RUNNING').all()


def test_edit_during_bundle_preparation_stops_review_dispatch(api_client, monkeypatch):
    from app.ai import review
    from app.domain.models import ReviewRun
    from verification.offline_openrouter import OfflineRouter, create_dossier
    client, factory, _ = api_client
    router = OfflineRouter(monkeypatch)
    cid = create_dossier(client)
    original = review.bundle
    def changed(case, **kwargs):
        data = original(case, **kwargs)
        assert client.put(f'/api/cases/{cid}/dossier', json={'duration': 'changed during preparation'}).status_code == 200
        return data
    monkeypatch.setattr(review, 'bundle', changed)
    result = client.post(f'/api/cases/{cid}/process').json()
    assert result['status'] == 'FAILED' and result['error_code'] == 'PROCESSING_INPUT_CHANGED'
    assert len(router.requests) == 1  # Classification only; obsolete review must not dispatch.
    with factory() as db:
        run = db.query(ReviewRun).one()
        assert run.status == 'FAILED' and run.output is None and run.source_index == []
