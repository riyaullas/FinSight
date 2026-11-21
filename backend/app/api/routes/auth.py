import uuid
from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import REFRESH_COOKIE, get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    decode_token,
    decrypt_field,
    encrypt_field,
    generate_recovery_codes,
    hash_opaque_token,
    hash_password,
    new_totp_secret,
    totp_uri,
    verify_password,
    verify_totp,
)
from app.models import AuthSession, User
from app.models.base import utcnow
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    MfaDisableRequest,
    MfaEnableRequest,
    MfaEnableResponse,
    MfaSetupResponse,
    MfaVerifyRequest,
)
from app.services import audit
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _raise(err: auth_service.AuthError) -> None:
    raise HTTPException(status_code=err.status_code, detail=err.message)


@router.get("/csrf")
def csrf(response: Response) -> dict:
    """Issue a CSRF token cookie. The client echoes it in the X-CSRF-Token header."""
    auth_service.set_csrf_cookie(response)
    return {"ok": True}


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        user = auth_service.authenticate(db, body.email, body.password, request)
    except auth_service.AuthError as err:
        _raise(err)
    if user.mfa_enabled:
        db.commit()
        return LoginResponse(mfa_required=True, mfa_token=auth_service.issue_mfa_token(user))
    auth_service.complete_login(db, user, response, request, method="password")
    return LoginResponse(user=auth_service.me_payload(user))


def _consume_recovery_code(user: User, code: str) -> bool:
    hashed = hash_opaque_token(code.strip().lower())
    if hashed in user.mfa_recovery_code_hashes:
        user.mfa_recovery_code_hashes = [h for h in user.mfa_recovery_code_hashes if h != hashed]
        return True
    return False


@router.post("/mfa/verify", response_model=LoginResponse)
def mfa_verify(body: MfaVerifyRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        payload = decode_token(body.mfa_token, "mfa")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "MFA challenge expired; sign in again") from None
    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active or not user.mfa_enabled or not user.mfa_secret_encrypted:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "MFA challenge invalid")
    locked_until = auth_service._aware(user.locked_until)
    if locked_until and locked_until > utcnow():
        raise HTTPException(status.HTTP_423_LOCKED, "Account temporarily locked after repeated failed attempts.")

    secret = decrypt_field(user.mfa_secret_encrypted)
    method = "totp"
    if not verify_totp(secret, body.code):
        if _consume_recovery_code(user, body.code):
            method = "recovery_code"
        else:
            user.failed_login_count += 1
            settings = get_settings()
            if user.failed_login_count >= settings.max_failed_logins:
                user.locked_until = utcnow() + timedelta(minutes=settings.lockout_minutes)
                user.failed_login_count = 0
            audit.record(db, "auth.mfa_failed", company_id=user.company_id, actor_user_id=user.id, request=request)
            db.commit()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid verification code")
    auth_service.complete_login(db, user, response, request, method=f"password+{method}")
    return LoginResponse(user=auth_service.me_payload(user))


@router.post("/refresh", response_model=MeResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> MeResponse:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        user = auth_service.rotate_session(db, token, response, request)
    except auth_service.AuthError as err:
        auth_service.clear_cookies(response)
        _raise(err)
    return auth_service.me_payload(user)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_opaque_token(token)))
        if session:
            auth_service.revoke_family(db, session.family_id)
            user = db.get(User, session.user_id)
            if user:
                audit.record(db, "auth.logout", company_id=user.company_id, actor_user_id=user.id, request=request)
            db.commit()
    auth_service.clear_cookies(response)
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> MeResponse:
    return auth_service.me_payload(user)


@router.post("/password", response_model=MeResponse)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must differ from the current password")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    # Invalidate every existing session, then start a fresh one for this device.
    user.password_changed_at = utcnow().replace(microsecond=0)
    auth_service.revoke_all_for_user(db, user.id)
    auth_service.start_session(db, user, response, request)
    audit.record(db, "auth.password_changed", company_id=user.company_id, actor_user_id=user.id, request=request)
    db.commit()
    return auth_service.me_payload(user)


@router.post("/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MfaSetupResponse:
    if user.mfa_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "MFA is already enabled")
    secret = new_totp_secret()
    user.mfa_pending_secret_encrypted = encrypt_field(secret)
    audit.record(db, "auth.mfa_setup_started", company_id=user.company_id, actor_user_id=user.id, request=request)
    db.commit()
    return MfaSetupResponse(secret=secret, otpauth_uri=totp_uri(secret, user.email, get_settings().product_name))


@router.post("/mfa/enable", response_model=MfaEnableResponse)
def mfa_enable(
    body: MfaEnableRequest, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> MfaEnableResponse:
    if user.mfa_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "MFA is already enabled")
    if not user.mfa_pending_secret_encrypted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Start MFA setup first")
    secret = decrypt_field(user.mfa_pending_secret_encrypted)
    if not verify_totp(secret, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid verification code")
    codes = generate_recovery_codes()
    user.mfa_secret_encrypted = user.mfa_pending_secret_encrypted
    user.mfa_pending_secret_encrypted = None
    user.mfa_enabled = True
    user.mfa_recovery_code_hashes = [hash_opaque_token(c) for c in codes]
    audit.record(db, "auth.mfa_enabled", company_id=user.company_id, actor_user_id=user.id, request=request)
    db.commit()
    return MfaEnableResponse(recovery_codes=codes)


@router.post("/mfa/disable", response_model=MeResponse)
def mfa_disable(
    body: MfaDisableRequest, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> MeResponse:
    if not user.mfa_enabled or not user.mfa_secret_encrypted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "MFA is not enabled")
    if user.company.require_mfa:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your company requires MFA")
    if not verify_password(body.password, user.password_hash) or not verify_totp(
        decrypt_field(user.mfa_secret_encrypted), body.code
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password or verification code is incorrect")
    user.mfa_enabled = False
    user.mfa_secret_encrypted = None
    user.mfa_recovery_code_hashes = []
    audit.record(db, "auth.mfa_disabled", company_id=user.company_id, actor_user_id=user.id, request=request)
    db.commit()
    return auth_service.me_payload(user)
