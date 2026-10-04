"""Portable atomic, DB-shared fixed-window authentication attempt budget."""
from datetime import timedelta
import hashlib

from fastapi import HTTPException
from sqlalchemy import case
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from app.domain.models import AuthRateLimit, utcnow

WINDOW = timedelta(minutes=15)
LIMIT = 5


def consume_attempt(db, action: str, normalized_email: str):
    now = utcnow()
    key = hashlib.sha256((action+'\0'+normalized_email).encode()).hexdigest()
    dialect = db.get_bind().dialect.name
    if dialect not in {'sqlite','postgresql'}:
        raise RuntimeError('AUTH_DATABASE_UNSUPPORTED')
    insert = sqlite_insert if dialect == 'sqlite' else postgres_insert
    statement = insert(AuthRateLimit).values(key_hash=key, window_started_at=now, attempts=1)
    reset = AuthRateLimit.window_started_at <= now-WINDOW
    statement = statement.on_conflict_do_update(index_elements=[AuthRateLimit.key_hash], set_={
        'attempts':case((reset,1),else_=AuthRateLimit.attempts+1),
        'window_started_at':case((reset,now),else_=AuthRateLimit.window_started_at),
    }).returning(AuthRateLimit.attempts)
    attempts = db.execute(statement).scalar_one()
    # Preserve the abuse budget even when subsequent credential work fails.
    # Call only before creating users/sessions or consuming the CSRF context.
    db.commit()
    if attempts > LIMIT:
        raise HTTPException(429, detail={'code':'AUTH_RATE_LIMITED','message_fa':'کمی بعد دوباره تلاش کنید.'},
                            headers={'Retry-After':str(int(WINDOW.total_seconds()))})
