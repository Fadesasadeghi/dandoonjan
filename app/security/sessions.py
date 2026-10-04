"""Opaque session credentials; hashes only in persistent storage."""
from datetime import timedelta, timezone
import hashlib
import re
import secrets

from fastapi import HTTPException, Request, Response
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.models import AuthSession, User, utcnow

ABSOLUTE = timedelta(hours=12)
IDLE = timedelta(minutes=30)
TOUCH_INTERVAL = timedelta(minutes=5)
TOKEN = re.compile(r'[0-9a-f]{64}\Z')


def token_valid(value: str | None) -> bool:
    return isinstance(value, str) and len(value) == 64 and TOKEN.fullmatch(value) is not None


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode('ascii')).hexdigest()


def new_token() -> str:
    return secrets.token_hex(32)


def as_utc(value):
    # SQLite returns naive timestamps even for DateTime(timezone=True).
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def development() -> bool:
    return get_settings().environment in {'development', 'test', 'local-synthetic'}


def cookie_name() -> str:
    return 'dandoonjan_dev_session' if development() else '__Host-dandoonjan_session'


def preauth_cookie_name() -> str:
    return 'dandoonjan_dev_preauth' if development() else '__Host-dandoonjan_preauth'


def set_cookie(response: Response, name: str, token: str, seconds: int):
    response.set_cookie(name, token, max_age=seconds, path='/', secure=not development(),
                        httponly=True, samesite='lax')


def clear_cookie(response: Response, name: str):
    response.delete_cookie(name, path='/', secure=not development(), httponly=True, samesite='lax')


def set_session_cookie(response: Response, token: str):
    set_cookie(response, cookie_name(), token, int(ABSOLUTE.total_seconds()))


def create_session(db: Session, user: User):
    if user.kind != 'ACCOUNT' or user.status != 'ACTIVE':
        raise ValueError('INVALID_SESSION_PRINCIPAL')
    raw, csrf = new_token(), new_token()
    now = utcnow()
    row = AuthSession(user_id=user.id, token_hash=token_hash(raw), csrf_token_hash=token_hash(csrf),
                      created_at=now, last_seen_at=now, expires_at=now+ABSOLUTE)
    db.add(row); db.flush()
    return row, raw, csrf


def find_session(db: Session, request: Request, *, touch: bool = True):
    raw = request.cookies.get(cookie_name())
    if not token_valid(raw):
        return None
    row = db.query(AuthSession).filter_by(token_hash=token_hash(raw)).one_or_none()
    now = utcnow()
    if row is None or row.revoked_at is not None or as_utc(row.expires_at) <= now or as_utc(row.last_seen_at)+IDLE <= now:
        return None
    user = db.get(User, row.user_id)
    if user is None or user.kind != 'ACCOUNT' or user.status != 'ACTIVE':
        return None
    if touch and as_utc(row.last_seen_at)+TOUCH_INTERVAL <= now:
        # Atomic monotonic touch: overlapping requests cannot move time backward.
        db.execute(update(AuthSession).where(AuthSession.id == row.id,
            AuthSession.last_seen_at < now-TOUCH_INTERVAL,
            AuthSession.revoked_at.is_(None)).values(last_seen_at=now).execution_options(synchronize_session=False))
    return row, user


def require_session(db: Session, request: Request):
    found = find_session(db, request)
    if found is None:
        raise HTTPException(401, detail={'code':'AUTH_REQUIRED', 'message_fa':'ورود به حساب لازم است.'})
    return found


def revoke_all(db: Session, user_id: int):
    db.execute(update(AuthSession).where(AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None)).values(revoked_at=utcnow()).execution_options(synchronize_session=False))
