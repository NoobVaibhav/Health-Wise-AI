"""Shapes for the clinical-intelligence module: emergency events, follow-up tasks and the doctor's reviews of the summary."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.health_history import Vitals

TIMELINE_KINDS = ("ARRIVAL", "VITALS", "INVESTIGATION", "RESULT", "ASSESSMENT", "TREATMENT", "REASSESSMENT", "DISPOSITION", "OTHER")


class TimelineEntryIn(BaseModel):
    occurred_at: datetime
    kind: Literal["ARRIVAL", "VITALS", "INVESTIGATION", "RESULT", "ASSESSMENT", "TREATMENT", "REASSESSMENT", "DISPOSITION", "OTHER"] = "OTHER"
    text: str = Field(min_length=2, max_length=500)


class EmergencyIn(BaseModel):
    """Every field is optional: an emergency record can be incomplete, and the review will say what is missing."""
    event_at: datetime | None = None
    arrival_method: str | None = Field(default=None, max_length=40)
    chief_complaint: str | None = Field(default=None, max_length=1000)
    symptoms: list[str] = Field(default_factory=list, max_length=30)
    onset_text: str | None = Field(default=None, max_length=120)
    duration_text: str | None = Field(default=None, max_length=120)
    vitals: Vitals = Field(default_factory=Vitals)
    recent_medication_changes: str | None = Field(default=None, max_length=1500)
    exam_findings: str | None = Field(default=None, max_length=2000)
    investigations_ordered: str | None = Field(default=None, max_length=1500)
    investigation_results: str | None = Field(default=None, max_length=2000)
    clinician_assessment: str | None = Field(default=None, max_length=2000)
    documented_cause: str | None = Field(default=None, max_length=1000)         # only if the treating clinician wrote one
    contributing_factors: list[str] = Field(default_factory=list, max_length=20)  # only factors the clinician recorded as relevant
    treatment_given: str | None = Field(default=None, max_length=2000)
    response_to_treatment: str | None = Field(default=None, max_length=1500)
    disposition: Literal["ADMITTED", "DISCHARGED", "TRANSFERRED", "OTHER"] | None = None
    discharge_instructions: str | None = Field(default=None, max_length=2000)
    follow_up_recommendations: str | None = Field(default=None, max_length=2000)
    treating_clinician: str | None = Field(default=None, max_length=150)
    source_report_ids: list[int] = Field(default_factory=list, max_length=20)
    timeline: list[TimelineEntryIn] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def something_is_recorded(self):
        if not any([self.event_at, self.chief_complaint, self.symptoms, self.clinician_assessment, self.treatment_given, self.timeline, self.exam_findings]):
            raise ValueError("Please record at least the date, the complaint, the assessment or one timeline entry.")
        return self


class FollowUpIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    details: str | None = Field(default=None, max_length=1000)
    due_date: date | None = None
    source_type: Literal["recommendation", "emergency", "assessment", "note", "report"] | None = None
    source_id: int | None = None


class FollowUpUpdate(BaseModel):
    status: Literal["PENDING", "DONE", "CANCELLED"]
    outcome: str | None = Field(default=None, max_length=1000)


class ReviewIn(BaseModel):
    item_key: str = Field(min_length=3, max_length=80)         # e.g. report:12, change:HbA1c, section:missing
    action: Literal["REVIEWED", "INTERPRETATION", "CORRECTION", "MISSING_FLAG"]
    text: str | None = Field(default=None, max_length=1500)

    @model_validator(mode="after")
    def text_needed(self):
        if self.action != "REVIEWED" and not (self.text and self.text.strip()):
            raise ValueError("Please write your interpretation, correction or note.")
        return self
