"""Controlled overlapping HTTP mutations on disposable SQLite, ACCOUNT and Demo."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

from fastapi.testclient import TestClient
import pytest

from app.domain.models import AuditEvent, Case, DossierRevision
from tests.regression_p0.test_assessment_freshness import assessed_case, history


def overlap_patch(client, path, data, concurrent, monkeypatch):
    """Pause one admitted PATCH after its read, before its mutation critical section."""
    from app.main import app
    from app.security import case_access

    loaded, release, mutex = Event(), Event(), Lock()
    original = case_access.owned_case
    held = False

    def hold_first(db, case_public_id, principal, *, lock=False):
        nonlocal held
        case = original(db, case_public_id, principal, lock=lock)
        with mutex:
            pause = not held
            held = True
        if pause:
            loaded.set()
            assert release.wait(10), 'Concurrent mutation did not finish'
        return case

    monkeypatch.setattr(case_access, 'owned_case', hold_first)
    with TestClient(app, raise_server_exceptions=False) as peer, ThreadPoolExecutor(max_workers=1) as pool:
        peer.cookies.update(client.cookies)
        peer.headers.update(client.headers)
        pending = pool.submit(peer.patch, path, data=data)
        try:
            assert loaded.wait(10), 'PATCH did not reach its admitted case read'
            concurrent()
        finally:
            release.set()
        response = pending.result(timeout=15)
    return response


@pytest.mark.parametrize('mutation', [
    'patch_disjoint', 'patch_two_commits', 'dossier', 'upload',
    'same_value', 'restore_original',
])
def test_patch_rechecks_committed_inputs_and_version(assessed_case, monkeypatch, mutation):
    client, sessions, path, cid, _ = assessed_case
    initial = client.get(path).json()
    baseline = initial['version']
    question = 'سؤال ساختگی ویرایش‌شده'
    patch = {'question': initial['question'] if mutation == 'restore_original' else question}
    with sessions() as db:
        frozen = history(db)

    def concurrent():
        if mutation in ('patch_disjoint', 'patch_two_commits'):
            first = client.patch(path, data={'dentist_recommendation': 'Tooth 46: Crown recommended'})
            assert first.status_code == 200 and first.json()['version'] == baseline + 1
            if mutation == 'patch_two_commits':
                second = client.patch(path, data={'dentist_recommendation': 'Tooth 46: Filling recommended'})
                assert second.status_code == 200 and second.json()['version'] == baseline + 2
        elif mutation == 'dossier':
            response = client.put(path + '/dossier', json={'duration': 'چهار روز'})
            assert response.status_code == 200 and response.json()['case_version'] == baseline + 1
        elif mutation == 'upload':
            response = client.post(path + '/artifacts', files={
                'file': ('additional.txt', b'SYNTHETIC additional note', 'text/plain')})
            assert response.status_code == 201
        else:
            response = client.patch(path, data={'question': question})
            assert response.status_code == 200 and response.json()['version'] == baseline + 1

    response = overlap_patch(client, path, patch, concurrent, monkeypatch)
    current = client.get(path).json()
    with sessions() as db:
        assert history(db) == frozen, 'Mutations must preserve derived records/history'
    assert response.status_code == 200, response.text
    increment = 1 if mutation == 'same_value' else 3 if mutation == 'patch_two_commits' else 2
    assert response.json() == {'case_id': cid, 'version': baseline + increment,
                               'changed': mutation != 'same_value'}, response.json()
    assert current['version'] == baseline + increment
    assert current['question'] == patch['question']
    if mutation in ('patch_disjoint', 'patch_two_commits'):
        treatment = 'Filling' if mutation == 'patch_two_commits' else 'Crown'
        assert current['dentist_recommendation'] == f'Tooth 46: {treatment} recommended'
    elif mutation == 'dossier':
        assert client.get(path + '/dossier').json()['fields']['duration'] == 'چهار روز'
        with sessions() as db:
            case = db.query(Case).filter_by(public_id=cid).one()
            revisions = db.query(DossierRevision).filter_by(case_id=case.id).order_by(DossierRevision.id).all()
            assert [(row.case_version, row.duration) for row in revisions] == [
                (baseline - 1, 'سه روز'), (baseline + 1, 'چهار روز')]
    elif mutation == 'upload':
        assert len(current['artifacts']) == len(initial['artifacts']) + 1
    assert client.get(path + '/assessment').json()['assessments'] == []
    assert client.get(path + '/report').status_code == 404
    with sessions() as db:
        case = db.query(Case).filter_by(public_id=cid).one()
        versions = [row.detail['new_version'] for row in db.query(AuditEvent).filter_by(
            case_id=case.id, event_type='case_updated').order_by(AuditEvent.id)]
        expected = ([baseline + 1, baseline + 2, baseline + 3] if mutation == 'patch_two_commits'
                    else [baseline + 1] if mutation == 'same_value'
                    else [baseline + 2] if mutation in ('dossier', 'upload')
                    else [baseline + 1, baseline + 2])
        assert versions == expected


def test_failed_stale_patch_rolls_back_without_losing_concurrent_commit(assessed_case, monkeypatch):
    from app.api import routes

    client, sessions, path, cid, _ = assessed_case
    baseline = client.get(path).json()['version']
    committed = {}
    audit = routes.audit
    armed = False

    def fail_after_flush(db, event_type, **kwargs):
        audit(db, event_type, **kwargs)
        if armed and event_type == 'case_updated':
            db.flush()  # Exercise rollback of both material values and audit insertion.
            raise RuntimeError('SYNTHETIC_MUTATION_FAILURE')

    monkeypatch.setattr(routes, 'audit', fail_after_flush)

    def concurrent():
        nonlocal armed
        response = client.patch(path, data={'dentist_recommendation': 'Tooth 46: Crown recommended'})
        assert response.status_code == 200 and response.json()['version'] == baseline + 1
        committed.update(client.get(path).json())
        armed = True

    with sessions() as db:
        frozen = history(db)
    response = overlap_patch(client, path, {'question': 'ویرایش ناموفق ساختگی'}, concurrent, monkeypatch)
    assert response.status_code == 500
    assert client.get(path).json() == committed
    with sessions() as db:
        assert history(db) == frozen
        case = db.query(Case).filter_by(public_id=cid).one()
        events = db.query(AuditEvent).filter_by(case_id=case.id, event_type='case_updated').all()
        assert len(events) == 1 and events[0].detail['new_version'] == baseline + 1
    assert client.get(path + '/assessment').json()['assessments'] == []
    assert client.get(path + '/report').status_code == 404
