"""First-run onboarding: create the company and its owner account."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.auth import LoginResponse, RegisterCompanyRequest, SetupStatus
from app.services import auth as auth_service
from app.services.companies import CompanyError, any_company_exists, create_company_with_owner

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatus)
def setup_status(db: Session = Depends(get_db)) -> SetupStatus:
    s = get_settings()
    initialised = any_company_exists(db)
    return SetupStatus(
        initialised=initialised,
        registration_open=(not initialised) or s.allow_open_registration,
        product_name=s.product_name,
    )


@router.post("/company", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register_company(
    body: RegisterCompanyRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> LoginResponse:
    if any_company_exists(db) and not get_settings().allow_open_registration:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This installation is already set up. Ask an administrator for an account."
        )
    try:
        _, owner = create_company_with_owner(
            db,
            company_name=body.company_name,
            owner_full_name=body.owner_full_name,
            owner_email=body.owner_email,
            owner_password=body.owner_password,
            country=body.country,
            currency=body.currency,
            timezone=body.timezone,
            request=request,
        )
    except CompanyError as err:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(err)) from None
    auth_service.complete_login(db, owner, response, request, method="registration")
    return LoginResponse(user=auth_service.me_payload(owner))
