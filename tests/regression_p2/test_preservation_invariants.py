"""Dossier preservation gaps: synthetic ACCOUNT/Demo, SQLite and Mock only."""
import pytest

from app.domain.models import AuditEvent, Case, DossierRevision
from app.governance.immutability import ImmutabilityViolationError
from tests.regression_p0.test_assessment_freshness import assessed_case, history
from tests.regression_p1.test_processing_retry import records


def test_dossier_failure_noop_and_revision_preserve_history(assessed_case, monkeypatch):
    client, sessions, path, _, _ = assessed_case
    revisions = records(sessions, DossierRevision)
    audits = records(sessions, AuditEvent)
    cases = records(sessions, Case)
    dossier = client.get(path + '/dossier').json()
    report = client.get(path + '/report').json()
    assessment = client.get(path + '/assessment').json()
    with sessions() as db:
        derived = history(db)
    assert len(revisions) == 1

    # Fail the real commit after the new revision/version and audit were flushed.
    # A new session below must see the old durable state, not pending ORM values.
    engine = sessions.kw['bind']
    with monkeypatch.context() as patch:
        def fail_commit(connection):
            raise RuntimeError('synthetic dossier commit failure')
        patch.setattr(engine.dialect, 'do_commit', fail_commit)
        with pytest.raises(RuntimeError, match='synthetic dossier commit failure'):
            client.put(path + '/dossier', json={'duration': 'four synthetic days'})
    assert records(sessions, Case) == cases
    assert records(sessions, DossierRevision) == revisions
    assert records(sessions, AuditEvent) == audits
    assert client.get(path + '/dossier').json() == dossier
    assert client.get(path + '/report').json() == report
    assert client.get(path + '/assessment').json() == assessment
    with sessions() as db:
        assert history(db) == derived

    # No-op saves may append an audit event, but cannot fabricate a revision.
    noop = client.put(path + '/dossier', json={'duration': dossier['fields']['duration']})
    assert noop.status_code == 200 and noop.json() == dossier
    assert records(sessions, DossierRevision) == revisions
    assert client.get(path + '/report').json() == report

    for increment, value in enumerate(('four synthetic days', 'five synthetic days'), 1):
        before = records(sessions, DossierRevision)
        saved = client.put(path + '/dossier', json={'duration': value})
        assert saved.status_code == 200
        assert saved.json()['case_version'] == dossier['case_version'] + increment
        after = records(sessions, DossierRevision)
        assert len(after) == len(before) + 1
        assert all(after[key] == row for key, row in before.items())
        new = after[(after.keys() - before.keys()).pop()]
        assert new['duration'] == value
        assert new['case_version'] == saved.json()['case_version']
        assert client.get(path + '/dossier').json() == saved.json()
        assert client.get(path + '/report').status_code == 404
        assert client.get(path + '/assessment').json()['assessments'] == []
        with sessions() as db:
            assert history(db) == derived
    final_audits = records(sessions, AuditEvent)
    assert all(final_audits[key] == row for key, row in audits.items())


@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_dossier_revision_guard_preserves_durable_state(assessed_case, operation):
    client, sessions, path, _, _ = assessed_case
    before = records(sessions, DossierRevision)
    report = client.get(path + '/report').json()
    dossier = client.get(path + '/dossier').json()
    with sessions() as db:
        row = db.query(DossierRevision).one()
        if operation == 'update':
            row.duration = 'synthetic forbidden rewrite'
        else:
            db.delete(row)
        with pytest.raises(ImmutabilityViolationError, match='DossierRevision'):
            db.flush()
        db.rollback()
    assert records(sessions, DossierRevision) == before
    assert client.get(path + '/dossier').json() == dossier
    assert client.get(path + '/report').json() == report
