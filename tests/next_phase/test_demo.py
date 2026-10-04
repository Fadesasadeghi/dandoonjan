"""Synthetic Demo regressions; no live transports or credentials."""
import json
from types import SimpleNamespace

import pymupdf
import pytest

MARKER = 'DANDOONJAN_SYNTHETIC_SAMPLE_V1'
DOSSIER = dict(symptoms='حساسیت به سرما در دندان ۴۶ — ساختگی', duration='سه روز',
    medical_history='ساختگی؛ گزارش نشده', medications='ندارد', allergies='ندارد',
    treatment_plan='Synthetic Treatment Plan: Tooth 46 RCT recommended',
    previous_reports='ساختگی؛ معاینه ثبت نشده', previous_treatments='ندارد')


def create_demo(client, context=MARKER, symptoms=None, plan=None):
    cid = client.post('/api/cases', data={'question': 'آیا پیشنهاد عصب‌کشی دندان ۴۶ پشتوانه دارد؟',
        'dentist_recommendation': 'عصب‌کشی و روکش دندان ۴۶ پیشنهاد شده', 'context': context}).json()['case_id']
    client.put(f'/api/cases/{cid}/dossier', json={**DOSSIER, **({'symptoms': symptoms} if symptoms else {})})
    from app.core.cases.sample import image_pattern, plan_pdf
    files = [('طرح-درمان-نمونه.txt', (plan or client.get('/api/demo/sample').text).encode(), 'text/plain', 'treatment_plan'),
        ('synthetic-pattern-not-radiograph.png', image_pattern(), 'image/png', 'dental_image'),
        ('synthetic-plan.pdf', plan_pdf(), 'application/pdf', 'treatment_plan'),
        ('synthetic-prior-report.txt', b'SYNTHETIC prior clinical note\nTooth 46: cold sensitivity for three days. No examination recorded.', 'text/plain', 'previous_report')]
    for name, content, mime, role in files:
        assert client.post(f'/api/cases/{cid}/artifacts', files={'file': (name, content, mime)}, data={'document_role': role}).status_code == 201
    return cid


@pytest.mark.parametrize('context,expected', [(MARKER, True), ('', False), (MARKER+' ', False), ('prefix '+MARKER, False)])
def test_exact_marker(context, expected):
    from app.core.cases.sample import is_demo
    assert is_demo(SimpleNamespace(context_text=context)) is expected


def test_demo_offline_identity_and_reuse(api_client, regression_settings, monkeypatch):
    from app.ai import gateway
    from app.domain.models import AssessmentSnapshot, ModelRun, Case
    from app.pipeline.orchestrator import effective_input_hash
    client, sessions, _ = api_client
    cid = create_demo(client)
    monkeypatch.setattr(regression_settings, 'ai_provider', 'openrouter')
    monkeypatch.setattr(regression_settings, 'ai_model_name', 'vendor/live-model')
    monkeypatch.setattr(regression_settings, 'live_provider_enabled', True)
    monkeypatch.setattr(regression_settings, 'openrouter_api_key', 'OFFLINE_TEST_ONLY')
    monkeypatch.setattr(gateway.OpenRouterProvider, '_exchange', lambda *a, **kw: pytest.fail('Live dispatch'))
    monkeypatch.setattr(gateway, 'OpenRouterProvider', lambda **kw: pytest.fail('Live provider constructed'))
    before = regression_settings.model_dump()
    assert client.post(f'/api/cases/{cid}/process').json()['report']
    report = client.get(f'/api/cases/{cid}/report').json()
    assert report['review']['run']['provider'] == 'mock'
    assert report['review']['run']['mode'] == 'MOCK'
    assert report['review']['diagnostic_hypotheses'] == []
    with sessions() as db:
        snap = db.query(AssessmentSnapshot).one()
        assert snap.versions['ai_provider'] == 'mock'
        assert snap.versions['ai_model'] == 'mock-evidence-v1'
        assert {(r.provider, r.model) for r in db.query(ModelRun)} == {('mock', 'mock-evidence-v1')}
        case = db.query(Case).filter_by(public_id=cid).one()
        previous = effective_input_hash(db, case)
        monkeypatch.setattr(regression_settings, 'ai_model_name', 'vendor/another-model')
        assert effective_input_hash(db, case) == previous
    monkeypatch.setattr(regression_settings, 'ai_model_name', before['ai_model_name'])
    assert regression_settings.model_dump() == before
    assert client.post(f'/api/cases/{cid}/process').json()['snapshot'] == report['snapshot_id']


def test_unmarked_provider_and_production_policy(api_client, regression_settings, monkeypatch):
    from app.ai import gateway
    from app.errors import ProviderUnavailableError
    client, _, _ = api_client
    seen = []
    def reject(**kw):
        seen.append(kw)
        raise ProviderUnavailableError(category='configuration')
    monkeypatch.setattr(gateway, 'OpenRouterProvider', reject)
    monkeypatch.setattr(regression_settings, 'ai_provider', 'openrouter')
    cid = create_demo(client, context=MARKER+' ')
    assert client.post(f'/api/cases/{cid}/process').json()['status'] == 'FAILED'
    assert len(seen) == 1
    seen.clear()
    cid = create_demo(client)
    monkeypatch.setattr(regression_settings, 'environment', 'production')
    assert client.post(f'/api/cases/{cid}/process').json()['status'] == 'FAILED'
    assert not seen


def test_fixture_text_and_png_nonclinical(api_client):
    from app.domain.models import Artifact, Finding, AssessmentSnapshot
    client, sessions, _ = api_client
    assert 'SYNTHETIC' in client.get('/api/demo/sample').text
    with pymupdf.open(stream=client.get('/api/demo/sample-plan').content, filetype='pdf') as pdf:
        assert 'SYNTHETIC' in pdf[0].get_text()
    cid = create_demo(client)
    client.post(f'/api/cases/{cid}/process')
    with sessions() as db:
        image = db.query(Artifact).filter_by(original_filename='synthetic-pattern-not-radiograph.png').one()
        assert image.document_role == 'dental_image'
        assert image.category.value != 'RADIOGRAPH'
        assert not db.query(Finding).filter_by(artifact_id=image.id).count()
        snap = db.query(AssessmentSnapshot).one()
        assert any(g['gap_type'] == 'APPROPRIATE_RADIOGRAPH' and g['status'] == 'MISSING' for g in snap.payload['gaps'])


def test_summary_sources_scope_changes_and_unchanged_rules(api_client):
    from app.domain.models import AssessmentSnapshot, Finding, TreatmentItem, Extraction, Case, Artifact
    client, sessions, _ = api_client
    other = create_demo(client, symptoms='OTHER_CASE_CANARY')
    client.post(f'/api/cases/{other}/process')
    cid = create_demo(client)
    client.post(f'/api/cases/{cid}/process')
    first = client.get(f'/api/cases/{cid}/report').json()['review']
    assert 'OTHER_CASE_CANARY' not in json.dumps(first)
    for audience in ('patient_summary', 'professional_report'):
        text = ' '.join(a['text'] for a in first[audience])
        for term in ('حساسیت', 'سه روز', 'روکش', 'معاینه', 'پالپ', 'رادیوگرافی', 'گفت‌وگو'):
            assert term in text
    assert {s['kind'] for s in first['source_index']} >= {'PATIENT_REPORTED', 'CLINICIAN_REPORTED', 'DOCUMENT_EXTRACTED'}
    document_assertion = first['patient_summary'][2]
    assert len(document_assertion['source_refs']) == 3
    assert not {s['source_ref'] for s in first['source_index'] if s.get('document_role') == 'dental_image'} & set(document_assertion['source_refs'])
    allowed = {s['source_ref'] for s in first['source_index']}
    for assertion in first['patient_summary'] + first['professional_report']:
        assert set(assertion['source_refs']) <= allowed
    # Poison only old synthetic derivation facts: a broad historical query would
    # repeat this tooth in the new summary. Original artifact text stays intact.
    with sessions() as db:
        case = db.query(Case).filter_by(public_id=cid).one()
        old_run = db.query(AssessmentSnapshot).filter_by(case_id=case.id).one().derivation_run_id
        for finding in db.query(Finding).filter_by(case_id=case.id, derivation_run_id=old_run):
            finding.normalized_subject = 'TOOTH_99'
        for item in db.query(TreatmentItem).join(Extraction).join(Artifact).filter(
                Artifact.case_id == case.id, TreatmentItem.derivation_run_id == old_run):
            item.tooth_id = 'TOOTH_99'
        db.commit()
    client.put(f'/api/cases/{cid}/dossier', json={'symptoms': 'NEW_SYMPTOM_CANARY'})
    client.post(f'/api/cases/{cid}/artifacts', files={'file': ('additional.txt', b'SYNTHETIC Treatment Plan\nTooth 47: filling recommended', 'text/plain')}, data={'document_role':'treatment_plan'})
    client.post(f'/api/cases/{cid}/process')
    second = client.get(f'/api/cases/{cid}/report').json()['review']
    assert 'NEW_SYMPTOM_CANARY' in json.dumps(second, ensure_ascii=False)
    assert '47' in ' '.join(a['text'] for a in second['professional_report'])
    assert '99' not in ' '.join(a['text'] for a in second['professional_report'])
    old_intake = {s['source_ref'] for s in first['source_index'] if not s['artifact_id']}
    assert not old_intake & {r for a in second['patient_summary'] for r in a['source_refs']}
    with sessions() as db:
        snapshots = db.query(AssessmentSnapshot).order_by(AssessmentSnapshot.id).all()
        assert all(a['status'] == 'INSUFFICIENT_EVIDENCE' for s in snapshots for a in s.payload['assessments'])
        gaps = {g['gap_type'] for g in snapshots[-1].payload['gaps'] if g['status'] == 'MISSING'}
        assert {'CLINICAL_EXAMINATION','SYMPTOM_HISTORY','PULP_TEST_RESULT','APPROPRIATE_RADIOGRAPH'} <= gaps


def test_demo_reuses_normal_assessment_and_safety_rules(api_client):
    from app.domain.models import AssessmentSnapshot
    client, sessions, _ = api_client
    for context in (MARKER, ''):
        cid = create_demo(client, context=context)
        assert client.post(f'/api/cases/{cid}/process').json()['report']
    with sessions() as db:
        demo, normal = db.query(AssessmentSnapshot).order_by(AssessmentSnapshot.id).all()
        def assessment_facts(snapshot):
            return sorted((a['claim_source_type'], a['claim_treatment'], a['status'],
                tuple(a['missing_evidence'])) for a in snapshot.payload['assessments'])
        assert assessment_facts(demo) == assessment_facts(normal)
        assert demo.safety_state == normal.safety_state


@pytest.mark.parametrize('symptoms,state', [('facial swelling', 'URGENT_EVALUATION'), ('prescribe me', 'BLOCKED')])
def test_demo_retains_restricted_safety(api_client, symptoms, state):
    client, _, _ = api_client
    cid = create_demo(client, symptoms=symptoms)
    result = client.post(f'/api/cases/{cid}/process').json()
    assert result['safety_state'] == state
    if state == 'BLOCKED':
        assert result['report'] is None
    else:
        report = client.get(f'/api/cases/{cid}/report').json()
        assert report['report_kind'] == 'URGENT'
        assert not report.get('review')
