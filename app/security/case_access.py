"""HTTP admission boundary. Never query clinical children before owned Case."""
from dataclasses import dataclass
from fastapi import Depends, HTTPException, Request
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import get_db
from app.domain.models import Case, DemoVisitor, User
from app.security import csrf, sessions, demo_sessions


class CaseAdmissionRoute(APIRoute):
    """Reject identity/CSRF failures before FastAPI parses JSON or multipart.

    The function-scoped dependency remains authoritative for ownership and the
    write transaction. This preliminary check never touches sessions or cases.
    """
    def get_route_handler(self):
        original = super().get_route_handler()

        async def admitted(request):
            path = request.url.path
            if path == '/api/cases' or path.startswith('/api/cases/'):
                await run_in_threadpool(check_headers, request, False)
            elif path == '/api/demo/cases' or path.startswith('/api/demo/cases/'):
                await run_in_threadpool(check_headers, request, True)
            if request.method == 'POST' and self.path.endswith('/artifacts'):
                from app.security.upload_form import with_bounded_upload_form
                return await with_bounded_upload_form(request, original)
            return await original(request)

        return admitted


def check_headers(request, demo):
    from app import db as database
    with database.SessionLocal() as db:
        principal = visitor(request, db) if demo else account(request, db)
        csrf.require_mutation_csrf(request, principal.credential)


@dataclass(frozen=True)
class Principal:
    user_id: int
    credential: object
    demo: bool = False


def account(request: Request, db: Session = Depends(get_db, scope='function')):
    # Read-only authentication first: upload BEGIN IMMEDIATE must precede touch.
    found = sessions.find_session(db, request, touch=False)
    if found is None:
        raise HTTPException(401, detail={'code':'AUTH_REQUIRED', 'message_fa':'ورود به حساب لازم است.'})
    return Principal(found[1].id, found[0])


def account_mutation(request: Request, principal: Principal = Depends(account)):
    csrf.require_mutation_csrf(request, principal.credential)
    return principal


def visitor(request: Request, db: Session = Depends(get_db, scope='function')):
    row = demo_sessions.require_session(db, request, touch=False)
    return Principal(row.user_id, row, True)


def visitor_mutation(request: Request, principal: Principal = Depends(visitor)):
    csrf.require_mutation_csrf(request, principal.credential)
    return principal


def owned_case(db, case_public_id, principal, *, lock=False):
    if lock and db.get_bind().dialect.name == 'sqlite':
        db.execute(text('BEGIN IMMEDIATE'))
    query = db.query(Case).join(User, Case.user_id == User.id).filter(
        Case.public_id == case_public_id, Case.user_id == principal.user_id)
    if principal.demo:
        query = query.join(DemoVisitor, DemoVisitor.user_id == Case.user_id).filter(
            DemoVisitor.id == principal.credential.id, User.kind == 'LEGACY', User.status == 'DISABLED')
    else:
        query = query.filter(User.kind == 'ACCOUNT', User.status == 'ACTIVE',
                             ~Case.demo_visitor.has())
    if lock:
        query = query.with_for_update(of=Case)
    case = query.one_or_none()
    if case is None:
        raise HTTPException(404, detail={'code':'CASE_NOT_FOUND', 'message_fa':'پرونده در دسترس نیست.'})
    touch(db, principal)
    return case


def touch(db, principal):
    if principal.demo:
        demo_sessions.touch_session(db, principal.credential)
    else:
        sessions.touch_session(db, principal.credential)


def read_case(case_public_id: str, principal: Principal = Depends(account),
              db: Session = Depends(get_db, scope='function')):
    return owned_case(db, case_public_id, principal)


def mutate_case(case_public_id: str, principal: Principal = Depends(account_mutation),
                db: Session = Depends(get_db, scope='function')):
    return owned_case(db, case_public_id, principal)


def upload_case(case_public_id: str, principal: Principal = Depends(account_mutation),
                db: Session = Depends(get_db, scope='function')):
    return owned_case(db, case_public_id, principal, lock=True)


def read_demo_case(case_public_id: str, principal: Principal = Depends(visitor),
                   db: Session = Depends(get_db, scope='function')):
    return owned_case(db, case_public_id, principal)


def mutate_demo_case(case_public_id: str, principal: Principal = Depends(visitor_mutation),
                     db: Session = Depends(get_db, scope='function')):
    return owned_case(db, case_public_id, principal)


def upload_demo_case(case_public_id: str, principal: Principal = Depends(visitor_mutation),
                     db: Session = Depends(get_db, scope='function')):
    return owned_case(db, case_public_id, principal, lock=True)
