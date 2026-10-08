from datetime import date

from pydantic import BaseModel, EmailStr, Field


class PatientFields(BaseModel):
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=30)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=300)
    emergency_contact: str | None = Field(default=None, max_length=150)
    # voluntary clinical details
    blood_group: str | None = Field(default=None, max_length=10)
    allergies: str | None = Field(default=None, max_length=1000)
    medical_history_text: str | None = Field(default=None, max_length=3000)
    current_medications: str | None = Field(default=None, max_length=1000)
    assigned_doctor_id: int | None = None


class PatientCreate(PatientFields):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    password: str | None = Field(default=None, min_length=8, max_length=128)  # generated when empty


class PatientUpdate(PatientFields):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)


class PatientBasic(BaseModel):
    """What reception staff and admins may see."""
    id: int
    patient_code: str
    full_name: str
    email: str
    date_of_birth: date | None
    age: int | None
    gender: str | None
    phone: str | None
    address: str | None
    emergency_contact: str | None
    assigned_doctor_id: int | None
    assigned_doctor_name: str | None
    is_active: bool


class PatientFull(PatientBasic):
    """What the patient and their authorized doctors may see."""
    blood_group: str | None
    allergies: str | None
    medical_history_text: str | None
    current_medications: str | None


class PatientCreated(BaseModel):
    patient: PatientBasic
    temporary_password: str | None = None
