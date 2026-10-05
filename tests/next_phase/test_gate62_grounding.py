"""Valid ontology values are insufficient when their source does not support them."""
import pytest


@pytest.mark.parametrize('defect', ['invented_item', 'invented_page', 'invented_claim', 'wrong_span', 'negated_item', 'invented_box'])
def test_unsupported_candidates_cannot_become_document_facts(api_client, monkeypatch, defect):
    from app.ai.providers import MockProvider
    from app.domain.models import TreatmentItem, Claim, AssessmentSnapshot
    client, factory, _ = api_client
    cid = client.post('/api/cases', data={'question':'پرسش کاملاً ساختگی درباره شواهد طرح درمان'}).json()['case_id']
    text = b'Treatment Plan\nTooth 46: RCT not recommended' if defect == 'negated_item' else b'Treatment Plan\nTooth 46: RCT recommended'
    assert client.post(f'/api/cases/{cid}/artifacts', files={'file':(
        'synthetic.txt', text, 'text/plain')}).status_code == 201
    original = MockProvider.run
    def altered(self, prompt, content, params):
        value = original(self, prompt, content, params)
        if prompt.prompt_id == 'treatment_plan_extractor':
            if defect == 'invented_item':
                value['treatment_items'][0].update(tooth='TOOTH_47', treatment='TREATMENT_CROWN', predicate='REQUIRED')
            if defect == 'invented_page': value['treatment_items'][0]['source_locator']['page'] = 99
            if defect == 'wrong_span': value['treatment_items'][0]['source_locator']['span'] = 'char:0-5'
            if defect == 'invented_box': value['treatment_items'][0]['source_locator']['bounding_box'] = '0,0,100,100'
        if prompt.prompt_id == 'claim_builder' and defect == 'invented_claim':
            value['claims'][0].update(subject='TOOTH_47', treatment='TREATMENT_CROWN')
        return value
    monkeypatch.setattr(MockProvider, 'run', altered)
    result = client.post(f'/api/cases/{cid}/process').json()
    assert result['status'] == 'FAILED' and result['report'] is None
    with factory() as db:
        assert db.query(AssessmentSnapshot).count() == 0
        if defect != 'invented_claim': assert db.query(TreatmentItem).count() == 0
        assert not db.query(Claim).filter_by(source_type='MODEL_INFERRED').all()
