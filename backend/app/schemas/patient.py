import re
from datetime import date

from pydantic import BaseModel, model_validator

from app.utils.validators import (
    Address, BloodGroup, DateOfBirth, Email, Gender, OptionalPhone, PersonName, Password, PositiveId, check_password, normalise_phone, opt_text, password_has_email_name,
    NO_NAME_IN_PASSWORD,
)


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")[-10:]


class PatientFields(BaseModel):
    date_of_birth: DateOfBirth = None
    gender: Gender = None
    phone: OptionalPhone = None
    address: Address = None
    emergency_contact: opt_text(150) = None
    # voluntary clinical details
    blood_group: BloodGroup = None
    allergies: opt_text(1000, multiline=True) = None
    medical_history_text: opt_text(3000, multiline=True) = None
    current_medications: opt_text(1000, multiline=True) = None
    assigned_doctor_id: PositiveId | None = None

    @model_validator(mode="after")
    def emergency_contact_is_someone_else(self):
        """The emergency contact is a person to call when the patient cannot answer: it must not be the patient's own number."""
        if self.phone and self.emergency_contact and len(_digits(self.phone)) >= 10 and _digits(self.phone) == _digits(self.emergency_contact):
            raise ValueError("The emergency contact must be a different person: it has the patient's own phone number.")
        return self


class PatientCreate(PatientFields):
    email: Email
    full_name: PersonName
    password: Password | None = None  # generated when empty

    @model_validator(mode="after")
    def not_the_email(self):
        if self.password and password_has_email_name(self.password, self.email):
            raise ValueError(NO_NAME_IN_PASSWORD)
        return self


class PatientUpdate(PatientFields):
    full_name: PersonName | None = None


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
