"""Password hashing, token handling, TOTP MFA and field-level encryption."""

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

_hasher = PasswordHasher()  # Argon2id with library-recommended parameters
_ALGORITHM = "HS256"

# A pre-computed hash used to equalise timing when the user does not exist.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def validate_password_strength(password: str) -> None:
    """Raise ValueError when a password does not meet the minimum policy."""
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long")
    if len(password) > 128:
        raise ValueError("Password must be at most 128 characters long")
    classes = sum(
        [
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        ]
    )
    if classes < 3:
        raise ValueError("Password must contain at least three of: lowercase, uppercase, digit, symbol")


# ---------------------------------------------------------------- tokens


def _now() -> datetime:
    return datetime.now(UTC)


def create_token(subject: str, purpose: str, lifetime: timedelta, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = _now()
    payload: dict[str, Any] = {
        "sub": subject,
        "purpose": purpose,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def decode_token(token: str, purpose: str) -> dict[str, Any]:
    """Decode and validate a token. Raises jwt.PyJWTError on any problem."""
    settings = get_settings()
    payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM], options={"require": ["exp", "sub"]})
    if payload.get("purpose") != purpose:
        raise jwt.InvalidTokenError("Unexpected token purpose")
    return payload


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_opaque_token(token: str) -> str:
    """Refresh tokens and recovery codes are stored as keyed hashes only."""
    key = get_settings().secret_key.encode()
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


# ---------------------------------------------------------------- field encryption


def _fernet() -> Fernet:
    key = get_settings().field_encryption_key
    if not key:
        # Development fallback: derive a key from SECRET_KEY. Production requires an explicit key.
        digest = hashlib.sha256(("field-encryption:" + get_settings().secret_key).encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode())


def encrypt_field(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_field(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt field; check FIELD_ENCRYPTION_KEY") from exc


# ---------------------------------------------------------------- TOTP MFA


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str, issuer: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_recovery_codes(count: int = 8) -> list[str]:
    return [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(count)]
