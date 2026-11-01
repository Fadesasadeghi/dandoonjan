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


def case_path(client, cid):
    namespace = '/api/demo/cases' if cid in getattr(client, 'demo_cases', set()) else '/api/cases'
    return f'{namespace}/{cid}'


def create_demo(client, context=MARKER, symptoms=None, plan=None):
    namespace = '/api/cases'
    headers = {}
    if context == MARKER:
        namespace = '/api/demo/cases'
        bootstrap = client.post('/api/demo/session', headers={'Origin':'http://testserver'})
        assert bootstrap.status_code == 200
        headers = {'Origin':'http://testserver', 'X-CSRF-Token':bootstrap.json()['csrf_token']}
        client.headers.update(headers)
    cid = client.post(namespace, data={'question': 'آیا پیشنهاد عصب‌کشی دندان ۴۶ پشتوانه دارد؟',
        'dentist_recommendation': 'عصب‌کشی و روکش دندان ۴۶ پیشنهاد شده', 'context': context}).json()['case_id']
    if context == MARKER:
        client.demo_cases = getattr(client, 'demo_cases', set()) | {cid}
    client.put(case_path(client, cid)+'/dossier', json={**DOSSIER, **({'symptoms': symptoms} if symptoms else {})})
    from app.core.cases.sample import image_pattern, plan_pdf
    files = [('طرح-درمان-نمونه.txt', (plan or client.get('/api/demo/sample').text).encode(), 'text/plain', 'treatment_plan'),
        ('synthetic-pattern-not-radiograph.png', image_pattern(), 'image/png', 'dental_image'),
        ('synthetic-plan.pdf', plan_pdf(), 'application/pdf', 'treatment_plan'),
        ('synthetic-prior-report.txt', b'SYNTHETIC prior clinical note\nTooth 46: cold sensitivity for three days. No examination recorded.', 'text/plain', 'previous_report')]
    for name, content, mime, role in files:
        assert client.post(case_path(client, cid)+'/artifacts', files={'file': (name, content, mime)}, data={'document_role': role}).status_code == 201
    return cid


@pytest.mark.parametrize('context,expected', [(MARKER, True), ('', False), (MARKER+' ', False), ('prefix '+MARKER, False)])
def test_marker_is_not_classification(context, expected):
    from app.core.cases.sample import is_demo
    assert is_demo(SimpleNamespace(context_text=context, demo_visitor=None)) is False
    assert is_demo(SimpleNamespace(context_text=context, demo_visitor=object())) is True


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
    assert client.post(case_path(client, cid)+'/process').json()['report']
    report = client.get(case_path(client, cid)+'/report').json()
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
    assert client.post(case_path(client, cid)+'/process').json()['snapshot'] == report['snapshot_id']


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
    assert client.post(case_path(client, cid)+'/process').json()['status'] == 'FAILED'
    assert len(seen) == 1
    seen.clear()
    cid = create_demo(client)
    from app.security.demo_sessions import cookie_name
    raw = client.cookies.get(cookie_name())
    monkeypatch.setattr(regression_settings, 'environment', 'production')
    client.cookies.set(cookie_name(), raw, domain='testserver.local', path='/')
    assert client.post(case_path(client, cid)+'/process').json()['status'] == 'FAILED'
    assert not seen


def test_fixture_text_and_png_nonclinical(api_client):
    from app.domain.models import Artifact, Finding, AssessmentSnapshot
    client, sessions, _ = api_client
    assert 'SYNTHETIC' in client.get('/api/demo/sample').text
    with pymupdf.open(stream=client.get('/api/demo/sample-plan').content, filetype='pdf') as pdf:
        assert 'SYNTHETIC' in pdf[0].get_text()
    cid = create_demo(client)
    client.post(case_path(client, cid)+'/process')
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
    client.post(case_path(client, other)+'/process')
    cid = create_demo(client)
    client.post(case_path(client, cid)+'/process')
    first = client.get(case_path(client, cid)+'/report').json()['review']
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
    client.put(case_path(client, cid)+'/dossier', json={'symptoms': 'NEW_SYMPTOM_CANARY'})
    client.post(case_path(client, cid)+'/artifacts', files={'file': ('additional.txt', b'SYNTHETIC Treatment Plan\nTooth 47: filling recommended', 'text/plain')}, data={'document_role':'treatment_plan'})
    client.post(case_path(client, cid)+'/process')
    second = client.get(case_path(client, cid)+'/report').json()['review']
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
        # Restore ACCOUNT CSRF after Demo operations on this mixed-cookie client.
        if context != MARKER:
            client.headers['X-CSRF-Token'] = client.get('/api/auth/csrf').json()['csrf_token']
        cid = create_demo(client, context=context)
        assert client.post(case_path(client, cid)+'/process').json()['report']
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
    result = client.post(case_path(client, cid)+'/process').json()
    assert result['safety_state'] == state
    if state == 'BLOCKED':
        assert result['report'] is None
    else:
        report = client.get(case_path(client, cid)+'/report').json()
        assert report['report_kind'] == 'URGENT'
        assert not report.get('review')


def test_portfolio_scenario_defaults_and_unknown_rejection(api_client):
    from app.core.cases.sample import PORTFOLIO_SCENARIOS

    client, _, _ = api_client

    bootstrap = client.post(
        '/api/demo/session',
        headers={'Origin': 'http://testserver'},
    )
    assert bootstrap.status_code == 200

    headers = {
        'Origin': 'http://testserver',
        'X-CSRF-Token': bootstrap.json()['csrf_token'],
    }
    client.headers.update(headers)

    assert set(PORTFOLIO_SCENARIOS) == {
        'root_canal',
        'extraction_gap',
        'treatment_cost',
    }

    for scenario_id, scenario in PORTFOLIO_SCENARIOS.items():
        created = client.post(
            '/api/demo/cases',
            data={
                'scenario': scenario_id,
            },
        )
        assert created.status_code == 201, created.text

        cid = created.json()['case_id']
        case = client.get(f'/api/demo/cases/{cid}')
        assert case.status_code == 200

        payload = case.json()
        assert payload['question'] == scenario['question']
        assert payload['dentist_recommendation'] == scenario['dentist_recommendation']

    rejected = client.post(
        '/api/demo/cases',
        data={
            'question': '',
            'dentist_recommendation': '',
            'scenario': 'does-not-exist',
        },
    )
    assert rejected.status_code == 422
    assert rejected.json()['detail']['code'] == 'UNKNOWN_DEMO_SCENARIO'


def test_portfolio_scenarios_extract_distinct_structured_facts():
    from app.ai.prompts import get_prompt
    from app.ai.providers import MockProvider
    from app.core.cases.sample import PORTFOLIO_SCENARIOS

    provider = MockProvider()
    prompt = get_prompt('treatment_plan_extractor')

    expected = {
        'root_canal': {
            ('TOOTH_46', 'TREATMENT_ROOT_CANAL'),
            ('TOOTH_46', 'TREATMENT_CROWN'),
        },
        'extraction_gap': {
            ('TOOTH_36', 'TREATMENT_EXTRACTION'),
        },
        'treatment_cost': {
            ('TOOTH_46', 'TREATMENT_ROOT_CANAL'),
            ('TOOTH_46', 'TREATMENT_CROWN'),
            ('TOOTH_36', 'TREATMENT_FILLING'),
        },
    }

    for scenario_id, scenario in PORTFOLIO_SCENARIOS.items():
        result = provider.run(
            prompt,
            scenario['treatment_plan'],
            {},
        )

        extracted = {
            (item['tooth'], item['treatment'])
            for item in result['treatment_items']
        }
        assert extracted == expected[scenario_id]

        if scenario_id == 'treatment_cost':
            prices = [
                field['raw_value']
                for field in result['fields']
                if field['field_name'] == 'price'
            ]
            assert prices == ['18,500,000 toman']



def test_portfolio_scenarios_run_end_to_end(api_client):
    from app.domain.models import (
        Artifact,
        AssessmentSnapshot,
        Case,
        ExtractedField,
        Extraction,
        TreatmentItem,
    )

    client, sessions, _ = api_client

    bootstrap = client.post(
        '/api/demo/session',
        headers={'Origin': 'http://testserver'},
    )
    assert bootstrap.status_code == 200
    client.headers.update({
        'Origin': 'http://testserver',
        'X-CSRF-Token': bootstrap.json()['csrf_token'],
    })

    expected_treatments = {
        'root_canal': {
            ('TOOTH_46', 'TREATMENT_ROOT_CANAL'),
            ('TOOTH_46', 'TREATMENT_CROWN'),
        },
        'extraction_gap': {
            ('TOOTH_36', 'TREATMENT_EXTRACTION'),
        },
        'treatment_cost': {
            ('TOOTH_46', 'TREATMENT_ROOT_CANAL'),
            ('TOOTH_46', 'TREATMENT_CROWN'),
            ('TOOTH_36', 'TREATMENT_FILLING'),
        },
    }

    for scenario_id, expected in expected_treatments.items():
        created = client.post(
            '/api/demo/cases',
            data={'scenario': scenario_id},
        )
        assert created.status_code == 201, created.text
        cid = created.json()['case_id']

        case_payload = client.get(f'/api/demo/cases/{cid}')
        assert case_payload.status_code == 200
        artifacts = case_payload.json()['artifacts']
        assert len(artifacts) == 1
        assert artifacts[0]['filename'] == (
            f'synthetic-{scenario_id}-treatment-plan.txt'
        )

        processed = client.post(f'/api/demo/cases/{cid}/process')
        assert processed.status_code == 200, processed.text
        assert processed.json()['report'], (
            f"{scenario_id}: process={processed.json()}"
        )

        report = client.get(f'/api/demo/cases/{cid}/report')
        assert report.status_code == 200, report.text
        payload = report.json()
        assert payload['review'], (
            f"{scenario_id}: report_kind={payload.get('report_kind')}, "
            f"safety_state={payload.get('safety_state')}, "
            f"sections={payload.get('sections')}"
        )

        with sessions() as db:
            case = db.query(Case).filter_by(public_id=cid).one()
            snapshot = (
                db.query(AssessmentSnapshot)
                .filter_by(case_id=case.id)
                .order_by(AssessmentSnapshot.id.desc())
                .first()
            )
            assert snapshot is not None
            run_id = snapshot.derivation_run_id

            actual = {
                (item.tooth_id, item.treatment_id)
                for item in (
                    db.query(TreatmentItem)
                    .join(Extraction)
                    .join(Artifact)
                    .filter(
                        Artifact.case_id == case.id,
                        TreatmentItem.derivation_run_id == run_id,
                    )
                    .all()
                )
            }
            assert actual == expected

            if scenario_id == 'treatment_cost':
                prices = [
                    field.raw_value
                    for field in (
                        db.query(ExtractedField)
                        .join(Extraction)
                        .join(Artifact)
                        .filter(
                            Artifact.case_id == case.id,
                            Extraction.derivation_run_id == run_id,
                            ExtractedField.field_name == 'price',
                        )
                        .all()
                    )
                ]
                assert prices == ['18,500,000 toman']

            if scenario_id == 'extraction_gap':
                missing = {
                    gap['gap_type']
                    for gap in snapshot.payload['gaps']
                    if gap['status'] == 'MISSING'
                }
                assert missing
