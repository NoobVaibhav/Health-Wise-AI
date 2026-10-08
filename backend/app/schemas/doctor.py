from datetime import date, datetime

from pydantic import BaseModel, Field

PRIORITIES = ("NORMAL", "IMPORTANT", "FOLLOW_UP_REQUIRED")


class NoteCreate(BaseModel):
    patient_id: int
    report_id: int | None = None
    note: str = Field(min_length=2, max_length=3000)
    priority: str = "NORMAL"


class NoteOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    doctor_name: str
    report_id: int | None
    note: str
    priority: str
    created_at: datetime
    label: str = "Doctor's Note"


class RecommendationCreate(BaseModel):
    patient_id: int
    report_id: int | None = None
    title: str = Field(min_length=2, max_length=200)
    recommendation: str = Field(min_length=2, max_length=3000)
    follow_up_date: date | None = None
    priority: str = "NORMAL"


class RecommendationOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    doctor_name: str
    report_id: int | None
    title: str
    recommendation: str
    follow_up_date: date | None
    priority: str
    created_at: datetime
    label: str = "Doctor's Recommendation"


class HistoryEntryCreate(BaseModel):
    patient_id: int
    entry_date: date
    entry_type: str = Field(min_length=2, max_length=40)
    description: str = Field(min_length=2, max_length=2000)


class DoctorOut(BaseModel):
    id: int
    full_name: str
    specialization: str | None
    department_id: int | None
    department_name: str | None
    is_active: bool
