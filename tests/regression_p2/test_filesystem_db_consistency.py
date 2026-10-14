"""Failure boundaries under the existing non-transactional local storage contract.

Orphan and missing-file observations are characterizations, not endorsements of
an operational recovery policy. See phase-7/gate-7.4 before tightening them.
"""
from pathlib import Path

import pytest
from sqlalchemy import event

from app.domain.models import Artifact, AuditEvent, Case, DossierRevision
from app.errors import StorageError
from app.security import ingestion as storage
from tests.regression_p2.test_upload_resource_boundaries import upload_context, files_snapshot


def upload(client, path, data=b'Synthetic new evidence'):
    return client.post(path + '/artifacts', files={'file': ('same.txt', data, 'text/plain')})


def state(sessions):
    with sessions() as db:
        return (
            [(a.public_id, a.storage_key, a.sha256) for a in db.query(Artifact).order_by(Artifact.id)],
            [(c.public_id, c.version) for c in db.query(Case).order_by(Case.id)],
            [(d.id, d.case_version) for d in db.query(DossierRevision).order_by(DossierRevision.id)],
            [(a.id, a.event_type) for a in db.query(AuditEvent).filter_by(event_type='artifact_uploaded').order_by(AuditEvent.id)],
        )


@pytest.mark.parametrize('boundary', ['flush', 'commit'])
@pytest.mark.parametrize('duplicate', [False, True])
def test_db_failure_preserves_rows_and_prior_bytes_characterizes_orphans(upload_context, monkeypatch, boundary, duplicate):
    client, sessions, root, path = upload_context
    assert client.put(path + '/dossier', json={'symptoms': 'Synthetic symptom'}).status_code == 200
    original = b'Synthetic original evidence'
    assert upload(client, path, original).status_code == 201
    before, files = state(sessions), files_snapshot(root)
    engine = sessions.kw['bind']
    with monkeypatch.context() as patch:
        if boundary == 'flush':
            def fail_insert(conn, cursor, statement, parameters, context, executemany):
                table = 'audit_events' if duplicate else 'artifacts'
                if statement.lower().startswith('insert into ' + table):
                    raise RuntimeError('synthetic DB boundary failure')
            event.listen(engine, 'before_cursor_execute', fail_insert)
        else:
            def fail_commit(connection):
                raise RuntimeError('synthetic DB boundary failure')
            patch.setattr(engine.dialect, 'do_commit', fail_commit)
        try:
            with pytest.raises(RuntimeError, match='synthetic DB boundary failure'):
                upload(client, path, original if duplicate else b'Synthetic new evidence')
        finally:
            if boundary == 'flush':
                event.remove(engine, 'before_cursor_execute', fail_insert)
    assert state(sessions) == before
    after = files_snapshot(root)
    assert all(after[key] == value for key, value in files.items())
    # Explicitly documented: final files precede DB commit; no rollback cleanup.
    assert len(after) == len(files) + int(not duplicate)
    response = upload(client, path, original if duplicate else b'Synthetic new evidence')
    assert response.status_code == 201
    assert bool(response.json()['duplicate_of']) == duplicate
    final = state(sessions)
    assert len(final[0]) == len(before[0]) + int(not duplicate)
    assert final[1][0][1] == before[1][0][1] + int(not duplicate)
    assert final[2] == before[2]
    assert len(files_snapshot(root)) == len(after) + int(not duplicate)
    for _, key, _ in final[0]:
        assert (root / key).is_file()


@pytest.mark.parametrize('boundary', ['mkdir', 'open', 'write', 'close'])
def test_storage_failure_rolls_back_and_retry_is_additive(upload_context, monkeypatch, boundary):
    client, sessions, root, path = upload_context
    assert upload(client, path, b'Synthetic prior').status_code == 201
    before, files = state(sessions), files_snapshot(root)
    original_open, original_mkdir = Path.open, Path.mkdir
    with monkeypatch.context() as patch:
        def failing_open(target, mode='r', *args, **kwargs):
            if mode != 'xb':
                return original_open(target, mode, *args, **kwargs)
            if boundary == 'open':
                raise OSError('synthetic private storage path')
            stream = original_open(target, mode, *args, **kwargs)
            class Writer:
                def __enter__(self):
                    return self
                def write(self, data):
                    if boundary == 'write':
                        stream.write(data[:3])
                        stream.flush()
                        raise OSError('synthetic private storage path')
                    return stream.write(data)
                def __exit__(self, *exc):
                    stream.close()
                    if boundary == 'close':
                        raise OSError('synthetic private storage path')
            return Writer()
        def failing_mkdir(target, *args, **kwargs):
            if target.is_relative_to(root):
                raise OSError('synthetic private storage path')
            return original_mkdir(target, *args, **kwargs)
        patch.setattr(Path, 'mkdir' if boundary == 'mkdir' else 'open', failing_mkdir if boundary == 'mkdir' else failing_open)
        response = upload(client, path)
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'STORAGE_ERROR'
    assert 'synthetic private' not in response.text
    assert state(sessions) == before
    after = files_snapshot(root)
    assert all(after[key] == value for key, value in files.items())
    assert len(after) == len(files) + int(boundary in ('write', 'close'))
    with sessions() as db:
        assert db.query(AuditEvent).filter_by(event_type='artifact_rejected').count() == 1
    assert upload(client, path).status_code == 201
    assert len(state(sessions)[0]) == 2
    assert state(sessions)[1][0][1] == before[1][0][1] + 1


def test_missing_file_read_and_duplicate_reuse_characterization(upload_context):
    client, sessions, root, path = upload_context
    first = upload(client, path)
    assert first.status_code == 201
    before = state(sessions)
    key = before[0][0][1]
    (root / key).unlink()  # Simulate external loss of this disposable synthetic object.
    with pytest.raises(StorageError, match='artifact missing'):
        storage.read_bytes(key)
    duplicate = upload(client, path)
    assert duplicate.status_code == 201
    assert duplicate.json()['duplicate_of'] == first.json()['artifact_id']
    assert state(sessions)[:3] == before[:3]
    assert not (root / key).exists()  # Dedup is DB-hash reuse, not repair.
    response = client.post(path + '/process')
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'STORAGE_ERROR'
    assert state(sessions)[:3] == before[:3]


def test_exclusive_creation_preserves_existing_file(regression_settings, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(storage.uuid, 'uuid4', lambda: SimpleNamespace(hex='synthetic-collision'))
    key = storage.store_bytes('CASE-synthetic', 'same.txt', b'original')
    with pytest.raises(StorageError):
        storage.store_bytes('CASE-synthetic', 'same.txt', b'replacement')
    assert storage.read_bytes(key) == b'original'


def test_failed_upload_preserves_report_authority_and_history(upload_context, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.domain.models import AssessmentSnapshot, Report, ProcessingRun
    from tests.regression_p1.test_processing_retry import records
    client, sessions, root, path = upload_context
    assert client.patch(path, data={'dentist_recommendation': 'Tooth 46: RCT recommended'}).status_code == 200
    assert client.put(path + '/dossier', json={'duration': 'three synthetic days'}).status_code == 200
    assert upload(client, path, b'SYNTHETIC Treatment Plan\nTooth 46: RCT recommended').status_code == 201
    processed = client.post(path + '/process')
    assert processed.status_code == 200 and processed.json()['report']
    before = state(sessions)
    history = [records(sessions, model) for model in (AssessmentSnapshot, Report, ProcessingRun)]
    report = client.get(path + '/report').json()
    assessment = client.get(path + '/assessment').json()
    engine = sessions.kw['bind']
    # Start the observer before injecting failure: startup also commits DDL.
    with TestClient(app, raise_server_exceptions=False) as observer:
        observer.cookies.update(client.cookies)
        observer.headers.update(client.headers)
        with monkeypatch.context() as patch:
            def fail_commit(connection):
                raise RuntimeError('synthetic private DB details')
            patch.setattr(engine.dialect, 'do_commit', fail_commit)
            response = upload(observer, path)
        assert response.status_code == 500
        assert response.text == 'Internal Server Error'
    assert state(sessions) == before
    assert [records(sessions, model) for model in (AssessmentSnapshot, Report, ProcessingRun)] == history
    assert client.get(path + '/report').json() == report
    assert client.get(path + '/assessment').json() == assessment
    assert upload(client, path).status_code == 201
    assert client.get(path + '/report').status_code == 404
    assert [records(sessions, model) for model in (AssessmentSnapshot, Report, ProcessingRun)] == history


def test_missing_prior_file_blocks_dossier_upload_without_new_file(upload_context):
    client, sessions, root, path = upload_context
    assert client.put(path + '/dossier', json={'duration': 'synthetic duration'}).status_code == 200
    assert upload(client, path).status_code == 201
    before = state(sessions)
    (root / before[0][0][1]).unlink()
    response = upload(client, path, b'Synthetic different evidence')
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'STORAGE_ERROR'
    assert state(sessions) == before
    assert files_snapshot(root) == {}
