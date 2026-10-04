"""Synchronizer tokens for pre-auth and authenticated mutations, including multipart."""
from datetime import timedelta
import hmac
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.models import PreAuthContext, utcnow
from app.security.sessions import as_utc, new_token, token_hash, token_valid, preauth_cookie_name

PREAUTH_LIFETIME = timedelta(minutes=10)


def failure():
    raise HTTPException(403, detail={'code':'CSRF_FAILED', 'message_fa':'درخواست معتبر نیست؛ دوباره تلاش کنید.'})


def validate_origin(request: Request):
    allowed = get_settings().auth_allowed_origins
    origin = request.headers.get('origin')
    if origin is not None:
        if origin not in allowed:
            failure()
    else:
        referer = request.headers.get('referer', '')
        try:
            parsed = urlsplit(referer)
        except ValueError:
            failure()
        if parsed.username or parsed.password or f'{parsed.scheme}://{parsed.netloc}' not in allowed:
            failure()


def validate_token(request: Request, expected: str):
    value = request.headers.get('x-csrf-token')
    if not token_valid(value) or not hmac.compare_digest(token_hash(value), expected):
        failure()
    validate_origin(request)


def issue_preauth(db: Session):
    raw, csrf = new_token(), new_token()
    row = PreAuthContext(token_hash=token_hash(raw), csrf_token_hash=token_hash(csrf),
                         expires_at=utcnow()+PREAUTH_LIFETIME)
    db.add(row); db.flush()
    return raw, csrf


def require_preauth(db: Session, request: Request):
    value = request.cookies.get(preauth_cookie_name())
    if not token_valid(value):
        failure()
    row = db.query(PreAuthContext).filter_by(token_hash=token_hash(value)).one_or_none()
    if row is None or row.consumed_at is not None or as_utc(row.expires_at) <= utcnow():
        failure()
    validate_token(request, row.csrf_token_hash)
    return row


def consume_preauth(db: Session, row: PreAuthContext):
    # One context cannot complete two concurrent registrations/logins.
    now = utcnow()
    result = db.execute(update(PreAuthContext).where(PreAuthContext.id == row.id,
        PreAuthContext.consumed_at.is_(None), PreAuthContext.expires_at > now).values(consumed_at=now)
        .execution_options(synchronize_session=False))
    if result.rowcount != 1:
        failure()


def require_mutation_csrf(request: Request, session):
    if request.method in {'POST','PUT','PATCH','DELETE'}:
        validate_token(request, session.csrf_token_hash)
