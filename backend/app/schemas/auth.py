"""Request schemas of the account endpoints. The input rules come from app/utils/validators.py (see docs/VALIDATION_RULES.md)."""
from pydantic import BaseModel, Field, model_validator

from app.utils.validators import (
    COMMON_PASSWORDS, NO_NAME_IN_PASSWORD, Email, OptionalPhone, PersonName, Password, PositiveId, check_password, opt_text, password_has_email_name, text,
)

__all__ = ["COMMON_PASSWORDS", "check_strength"]


def check_strength(value: str) -> str:
    """Kept for older imports: the rule now lives in validators.check_password."""
    return check_password(value)


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=128)        # the real password rules apply when a password is CHOSEN, not when it is used


class FirstAdminRequest(BaseModel):
    """Used once, on a brand new system, to create the first administrator."""
    email: Email
    full_name: PersonName
    password: Password

    @model_validator(mode="after")
    def not_the_email(self):
        if password_has_email_name(self.password, self.email):
            raise ValueError(NO_NAME_IN_PASSWORD)
        return self


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: Password

    @model_validator(mode="after")
    def different(self):
        if self.current_password == self.new_password:
            raise ValueError("The new password must be different from the current one.")
        return self


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    must_change_password: bool = False
    has_avatar: bool = False
    avatar_version: str | None = None      # changes whenever the picture changes (so browsers reload it)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class StaffCreate(BaseModel):
    """Admin creates doctors, employees and pharmacy staff with this one schema; unused fields are ignored."""
    email: Email
    full_name: PersonName
    password: Password | None = None                  # generated when empty
    phone: OptionalPhone = None
    # doctor
    department_id: PositiveId | None = None
    specialization: opt_text(120) = None
    # employee
    designation: opt_text(100) = None
    # pharmacy
    pharmacy_name: opt_text(150) = None
    # laboratory
    lab_name: opt_text(150) = None

    @model_validator(mode="after")
    def not_the_email(self):
        if self.password and password_has_email_name(self.password, self.email):
            raise ValueError(NO_NAME_IN_PASSWORD)
        return self


class CreatedUserResponse(BaseModel):
    user: UserOut
    temporary_password: str | None = None  # shown ONCE, only when the system generated it


class UserUpdate(BaseModel):
    is_active: bool | None = None
    full_name: PersonName | None = None


class DepartmentCreate(BaseModel):
    name: text(100, min_length=2)
