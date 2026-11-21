import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import validate_password_strength


def _password(v: str) -> str:
    validate_password_strength(v)
    return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class MfaVerifyRequest(BaseModel):
    mfa_token: str = Field(max_length=2048)
    code: str = Field(min_length=6, max_length=20, description="6-digit TOTP code or a recovery code")


class LoginResponse(BaseModel):
    mfa_required: bool = False
    mfa_token: str | None = None
    user: "MeResponse | None" = None


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class MfaEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class MfaEnableResponse(BaseModel):
    recovery_codes: list[str]


class MfaDisableRequest(BaseModel):
    password: str = Field(max_length=128)
    code: str = Field(min_length=6, max_length=20)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)

    _check = field_validator("new_password")(_password)


class CompanyBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    currency: str
    country: str
    timezone: str
    is_demo: bool
    require_mfa: bool
    onboarding_completed: bool


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    role_name: str
    permissions: list[str]
    mfa_enabled: bool
    must_change_password: bool
    company: CompanyBrief


class SetupStatus(BaseModel):
    initialised: bool
    registration_open: bool
    product_name: str


class RegisterCompanyRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    owner_full_name: str = Field(min_length=2, max_length=200)
    owner_email: EmailStr
    owner_password: str = Field(max_length=128)
    country: str = Field(default="IN", min_length=2, max_length=2)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    timezone: str = Field(default="Asia/Kolkata", max_length=64)

    _check = field_validator("owner_password")(_password)

    @field_validator("country", "currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        if not v.isalpha():
            raise ValueError("Must be alphabetic")
        return v.upper()
