from datetime import datetime

from pydantic import BaseModel, Field

STATUSES = ("SCHEDULED", "CONFIRMED", "COMPLETED", "CANCELLED")


class AppointmentCreate(BaseModel):
    patient_id: int | None = None      # patients booking for themselves may leave this empty
    doctor_id: int
    department_id: int | None = None
    scheduled_at: datetime
    reason: str | None = Field(default=None, max_length=300)


class AppointmentUpdate(BaseModel):
    status: str | None = None
    scheduled_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=300)


class AppointmentOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_code: str
    doctor_id: int
    doctor_name: str
    department_name: str | None
    scheduled_at: datetime
    reason: str | None
    status: str
