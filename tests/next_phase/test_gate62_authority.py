"""Frozen audience content and real text evidence, with injected HTTP only."""
import json
import httpx

from tests.next_phase.test_gate62_output import safe_review, assertion


def test_text_evidence_and_partial_limitations_are_frozen(api_client, monkeypatch):
    from app.ai.providers import OpenRouterProvider
    from app.domain.models import Artifact, ReviewRun, HypothesisEvidence, AssessmentSnapshot
    from verification.offline_openrouter import OfflineRouter, create_dossier
    client, factory, _ = api_client
    router = OfflineRouter(monkeypatch)
    cid = create_dossier(client)
    evidence = 'حساسیت به سرما گزارش شده است\n' + 'متن کاملاً ساختگی برای آزمون انتقال. ' * 1000
    assert client.post(f'/api/cases/{cid}/artifacts', files={'file':(
        'PRIVATE_TEXT_NAME.txt', evidence.encode(), 'text/plain')}).status_code == 201
    calls = []
    def handler(request):
        payload = json.loads(request.content)
        if 'review-instructions-' not in payload['messages'][0]['content']:
            return router.handle(request)
        data = json.loads(payload['messages'][1]['content'][0]['text']); calls.append(data)
        source = next(s for s in data['sources'] if s['kind']=='DOCUMENT_EXTRACTED' and s['representation']=='TEXT')
        assert source['partial'] is True
        text = next(t['text'] for t in data['documents'] if t['source_ref']==source['source_ref'])
        assert len(text)==20000
        refs = [s['source_ref'] for s in data['sources']]
        raw = safe_review([source['source_ref']]); raw['source_index']=[{'source_ref':r} for r in refs]
        raw['diagnostic_hypotheses']=[{'truth_type':'MODEL_INFERRED','label':'حساسیت دندانی احتمالی',
            'confidence_label':'LOW','supporting_evidence_refs':[source['source_ref']],
            'contradicting_evidence_refs':[], 'insufficient_support':True,
            'missing_information':[assertion('کفایت شواهد بالینی هنوز تأیید نشده است.',())],
            'recommended_checks':[assertion('درباره معاینه با دندان‌پزشک گفت‌وگو کنید.',())]}]
        return httpx.Response(200,json={'model':'synthetic/fixed-model','choices':[
            {'finish_reason':'stop','message':{'content':json.dumps(raw)}}]})
    monkeypatch.setattr('app.ai.gateway.OpenRouterProvider',lambda **kw:
        OpenRouterProvider('OFFLINE_TEST_ONLY','synthetic/fixed-model',offline_handler=handler))
    result=client.post(f'/api/cases/{cid}/process').json()
    assert result['report'], result
    report=client.get(f'/api/cases/{cid}/report').json()
    assert any('بررسی کامل متن انجام نشده' in a['text'] for a in report['review']['limitations'])
    with factory() as db:
        run=db.query(ReviewRun).one(); frozen=db.query(AssessmentSnapshot).one()
        artifact=db.query(Artifact).filter_by(original_filename='PRIVATE_TEXT_NAME.txt').one()
        link=db.query(HypothesisEvidence).one()
        assert link.artifact_id==artifact.id and link.dossier_revision_id is None
        assert link.source_ref==artifact.public_id+':text'
        for audience in ('patient_summary','professional_report','limitations'):
            assert report['review'][audience]==run.output[audience]==frozen.payload['review'][audience]
        assert frozen.payload['review']['source_index']==run.source_index
        before=json.dumps(frozen.payload,sort_keys=True)
    assert client.post(f'/api/cases/{cid}/process').json()['reused'] and len(calls)==1
    assert client.put(f'/api/cases/{cid}/dossier',json={'duration':'چهار روز — ساختگی'}).status_code==200
    assert client.get(f'/api/cases/{cid}/report').status_code==404
    with factory() as db: assert json.dumps(db.query(AssessmentSnapshot).one().payload,sort_keys=True)==before


def test_unauthenticated_case_cannot_construct_multimodal_input(raw_api_client, monkeypatch):
    from app.ai import review, gateway
    client, _, _ = raw_api_client
    def forbidden(*args, **kwargs):
        raise AssertionError('unauthorized provider or multimodal construction')
    monkeypatch.setattr(review,'bundle',forbidden)
    monkeypatch.setattr(gateway,'ModelGateway',forbidden)
    assert client.post('/api/cases/CASE-FOREIGN/process').status_code==401
