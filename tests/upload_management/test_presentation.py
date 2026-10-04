import copy
from types import SimpleNamespace
import pytest
from app.api import presentation
from app.domain.models import Case
from app.errors import SafetyBlockedError
from tests.upload_management.test_upload import case


@pytest.mark.parametrize('invalid', [None, 'missing', 'cross-case'])
def test_frozen_source_order_and_isolation(api_client, monkeypatch, invalid):
    client, sessions, _ = api_client
    cid = case(client)
    identifiers = []
    for n in range(3):
        identifiers.append(client.post(f'/api/cases/{cid}/artifacts', files={'file': (f'{n}.txt', f'ordinary text {n}'.encode(), 'text/plain')}).json()['artifact_id'])
    other = case(client)
    foreign = client.post(f'/api/cases/{other}/artifacts', files={'file': ('foreign.txt', b'foreign text', 'text/plain')}).json()['artifact_id']
    payload = {'artifacts':[{'artifact_id':i} for i in identifiers],
        'review':{'source_index':[{'artifact_id': identifiers[1], 'page':1}, {'artifact_id':identifiers[1], 'page':2}, {'artifact_id':identifiers[0]}]}}
    if invalid:
        payload['review']['source_index'].append({'artifact_id': foreign if invalid == 'cross-case' else 'missing'})
    before = copy.deepcopy(payload)
    monkeypatch.setattr(presentation, 'verify_snapshot_integrity', lambda _: True)
    with sessions() as db:
        snapshot = SimpleNamespace(case_id=db.query(Case).filter_by(public_id=cid).one().id,
            derivation_run_id=None, payload=payload)
        report = SimpleNamespace(content={'report_kind':'STANDARD'})
        if invalid:
            with pytest.raises(SafetyBlockedError):
                presentation.report_presentation(db, report, snapshot)
        else:
            result = presentation.report_presentation(db, report, snapshot)
            assert set(result) == {'materials','claims'}
            assert [m['filename'] for m in result['materials']] == ['1.txt','0.txt','2.txt']
            assert all(set(m) == {'filename','image_analysis_disabled'} for m in result['materials'])
    assert payload == before
