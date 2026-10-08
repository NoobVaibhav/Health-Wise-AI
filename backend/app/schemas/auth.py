from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class FirstAdminRequest(BaseModel):
    """Used once, on a brand new system, to create the first administrator."""
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    must_change_password: bool = False


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


class CreatedUserResponse(BaseModel):
    user: UserOut
    temporary_password: str | None = None  # shown ONCE, only when the system generated it


class UserUpdate(BaseModel):
    is_active: bool | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=150)


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
