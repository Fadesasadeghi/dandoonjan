from app.domain.models import Case


def test_dossier_versions_completeness_and_safety(api_client):
    client, Session, _ = api_client
    cid = client.post('/api/cases', data={'question': 'Synthetic question'}).json()['case_id']
    initial = client.get(f'/api/cases/{cid}/dossier').json()
    assert 'allergies' in initial['missing_information']
    values = {'symptoms': 'facial swelling', 'duration': '3 days', 'allergies': 'none'}
    saved = client.put(f'/api/cases/{cid}/dossier', json=values)
    assert saved.status_code == 200
    assert 'allergies' not in saved.json()['missing_information']
    assert client.get(f'/api/cases/{cid}/dossier').json()['fields']['duration'] == '3 days'
    version = saved.json()['case_version']
    assert client.put(f'/api/cases/{cid}/dossier', json=values).json()['case_version'] == version
    result = client.post(f'/api/cases/{cid}/process').json()
    assert result['safety_state'] == 'URGENT_EVALUATION'
    assert client.put(f'/api/cases/{cid}/dossier', json={'duration': '4 days'}).json()['case_version'] == version + 1
    assert client.get(f'/api/cases/{cid}/report').status_code == 404


def test_dossier_rejects_unknown_and_preserves_history(api_client):
    from app.domain.models import DossierRevision
    client, Session, _ = api_client
    cid = client.post('/api/cases', data={'question': 'Synthetic'}).json()['case_id']
    assert client.put(f'/api/cases/{cid}/dossier', json={'patient_name': 'not accepted'}).status_code == 422
    for value in ['none', 'unknown']:
        assert client.put(f'/api/cases/{cid}/dossier', json={'medications': value}).status_code == 200
    with Session() as db:
        case = db.query(Case).filter_by(public_id=cid).one()
        assert [r.medications for r in db.query(DossierRevision).filter_by(case_id=case.id).order_by(DossierRevision.id)] == ['none', 'unknown']


def test_empty_dossier_enrolls_once_without_fabricating_information(api_client):
    from app.domain.models import DossierRevision
    client, sessions, _ = api_client
    cid = client.post('/api/cases', data={'question':'Synthetic'}).json()['case_id']
    first = client.put(f'/api/cases/{cid}/dossier', json={}).json()
    second = client.put(f'/api/cases/{cid}/dossier', json={}).json()
    assert first['case_version'] == second['case_version']
    with sessions() as db:
        assert db.query(DossierRevision).count() == 1
    assert client.post(f'/api/cases/{cid}/process').json()['status'] == 'NEEDS_MORE_EVIDENCE'
