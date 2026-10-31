from datetime import date, datetime

from typing import Literal

from pydantic import BaseModel, Field
from app.utils.validators import PastOrTodayRequired, text, PositiveId

PRIORITIES = ("NORMAL", "IMPORTANT", "FOLLOW_UP_REQUIRED")


class NoteCreate(BaseModel):
    patient_id: PositiveId
    report_id: PositiveId | None = None
    note: text(3000, min_length=2, multiline=True)
    priority: Literal["NORMAL", "IMPORTANT", "FOLLOW_UP_REQUIRED"] = "NORMAL"


class NoteOut(BaseModel):
    id: int
    patient_id: PositiveId
    patient_name: str
    doctor_name: str
    report_id: int | None
    note: str
    priority: str
    created_at: datetime
    label: str = "Doctor's Note"


class RecommendationCreate(BaseModel):
    patient_id: PositiveId
    report_id: PositiveId | None = None
    title: text(200, min_length=2)
    recommendation: text(3000, min_length=2, multiline=True)
    follow_up_date: date | None = None
    priority: str = "NORMAL"


class RecommendationOut(BaseModel):
    id: int
    patient_id: PositiveId
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
    patient_id: PositiveId
    entry_date: PastOrTodayRequired
    entry_type: text(40, min_length=2)
    description: text(2000, min_length=2, multiline=True)


class DoctorOut(BaseModel):
    id: int
    full_name: str
    specialization: str | None
    department_id: int | None
    department_name: str | None
    is_active: bool
