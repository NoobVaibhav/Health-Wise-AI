import re

from pydantic import BaseModel, EmailStr, Field, field_validator

COMMON_PASSWORDS = {"password", "password1", "password123", "12345678", "123456789", "qwerty123", "admin123", "welcome123", "iloveyou1"}


def check_strength(value: str) -> str:
    """At least one letter and one digit, and not a well-known password."""
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("The password must contain at least one letter and one number.")
    if value.lower() in COMMON_PASSWORDS:
        raise ValueError("This password is too common. Please choose another one.")
    return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class FirstAdminRequest(BaseModel):
    """Used once, on a brand new system, to create the first administrator."""
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8, max_length=128)

    _strong = field_validator("password")(check_strength)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    _strong = field_validator("new_password")(check_strength)


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
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    password: str | None = Field(default=None, min_length=8, max_length=128)  # generated when empty
    phone: str | None = Field(default=None, max_length=30)
    # doctor
    department_id: int | None = None
    specialization: str | None = Field(default=None, max_length=120)
    # employee
    designation: str | None = Field(default=None, max_length=100)
    # pharmacy
    pharmacy_name: str | None = Field(default=None, max_length=150)
    # laboratory
    lab_name: str | None = Field(default=None, max_length=150)


class CreatedUserResponse(BaseModel):
    user: UserOut
    temporary_password: str | None = None  # shown ONCE, only when the system generated it


class UserUpdate(BaseModel):
    is_active: bool | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=150)


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
