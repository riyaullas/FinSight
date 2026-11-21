"""Authentication workflows: credential checks, lockout, session issuance and rotation."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE
from app.core.config import get_settings
from app.core.security import (
    create_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.models import AuthSession, User
from app.models.base import utcnow
from app.schemas.auth import CompanyBrief, MeResponse
from app.services import audit


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


GENERIC_LOGIN_ERROR = "Invalid email or password"


def authenticate(db: Session, email: str, password: str, request: Request | None) -> User:
    settings = get_settings()
    user = db.scalar(select(User).where(User.email == email.lower()))
    now = utcnow()

    if user is None:
        verify_password(password, None)  # equalise timing
        audit.record(db, "auth.login_failed", company_id=None, details={"reason": "unknown_user"}, request=request)
        db.commit()
        raise AuthError(GENERIC_LOGIN_ERROR)

    locked_until = _aware(user.locked_until)
    if locked_until and locked_until > now:
        audit.record(db, "auth.login_blocked", company_id=user.company_id, actor_user_id=user.id, request=request)
        db.commit()
        raise AuthError("Account temporarily locked after repeated failed attempts. Try again later.", 423)

    if not verify_password(password, user.password_hash) or not user.is_active:
        user.failed_login_count += 1
        details = {"reason": "bad_password" if user.is_active else "inactive", "attempt": user.failed_login_count}
        if user.failed_login_count >= settings.max_failed_logins:
            user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
            user.failed_login_count = 0
            details["locked"] = True
        audit.record(db, "auth.login_failed", company_id=user.company_id, actor_user_id=user.id, details=details, request=request)
        db.commit()
        raise AuthError(GENERIC_LOGIN_ERROR)

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None
    return user


def issue_mfa_token(user: User) -> str:
    return create_token(str(user.id), "mfa", timedelta(minutes=get_settings().mfa_token_minutes))


def _set_cookie(response: Response, key: str, value: str, max_age: int, path: str, http_only: bool = True) -> None:
    s = get_settings()
    response.set_cookie(
        key,
        value,
        max_age=max_age,
        path=path,
        domain=s.cookie_domain,
        secure=s.cookie_secure,
        httponly=http_only,
        samesite="strict",
    )


def set_csrf_cookie(response: Response) -> str:
    token = generate_opaque_token()
    _set_cookie(response, CSRF_COOKIE, token, max_age=60 * 60 * 24, path="/", http_only=False)
    return token


def start_session(
    db: Session, user: User, response: Response, request: Request | None, family_id: uuid.UUID | None = None
) -> None:
    s = get_settings()
    refresh = generate_opaque_token()
    db.add(
        AuthSession(
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=hash_opaque_token(refresh),
            expires_at=utcnow() + timedelta(days=s.refresh_token_days),
            ip_address=request.client.host if request and request.client else None,
            user_agent=(request.headers.get("user-agent") or "")[:300] if request else None,
        )
    )
    access = create_token(str(user.id), "access", timedelta(minutes=s.access_token_minutes))
    _set_cookie(response, ACCESS_COOKIE, access, s.access_token_minutes * 60, "/api")
    _set_cookie(response, REFRESH_COOKIE, refresh, s.refresh_token_days * 86400, "/api/auth")
    set_csrf_cookie(response)


def complete_login(db: Session, user: User, response: Response, request: Request | None, method: str) -> None:
    user.last_login_at = utcnow()
    start_session(db, user, response, request)
    audit.record(db, "auth.login", company_id=user.company_id, actor_user_id=user.id, details={"method": method}, request=request)
    db.commit()


def rotate_session(db: Session, refresh_token: str, response: Response, request: Request | None) -> User:
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_opaque_token(refresh_token)))
    if session is None:
        raise AuthError("Invalid session")
    user = db.get(User, session.user_id)
    if session.revoked_at is not None:
        # A rotated token was replayed: assume theft and revoke the whole family.
        revoke_family(db, session.family_id)
        if user:
            audit.record(db, "auth.refresh_reuse_detected", company_id=user.company_id, actor_user_id=user.id, request=request)
        db.commit()
        raise AuthError("Session revoked")
    if _aware(session.expires_at) <= utcnow() or user is None or not user.is_active:
        session.revoked_at = utcnow()
        db.commit()
        raise AuthError("Session expired")
    session.revoked_at = utcnow()
    start_session(db, user, response, request, family_id=session.family_id)
    db.commit()
    return user


def revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def revoke_all_for_user(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)).values(revoked_at=utcnow())
    )


def clear_cookies(response: Response) -> None:
    s = get_settings()
    for key, path in ((ACCESS_COOKIE, "/api"), (REFRESH_COOKIE, "/api/auth"), (CSRF_COOKIE, "/")):
        response.delete_cookie(key, path=path, domain=s.cookie_domain, secure=s.cookie_secure, samesite="strict")


def me_payload(user: User) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.slug,
        role_name=user.role.name,
        permissions=sorted(user.role.permission_codes),
        mfa_enabled=user.mfa_enabled,
        must_change_password=user.must_change_password,
        company=CompanyBrief.model_validate(user.company),
    )
