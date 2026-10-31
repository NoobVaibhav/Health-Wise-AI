import re
from datetime import date

from pydantic import BaseModel, Field, field_validator
from app.utils.validators import Quantity, check_duration, opt_text, text, PositiveId


class PrescriptionItemCreate(BaseModel):
    medicine_name: text(200, min_length=2)
    dosage: text(100, min_length=1)
    frequency: text(100, min_length=1)
    duration: text(100, min_length=1)
    quantity: Quantity
    instructions: opt_text(1000, multiline=True) = None

    @field_validator("dosage", "frequency")
    @classmethod
    def _positive(cls, value):
        """A dose or frequency of zero or a negative number is a mistake ('0 mg', '-1 tablet')."""
        if value.lstrip().startswith("-") or re.match(r"^\s*0+(\.0+)?(\s|[A-Za-z]|$)", value):
            raise ValueError("The dose and the frequency must be more than zero.")
        return value

    @field_validator("duration")
    @classmethod
    def _duration(cls, value):
        return check_duration(value)


class PrescriptionCreate(BaseModel):
    patient_id: PositiveId
    report_id: PositiveId | None = None
    encounter_id: PositiveId | None = None        # the visit this prescription belongs to (OPD consultation)
    clinical_indication: opt_text(300) = None
    notes: opt_text(2000, multiline=True) = None
    items: list[PrescriptionItemCreate] = Field(min_length=1, max_length=30)
    tests: list[text(120)] = Field(default_factory=list, max_length=30)   # tests to get done (lab); not shown to the pharmacy

    @field_validator("tests")
    @classmethod
    def clean_tests(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for name in value:
            name = " ".join(name.split())
            if len(name) < 2 or len(name) > 200:
                raise ValueError("Each test name must be between 2 and 200 characters.")
            if name.lower() not in [c.lower() for c in cleaned]:
                cleaned.append(name)
        return cleaned


class PrescriptionItemOut(BaseModel):
    id: int
    medicine_name: str
    dosage: str
    frequency: str
    duration: str
    quantity: int
    instructions: str | None
    dispense_status: str
    dispensed_quantity: int
    remaining_quantity: int


class DoctorInfo(BaseModel):
    """For the letterhead of the printed prescription. Anything that is not recorded stays empty (the sheet then shows nothing)."""
    qualification: str | None = None
    specialization: str | None = None
    department: str | None = None
    registration_number: str | None = None


class PatientInfo(BaseModel):
    """For the patient strip of the printed prescription. The pharmacy gets age and sex only (as before, it never sees a patient's phone or allergies)."""
    age: int | None = None
    gender: str | None = None
    phone: str | None = None
    allergies: str | None = None


class HospitalInfo(BaseModel):
    """From the settings (HOSPITAL_NAME, HOSPITAL_ADDRESS, HOSPITAL_PHONE, HOSPITAL_EMAIL). Empty until the hospital sets them."""
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None


class PrescriptionOut(BaseModel):
    id: int
    code: str
    patient_id: PositiveId
    patient_name: str
    patient_code: str
    doctor_id: PositiveId
    doctor_name: str
    report_id: int | None
    prescription_date: date
    valid_until: date
    clinical_indication: str | None
    notes: str | None
    status: str
    items: list[PrescriptionItemOut]
    tests: list[str] = []   # empty for the pharmacy, which never sees tests
    label: str = "Prescribed by a doctor"
    warnings: list[str] = []      # for the doctor who just wrote it: for example the same medicine twice
    doctor_info: DoctorInfo = DoctorInfo()
    patient_info: PatientInfo = PatientInfo()
    hospital: HospitalInfo = HospitalInfo()
