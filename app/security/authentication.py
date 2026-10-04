"""Credential primitives only. No case authorization or clinical mutations."""
from functools import lru_cache
import secrets
import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from email_validator import EmailNotValidError, validate_email

HASHER = PasswordHasher()  # Argon2id; encoded hashes include salt/parameters.


def normalize_email(value: str) -> tuple[str, str]:
    try:
        email = validate_email(value.strip(), check_deliverability=False)
    except EmailNotValidError:
        raise ValueError('INVALID_EMAIL') from None
    # Explicit portable case-insensitive policy; no dot or plus-tag rewriting.
    local = unicodedata.normalize('NFC', email.local_part.casefold())
    normalized = local + '@' + email.ascii_domain.lower()
    if len(normalized) > 320:
        raise ValueError('INVALID_EMAIL')
    return email.normalized, normalized


def password_value(value: str) -> str:
    # Preserve every supplied code point, including leading/trailing spaces.
    # No implicit Unicode normalization: registration and verification are exact.
    if not 15 <= len(value) <= 128:
        raise ValueError('INVALID_PASSWORD_LENGTH')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        raise ValueError('INVALID_PASSWORD_ENCODING') from None
    return value


def hash_password(value: str) -> str:
    return HASHER.hash(password_value(value))


def verify_password(encoded: str, value: str) -> bool:
    try:
        return HASHER.verify(encoded, value)
    except (VerificationError, InvalidHashError):
        return False


@lru_cache(maxsize=1)
def dummy_hash() -> str:
    return HASHER.hash(secrets.token_hex(32))


def account_public_id() -> str:
    return 'USR-' + secrets.token_hex(16)
