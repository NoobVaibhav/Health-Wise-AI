from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from app.utils.appointment_time import check_appointment_time
from app.utils.clock import to_hospital_time
from app.utils.validators import opt_text, text, PositiveId

STATUSES = ("SCHEDULED", "CONFIRMED", "COMPLETED", "CANCELLED")


class AppointmentCreate(BaseModel):
    patient_id: PositiveId | None = None      # patients booking for themselves may leave this empty
    doctor_id: PositiveId
    department_id: PositiveId | None = None
    scheduled_at: datetime
    reason: opt_text(300) = None      # the main problem, in a few words
    symptoms: list[text(120)] = Field(default_factory=list, max_length=20)   # ticked: fever, chest pain, giddiness ...
    duration: opt_text(60) = None          # since when
    details: opt_text(1000, multiline=True) = None         # what is happening, in the patient's words

    @field_validator("scheduled_at")
    @classmethod
    def _time(cls, value):
        return check_appointment_time(to_hospital_time(value))          # with or without an offset: the hospital's wall-clock time; then past / slot / opening hours / 30 days ahead


class AppointmentUpdate(BaseModel):
    status: str | None = None
    scheduled_at: datetime | None = None
    reason: opt_text(300) = None

    @field_validator("status")
    @classmethod
    def _status(cls, value):
        if value is None:
            return value
        if value.strip().upper() not in STATUSES:
            raise ValueError(f"The status must be one of: {', '.join(STATUSES)}.")
        return value.strip().upper()

    @field_validator("scheduled_at")
    @classmethod
    def _time(cls, value):
        return None if value is None else check_appointment_time(to_hospital_time(value))


class AppointmentOut(BaseModel):
    id: int
    patient_id: PositiveId
    patient_name: str
    patient_code: str
    doctor_id: PositiveId
    doctor_name: str
    department_name: str | None
    scheduled_at: datetime
    reason: str | None
    status: str
    encounter_id: int | None = None          # set once the patient is checked in
    # the patient's own description of the problem: only the patient and the doctor get it
    symptoms: list[str] = []
    duration: str | None = None
    details: str | None = None
