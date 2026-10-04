"""Gate 1 backend foundation. Normal case APIs remain UNPROTECTED until Gate 2."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, SecretStr, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.domain.models import User, utcnow
from app.security import authentication, csrf, sessions
from app.security.rate_limits import consume_attempt


def foundation(request: Request):
    settings = get_settings()
    if not settings.auth_foundation_enabled:
        raise HTTPException(404, detail={'code':'AUTH_NOT_ENABLED'})
    origins = settings.auth_allowed_origins
    if not origins or (not sessions.development() and
                       (request.url.scheme != 'https' or any(not origin.startswith('https://') for origin in origins))):
        raise HTTPException(503, detail={'code':'AUTH_CONFIGURATION_INVALID'})


router = APIRouter(prefix='/auth', dependencies=[Depends(foundation)])


class Credentials(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    email: str
    password: SecretStr

    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        if len(value) > 320:
            raise ValueError('INVALID_EMAIL')
        return authentication.normalize_email(value)[0]

    @field_validator('password')
    @classmethod
    def password_valid(cls, value):
        authentication.password_value(value.get_secret_value())
        return value


class AccountResponse(BaseModel):
    public_id: str
    email: str
    email_verified: bool


class CSRFResponse(BaseModel):
    csrf_token: str


class LoginResponse(BaseModel):
    user: AccountResponse
    csrf_token: str


def account(user):
    return AccountResponse(public_id=user.public_id, email=user.email,
                           email_verified=user.email_verified_at is not None)


def preauth(request: Request, db: Session = Depends(get_db, scope='function')):
    return csrf.require_preauth(db, request)


@router.get('/csrf', response_model=CSRFResponse)
def get_csrf(request: Request, response: Response, db: Session = Depends(get_db, scope='function')):
    response.headers['Cache-Control'] = 'no-store'
    found = sessions.find_session(db, request)
    raw, raw_csrf = csrf.issue_preauth(db)
    sessions.set_cookie(response, sessions.preauth_cookie_name(), raw, int(csrf.PREAUTH_LIFETIME.total_seconds()))
    if found:
        found[0].csrf_token_hash = sessions.token_hash(raw_csrf)
    return CSRFResponse(csrf_token=raw_csrf)


@router.post('/register', status_code=201, response_model=AccountResponse)
def register(credentials: Credentials, request: Request, response: Response,
             context=Depends(preauth), db: Session = Depends(get_db, scope='function')):
    email, normalized = authentication.normalize_email(credentials.email)
    consume_attempt(db, 'register', normalized)
    # Registration always INSERTs an ACCOUNT; it never upgrades a legacy row.
    user = User(public_id=authentication.account_public_id(), email=email,
                normalized_email=normalized, password_hash=authentication.hash_password(credentials.password.get_secret_value()),
                kind='ACCOUNT', status='ACTIVE')
    try:
        csrf.consume_preauth(db, context)
        db.add(user)
        db.flush()
    except IntegrityError as exc:
        # Only known normalized-email conflicts become registration failures.
        original = exc.orig
        db.rollback()
        is_duplicate = (getattr(original, 'sqlstate', None) == '23505' and
            getattr(getattr(original, 'diag', None), 'constraint_name', None) == 'uq_users_normalized_email') or (
            db.get_bind().dialect.name == 'sqlite' and str(original) == 'UNIQUE constraint failed: users.normalized_email')
        if not is_duplicate:
            raise
        raise HTTPException(400, detail={'code':'REGISTRATION_FAILED','message_fa':'ثبت‌نام انجام نشد؛ اطلاعات را بررسی کنید.'}) from None
    sessions.clear_cookie(response, sessions.preauth_cookie_name())
    response.headers['Cache-Control'] = 'no-store'
    return account(user)


@router.post('/login', response_model=LoginResponse)
def login(credentials: Credentials, request: Request, response: Response,
          context=Depends(preauth), db: Session = Depends(get_db, scope='function')):
    _, normalized = authentication.normalize_email(credentials.email)
    consume_attempt(db, 'login', normalized)
    user = db.query(User).filter_by(normalized_email=normalized, kind='ACCOUNT').one_or_none()
    encoded = user.password_hash if user else authentication.dummy_hash()
    valid = authentication.verify_password(encoded, credentials.password.get_secret_value())
    if not valid or user is None or user.status != 'ACTIVE':
        raise HTTPException(401, detail={'code':'INVALID_CREDENTIALS','message_fa':'اطلاعات ورود معتبر نیست.'})
    csrf.consume_preauth(db, context)
    previous = sessions.find_session(db, request, touch=False)
    if previous:
        previous[0].revoked_at = utcnow()
    if authentication.HASHER.check_needs_rehash(user.password_hash):
        user.password_hash = authentication.hash_password(credentials.password.get_secret_value())
    _, raw, raw_csrf = sessions.create_session(db, user)
    sessions.set_session_cookie(response, raw)
    sessions.clear_cookie(response, sessions.preauth_cookie_name())
    response.headers['Cache-Control'] = 'no-store'
    return LoginResponse(user=account(user), csrf_token=raw_csrf)


@router.post('/logout', status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db, scope='function')):
    found = sessions.find_session(db, request, touch=False)
    if found:
        csrf.require_mutation_csrf(request, found[0])
        found[0].revoked_at = utcnow()
    else:
        # Idempotent absent/expired session: no credentials changed, trusted origin still required.
        csrf.validate_origin(request)
    sessions.clear_cookie(response, sessions.cookie_name())
    sessions.clear_cookie(response, sessions.preauth_cookie_name())
    response.headers['Cache-Control'] = 'no-store'


@router.get('/me', response_model=AccountResponse)
def me(request: Request, response: Response, db: Session = Depends(get_db, scope='function')):
    _, user = sessions.require_session(db, request)
    response.headers['Cache-Control'] = 'no-store'
    return account(user)
