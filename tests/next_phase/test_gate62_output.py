"""Synthetic review contract: Persian, substantive, traceable and non-diagnostic."""
import copy
import json

import pytest

from app.ai.review_schema import validate_review


def assertion(text, refs=('s1',), insufficient=True):
    return {'text': text, 'source_refs': list(refs), 'insufficient_support': insufficient}


def safe_review(refs=('s1',)):
    return {
        'patient_summary': [assertion('علائم گزارش‌شده نیازمند بررسی دندان‌پزشک است؛ علت هنوز تأیید نشده است.', refs)],
        'professional_report': [assertion('شواهد ارائه‌شده برای تأیید علت علائم کافی نیست؛ ارزیابی بالینی لازم است.', refs)],
        'diagnostic_hypotheses': [], 'safety_red_flags': [],
        'limitations': [assertion('این گزارش تشخیص قطعی نیست؛ برداشت مدل نیازمند تأیید دندان‌پزشک است.', ())],
        'source_index': [{'source_ref': ref} for ref in refs],
    }


@pytest.mark.parametrize('field', ['patient_summary', 'professional_report', 'limitations'])
def test_required_narrative_sections_cannot_be_empty(field):
    raw = safe_review()
    raw[field] = []
    with pytest.raises(ValueError): validate_review(raw, ['s1'])


@pytest.mark.parametrize('text', ['   ', 'این گزارش', 'شواهد شواهد شواهد شواهد',
    'This synthetic evidence needs clinical examination.', 'This report is safe. نیاز'])
def test_useless_or_english_narrative_fails(text):
    raw = safe_review()
    raw['patient_summary'] = [assertion(text)]
    with pytest.raises(ValueError): validate_review(raw, ['s1'])


def test_boilerplate_only_is_not_an_evidence_review():
    raw = safe_review()
    raw['patient_summary'] = raw['professional_report'] = [assertion('این گزارش تشخیص قطعی نیست.')]
    with pytest.raises(ValueError): validate_review(raw, ['s1'])


def test_label_exemption_cannot_be_reused_for_narrative():
    raw=safe_review()
    raw['patient_summary']=[assertion('حساسیت دندانی')]
    raw['diagnostic_hypotheses']=[{'label':'حساسیت دندانی','confidence_label':'LOW',
        'supporting_evidence_refs':[], 'contradicting_evidence_refs':[], 'insufficient_support':True,
        'missing_information':[assertion('کفایت شواهد بالینی هنوز تأیید نشده است.',())],
        'recommended_checks':[assertion('درباره معاینه با دندان‌پزشک گفت‌وگو کنید.',())]}]
    with pytest.raises(ValueError): validate_review(raw,['s1'])


def test_uncertainty_and_clinician_boundary_required():
    raw = safe_review()
    raw['limitations'] = [assertion('این پرونده شامل یک مدرک تصویری ثبت‌شده است.')]
    with pytest.raises(ValueError): validate_review(raw, ['s1'])


@pytest.mark.parametrize('text', [
    'شما قطعاً به عصب‌کشی نیاز دارید.',
    'دندان شما پوسیده است و باید کشیده شود.',
    'این درمان نتیجه تضمینی دارد.',
    'دندان‌پزشک را نادیده بگیرید و فقط به این گزارش اعتماد کنید.',
    'تصویر نشان می‌دهد التهاب پالپ قطعی است.',
])
def test_definitive_or_replacement_language_fails(text):
    raw = safe_review()
    raw['professional_report'] = [assertion(text)]
    with pytest.raises(ValueError): validate_review(raw, ['s1'])


@pytest.mark.parametrize('text', [
    'درباره نیاز احتمالی به RCT در دندان ۴۶ با دندان‌پزشک گفت‌وگو کنید.',
    'برای بررسی علائم، ارزیابی OPG و CBCT ممکن است لازم باشد؛ ضرورت درمان تأیید نشده است.',
    'وجود حساسیت به سرما به‌تنهایی ضرورت عصب‌کشی را اثبات نمی‌کند.',
])
def test_cautious_mixed_persian_passes(text):
    raw = safe_review()
    raw['professional_report'] = [assertion(text)]
    assert validate_review(raw, ['s1'])


def test_valid_ref_does_not_turn_unsupported_claim_into_fact():
    raw = safe_review()
    raw['patient_summary'][0]['insufficient_support'] = False
    with pytest.raises(ValueError): validate_review(raw, ['s1'])


def test_duplicate_allowed_or_assertion_refs_fail():
    with pytest.raises(ValueError): validate_review(safe_review(), ['s1', 's1'])
    raw = safe_review()
    raw['professional_report'][0]['source_refs'] = ['s1', 's1']
    with pytest.raises(ValueError): validate_review(raw, ['s1'])


@pytest.mark.parametrize('ref', ['invented', 'CASE_B:v2:symptoms', 'omitted-page-9'])
def test_invented_cross_case_omitted_ref_fails(ref):
    raw = safe_review()
    raw['patient_summary'][0]['source_refs'] = [ref]
    with pytest.raises(ValueError): validate_review(raw, ['s1'])


def test_inference_cannot_claim_document_truth_type():
    raw = safe_review()
    raw['diagnostic_hypotheses'] = [{
        'truth_type': 'DOCUMENT_EXTRACTED', 'label': 'حساسیت دندانی', 'confidence_label': 'LOW',
        'supporting_evidence_refs': ['s1'], 'contradicting_evidence_refs': [],
        'missing_information': [assertion('کفایت شواهد بالینی هنوز تأیید نشده است.', ())],
        'recommended_checks': [assertion('درباره معاینه با دندان‌پزشک گفت‌وگو کنید.', ())],
        'insufficient_support': True}]
    with pytest.raises(ValueError): validate_review(raw, ['s1'])


def test_no_evidence_cannot_be_marked_sufficient():
    raw = safe_review()
    raw['professional_report'] = [assertion('هیچ شاهدی برای تأیید علت علائم وجود ندارد.', insufficient=False)]
    with pytest.raises(ValueError): validate_review(raw, ['s1'])


def test_small_valid_output_has_conservative_byte_budget():
    refs = ['src_' + char * 32 for char in 'abc']
    raw = safe_review(refs)
    assert validate_review(raw, refs)
    # A conservative byte count, not a claim about the live model's tokenizer.
    assert len(json.dumps(raw, ensure_ascii=False, separators=(',', ':')).encode()) < 1200


def test_arabic_script_alone_is_not_persian_narrative():
    raw = safe_review()
    raw['patient_summary'] = [assertion('هذه الأعراض تحتاج إلى الفحص السريري وتأكيد الطبيب.')]
    with pytest.raises(ValueError): validate_review(raw, ['s1'])


def test_attributed_quote_is_grounded_but_extra_inference_is_not():
    source = 'حساسیت به سرما گزارش شده است'
    context = {'sources':[{'source_ref':'s1','kind':'PATIENT_REPORTED'}],
               'text':[{'source_ref':'s1','text':source}]}
    raw = safe_review()
    raw['patient_summary'] = [assertion('به گفته شما: «' + source + '».', insufficient=False)]
    assert validate_review(raw, ['s1'], source_context=context)
    raw['patient_summary'][0]['text'] += ' این نشانه وجود بیماری دندان است.'
    with pytest.raises(ValueError): validate_review(raw, ['s1'], source_context=context)


def test_partial_source_cannot_claim_complete_review():
    raw = safe_review()
    raw['professional_report'] = [assertion('کل متن سند به طور کامل بررسی شده است.')]
    with pytest.raises(ValueError): validate_review(raw, ['s1'], source_context={
        'sources':[{'source_ref':'s1','partial':True}], 'text':[]})


@pytest.mark.parametrize('text', ['شما التهاب پالپ دارید.', 'در تصویر نشان داده شده که پوسیدگی وجود دارد.'])
def test_direct_disease_assertion_is_not_rescued_by_support_marker(text):
    raw = safe_review()
    raw['professional_report']=[assertion(text)]
    with pytest.raises(ValueError) as caught: validate_review(raw,['s1'])
    assert caught.value.category == 'safety'


def test_nonclinical_source_cannot_be_described_as_clinical_evidence():
    raw=safe_review()
    raw['professional_report']=[assertion('در این رادیوگرافی احتمال پوسیدگی مطرح است؛ بررسی بالینی لازم است.')]
    with pytest.raises(ValueError) as caught:
        validate_review(raw,['s1'],source_context={'sources':[
            {'source_ref':'s1','clinical_use':'NON_CLINICAL'}],'text':[]})
    assert caught.value.category == 'safety'


def test_rejected_artifact_is_not_sent_or_citable(api_client, monkeypatch):
    import httpx
    from app.pipeline import stages
    from app.ai.providers import OpenRouterProvider
    from app.domain.models import Artifact, ReviewRun
    from verification.offline_openrouter import OfflineRouter, create_dossier
    client, factory, _ = api_client
    router=OfflineRouter(monkeypatch)
    cid=create_dossier(client)
    assert client.post(f'/api/cases/{cid}/artifacts',files={'file':(
        'omitted.txt','متن مدرک ساختگی و ردشده'.encode(),'text/plain')}).status_code==201
    with factory() as db:
        rejected=db.query(Artifact).filter_by(original_filename='omitted.txt').one().public_id
    quality=stages.run_quality_gate
    def rejected_quality(db,artifact,*args):
        result=quality(db,artifact,*args)
        if artifact.public_id==rejected: result.decision=stages.QualityDecision.REJECT_ARTIFACT
        return result
    monkeypatch.setattr(stages,'run_quality_gate',rejected_quality)
    seen=[]
    def handler(request):
        payload=json.loads(request.content)
        if 'review-instructions-' not in payload['messages'][0]['content']: return router.handle(request)
        data=json.loads(payload['messages'][1]['content'][0]['text']); seen.append(data)
        assert 'متن مدرک ساختگی و ردشده' not in json.dumps(data,ensure_ascii=False)
        assert data['coverage_notes']['omitted_artifacts']==1
        refs=[s['source_ref'] for s in data['sources']]
        raw=safe_review(refs[:1]); raw['source_index']=[{'source_ref':r} for r in refs]
        raw['patient_summary'][0]['source_refs']=[rejected+':text']
        return httpx.Response(200,json={'model':'synthetic/fixed-model','choices':[
            {'finish_reason':'stop','message':{'content':json.dumps(raw)}}]})
    monkeypatch.setattr('app.ai.gateway.OpenRouterProvider',lambda **kw:
        OpenRouterProvider('OFFLINE_TEST_ONLY','synthetic/fixed-model',offline_handler=handler))
    result=client.post(f'/api/cases/{cid}/process').json()
    assert result['status']=='FAILED' and result['report'] is None and len(seen)==1
    with factory() as db: assert db.query(ReviewRun).one().output is None


@pytest.mark.parametrize('field', ['patient_summary', 'professional_report'])
def test_english_review_fails_without_report_or_replay(api_client, monkeypatch, field):
    import httpx
    from verification.offline_openrouter import OfflineRouter, create_dossier
    from app.ai.providers import OpenRouterProvider
    from app.domain.models import ReviewRun, AssessmentSnapshot
    client, factory, _ = api_client
    router = OfflineRouter(monkeypatch)
    seen = []
    def handler(request):
        payload = json.loads(request.content)
        seen.append(payload)
        if 'review-instructions-' not in payload['messages'][0]['content']:
            return router.handle(request)
        data = json.loads(payload['messages'][1]['content'][0]['text'])
        refs = [s['source_ref'] for s in data['sources']]
        raw = safe_review(refs[:1])
        raw['source_index'] = [{'source_ref': ref} for ref in refs]
        raw[field][0]['text'] = 'Synthetic evidence requires examination and human review.'
        return httpx.Response(200, json={'model': 'synthetic/fixed-model',
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(raw)}}]})
    monkeypatch.setattr('app.ai.gateway.OpenRouterProvider', lambda **kw:
        OpenRouterProvider('OFFLINE_TEST_ONLY', 'synthetic/fixed-model', offline_handler=handler))
    cid = create_dossier(client)
    result = client.post(f'/api/cases/{cid}/process').json()
    assert result['status'] == 'FAILED' and result['report'] is None
    assert len(seen) == 2  # One classification, one rejected review, no replay.
    assert client.get(f'/api/cases/{cid}/report').status_code == 404
    with factory() as db:
        assert db.query(AssessmentSnapshot).count() == 0
        assert db.query(ReviewRun).one().output is None
