"""Reusable deterministic HTTP boundary for SQLite/PostgreSQL lifecycle rehearsal."""
import json
import httpx
from app.ai.providers import OpenRouterProvider

MODEL = 'synthetic/fixed-model'


class OfflineRouter:
    def __init__(self, monkeypatch):
        from app.config import get_settings
        self.requests = []
        self.failure = None
        settings = get_settings()
        monkeypatch.setattr(settings, 'ai_provider', 'openrouter')
        monkeypatch.setattr(settings, 'ai_model_name', MODEL)
        monkeypatch.setattr(settings, 'live_provider_enabled', False)
        monkeypatch.setattr('app.ai.gateway.OpenRouterProvider', lambda **kwargs:
            OpenRouterProvider('OFFLINE_TEST_ONLY', MODEL, offline_handler=self.handle))
        monkeypatch.setattr('app.ai.providers.MockProvider.run', self.forbidden)
        monkeypatch.setattr('app.ai.review.mock_review', self.forbidden)

    @staticmethod
    def forbidden(*args):
        raise AssertionError('Mock substitution forbidden')

    def handle(self, request):
        payload = json.loads(request.content)
        self.requests.append(payload)
        system = payload['messages'][0]['content']
        if 'review-instructions-' in system:
            if self.failure == 'authentication':
                return httpx.Response(403)
            assert set(payload) == {'model', 'temperature', 'max_tokens', 'response_format', 'messages'}
            assert payload['model'] == MODEL and payload['temperature'] == 0
            parts = payload['messages'][1]['content']
            data = json.loads(parts[0]['text'])
            assert set(data) == {'sources', 'documents', 'coverage_notes'}
            for source in data['sources']:
                assert set(source) <= {'source_ref', 'kind', 'page', 'label', 'document_role', 'representation', 'partial', 'clinical_use'}
                assert source['source_ref'].startswith('src_') and len(source['source_ref']) == 36
            for document in data['documents']:
                assert set(document) == {'source_ref', 'text'}
            for part in parts[1:]:
                assert set(part) in ({'type', 'text'}, {'type', 'image_url'})
                if part['type'] == 'image_url':
                    assert set(part['image_url']) == {'url'}
                    assert part['image_url']['url'].startswith('data:image/jpeg;base64,')
            refs = [s['source_ref'] for s in data['sources']]
            image = next(s['source_ref'] for s in data['sources'] if s['kind'] == 'DOCUMENT_EXTRACTED')
            intake = next(s['source_ref'] for s in data['sources'] if s['label'] == 'symptoms')
            assertion = lambda text, refs: {'text': text, 'source_refs': refs, 'insufficient_support': True}
            value = {'patient_summary': [assertion('علائم گزارش‌شده نیازمند معاینه است؛ علت هنوز تأیید نشده است.', [intake])],
                'professional_report': [assertion('تصویر الگوی ساختگی ارسال شده است؛ تفسیر بالینی آن تأیید نشده است.', [image])],
                'diagnostic_hypotheses': [{'truth_type': 'MODEL_INFERRED', 'label': 'حساسیت دندانی احتمالی',
                    'confidence_label': 'LOW', 'supporting_evidence_refs': [intake],
                    'contradicting_evidence_refs': [], 'insufficient_support': True,
                    'missing_information': [assertion('کفایت شواهد بالینی هنوز تأیید نشده است.', [])],
                    'recommended_checks': [assertion('درباره معاینه با دندان‌پزشک گفت‌وگو کنید.', [])]}],
                'safety_red_flags': [], 'limitations': [assertion('این گزارش تشخیص قطعی نیست؛ برداشت نیازمند تأیید دندان‌پزشک است.', [])],
                'source_index': [{'source_ref': ref} for ref in refs]}
            if self.failure == 'reference': value['source_index'][0]['source_ref'] = 'foreign_alias'
            if self.failure == 'safety': value['patient_summary'][0]['text'] = 'Diagnostic confidence: 0.95'
            if self.failure == 'schema': value['diagnostic_hypotheses'] = 'PRIVATE_CANARY'
        elif 'classify this' in system:
            value = {'category': 'PHOTO', 'subtype': 'INTRAORAL', 'confidence': 0.8}
        elif 'extract structured' in system:
            value = {'fields': [], 'treatment_items': []}
        else:
            value = {'claims': []}
        return httpx.Response(200, json={'model': MODEL, 'choices': [{'finish_reason': 'stop',
            'message': {'content': json.dumps(value)}}]})


def create_dossier(client):
    from app.core.cases.sample import image_pattern
    cid = client.post('/api/cases', data={'question': 'Synthetic preflight question'}).json()['case_id']
    assert client.put(f'/api/cases/{cid}/dossier', json={'symptoms': 'Synthetic cold sensitivity',
        'duration': '3 days', 'medical_history': 'none', 'medications': 'none', 'allergies': 'none',
        'treatment_plan': 'Synthetic examination', 'previous_reports': 'Synthetic prior note',
        'previous_treatments': 'none'}).status_code == 200
    assert client.post(f'/api/cases/{cid}/artifacts', data={'document_role': 'dental_image'},
        files={'file': ('PRIVATE_FILENAME.png', image_pattern(), 'image/png')}).status_code == 201
    return cid


def verify_success(client, sessions, router):
    from app.domain.models import ReviewRun, AssessmentSnapshot, Artifact, HypothesisEvidence
    cid = create_dossier(client)
    result = client.post(f'/api/cases/{cid}/process').json()
    assert result['report'], result
    report = client.get(f'/api/cases/{cid}/report').json()
    assert report['review']['run']['mode'] == 'REAL'
    assert report['review']['patient_summary'] and report['review']['professional_report']
    serialized = json.dumps(router.requests)
    with sessions() as db:
        review = db.query(ReviewRun).one()
        artifact = db.query(Artifact).one()
        snapshot = db.query(AssessmentSnapshot).one()
        assert review.status == 'SUCCEEDED' and review.output
        assert snapshot.payload['review']['patient_summary'] == review.output['patient_summary']
        assert snapshot.payload['review']['professional_report'] == review.output['professional_report']
        evidence = db.query(HypothesisEvidence).one()
        assert evidence.artifact_id is None  # Nonclinical pattern cannot support diagnosis.
        assert evidence.dossier_revision_id is not None
        assert evidence.source_ref.endswith(':symptoms')
        for private in (cid, artifact.public_id, artifact.storage_key, artifact.sha256, 'PRIVATE_FILENAME'):
            assert private not in serialized
        for source in review.source_index:
            assert source['source_ref'] not in serialized
            assert source['sha256'] not in serialized
            if 'derivative_sha256' in source: assert source['derivative_sha256'] not in serialized
        assert all(not source['source_ref'].startswith('src_') for source in review.source_index)
        frozen = json.loads(json.dumps(snapshot.payload))
    requests = len(router.requests)
    assert client.post(f'/api/cases/{cid}/process').json()['reused']
    assert len(router.requests) == requests
    return cid, report, frozen
