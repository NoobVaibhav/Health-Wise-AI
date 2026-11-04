"""Shapes for the clinical-intelligence module: emergency events, follow-up tasks and the doctor's reviews of the summary."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.health_history import Vitals
from app.utils.validators import PlannedDate, RecordedTime, opt_text, text, PositiveId

TIMELINE_KINDS = ("ARRIVAL", "VITALS", "INVESTIGATION", "RESULT", "ASSESSMENT", "TREATMENT", "REASSESSMENT", "DISPOSITION", "OTHER")


class TimelineEntryIn(BaseModel):
    occurred_at: RecordedTime
    kind: Literal["ARRIVAL", "VITALS", "INVESTIGATION", "RESULT", "ASSESSMENT", "TREATMENT", "REASSESSMENT", "DISPOSITION", "OTHER"] = "OTHER"
    text: text(500, min_length=2, multiline=True)


class EmergencyIn(BaseModel):
    """Every field is optional: an emergency record can be incomplete, and the review will say what is missing."""
    event_at: datetime | None = None
    arrival_method: opt_text(40) = None
    chief_complaint: opt_text(1000, multiline=True) = None
    symptoms: list[text(120)] = Field(default_factory=list, max_length=30)
    onset_text: opt_text(120) = None
    duration_text: opt_text(120) = None
    vitals: Vitals = Field(default_factory=Vitals)
    recent_medication_changes: opt_text(1500, multiline=True) = None
    exam_findings: opt_text(2000, multiline=True) = None
    investigations_ordered: opt_text(1500, multiline=True) = None
    investigation_results: opt_text(2000, multiline=True) = None
    clinician_assessment: opt_text(2000, multiline=True) = None
    documented_cause: opt_text(1000, multiline=True) = None         # only if the treating clinician wrote one
    contributing_factors: list[text(120)] = Field(default_factory=list, max_length=20)  # only factors the clinician recorded as relevant
    treatment_given: opt_text(2000, multiline=True) = None
    response_to_treatment: opt_text(1500, multiline=True) = None
    disposition: Literal["ADMITTED", "DISCHARGED", "TRANSFERRED", "OTHER"] | None = None
    discharge_instructions: opt_text(2000, multiline=True) = None
    follow_up_recommendations: opt_text(2000, multiline=True) = None
    treating_clinician: opt_text(150) = None
    source_report_ids: list[PositiveId] = Field(default_factory=list, max_length=20)
    timeline: list[TimelineEntryIn] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def something_is_recorded(self):
        if not any([self.event_at, self.chief_complaint, self.symptoms, self.clinician_assessment, self.treatment_given, self.timeline, self.exam_findings]):
            raise ValueError("Please record at least the date, the complaint, the assessment or one timeline entry.")
        return self


class FollowUpIn(BaseModel):
    title: text(200, min_length=3)
    details: opt_text(1000, multiline=True) = None
    due_date: PlannedDate = None
    source_type: Literal["recommendation", "emergency", "assessment", "note", "report"] | None = None
    source_id: PositiveId | None = None


class FollowUpUpdate(BaseModel):
    status: Literal["PENDING", "DONE", "CANCELLED"]
    outcome: opt_text(1000, multiline=True) = None


class ReviewIn(BaseModel):
    item_key: text(80, min_length=3)         # e.g. report:12, change:HbA1c, section:missing
    action: Literal["REVIEWED", "INTERPRETATION", "CORRECTION", "MISSING_FLAG"]
    text: opt_text(1500, multiline=True) = None

    @model_validator(mode="after")
    def text_needed(self):
        if self.action != "REVIEWED" and not (self.text and self.text.strip()):
            raise ValueError("Please write your interpretation, correction or note.")
        return self
