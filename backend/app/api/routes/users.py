"""User, role and audit-log administration. Every query is scoped to the caller's company."""

import re
import secrets
import string
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import PERMISSIONS
from app.core.security import hash_password
from app.models import AuditLog, Permission, Role, User
from app.services import audit
from app.services.auth import revoke_all_for_user

router = APIRouter(tags=["administration"])


# ------------------------------------------------------------------ schemas


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    is_system: bool
    permissions: list[str]
    user_count: int = 0


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    department: str | None
    is_active: bool
    mfa_enabled: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime
    role_id: uuid.UUID
    role_name: str = ""


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    role_id: uuid.UUID
    department: str | None = Field(default=None, max_length=100)


class UserCreated(BaseModel):
    user: UserOut
    temporary_password: str


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    role_id: uuid.UUID | None = None
    department: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    permissions: list[str]

    @field_validator("permissions")
    @classmethod
    def _known(cls, v: list[str]) -> list[str]:
        unknown = set(v) - set(PERMISSIONS)
        if unknown:
            raise ValueError(f"Unknown permissions: {', '.join(sorted(unknown))}")
        return sorted(set(v))


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    permissions: list[str] | None = None

    @field_validator("permissions")
    @classmethod
    def _known(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else RoleCreate._known(v)


class PermissionOut(BaseModel):
    code: str
    module: str
    description: str


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    actor_user_id: uuid.UUID | None
    actor_name: str | None = None
    entity_type: str | None
    entity_id: str | None
    ip_address: str | None
    details: dict
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditOut]
    total: int
    chain_intact: bool


# ------------------------------------------------------------------ helpers


def _user_out(u: User) -> UserOut:
    out = UserOut.model_validate(u)
    out.role_name = u.role.name
    return out


def _role_out(db: Session, r: Role) -> RoleOut:
    count = db.scalar(select(func.count()).select_from(User).where(User.role_id == r.id)) or 0
    return RoleOut(
        id=r.id,
        name=r.name,
        slug=r.slug,
        description=r.description,
        is_system=r.is_system,
        permissions=sorted(r.permission_codes),
        user_count=count,
    )


def _get_user(db: Session, company_id: uuid.UUID, user_id: uuid.UUID) -> User:
    u = db.scalar(select(User).where(User.id == user_id, User.company_id == company_id))
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return u


def _get_role(db: Session, company_id: uuid.UUID, role_id: uuid.UUID) -> Role:
    r = db.scalar(select(Role).where(Role.id == role_id, Role.company_id == company_id))
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    return r


def _temporary_password() -> str:
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(14))
    return f"{core[:7]}-{core[7:]}9a"


def _owner_count(db: Session, company_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(User)
            .join(Role, User.role_id == Role.id)
            .where(User.company_id == company_id, Role.slug == "owner", User.is_active.is_(True))
        )
        or 0
    )


def _guard_privilege(actor: User, role: Role) -> None:
    """Prevent privilege escalation: nobody may grant permissions they do not hold."""
    if not role.permission_codes <= actor.role.permission_codes:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot assign a role with permissions you do not hold")
    if role.slug == "owner" and actor.role.slug != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an owner can assign the owner role")


# ------------------------------------------------------------------ users


@router.get("/users", response_model=list[UserOut])
def list_users(actor: User = Depends(require_permission("users:manage")), db: Session = Depends(get_db)) -> list[UserOut]:
    users = db.scalars(select(User).where(User.company_id == actor.company_id).order_by(User.created_at)).all()
    return [_user_out(u) for u in users]


@router.post("/users", response_model=UserCreated, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    request: Request,
    actor: User = Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
) -> UserCreated:
    role = _get_role(db, actor.company_id, body.role_id)
    _guard_privilege(actor, role)
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")
    temp = _temporary_password()
    user = User(
        company_id=actor.company_id,
        email=email,
        full_name=body.full_name.strip(),
        role_id=role.id,
        department=body.department,
        password_hash=hash_password(temp),
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    audit.record(
        db,
        "user.created",
        company_id=actor.company_id,
        actor_user_id=actor.id,
        entity_type="user",
        entity_id=user.id,
        details={"email": email, "role": role.slug},
        request=request,
    )
    db.commit()
    return UserCreated(user=_user_out(user), temporary_password=temp)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    request: Request,
    actor: User = Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
) -> UserOut:
    target = _get_user(db, actor.company_id, user_id)
    changes = body.model_dump(exclude_unset=True)
    if target.role.slug == "owner" and actor.role.slug != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an owner can modify an owner account")
    if "role_id" in changes and changes["role_id"] != target.role_id:
        new_role = _get_role(db, actor.company_id, changes["role_id"])
        _guard_privilege(actor, new_role)
        if target.role.slug == "owner" and _owner_count(db, actor.company_id) <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "The company must keep at least one active owner")
        target.role_id = new_role.id
        changes["role_id"] = str(new_role.id)
    if changes.get("is_active") is False:
        if target.id == actor.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account")
        if target.role.slug == "owner" and _owner_count(db, actor.company_id) <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "The company must keep at least one active owner")
        revoke_all_for_user(db, target.id)
    for key in ("full_name", "department", "is_active"):
        if key in changes:
            setattr(target, key, changes[key])
    audit.record(
        db,
        "user.updated",
        company_id=actor.company_id,
        actor_user_id=actor.id,
        entity_type="user",
        entity_id=target.id,
        details={k: (str(v) if v is not None else None) for k, v in changes.items()},
        request=request,
    )
    db.commit()
    db.refresh(target)
    return _user_out(target)


@router.post("/users/{user_id}/reset-password", response_model=UserCreated)
def reset_password(
    user_id: uuid.UUID,
    request: Request,
    actor: User = Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
) -> UserCreated:
    target = _get_user(db, actor.company_id, user_id)
    if target.role.slug == "owner" and actor.role.slug != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an owner can reset an owner's password")
    temp = _temporary_password()
    target.password_hash = hash_password(temp)
    target.must_change_password = True
    target.failed_login_count = 0
    target.locked_until = None
    revoke_all_for_user(db, target.id)
    audit.record(
        db,
        "user.password_reset",
        company_id=actor.company_id,
        actor_user_id=actor.id,
        entity_type="user",
        entity_id=target.id,
        request=request,
    )
    db.commit()
    return UserCreated(user=_user_out(target), temporary_password=temp)


# ------------------------------------------------------------------ roles


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(_: User = Depends(require_permission("roles:manage")), db: Session = Depends(get_db)) -> list[Permission]:
    return list(db.scalars(select(Permission).order_by(Permission.module, Permission.code)))


@router.get("/roles", response_model=list[RoleOut])
def list_roles(actor: User = Depends(require_permission("users:manage")), db: Session = Depends(get_db)) -> list[RoleOut]:
    roles = db.scalars(select(Role).where(Role.company_id == actor.company_id).order_by(Role.is_system.desc(), Role.name))
    return [_role_out(db, r) for r in roles]


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:60] or "role"


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    body: RoleCreate,
    request: Request,
    actor: User = Depends(require_permission("roles:manage")),
    db: Session = Depends(get_db),
) -> RoleOut:
    if not set(body.permissions) <= actor.role.permission_codes:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot grant permissions you do not hold")
    slug = "custom_" + _slugify(body.name)
    if db.scalar(select(Role.id).where(Role.company_id == actor.company_id, Role.slug == slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A role with this name already exists")
    perms = list(db.scalars(select(Permission).where(Permission.code.in_(body.permissions))))
    role = Role(company_id=actor.company_id, name=body.name, slug=slug, description=body.description, permissions=perms)
    db.add(role)
    db.flush()
    audit.record(
        db,
        "role.created",
        company_id=actor.company_id,
        actor_user_id=actor.id,
        entity_type="role",
        entity_id=role.id,
        details={"name": role.name, "permissions": body.permissions},
        request=request,
    )
    db.commit()
    return _role_out(db, role)


@router.patch("/roles/{role_id}", response_model=RoleOut)
def update_role(
    role_id: uuid.UUID,
    body: RoleUpdate,
    request: Request,
    actor: User = Depends(require_permission("roles:manage")),
    db: Session = Depends(get_db),
) -> RoleOut:
    role = _get_role(db, actor.company_id, role_id)
    if role.is_system:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "System roles cannot be modified; create a custom role instead")
    changes = body.model_dump(exclude_unset=True)
    if body.permissions is not None:
        if not set(body.permissions) <= actor.role.permission_codes:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot grant permissions you do not hold")
        role.permissions = list(db.scalars(select(Permission).where(Permission.code.in_(body.permissions))))
    if body.name is not None:
        role.name = body.name
    if "description" in changes:
        role.description = body.description
    audit.record(
        db,
        "role.updated",
        company_id=actor.company_id,
        actor_user_id=actor.id,
        entity_type="role",
        entity_id=role.id,
        details={k: v for k, v in changes.items()},
        request=request,
    )
    db.commit()
    return _role_out(db, role)


# ------------------------------------------------------------------ audit log


@router.get("/audit-logs", response_model=AuditPage)
def list_audit_logs(
    actor: User = Depends(require_permission("audit:read")),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None, max_length=100),
) -> AuditPage:
    q = select(AuditLog).where(AuditLog.company_id == actor.company_id)
    if action:
        q = q.where(AuditLog.action.startswith(action))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)).all()
    names = dict(db.execute(select(User.id, User.full_name).where(User.company_id == actor.company_id)).all())
    items = []
    for r in rows:
        item = AuditOut.model_validate(r)
        item.actor_name = names.get(r.actor_user_id)
        items.append(item)
    intact, _ = audit.verify_chain(db, actor.company_id)
    return AuditPage(items=items, total=total, chain_intact=intact)
