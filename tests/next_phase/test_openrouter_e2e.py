"""Full real-adapter pipeline with synthetic inputs and injected HTTP only."""
import json
import pytest
from verification.offline_openrouter import OfflineRouter, verify_success, create_dossier


def test_offline_openrouter_restart_and_failure(api_client, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.domain.models import ReviewRun, AssessmentSnapshot
    client, sessions, _ = api_client
    router = OfflineRouter(monkeypatch)
    cid, report, frozen = verify_success(client, sessions, router)
    # Dispose connections and create a fresh application client/session lifecycle.
    sessions.kw['bind'].dispose()
    with TestClient(app) as restarted:
        assert restarted.get(f'/api/cases/{cid}/report').json() == report
        count = len(router.requests)
        assert restarted.post(f'/api/cases/{cid}/process').json()['snapshot'] == report['snapshot_id']
        assert len(router.requests) == count
        assert restarted.put(f'/api/cases/{cid}/dossier', json={'duration': '4 days'}).status_code == 200
        router.failure = 'authentication'
        failed = restarted.post(f'/api/cases/{cid}/process').json()
        assert failed['status'] == 'FAILED' and failed['report'] is None
        assert restarted.get(f'/api/cases/{cid}/report').status_code == 404
    with sessions() as db:
        assert db.query(AssessmentSnapshot).one().payload == frozen
        run = db.query(ReviewRun).order_by(ReviewRun.id.desc()).first()
        assert run.error_code == 'REAL_PROVIDER_AUTHENTICATION'
        assert run.output is None and run.source_index == []


@pytest.mark.parametrize('failure,code', [('reference', 'REAL_PROVIDER_REFERENCE'),
    ('safety', 'REAL_PROVIDER_SAFETY'), ('schema', 'SCHEMA_VALIDATION_FAILED')])
def test_review_failure_audit(api_client, monkeypatch, failure, code):
    from app.domain.models import ReviewRun, AssessmentSnapshot
    client, sessions, _ = api_client
    router = OfflineRouter(monkeypatch)
    router.failure = failure
    cid = create_dossier(client)
    result = client.post(f'/api/cases/{cid}/process').json()
    assert result['status'] == 'FAILED' and result['report'] is None
    assert client.get(f'/api/cases/{cid}/report').status_code == 404
    with sessions() as db:
        run = db.query(ReviewRun).one()
        assert run.error_code == code and run.output is None and run.source_index == []
        assert 'PRIVATE' not in run.error_code
        assert db.query(AssessmentSnapshot).count() == 0


def test_configuration_failure_cannot_return_prior_report(api_client, monkeypatch):
    from app.config import get_settings
    from app.domain.models import ReviewRun
    from test_review_flow import create
    client, sessions, _ = api_client
    cid = create(client)
    assert client.post(f'/api/cases/{cid}/process').json()['report']
    monkeypatch.setattr(get_settings(), 'ai_provider', 'openrouter')
    monkeypatch.setattr(get_settings(), 'openrouter_api_key', '')
    result = client.post(f'/api/cases/{cid}/process').json()
    assert result['status'] == 'FAILED' and result['report'] is None
    assert client.get(f'/api/cases/{cid}/report').status_code == 404
    with sessions() as db:
        run = db.query(ReviewRun).order_by(ReviewRun.id.desc()).first()
        assert run.error_code == 'REAL_PROVIDER_CONFIGURATION' and run.output is None


def test_recovery_after_configuration_failure_creates_current_result(api_client, monkeypatch):
    from app.config import get_settings
    from test_review_flow import create
    client, _, _ = api_client
    cid = create(client)
    first = client.post(f'/api/cases/{cid}/process').json()
    assert first['report']
    monkeypatch.setattr(get_settings(), 'ai_provider', 'openrouter')
    assert client.post(f'/api/cases/{cid}/process').json()['status'] == 'FAILED'
    monkeypatch.setattr(get_settings(), 'ai_provider', 'mock')
    recovered = client.post(f'/api/cases/{cid}/process').json()
    assert recovered['report'] and not recovered['reused']
    assert client.get(f'/api/cases/{cid}/report').status_code == 200
