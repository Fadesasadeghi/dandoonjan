"""Separate opaque Demo visitor identity. Association survives credential expiry."""
from sqlalchemy import update
from fastapi import HTTPException
from app.domain.models import DemoVisitor, User, public_id, utcnow
from app.security import sessions


def cookie_name():
    return 'dandoonjan_dev_demo' if sessions.development() else '__Host-dandoonjan_demo'


def find_session(db, request, *, touch=True):
    raw = request.cookies.get(cookie_name())
    if not sessions.token_valid(raw):
        return None
    row = (db.query(DemoVisitor).join(User, DemoVisitor.user_id == User.id)
           .filter(DemoVisitor.token_hash == sessions.token_hash(raw),
                   User.kind == 'LEGACY', User.status == 'DISABLED').one_or_none())
    now = utcnow()
    if row is None or row.revoked_at is not None or sessions.as_utc(row.expires_at) <= now or sessions.as_utc(row.last_seen_at)+sessions.IDLE <= now:
        return None
    if touch:
        touch_session(db, row, now)
    return row


def touch_session(db, row, now=None):
    now = now or utcnow()
    if sessions.as_utc(row.last_seen_at)+sessions.TOUCH_INTERVAL <= now:
        db.execute(update(DemoVisitor).where(DemoVisitor.id == row.id,
            DemoVisitor.last_seen_at < now-sessions.TOUCH_INTERVAL,
            DemoVisitor.revoked_at.is_(None)).values(last_seen_at=now)
            .execution_options(synchronize_session=False))


def require_session(db, request, *, touch=True):
    row = find_session(db, request, touch=touch)
    if row is None:
        raise HTTPException(401, detail={'code':'DEMO_AUTH_REQUIRED', 'message_fa':'نشست نمونه در دسترس نیست؛ نمونهٔ تازه بسازید.'})
    return row


def create_session(db):
    # Never associate an existing User, including old marker-bearing sample users.
    user = User(public_id=public_id('USR'), kind='LEGACY', status='DISABLED')
    db.add(user); db.flush()
    raw, csrf = sessions.new_token(), sessions.new_token()
    now = utcnow()
    row = DemoVisitor(user_id=user.id, token_hash=sessions.token_hash(raw),
        csrf_token_hash=sessions.token_hash(csrf), created_at=now,
        last_seen_at=now, expires_at=now+sessions.ABSOLUTE)
    db.add(row); db.flush()
    return row, raw, csrf
