"""What a trainee sends and receives: the history form (a draft may be half empty, a complete one may not) and the referral."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.health_history import Vitals
from app.utils.validators import PositiveId, opt_text, text


class TraineeHistoryData(BaseModel):
    chief_complaint: opt_text(300) = None
    duration: opt_text(60) = None
    symptoms: list[text(120)] = Field(default_factory=list, max_length=30)
    present_illness: opt_text(3000, multiline=True) = None
    past_medical: opt_text(2000, multiline=True) = None
    past_surgical: opt_text(2000, multiline=True) = None
    medications: opt_text(1500, multiline=True) = None
    allergies: Literal["NONE", "YES"] | None = None             # "none" is an explicit answer, not a blank
    allergy_details: opt_text(500, multiline=True) = None
    family_history: opt_text(1000, multiline=True) = None
    smoking: Literal["NONE", "SMOKER", "CHEWER", "FORMER"] | None = None
    alcohol: Literal["NONE", "OCCASIONAL", "REGULAR", "FORMER"] | None = None
    personal_social: opt_text(1000, multiline=True) = None
    menstrual_obstetric: opt_text(1000, multiline=True) = None
    vitals: Vitals = Vitals()

    @model_validator(mode="after")
    def allergy_needs_details(self):
        if self.allergies == "NONE":
            self.allergy_details = None
        return self


class TraineeHistoryStart(BaseModel):
    patient_id: PositiveId


class TraineeHistorySave(BaseModel):
    data: TraineeHistoryData


class DoctorHistoryEdit(BaseModel):
    data: TraineeHistoryData | None = None
    note: opt_text(2000, multiline=True) = None


class ReferralCreate(BaseModel):
    history_id: PositiveId
    doctor_id: PositiveId
    reason: text(300, min_length=2)
    urgent: bool = False
    suggested_department_id: PositiveId | None = None
    book_at: datetime | None = None


class SupervisorReview(BaseModel):
    approved: bool = True
    note: opt_text(500) = None
    doctor_id: PositiveId | None = None                           # "correct": send the patient to another doctor instead
