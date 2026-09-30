import io
import json
import httpx
import pytest
from PIL import Image


def create(client):
    cid = client.post('/api/cases', data={'question': 'Synthetic question'}).json()['case_id']
    client.put(f'/api/cases/{cid}/dossier', json={'symptoms': 'cold sensitivity', 'duration': '3 days',
        'medical_history': 'none', 'medications': 'none', 'allergies': 'none',
        'treatment_plan': 'Synthetic proposed examination', 'previous_reports': 'Synthetic prior note',
        'previous_treatments': 'none'})
    buf = io.BytesIO()
    Image.new('RGB', (64, 64), 'gray').save(buf, 'PNG')
    client.post(f'/api/cases/{cid}/artifacts', files={'file': ('PRIVATE_CANARY.png', buf.getvalue(), 'image/png')})
    return cid


def test_shared_snapshot_reuse_failure_and_history(api_client, monkeypatch):
    from app.ai.providers import MockProvider
    from app.ai import review
    from app.domain.models import ReviewRun, AssessmentSnapshot
    client, sessions, _ = api_client
    cid = create(client)
    result = client.post(f'/api/cases/{cid}/process').json()
    assert result['report']
    report = client.get(f'/api/cases/{cid}/report').json()
    assert report['review']['run']['mode'] == 'MOCK'
    assert report['review']['patient_summary'] and report['review']['professional_report']
    assert 'PRIVATE_CANARY' not in json.dumps(report['review'])
    assert client.post(f'/api/cases/{cid}/process').json()['snapshot'] == report['snapshot_id']
    client.put(f'/api/cases/{cid}/dossier', json={'duration': '4 days'})
    def fail(*args):
        raise RuntimeError('PRIVATE_CANARY https://secret.invalid')
    monkeypatch.setattr(review, 'mock_review', fail)
    failed = client.post(f'/api/cases/{cid}/process').json()
    assert failed['status'] == 'FAILED' and failed['report'] is None
    assert client.get(f'/api/cases/{cid}/report').status_code == 404
    with sessions() as db:
        assert db.query(AssessmentSnapshot).count() == 1
        run = db.query(ReviewRun).order_by(ReviewRun.id.desc()).first()
        assert run.status == 'FAILED' and run.error_code == 'REVIEW_FAILED'
        assert run.output is None


def test_offline_real_adapter_images_and_retry():
    from app.ai.providers import OpenRouterProvider
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        if len(seen) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={'model': 'vendor/fixed-model', 'choices': [{'finish_reason': 'stop', 'message': {'content': '{"offline": true}'}}]})
    provider = OpenRouterProvider('OFFLINE_TEST_ONLY', 'vendor/fixed-model', offline_handler=handler)
    assert provider.review({'sources': [], 'text': [], 'images': [{'source_ref': 's1', 'data': 'AA=='}]}) == {'offline': True}
    assert len(seen) == 2
    assert seen[-1]['messages'][1]['content'][-1]['type'] == 'image_url'


def test_live_transport_disabled(regression_settings):
    from app.ai.providers import OpenRouterProvider
    from app.errors import ProviderUnavailableError
    with pytest.raises(ProviderUnavailableError, match='CONFIGURATION'):
        OpenRouterProvider('OFFLINE_TEST_ONLY', 'vendor/fixed-model').review({'sources': [], 'text': [], 'images': []})


@pytest.mark.parametrize('mode', ['openrouter', 'unknown-provider'])
def test_explicit_real_configuration_never_falls_back(db, regression_settings, monkeypatch, mode):
    from app.ai.gateway import ModelGateway
    from app.errors import ProviderUnavailableError
    monkeypatch.setattr(regression_settings, 'ai_provider', mode)
    with pytest.raises(ProviderUnavailableError):
        ModelGateway(db, strict_real=True)


def test_retry_exhaustion_is_bounded():
    from app.ai.providers import OpenRouterProvider
    from app.errors import ProviderUnavailableError
    requests = []
    def fail(request):
        requests.append(request)
        return httpx.Response(503)
    provider = OpenRouterProvider('OFFLINE_TEST_ONLY', 'vendor/fixed-model', offline_handler=fail)
    with pytest.raises(ProviderUnavailableError):
        provider.review({'sources': [], 'text': [], 'images': []})
    assert len(requests) == 2


@pytest.mark.parametrize('symptom,state', [('facial swelling', 'URGENT_EVALUATION'), ('prescribe me', 'BLOCKED')])
def test_deterministic_restrictions_skip_review(api_client, monkeypatch, symptom, state):
    from app.ai.gateway import ModelGateway
    client, _, _ = api_client
    cid = create(client)
    client.put(f'/api/cases/{cid}/dossier', json={'symptoms': symptom})
    def forbidden(*args):
        pytest.fail('Restricted case must not request model review')
    monkeypatch.setattr(ModelGateway, 'review', forbidden)
    result = client.post(f'/api/cases/{cid}/process').json()
    assert result['safety_state'] == state
    if result['report']:
        assert client.get(f'/api/cases/{cid}/report').json()['review'] is None
