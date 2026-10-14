"""Current assessment authority, using real ACCOUNT/Demo admission and Mock only."""
from copy import deepcopy

import pytest

from app.domain.enums import CaseStatus, ProcessingRunStatus, RunAuthority
from app.domain.models import (Assessment, AssessmentSnapshot, Case, ProcessingRun,
                               Report, public_id)


def history(db):
    """Compare persisted reasoning/history columns, not mutable ORM references."""
    return {model.__tablename__: {
        row.id: deepcopy({column.name: getattr(row, column.name)
                          for column in model.__table__.columns})
        for row in db.query(model).all()}
        for model in (Assessment, AssessmentSnapshot, ProcessingRun, Report)}


@pytest.fixture(params=['ACCOUNT', 'DEMO'])
def assessed_case(api_client, request):
    client, sessions, _ = api_client
    prefix = '/api/cases'
    if request.param == 'DEMO':
        response = client.post('/api/demo/session')
        assert response.status_code == 200
        client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        prefix = '/api/demo/cases'
    created = client.post(prefix, data={
        'question': 'پیشنهاد درمان دندان ۴۶ چه پشتوانه‌ای دارد؟',
        'dentist_recommendation': 'Tooth 46: RCT recommended'})
    assert created.status_code == 201
    cid = created.json()['case_id']
    path = f'{prefix}/{cid}'
    assert client.put(path + '/dossier', json={'duration': 'سه روز'}).status_code == 200
    uploaded = client.post(path + '/artifacts', files={
        'file': ('plan.txt', b'SYNTHETIC Treatment Plan\nTooth 46: RCT recommended', 'text/plain')})
    assert uploaded.status_code == 201
    processed = client.post(path + '/process')
    assert processed.status_code == 200 and processed.json()['report'], processed.text
    response = client.get(path + '/assessment')
    assert response.status_code == 200 and response.json()['assessments'], response.text
    assert set(response.json()) == {'case_id', 'status', 'assessments'}
    assert client.get(path + '/report').status_code == 200
    return client, sessions, path, cid, response.json()


@pytest.mark.parametrize('change', [
    'none', 'question', 'recommendation', 'dossier', 'evidence', 'RUNNING', 'FAILED',
    'other_case_running', 'module_running',
])
def test_only_current_assessments_are_returned(assessed_case, change):
    client, sessions, path, cid, original = assessed_case
    with sessions() as db:
        original_history = history(db)
    if change == 'question':
        assert client.patch(path, data={'question': 'سؤال ساختگی دیگری دربارهٔ درمان'}).status_code == 200
    elif change == 'recommendation':
        assert client.patch(path, data={'dentist_recommendation': 'Tooth 46: Crown recommended'}).status_code == 200
    elif change == 'dossier':
        assert client.put(path + '/dossier', json={'duration': 'چهار روز'}).status_code == 200
    elif change == 'evidence':
        assert client.post(path + '/artifacts', files={
            'file': ('extra.txt', b'SYNTHETIC prior note: additional evidence', 'text/plain')}).status_code == 201
    elif change in ('RUNNING', 'FAILED', 'other_case_running', 'module_running'):
        # Persist a newer unresolved/failed attempt without changing inputs, so
        # this tests latest-attempt authority independently of hash freshness.
        with sessions() as db:
            case = db.query(Case).filter_by(public_id=cid).one()
            prior = db.query(ProcessingRun).filter_by(case_id=case.id, module='pipeline').one()
            case_id = case.id
            if change == 'other_case_running':
                other = Case(public_id=public_id('CASE'), user_id=case.user_id)
                db.add(other)
                db.flush()
                case_id = other.id
            status = ProcessingRunStatus.FAILED if change == 'FAILED' else ProcessingRunStatus.RUNNING
            db.add(ProcessingRun(public_id=public_id('RUN'), case_id=case_id,
                module='classification' if change == 'module_running' else 'pipeline',
                status=status, authority=RunAuthority.NON_AUTHORITATIVE,
                input_hash=prior.input_hash, input_version=prior.input_version, attempt=2))
            if change in ('RUNNING', 'FAILED'):
                case.status = CaseStatus.FAILED if change == 'FAILED' else CaseStatus.PROCESSING
            db.commit()

    with sessions() as db:
        before_read = history(db)
        # Input changes and new attempts must not rewrite previous history.
        for table, rows in original_history.items():
            assert all(before_read[table][key] == value for key, value in rows.items())
    current_status = client.get(path).json()['status']
    assessment = client.get(path + '/assessment')
    report = client.get(path + '/report')
    with sessions() as db:
        assert history(db) == before_read, 'Reading freshness must not mutate reasoning history'
    assert assessment.status_code == 200
    assert set(assessment.json()) == {'case_id', 'status', 'assessments'}
    assert assessment.json()['case_id'] == cid
    assert assessment.json()['status'] == current_status
    if change in ('none', 'other_case_running', 'module_running'):
        assert assessment.json() == original
        assert report.status_code == 200
    else:
        assert report.status_code == 404 and report.json()['detail'] == 'REPORT_NOT_READY'
        assert assessment.json()['assessments'] == [], 'Historical assessment leaked as current'


def test_fresh_success_after_edit_restores_assessments(assessed_case):
    client, sessions, path, _, original = assessed_case
    assert client.put(path + '/dossier', json={'duration': 'چهار روز'}).status_code == 200
    result = client.post(path + '/process')
    assert result.status_code == 200 and result.json()['report'], result.text
    with sessions() as db:
        before = history(db)
        assert len(before['assessment_snapshots']) == 2
        assert len(before['reports']) == 2
    assert client.get(path + '/assessment').json() == original
    assert client.get(path + '/report').status_code == 200
    with sessions() as db:
        assert history(db) == before


@pytest.mark.parametrize('change', ['rules_version', 'pack_unavailable'])
def test_processing_contract_changes_hide_assessments(
        assessed_case, regression_settings, monkeypatch, change):
    client, sessions, path, _, _ = assessed_case
    if change == 'rules_version':
        # Rule version participates in both ACCOUNT and fixed-identity Demo hashes.
        from app.pipeline.orchestrator import MODULE_VERSIONS
        monkeypatch.setitem(MODULE_VERSIONS, 'assessment', 'synthetic-new-rules')
    else:
        monkeypatch.setattr(regression_settings, 'require_clinician_reviewed_knowledge_pack', True)
    with sessions() as db:
        before = history(db)
    response = client.get(path + '/assessment')
    report = client.get(path + '/report')
    with sessions() as db:
        assert history(db) == before
    assert report.status_code == (422 if change == 'pack_unavailable' else 404)
    assert response.status_code == 200
    assert response.json()['assessments'] == []
