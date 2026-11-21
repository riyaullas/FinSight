"""Request dependencies: authentication, policy enforcement and permission checks."""

import uuid
from collections.abc import Callable
from datetime import UTC

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User

ACCESS_COOKIE = "fs_access"
REFRESH_COOKIE = "fs_refresh"
CSRF_COOKIE = "fs_csrf"
CSRF_HEADER = "x-csrf-token"


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Authenticated user, without enforcing MFA-enrolment or password-change policies."""
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise _unauthorized()
    try:
        payload = decode_token(token, "access")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise _unauthorized("Invalid or expired session") from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Invalid or expired session")
    changed = user.password_changed_at
    if changed.tzinfo is None:
        changed = changed.replace(tzinfo=UTC)
    if payload.get("iat", 0) < int(changed.timestamp()):
        raise _unauthorized("Session invalidated by a password change")
    request.state.user = user
    return user


def get_active_user(user: User = Depends(get_current_user)) -> User:
    """Authenticated user who satisfies company security policy."""
    if user.must_change_password:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="password_change_required")
    if user.company.require_mfa and not user.mfa_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="mfa_enrollment_required")
    return user


def require_permission(*codes: str) -> Callable[..., User]:
    """Dependency factory: the user must hold every listed permission."""

    def checker(user: User = Depends(get_active_user)) -> User:
        held = user.role.permission_codes
        missing = [c for c in codes if c not in held]
        if missing:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return checker
