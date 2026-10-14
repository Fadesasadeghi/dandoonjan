"""Synthetic HTTP intake parity; no provider dispatch or real database."""
import pytest

from app.domain.models import Case
from tests.regression_p0.test_assessment_freshness import assessed_case, history


@pytest.fixture(params=['ACCOUNT', 'DEMO'])
def intake(api_client, request):
    client, sessions, _ = api_client
    prefix = '/api/cases'
    if request.param == 'DEMO':
        response = client.post('/api/demo/session')
        assert response.status_code == 200
        client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        prefix = '/api/demo/cases'
    return client, sessions, prefix


def form(values, encoding):
    if encoding == 'multipart':
        return {'files': {key: (None, value) for key, value in values.items()}}
    return {'data': values}


@pytest.mark.parametrize('encoding', ['urlencoded', 'multipart'])
def test_empty_recommendation_patch_matches_creation(intake, encoding):
    client, sessions, prefix = intake
    created = client.post(prefix, **form({'question': 'Synthetic',
        'dentist_recommendation': ''}, encoding))
    assert created.status_code == 201
    path = prefix + '/' + created.json()['case_id']
    assert client.get(path).json()['dentist_recommendation'] == ''
    edited = client.patch(path, data={'dentist_recommendation': 'Synthetic recommendation'})
    baseline = edited.json()['version']
    omitted = client.patch(path, data={'question': 'Synthetic'})
    assert omitted.json()['changed'] is False
    response = client.patch(path, **form({'dentist_recommendation': ''}, encoding))
    assert response.status_code == 200
    assert response.json() == {'case_id': created.json()['case_id'],
                               'version': baseline + 1, 'changed': True}
    assert client.get(path).json()['dentist_recommendation'] == ''
    with sessions() as db:
        assert db.query(Case).filter_by(public_id=created.json()['case_id']).one().dentist_recommendation_text == ''
    assert client.patch(path, **form({'dentist_recommendation': ''}, encoding)).json() == {
        'case_id': created.json()['case_id'], 'version': baseline + 1, 'changed': False}


@pytest.mark.parametrize('encoding', ['urlencoded', 'multipart'])
def test_empty_account_context_patch_matches_creation(api_client, encoding):
    client, sessions, _ = api_client
    cid = client.post('/api/cases', data={'question': 'Synthetic', 'context': ''}).json()['case_id']
    path = '/api/cases/' + cid
    baseline = client.patch(path, data={'context': 'Synthetic context'}).json()['version']
    assert client.patch(path, data={'question': 'Synthetic'}).json()['changed'] is False
    response = client.patch(path, **form({'context': ''}, encoding))
    assert response.status_code == 200
    assert response.json() == {'case_id': cid, 'version': baseline + 1, 'changed': True}
    with sessions() as db:
        assert db.query(Case).filter_by(public_id=cid).one().context_text == ''


@pytest.mark.parametrize('value', ['x', ' \t ', '  سؤال ساختگی  ', 'x' * 10001])
def test_nonempty_case_text_round_trip_and_noop_parity(intake, value):
    client, _, prefix = intake
    payload = {'question': value, 'dentist_recommendation': value}
    response = client.post(prefix, data=payload)
    assert response.status_code == 201
    path = prefix + '/' + response.json()['case_id']
    before = client.get(path).json()
    assert {key: before[key] for key in payload} == payload
    assert client.patch(path, data=payload).json() == {
        'case_id': before['case_id'], 'version': before['version'], 'changed': False}
    assert client.patch(path, data={'question': 'Other', 'dentist_recommendation': 'Other'}).status_code == 200
    assert client.patch(path, data=payload).json()['changed'] is True
    after = client.get(path).json()
    assert {key: after[key] for key in payload} == payload
    assert after['version'] == before['version'] + 2


@pytest.mark.parametrize('payload', [{}, {'question': ''}])
def test_missing_and_empty_question_current_behavior(intake, payload):
    client, _, prefix = intake
    assert client.post(prefix, data=payload).status_code == 422
    cid = client.post(prefix, data={'question': 'Synthetic'}).json()['case_id']
    path = prefix + '/' + cid
    before = client.get(path).json()
    response = client.patch(path, data=payload)
    assert response.status_code == 200
    assert response.json()['changed'] is False
    assert client.get(path).json() == before


@pytest.mark.parametrize('payload,status,expected', [
    ({'duration': '  three days  '}, 200, 'three days'),
    ({'duration': ''}, 200, ''),
    ({'duration': ' \t '}, 200, ''),
    ({'duration': None}, 200, 'original'),
    ({}, 200, 'original'),
    ({'duration': 'x' * 10000}, 200, 'x' * 10000),
    ({'duration': 'x' * 10001}, 422, 'original'),
    ({'duration': 123}, 422, 'original'),
    ({'duration': []}, 422, 'original'),
    ({'unknown': 'value'}, 422, 'original'),
])
def test_dossier_validation_parity(intake, payload, status, expected):
    client, _, prefix = intake
    cid = client.post(prefix, data={'question': 'Synthetic'}).json()['case_id']
    path = prefix + '/' + cid + '/dossier'
    before = client.put(path, json={'duration': 'original'}).json()
    assert client.put(path, json=payload).status_code == status
    after = client.get(path).json()
    assert after['fields']['duration'] == expected
    assert after['case_version'] == before['case_version'] + (expected != 'original')


def test_clearing_recommendation_invalidates_current_results_preserves_history(assessed_case):
    client, sessions, path, cid, _ = assessed_case
    before = client.get(path).json()
    with sessions() as db:
        frozen = history(db)
    response = client.patch(path, data={'dentist_recommendation': ''})
    assert response.json() == {'case_id': cid, 'version': before['version'] + 1, 'changed': True}
    assert client.get(path).json()['artifacts'] == before['artifacts']
    assert client.get(path + '/assessment').json()['assessments'] == []
    assert client.get(path + '/report').status_code == 404
    with sessions() as db:
        assert history(db) == frozen


@pytest.mark.parametrize('field', ['question', 'dentist_recommendation', 'context'])
def test_file_is_not_a_text_field(intake, field):
    client, _, prefix = intake
    values = {} if field == 'question' else {'question': 'Synthetic'}
    uploaded = {'files': {field: ('unexpected.txt', b'Synthetic', 'text/plain')}, 'data': values}
    # Demo intentionally ignores client context at creation and update.
    expected = 201 if field == 'context' and '/demo/' in prefix else 422
    assert client.post(prefix, **uploaded).status_code == expected
    cid = client.post(prefix, data={'question': 'Synthetic'}).json()['case_id']
    path = prefix + '/' + cid
    before = client.get(path).json()
    assert client.patch(path, **uploaded).status_code == 422
    assert client.get(path).json() == before


def test_demo_context_remains_server_owned(api_client):
    client, sessions, _ = api_client
    response = client.post('/api/demo/session')
    assert response.status_code == 200
    client.headers['X-CSRF-Token'] = response.json()['csrf_token']
    prefix = '/api/demo/cases'
    from app.core.cases.sample import DEMO_MARKER
    cid = client.post(prefix, data={'question': 'Synthetic', 'context': 'client hint'}).json()['case_id']
    for value in ['', 'client hint']:
        response = client.patch(prefix + '/' + cid, data={'context': value})
        assert response.status_code == 200 and response.json()['changed'] is False
    with sessions() as db:
        assert db.query(Case).filter_by(public_id=cid).one().context_text == DEMO_MARKER
