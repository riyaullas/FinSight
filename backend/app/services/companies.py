from datetime import date

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import create_system_roles
from app.core.security import hash_password
from app.models import CashAccount, Company, User
from app.models.base import ZERO
from app.services import audit


class CompanyError(Exception):
    pass


def any_company_exists(db: Session) -> bool:
    return db.scalar(select(Company.id).limit(1)) is not None


def create_company_with_owner(
    db: Session,
    *,
    company_name: str,
    owner_full_name: str,
    owner_email: str,
    owner_password: str,
    country: str = "IN",
    currency: str = "INR",
    timezone: str = "Asia/Kolkata",
    is_demo: bool = False,
    request: Request | None = None,
) -> tuple[Company, User]:
    email = owner_email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise CompanyError("A user with this email already exists")

    company = Company(
        name=company_name.strip(),
        country=country,
        currency=currency,
        timezone=timezone,
        is_demo=is_demo,
        fiscal_year_start_month=4 if country == "IN" else 1,
    )
    db.add(company)
    db.flush()
    roles = create_system_roles(db, company.id)
    owner = User(
        company_id=company.id,
        email=email,
        full_name=owner_full_name.strip(),
        password_hash=hash_password(owner_password),
        role_id=roles["owner"].id,
    )
    db.add(owner)
    db.add(CashAccount(company_id=company.id, name="Primary bank account", opening_balance=ZERO, opening_date=date.today()))
    db.flush()
    audit.record(
        db,
        "company.created",
        company_id=company.id,
        actor_user_id=owner.id,
        entity_type="company",
        entity_id=company.id,
        details={"name": company.name, "is_demo": is_demo},
        request=request,
    )
    return company, owner
