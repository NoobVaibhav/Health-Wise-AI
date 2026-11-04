"""Request shapes of the clinical workflows (OPD, consultation, nursing, emergency, IPD, discharge, referral requests)."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.utils.validators import (
    DIASTOLIC, HEIGHT_CM, PULSE, RESP_RATE, SPO2, SYSTOLIC, TEMPERATURE_F, WEIGHT_KG, PlannedDate, PositiveId, opt_text, text,
)

ORDER_KINDS = ("LAB", "RADIOLOGY", "PROCEDURE", "DIET", "NURSING", "OTHER")


class VitalsIn(BaseModel):
    pulse: PULSE = None
    bp_systolic: SYSTOLIC = None
    bp_diastolic: DIASTOLIC = None
    temperature_f: TEMPERATURE_F = None
    resp_rate: RESP_RATE = None
    spo2: SPO2 = None
    weight_kg: WEIGHT_KG = None
    height_cm: HEIGHT_CM = None
    pain_score: int | None = Field(default=None, ge=0, le=10)
    gcs: int | None = Field(default=None, ge=3, le=15)
    note: opt_text(300) = None

    @model_validator(mode="after")
    def something_measured(self):
        if all(getattr(self, k) is None for k in ("pulse", "bp_systolic", "bp_diastolic", "temperature_f", "resp_rate", "spo2", "weight_kg", "height_cm", "pain_score", "gcs")):
            raise ValueError("Please enter at least one measurement.")
        if (self.bp_systolic is None) != (self.bp_diastolic is None):
            raise ValueError("Please enter both blood pressure values.")
        if self.bp_systolic is not None and self.bp_diastolic is not None and self.bp_diastolic >= self.bp_systolic:
            raise ValueError("The lower blood pressure must be lower than the upper one.")
        return self


# ------------------------------------------------------------------ OPD
class CheckInIn(BaseModel):
    appointment_id: PositiveId
    urgent: bool = False


class WalkInIn(BaseModel):
    patient_id: PositiveId
    doctor_id: PositiveId
    department_id: PositiveId | None = None
    reason: opt_text(300) = None
    urgent: bool = False


# ------------------------------------------------------------------ consultation
class ConsultationIn(BaseModel):
    complaint: opt_text(2000, multiline=True) = None
    hpi: opt_text(4000, multiline=True) = None
    past_history: opt_text(3000, multiline=True) = None
    family_history: opt_text(2000, multiline=True) = None
    examination: opt_text(4000, multiline=True) = None
    assessment: opt_text(3000, multiline=True) = None
    plan: opt_text(3000, multiline=True) = None
    advice: opt_text(3000, multiline=True) = None
    follow_up_date: PlannedDate = None
    template_id: PositiveId | None = None
    data: dict[str, str | int | float | None] = Field(default_factory=dict, max_length=40)

    @field_validator("data")
    @classmethod
    def short_values(cls, value):
        for key, item in value.items():
            if len(str(key)) > 40 or (isinstance(item, str) and len(item) > 3000):
                raise ValueError("A template answer is too long.")
        return value


class AddendumIn(BaseModel):
    text: text(3000, min_length=3, multiline=True)


class DiagnosisIn(BaseModel):
    text: text(300, min_length=2)
    code: opt_text(20) = None
    kind: Literal["PROVISIONAL", "FINAL"] = "PROVISIONAL"


class OrderIn(BaseModel):
    kind: Literal["LAB", "RADIOLOGY", "PROCEDURE", "DIET", "NURSING", "OTHER"]
    text: text(300, min_length=2)
    priority: Literal["ROUTINE", "URGENT", "STAT"] = "ROUTINE"


class OrderStatusIn(BaseModel):
    status: Literal["IN_PROGRESS", "DONE", "CANCELLED"]
    note: opt_text(300) = None


class TemplateField(BaseModel):
    key: text(40, min_length=1)
    label: text(100, min_length=1)
    kind: Literal["text", "longtext", "number", "choice"] = "text"
    options: list[text(60)] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def key_is_plain(self):
        if not self.key.replace("_", "").isalnum():
            raise ValueError("A field key can only have letters, digits and underscores.")
        if self.kind == "choice" and len(self.options) < 2:
            raise ValueError("A choice field needs at least two options.")
        return self


class TemplateIn(BaseModel):
    name: text(120, min_length=2)
    department_id: PositiveId | None = None
    fields: list[TemplateField] = Field(max_length=30)
    is_active: bool = True


# ------------------------------------------------------------------ nursing
class NursingNoteIn(BaseModel):
    kind: Literal["NOTE", "CARE_PLAN", "HANDOVER"] = "NOTE"
    shift: Literal["MORNING", "EVENING", "NIGHT"] | None = None
    text: text(3000, min_length=3, multiline=True)

    @model_validator(mode="after")
    def handover_has_shift(self):
        if self.kind == "HANDOVER" and not self.shift:
            raise ValueError("Please choose the shift for a handover.")
        return self


class IntakeOutputIn(BaseModel):
    kind: Literal["INTAKE", "OUTPUT"]
    item: text(100, min_length=2)
    amount_ml: int = Field(gt=0, le=10000)


class MarActIn(BaseModel):
    status: Literal["GIVEN", "REFUSED", "HELD"]
    note: opt_text(300) = None

    @model_validator(mode="after")
    def reason_when_not_given(self):
        if self.status != "GIVEN" and not self.note:
            raise ValueError("Please write the reason when a dose is refused or held.")
        return self


class AckIn(BaseModel):
    note: opt_text(300) = None


class RuleIn(BaseModel):
    parameter: Literal["pulse", "bp_systolic", "bp_diastolic", "temperature_f", "resp_rate", "spo2", "gcs"]
    comparison: Literal["LT", "GT"]
    threshold: float = Field(ge=0, le=500, allow_inf_nan=False)
    level: Literal["WARNING", "CRITICAL"]
    message: text(200, min_length=3)
    is_active: bool = True


# ------------------------------------------------------------------ emergency
class UnidentifiedIn(BaseModel):
    gender: Literal["male", "female", "other"] | None = None
    approx_age: int | None = Field(default=None, ge=0, le=120)
    description: opt_text(200) = None


class EdVisitIn(BaseModel):
    patient_id: PositiveId | None = None
    unidentified: UnidentifiedIn | None = None
    chief_complaint: text(300, min_length=2)
    arrival_mode: Literal["WALK_IN", "AMBULANCE", "POLICE", "REFERRED"] = "WALK_IN"
    triage_category: int | None = Field(default=None, ge=1, le=5)

    @model_validator(mode="after")
    def who(self):
        if (self.patient_id is None) == (self.unidentified is None):
            raise ValueError("Choose a registered patient, or register an unidentified patient.")
        return self


class TriageIn(BaseModel):
    category: int = Field(ge=1, le=5)
    note: opt_text(300) = None
    vitals: VitalsIn | None = None


class AssignIn(BaseModel):
    doctor_id: PositiveId


class TimelineIn(BaseModel):
    kind: Literal["ASSESSMENT", "TREATMENT", "NOTE"]
    text: text(500, min_length=3)


class DispositionIn(BaseModel):
    disposition: Literal["DISCHARGE", "ADMIT", "ICU", "TRANSFER", "LAMA", "DEATH"]
    note: opt_text(500) = None
    attending_doctor_id: PositiveId | None = None
    bed_id: PositiveId | None = None
    department_id: PositiveId | None = None
    diagnosis: opt_text(300) = None

    @model_validator(mode="after")
    def needs_note(self):
        if self.disposition in ("TRANSFER", "LAMA", "DEATH") and not self.note:
            raise ValueError("Please write a note for this outcome.")
        return self


# ------------------------------------------------------------------ IPD
class WardIn(BaseModel):
    name: text(100, min_length=2)
    ward_type: Literal["GENERAL", "PRIVATE", "SEMI_PRIVATE", "ICU", "NICU", "PICU", "EMERGENCY", "ISOLATION", "RECOVERY"]
    branch_id: PositiveId | None = None


class WardUpdate(BaseModel):
    name: text(100, min_length=2) | None = None
    is_active: bool | None = None


class BedIn(BaseModel):
    code: text(20, min_length=1)


class BedStatusIn(BaseModel):
    status: Literal["AVAILABLE", "RESERVED", "CLEANING", "MAINTENANCE"]
    reserved_for_patient_id: PositiveId | None = None


class AdmitIn(BaseModel):
    patient_id: PositiveId
    attending_doctor_id: PositiveId | None = None
    department_id: PositiveId | None = None
    diagnosis: opt_text(300) = None
    source_encounter_id: PositiveId | None = None
    bed_id: PositiveId | None = None
    expected_discharge: PlannedDate = None


class BedAssignIn(BaseModel):
    bed_id: PositiveId
    reason: opt_text(200) = None


class StaffAssignIn(BaseModel):
    user_id: PositiveId
    kind: Literal["CONSULTING_DOCTOR", "NURSE"]


class ProgressNoteIn(BaseModel):
    note: text(4000, min_length=3, multiline=True)
    corrects_id: PositiveId | None = None


class MedicationOrderIn(BaseModel):
    medicine_name: text(200, min_length=2)
    dose: text(100, min_length=1)
    route: opt_text(40) = None
    times: list[text(5)] = Field(min_length=1, max_length=8)
    instructions: opt_text(300) = None
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("times")
    @classmethod
    def clock_times(cls, value):
        for t in value:
            parts = t.split(":")
            if len(parts) != 2 or len(parts[0]) != 2 or len(parts[1]) != 2 or not all(p.isdigit() for p in parts) or int(parts[0]) > 23 or int(parts[1]) > 59:
                raise ValueError("Dose times must look like 08:00.")
        if len(set(value)) != len(value):
            raise ValueError("A dose time is repeated.")
        return value

    @model_validator(mode="after")
    def dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("The end date cannot be before the start date.")
        return self


class DischargeSummaryIn(BaseModel):
    final_diagnosis: opt_text(3000, multiline=True) = None
    hospital_course: opt_text(5000, multiline=True) = None
    procedures: opt_text(3000, multiline=True) = None
    investigations_summary: opt_text(4000, multiline=True) = None
    discharge_medicines: opt_text(4000, multiline=True) = None
    follow_up: opt_text(2000, multiline=True) = None
    diet_advice: opt_text(2000, multiline=True) = None
    warning_signs: opt_text(2000, multiline=True) = None


class DischargeIn(BaseModel):
    discharge_type: Literal["NORMAL", "LAMA", "TRANSFER", "DEATH"] = "NORMAL"
    note: opt_text(500) = None


# ------------------------------------------------------------------ referral requests
class ReferralRequestIn(BaseModel):
    patient_id: PositiveId
    from_encounter_id: PositiveId | None = None
    to_department_id: PositiveId
    to_doctor_id: PositiveId | None = None
    reason: text(500, min_length=5)
    urgency: Literal["ROUTINE", "URGENT"] = "ROUTINE"


class ReferralResponseIn(BaseModel):
    note: opt_text(2000, multiline=True) = None
