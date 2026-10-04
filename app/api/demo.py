"""Visitor-scoped transport; existing handlers retain clinical behavior."""
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.api import routes
from app.config import get_settings
from app.core.cases import dossier
from app.core.cases.sample import DEMO_MARKER
from app.db import get_db
from app.domain.models import Case
from app.security import case_access as access, csrf, demo_sessions, sessions

router = APIRouter(prefix='/demo', route_class=access.CaseAdmissionRoute)


def configuration(request: Request):
    origins = get_settings().auth_allowed_origins
    if not origins or (not sessions.development() and
            (request.url.scheme != 'https' or any(not o.startswith('https://') for o in origins))):
        raise HTTPException(503, detail={'code': 'AUTH_CONFIGURATION_INVALID'})


@router.post('/session', dependencies=[Depends(configuration)])
def bootstrap(request: Request, response: Response,
              db: Session = Depends(get_db, scope='function')):
    csrf.validate_origin(request)
    row = demo_sessions.find_session(db, request)
    token = sessions.new_token()
    if row is None:
        row, raw, token = demo_sessions.create_session(db)
        sessions.set_cookie(response, demo_sessions.cookie_name(), raw,
                            int(sessions.ABSOLUTE.total_seconds()))
    else:
        row.csrf_token_hash = sessions.token_hash(token)
    return {'csrf_token': token}


@router.get('/session', dependencies=[Depends(configuration)])
def visitor_csrf(request: Request, db: Session = Depends(get_db, scope='function')):
    row = demo_sessions.require_session(db, request)
    token = sessions.new_token()
    row.csrf_token_hash = sessions.token_hash(token)
    return {'csrf_token': token}


@router.post('/cases', status_code=201)
def create_case(question: str = Form(...), dentist_recommendation: str = Form(''),
                principal: access.Principal = Depends(access.visitor_mutation),
                db: Session = Depends(get_db, scope='function')):
    access.touch(db, principal)
    return routes.create_owned_case(db, principal.user_id, question,
                                    dentist_recommendation, DEMO_MARKER)


@router.get('/cases/{case_public_id}')
def get_case(case_public_id: str, case: Case = Depends(access.read_demo_case),
             db: Session = Depends(get_db, scope='function')):
    return routes.get_case(case_public_id, case, db)


@router.patch('/cases/{case_public_id}')
def update_case(case_public_id: str, question: str = Form(None),
                dentist_recommendation: str = Form(None), context: str = Form(None),
                case: Case = Depends(access.mutate_demo_case),
                db: Session = Depends(get_db, scope='function')):
    # Keep server-written synthetic context; client hints cannot change mode.
    return routes.update_case(case_public_id, question, dentist_recommendation, None, case, db)


@router.get('/cases/{case_public_id}/dossier')
def get_dossier(case_public_id: str, case: Case = Depends(access.read_demo_case),
                db: Session = Depends(get_db, scope='function')):
    return routes.get_dossier(case_public_id, case, db)


@router.put('/cases/{case_public_id}/dossier')
def put_dossier(case_public_id: str, patch: dossier.DossierPatch,
                case: Case = Depends(access.mutate_demo_case),
                db: Session = Depends(get_db, scope='function')):
    return routes.put_dossier(case_public_id, patch, case, db)


@router.post('/cases/{case_public_id}/artifacts', status_code=201)
def upload_artifact(case_public_id: str, file: UploadFile = File(...),
                    document_role: Literal['unspecified', 'treatment_plan', 'prescription',
                                           'dental_image', 'previous_report'] = Form('unspecified'),
                    case: Case = Depends(access.upload_demo_case),
                    db: Session = Depends(get_db, scope='function')):
    return routes.upload_artifact(case_public_id, file, document_role, case, db)


@router.post('/cases/{case_public_id}/process')
def process_case(case_public_id: str, case: Case = Depends(access.mutate_demo_case),
                 db: Session = Depends(get_db, scope='function')):
    return routes.process_case(case_public_id, case, db)


@router.get('/cases/{case_public_id}/status')
def case_status(case_public_id: str, case: Case = Depends(access.read_demo_case),
                db: Session = Depends(get_db, scope='function')):
    return routes.case_status(case_public_id, case, db)


@router.get('/cases/{case_public_id}/assessment')
def case_assessment(case_public_id: str, case: Case = Depends(access.read_demo_case),
                    db: Session = Depends(get_db, scope='function')):
    return routes.case_assessment(case_public_id, case, db)


@router.get('/cases/{case_public_id}/report')
def case_report(case_public_id: str, case: Case = Depends(access.read_demo_case),
                db: Session = Depends(get_db, scope='function')):
    return routes.case_report(case_public_id, case, db)
