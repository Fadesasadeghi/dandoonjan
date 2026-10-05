"""One disposable ACCOUNT case. Offline by default; live needs separate approval.

Never supply credentials on the command line. Only sanitized scalar results leave
the process. No raw response/payload/derivative persistence is added.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'qwen/qwen3.8-27b:free'
PLAN = ('artifact_classifier', 'artifact_classifier', 'treatment_plan_extractor',
        'claim_builder', 'review')
QUESTION = 'این پرونده آزمون نرم‌افزار است؛ منابع ساختگی و محدودیت آن‌ها را توضیح دهید.'
DOSSIER = {'symptoms': 'حساسیت فرضی به سرما برای آزمون نرم‌افزار؛ این شرح حال متعلق به بیمار واقعی نیست.',
           'duration': 'سه روز — کاملاً ساختگی'}


def execute(live=False, failure=None):
    sys.path.insert(0, str(ROOT))
    from app.config import Settings, get_settings
    # Live-only credential read, never printed. Offline never reads the workspace
    # dotenv or actual credential variables through Settings.
    key = Settings().openrouter_api_key if live else 'OFFLINE_TEST_ONLY'
    Settings.model_config['env_file'] = None
    with tempfile.TemporaryDirectory(prefix='dj-gate63-') as directory:
        folder = Path(directory)
        os.environ.update({
            'DJ_DATABASE_URL': 'sqlite:///' + (folder / 'synthetic.db').as_posix(),
            'DJ_ARTIFACT_STORAGE_DIR': str(folder / 'store'),
            'DJ_AI_PROVIDER': 'openrouter', 'DJ_AI_MODEL_NAME': MODEL,
            'DJ_ENVIRONMENT': 'local-synthetic',
            'DJ_LOCAL_SYNTHETIC_ACCEPTANCE_ENABLED': 'true',
            'DJ_LIVE_PROVIDER_ENABLED': str(live).lower(),
            'DJ_OPENROUTER_API_KEY': key, 'DJ_OPENAI_API_KEY': '',
            'DJ_AUTH_FOUNDATION_ENABLED': 'true',
            'DJ_AUTH_ALLOWED_ORIGINS': '["http://testserver"]',
            'DJ_CORS_ORIGINS': '[]',
            'DJ_REQUIRE_CLINICIAN_REVIEWED_KNOWLEDGE_PACK': 'false',
        })
        get_settings.cache_clear()
        import httpx
        from app.ai.dispatch import DispatchAccounting
        from app.ai.providers import OpenRouterProvider, REVIEW_MAX_TOKENS
        from app.errors import ProviderUnavailableError
        from app.ai import gateway
        from app.core.cases.sample import image_pattern, plan_pdf
        from app.main import app
        from app.db import engine, SessionLocal
        from app.domain.models import ReviewRun, AssessmentSnapshot, Artifact
        from app.governance.immutability import verify_snapshot_integrity
        from fastapi.testclient import TestClient
        from tests.auth.helpers import register, login

        class Budget(DispatchAccounting):
            deviation = False
            def record(self, event, provider, model, kind, image_bearing):
                if event == 'logical_call':
                    previous = sum(e['event']=='logical_call' for e in self.snapshot())
                    if previous >= len(PLAN) or kind != PLAN[previous]:
                        self.deviation = True
                        raise ProviderUnavailableError(category='configuration')
                super().record(event, provider, model, kind, image_bearing)
        accounting = Budget()
        transport_proof = {'visual_parts': 0, 'pdf_pages': 0, 'bounded_text': False}

        def offline(request):
            payload = json.loads(request.content)
            system = payload['messages'][0]['content']
            if failure:
                return httpx.Response(429 if failure=='rate_limit' else 401)
            if 'review-instructions-' in system:
                from tests.next_phase.test_gate62_output import safe_review
                data = json.loads(payload['messages'][1]['content'][0]['text'])
                value = safe_review([s['source_ref'] for s in data['sources']])
            elif 'classify this' in system:
                pdf = 'application/pdf' in payload['messages'][1]['content']
                value = {'category':'CLINICAL_DOCUMENT' if pdf else 'PHOTO',
                         'subtype':'TREATMENT_PLAN' if pdf else 'INTRAORAL', 'confidence':0.7}
            elif 'extract structured' in system:
                value = {'fields':[], 'treatment_items':[{'tooth':'TOOTH_46',
                    'treatment':'TREATMENT_ROOT_CANAL', 'predicate':'RECOMMENDED',
                    'confidence':0.7, 'source_locator':{'page':1,'span':'line:1','bounding_box':None}}]}
            else:
                value = {'claims':[]}
            return httpx.Response(200,json={'model':MODEL,'choices':[
                {'finish_reason':'stop','message':{'content':json.dumps(value)}}]})

        class Observed(OpenRouterProvider):
            def _exchange(self, payload, deadline, kind, image_bearing):
                if kind == 'review':
                    parts = payload['messages'][1]['content']
                    data = json.loads(parts[0]['text'])
                    visuals = [p for p in parts if p['type']=='image_url']
                    pages = [s for s in data['sources'] if s.get('representation')=='PDF_PAGE']
                    assert payload['max_tokens']==REVIEW_MAX_TOKENS==1200
                    assert image_bearing and len(visuals)==2 and len(pages)==1 and pages[0]['page']==1
                    assert all(p['image_url']['url'].startswith('data:image/jpeg;base64,') for p in visuals)
                    assert all(s['source_ref'].startswith('src_') for s in data['sources'])
                    assert any(s.get('clinical_use')=='NON_CLINICAL' for s in data['sources'])
                    assert all(len(t['text'])<=20000 for t in data['documents'])
                    assert all('artifact_id' not in s and 'sha256' not in s for s in data['sources'])
                    transport_proof.update(visual_parts=2,pdf_pages=1,bounded_text=True)
                return super()._exchange(payload,deadline,kind,image_bearing)

        original_factory = gateway.OpenRouterProvider
        gateway.OpenRouterProvider = lambda **kw: Observed(**kw,
            offline_handler=None if live else offline, dispatch_accounting=accounting)
        real_transport = httpx.HTTPTransport.handle_request
        if not live:
            def forbidden(*args, **kwargs):
                raise AssertionError('OFFLINE_NETWORK_FORBIDDEN')
            httpx.HTTPTransport.handle_request = forbidden
        try:
            with TestClient(app) as client:
                assert register(client,'synthetic-gate63@example.com').status_code==201
                authenticated = login(client,'synthetic-gate63@example.com')
                assert authenticated.status_code==200
                client.headers.update({'Origin':'http://testserver',
                    'X-CSRF-Token':authenticated.json()['csrf_token']})
                cid = client.post('/api/cases',data={'question':QUESTION}).json()['case_id']
                assert client.put(f'/api/cases/{cid}/dossier',json=DOSSIER).status_code==200
                for name, body, mime, role in (
                        ('synthetic-not-radiograph.png',image_pattern(),'image/png','dental_image'),
                        ('synthetic-plan.pdf',plan_pdf(),'application/pdf','treatment_plan')):
                    assert client.post(f'/api/cases/{cid}/artifacts',data={'document_role':role},
                        files={'file':(name,body,mime)}).status_code==201
                outcome = client.post(f'/api/cases/{cid}/process').json()
                code = outcome.get('error_code')
                if not outcome.get('report'):
                    result = 'RATE_LIMITED' if code=='REAL_PROVIDER_RATE_LIMIT' else (
                        'INCONCLUSIVE' if code in ('REAL_PROVIDER_TIMEOUT','REAL_PROVIDER_PROVIDER',
                            'REAL_PROVIDER_PROVIDER_UNAVAILABLE') else 'FAIL')
                    return summary(result,accounting,transport_proof,code)
                report = client.get(f'/api/cases/{cid}/report').json()
                with SessionLocal() as db:
                    run=db.query(ReviewRun).one(); snapshot=db.query(AssessmentSnapshot).one()
                    assert run.provider=='openrouter' and run.model==MODEL and run.status=='SUCCEEDED'
                    assert verify_snapshot_integrity(snapshot)
                    allowed={s['source_ref'] for s in run.source_index}
                    artifact_ids={a.public_id for a in db.query(Artifact)}
                    assert {s['artifact_id'] for s in run.source_index if s['artifact_id']}==artifact_ids
                    for section in ('patient_summary','professional_report','limitations'):
                        assert report['review'][section]==run.output[section]==snapshot.payload['review'][section]
                        assert all(set(a['source_refs'])<=allowed for a in run.output[section])
                    assert any('غیر بالینی' in a['text'] for a in run.output['limitations'])
                before=accounting.snapshot()
                assert client.post(f'/api/cases/{cid}/process').json()['reused']
                assert accounting.snapshot()==before
                assert sum(e['event']=='http_dispatch' for e in before)==5
                return summary('PASS' if live else 'OFFLINE_PASS',accounting,transport_proof,None)
        except Exception:
            return summary('FAIL',accounting,transport_proof,'HARNESS_VALIDATION')
        finally:
            gateway.OpenRouterProvider=original_factory
            httpx.HTTPTransport.handle_request=real_transport
            get_settings().live_provider_enabled=False
            get_settings().openrouter_api_key=''
            os.environ['DJ_LIVE_PROVIDER_ENABLED']='false'
            os.environ['DJ_OPENROUTER_API_KEY']=''
            engine.dispose()


def summary(result, accounting, proof, code):
    from app.errors import ProviderUnavailableError
    allowed={'REAL_PROVIDER_'+c.upper() for c in ProviderUnavailableError.CATEGORIES}
    allowed.update(('SCHEMA_VALIDATION_FAILED','EXTRACTION_VALIDATION','PROCESSING_INPUT_CHANGED'))
    return {'result':result, 'provider':'openrouter','model':MODEL,'review_budget':1200,
            'logical_calls':sum(e['event']=='logical_call' for e in accounting.snapshot()),
            'http_dispatches':sum(e['event']=='http_dispatch' for e in accounting.snapshot()),
            'failure_code':code if code in allowed else ('SANITIZED_FAILURE' if code else None),
            'plan_deviation':accounting.deviation, **proof}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--owner-authorized',action='store_true')
    parser.add_argument('--offline-failure',choices=('rate_limit','authentication'))
    args=parser.parse_args()
    if args.live and (not args.owner_authorized or args.offline_failure):
        print('{"result":"AUTHORIZATION_REQUIRED","http_dispatches":0}')
        return 2
    try:
        result=execute(args.live,args.offline_failure)
    except Exception:
        # Never print an exception/traceback that could retain sensitive locals.
        print('{"result":"FAIL","failure_code":"SANITIZED_HARNESS_FAILURE"}')
        return 1
    print(json.dumps(result,sort_keys=True))
    return 0 if result['result'] in ('PASS','OFFLINE_PASS') else 1


if __name__=='__main__':
    raise SystemExit(main())
