"""Processing contract characterization: synthetic SQLite and Mock only."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event

import pytest

from app.domain.models import AssessmentSnapshot, Case, ProcessingRun, Report
from tests.next_phase.test_processing_concurrency import peer


@pytest.fixture(params=['ACCOUNT', 'DEMO'])
def workflow(api_client, request):
    client, sessions, _ = api_client
    prefix = '/api/cases'
    if request.param == 'DEMO':
        token = client.post('/api/demo/session').json()['csrf_token']
        client.headers['X-CSRF-Token'] = token
        prefix = '/api/demo/cases'
    response = client.post(prefix, data={
        'question': 'Synthetic question about tooth 46',
        'dentist_recommendation': 'Tooth 46: RCT recommended'})
    assert response.status_code == 201
    cid = response.json()['case_id']
    path = f'{prefix}/{cid}'
    assert client.put(path + '/dossier', json={'duration': 'three synthetic days'}).status_code == 200
    assert client.post(path + '/artifacts', files={'file': (
        'plan.txt', b'SYNTHETIC Treatment Plan\nTooth 46: RCT recommended', 'text/plain')}).status_code == 201
    return client, sessions, path, cid


def no_current(client, path):
    assert client.get(path + '/report').status_code == 404
    assert client.get(path + '/assessment').json()['assessments'] == []


def records(sessions, model):
    with sessions() as db:
        return {row.id: deepcopy({c.name: getattr(row, c.name)
                                 for c in model.__table__.columns})
                for row in db.query(model).all()}


def test_failure_retry_reuse_and_changed_input_history(workflow, monkeypatch):
    from app.ai.providers import MockProvider
    from app.errors import ProviderUnavailableError
    client, sessions, path, cid = workflow
    no_current(client, path)
    assert records(sessions, ProcessingRun) == {}
    original = MockProvider.run

    def fail(*args, **kwargs):
        raise ProviderUnavailableError(category='authentication')

    monkeypatch.setattr(MockProvider, 'run', fail)
    failed_ids = []
    for attempt in (1, 2):
        response = client.post(path + '/process')
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'FAILED' and result['report'] is None
        failed_ids.append(result['pipeline_run_id'])
        assert client.get(path).json()['status'] == 'FAILED'
        no_current(client, path)
    assert len(set(failed_ids)) == 2
    failed_history = records(sessions, ProcessingRun)
    monkeypatch.setattr(MockProvider, 'run', original)
    success = client.post(path + '/process').json()
    assert success['report'] and not success['reused']
    assert client.get(path + '/assessment').json()['assessments']
    snapshot_history = records(sessions, AssessmentSnapshot)
    report_history = records(sessions, Report)
    runs = records(sessions, ProcessingRun)
    assert all(runs[key] == value for key, value in failed_history.items())
    pipelines = [r for r in runs.values() if r['module'] == 'pipeline']
    assert [r['attempt'] for r in pipelines] == [1, 2, 3]
    assert [r['status'].value for r in pipelines] == ['FAILED', 'FAILED', 'SUCCEEDED']

    monkeypatch.setattr(MockProvider, 'run', lambda *a, **kw: pytest.fail('Reuse dispatched Mock'))
    reused = client.post(path + '/process').json()
    assert reused['reused'] and reused['pipeline_run_id'] == success['pipeline_run_id']
    assert reused['report'] == success['report']
    assert records(sessions, ProcessingRun) == runs

    assert client.patch(path, data={'question': 'Changed synthetic question'}).json()['changed']
    no_current(client, path)
    monkeypatch.setattr(MockProvider, 'run', fail)
    assert client.post(path + '/process').json()['status'] == 'FAILED'
    no_current(client, path)
    assert records(sessions, AssessmentSnapshot) == snapshot_history
    assert records(sessions, Report) == report_history
    monkeypatch.setattr(MockProvider, 'run', original)
    fresh = client.post(path + '/process').json()
    assert fresh['report'] and fresh['report'] != success['report']
    assert client.get(path + '/report').json()['report_id'] == fresh['report']
    with sessions() as db:
        case = db.query(Case).filter_by(public_id=cid).one()
        pipelines = db.query(ProcessingRun).filter_by(module='pipeline').order_by(ProcessingRun.id).all()
        assert [r.attempt for r in pipelines] == [1, 2, 3, 1, 2]
        assert [r.authority.value for r in pipelines] == [
            'NON_AUTHORITATIVE', 'NON_AUTHORITATIVE', 'SUPERSEDED', 'NON_AUTHORITATIVE', 'ACTIVE']
        assert pipelines[-1].input_version == f'case-v{case.version}'
        assert not db.query(ProcessingRun).filter_by(status='RUNNING').count()
    assert len(records(sessions, AssessmentSnapshot)) == 2
    assert len(records(sessions, Report)) == 2
    assert all(records(sessions, AssessmentSnapshot)[k] == v for k, v in snapshot_history.items())
    assert all(records(sessions, Report)[k] == v for k, v in report_history.items())


def test_running_request_reconciles_without_second_execution(workflow, monkeypatch):
    from app.ai.providers import MockProvider
    client, sessions, path, _ = workflow
    entered, release = Event(), Event()
    original = MockProvider.run
    calls = []

    def held(self, prompt, *args):
        if prompt.prompt_id == 'artifact_classifier':
            calls.append(prompt.prompt_id)
            entered.set()
            assert release.wait(15)
        return original(self, prompt, *args)

    monkeypatch.setattr(MockProvider, 'run', held)
    with peer(client) as other, ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, path + '/process')
        try:
            assert entered.wait(10)
            assert other.get(path).json()['status'] == 'PROCESSING'
            no_current(other, path)
            response = other.post(path + '/process')
            assert response.status_code == 200
            observed = response.json()
            assert observed['status'] == 'PROCESSING' and observed['report'] is None
            assert not observed['reused']
        finally:
            release.set()
        result = pending.result(timeout=20).json()
    assert result['report'] and result['pipeline_run_id'] == observed['pipeline_run_id']
    assert len(calls) == 1
    assert client.get(path).json()['status'] == 'REPORT_READY'
    assert client.get(path + '/report').json()['report_id'] == result['report']
    assert len([r for r in records(sessions, ProcessingRun).values() if r['module'] == 'pipeline']) == 1
