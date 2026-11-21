"""Company profile and security settings."""

import re
import uuid
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, require_permission
from app.core.database import get_db
from app.models import CashAccount, Company, User
from app.services import audit

router = APIRouter(prefix="/company", tags=["company"])

_GSTIN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    legal_name: str | None
    industry: str | None
    country: str
    currency: str
    timezone: str
    gstin: str | None
    fiscal_year_start_month: int
    require_mfa: bool
    is_demo: bool
    onboarding_completed: bool


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    legal_name: str | None = Field(default=None, max_length=300)
    industry: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=64)
    gstin: str | None = Field(default=None, max_length=15)
    fiscal_year_start_month: int | None = Field(default=None, ge=1, le=12)
    require_mfa: bool | None = None
    onboarding_completed: bool | None = None
    opening_cash_balance: str | None = Field(default=None, max_length=24, description="Opening bank balance")

    @field_validator("gstin")
    @classmethod
    def _gstin(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        v = v.strip().upper()
        if not _GSTIN.match(v):
            raise ValueError("GSTIN format is invalid")
        return v


@router.get("", response_model=CompanyOut)
def get_company(user: User = Depends(get_active_user)) -> Company:
    return user.company


@router.patch("", response_model=CompanyOut)
def update_company(
    body: CompanyUpdate,
    request: Request,
    user: User = Depends(require_permission("settings:manage")),
    db: Session = Depends(get_db),
) -> Company:
    company = db.get(Company, user.company_id)
    changes = body.model_dump(exclude_unset=True)
    opening = changes.pop("opening_cash_balance", None)
    if changes.get("require_mfa") and not user.mfa_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enable MFA on your own account before requiring it company-wide")
    for key, value in changes.items():
        setattr(company, key, value)
    if opening is not None:
        try:
            amount = Decimal(opening).quantize(Decimal("0.01"))
        except InvalidOperation:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Opening balance must be a number") from None
        account = db.scalar(select(CashAccount).where(CashAccount.company_id == company.id).order_by(CashAccount.created_at))
        if account:
            account.opening_balance = amount
        changes["opening_cash_balance"] = str(amount)
    audit.record(
        db,
        "company.updated",
        company_id=company.id,
        actor_user_id=user.id,
        entity_type="company",
        entity_id=company.id,
        details={"fields": sorted(changes)},
        request=request,
    )
    db.commit()
    return company
