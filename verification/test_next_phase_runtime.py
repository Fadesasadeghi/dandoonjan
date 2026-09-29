"""Complete synthetic HTTP case, restart, content-free logs, five-case isolation."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from verification.test_rc_runtime import running_server, file_hashes
from app.core.cases.sample import image_pattern, plan_pdf

EVIDENCE = Path('docs/next-phase/evidence')
CANARY = 'SYNTHETIC_PRIVATE_CONTENT_CANARY'


def test_complete_dossiers_restart_and_logs(tmp_path):
    url = f"sqlite:///{(tmp_path / 'offline.db').as_posix()}"
    reports = {}
    with running_server(tmp_path, url) as client:
        cases = []
        for number in range(5):
            cid = client.post('/api/cases', data={'question': f'{CANARY} question {number}'}).json()['case_id']
            cases.append(cid)
            response = client.put(f'/api/cases/{cid}/dossier', json={
                'symptoms': 'Synthetic cold sensitivity', 'duration': '3 days',
                'medical_history': 'none reported', 'medications': 'none', 'allergies': 'none',
                'treatment_plan': 'Synthetic proposed examination',
                'previous_reports': 'Synthetic prior note', 'previous_treatments': 'none'})
            assert response.status_code == 200
            for name, content, mime, role in [
                ('synthetic-plan.pdf', plan_pdf(), 'application/pdf', 'treatment_plan'),
                ('pattern-not-radiograph.png', image_pattern(), 'image/png', 'dental_image'),
                ('prior.txt', b'Synthetic prior clinical note\nTooth 46: cold sensitivity', 'text/plain', 'previous_report')]:
                assert client.post(f'/api/cases/{cid}/artifacts', data={'document_role':role},
                                   files={'file':(name,content,mime)}).status_code == 201
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(lambda cid: client.post(f'/api/cases/{cid}/process').json(), cases))
        assert all(r.get('report') for r in results), results
        for cid in cases:
            report = client.get(f'/api/cases/{cid}/report').json()
            assert report['review']['run']['mode'] == 'MOCK'
            for source in report['review']['source_index']:
                if source['artifact_id'] is None:
                    assert source['source_ref'].startswith(cid + ':')
            reports[cid] = report
    hashes = file_hashes(tmp_path / 'store')
    assert len(hashes) == 15
    with running_server(tmp_path, url) as client:
        for cid, report in reports.items():
            assert client.get(f'/api/cases/{cid}/report').json() == report
            assert client.post(f'/api/cases/{cid}/process').json()['snapshot'] == report['snapshot_id']
    assert file_hashes(tmp_path / 'store') == hashes
    log = (tmp_path / 'server.log').read_text(encoding='utf-8')
    assert all(term not in log for term in [CANARY, 'cold sensitivity', 'synthetic-plan', url, 'base64', 'Traceback'])
    events = [json.loads(line) for line in log.splitlines()]
    assert all(set(event) <= {'level','event','status'} for event in events)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / 'offline-server.log').write_text(log, encoding='utf-8')
    (EVIDENCE / 'offline-runtime.json').write_text(json.dumps({
        'mode':'MOCK', 'live_provider_used':False, 'cases':5, 'persisted_files':15,
        'shared_reports_unchanged_after_restart':True, 'source_case_isolation':True,
        'log_records_checked':len(events), 'content_canaries_present':False,
        'radiograph':'NOT VERIFIED: nonclinical transport pattern only'}, indent=2), encoding='utf-8')
