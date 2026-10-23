"""Shapes for the detailed past medical history: chronic illnesses, regular medicines, hospital admissions and operations.
Every field is optional unless it is the name of the thing itself: a doctor records what is known, and what is not known stays empty
("Not recorded"). Nothing here is ever filled in by the system."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# who the information came from. EARLIER_ENTRY is only set by the migration of records written before these screens existed.
Source = Literal["PATIENT_REPORTED", "DOCTOR_VERIFIED", "HOSPITAL_RECORD"]
YesNoUnknown = Literal["YES", "NO", "UNKNOWN"]
Kind = Literal["DIABETES", "HYPERTENSION", "OTHER"]
Control = Literal["GOOD", "FAIR", "POOR", "UNKNOWN"]

DIABETES_COMPLICATIONS = ("retinopathy", "neuropathy", "nephropathy", "foot", "cardiovascular", "hypoglycemia")
HYPERTENSION_COMPLICATIONS = ("heart_disease", "stroke", "kidney_damage")
COMPLICATION_LABELS = {
    "retinopathy": "Diabetic retinopathy (eye)", "neuropathy": "Diabetic neuropathy (nerves)", "nephropathy": "Diabetic nephropathy (kidney)",
    "foot": "Diabetic foot or non-healing wounds", "cardiovascular": "Cardiovascular complications",
    "hypoglycemia": "Earlier low sugar (hypoglycaemia) or diabetic emergency",
    "heart_disease": "Heart disease", "stroke": "Stroke", "kidney_damage": "Kidney damage",
}
THIS_YEAR = date.today().year


class ControlReadings(BaseModel):
    """Readings the patient or doctor reports for how well the illness is controlled (dated, so they are never mixed with today's)."""
    fasting: float | None = Field(default=None, ge=20, le=700)          # mg/dL
    postprandial: float | None = Field(default=None, ge=20, le=900)     # mg/dL
    random: float | None = Field(default=None, ge=20, le=900)           # mg/dL
    hba1c: float | None = Field(default=None, ge=3, le=20)              # %
    bp_usual: str | None = Field(default=None, max_length=30)           # e.g. 130/80
    bp_recent: str | None = Field(default=None, max_length=60)          # e.g. 142/90 on 4 Sep 2026
    noted_on: str | None = Field(default=None, max_length=40)           # when these were measured


class Hospitalisation(BaseModel):
    happened: YesNoUnknown = "UNKNOWN"
    reason: str | None = Field(default=None, max_length=400)
    date_text: str | None = Field(default=None, max_length=60)
    treatment: str | None = Field(default=None, max_length=600)
    outcome: str | None = Field(default=None, max_length=400)


class ConditionIn(BaseModel):
    kind: Kind
    name: str | None = Field(default=None, max_length=150)              # diabetes and hypertension get a standard name when left empty
    diagnosis_type: str | None = Field(default=None, max_length=60)     # Type 1 / Type 2 / Gestational / Other / Unknown
    duration_text: str | None = Field(default=None, max_length=60)      # "5 years"
    diagnosis_year: int | None = Field(default=None, ge=1900)
    control_status: Control | None = None
    on_treatment: bool | None = None
    control: ControlReadings = Field(default_factory=ControlReadings)
    complications: dict[str, YesNoUnknown] = Field(default_factory=dict)
    complications_other: str | None = Field(default=None, max_length=500)
    hospitalisation: Hospitalisation = Field(default_factory=Hospitalisation)
    other_details: str | None = Field(default=None, max_length=1500)
    notes: str | None = Field(default=None, max_length=1500)
    source: Source = "PATIENT_REPORTED"

    @field_validator("diagnosis_year")
    @classmethod
    def not_in_the_future(cls, v):
        if v is not None and v > THIS_YEAR:
            raise ValueError("The year of diagnosis cannot be in the future.")
        return v

    @model_validator(mode="after")
    def check(self):
        if self.kind == "OTHER" and len((self.name or "").strip()) < 2:
            raise ValueError("Please write the name of the illness (at least two letters).")
        allowed = {"DIABETES": DIABETES_COMPLICATIONS, "HYPERTENSION": HYPERTENSION_COMPLICATIONS}.get(self.kind, ())
        extra = [k for k in self.complications if k not in allowed]
        if extra and self.kind != "OTHER":
            raise ValueError(f"Unknown complication: {extra[0]}")
        return self


class PastMedicationIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    dose: str | None = Field(default=None, max_length=100)
    frequency: str | None = Field(default=None, max_length=100)
    route: str | None = Field(default=None, max_length=40)
    since: str | None = Field(default=None, max_length=60)              # start date or duration, if known
    prescriber: str | None = Field(default=None, max_length=150)
    adherence: Literal["REGULAR", "SOMETIMES_MISSED", "OFTEN_MISSED", "UNKNOWN"] | None = None
    reason: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=300)
    condition_id: int | None = None                                      # the illness this medicine is taken for
    is_current: bool = True
    source: Source = "PATIENT_REPORTED"


class AdmissionVitals(BaseModel):
    """Measured at the time of admission (never today's readings)."""
    bp_systolic: int | None = Field(default=None, ge=30, le=300)
    bp_diastolic: int | None = Field(default=None, ge=20, le=200)
    pulse: int | None = Field(default=None, ge=10, le=300)
    resp_rate: int | None = Field(default=None, ge=4, le=80)
    temperature_f: float | None = Field(default=None, ge=80, le=115)
    spo2: int | None = Field(default=None, ge=30, le=100)
    pain_score: int | None = Field(default=None, ge=0, le=10)
    recorded_at: str | None = Field(default=None, max_length=60)


class AdmissionMed(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    dose: str | None = Field(default=None, max_length=100)
    frequency: str | None = Field(default=None, max_length=100)
    route: str | None = Field(default=None, max_length=40)
    duration: str | None = Field(default=None, max_length=100)
    category: Literal["ANTIBIOTIC", "PAINKILLER", "IV_FLUID", "OXYGEN", "OTHER"] | None = None
    note: str | None = Field(default=None, max_length=300)


T1500 = Field(default=None, max_length=1500)
T3000 = Field(default=None, max_length=3000)


class AdmissionIn(BaseModel):
    hospital_name: str | None = Field(default=None, max_length=200)
    admitted_at: datetime | None = None
    admitted_date_text: str | None = Field(default=None, max_length=40)     # "March 2019" when no exact date is known
    discharged_at: datetime | None = None
    admission_type: Literal["EMERGENCY", "PLANNED", "REFERRAL", "OTHER"] | None = None
    main_complaint: str | None = T1500
    secondary_complaints: str | None = T1500
    provisional_diagnosis: str | None = T1500
    final_diagnosis: str | None = T1500
    reason: str | None = T1500
    referred_by: str | None = Field(default=None, max_length=200)
    symptoms: str | None = T1500
    history_of_present_illness: str | None = T3000
    preexisting_conditions: str | None = T1500
    vitals: AdmissionVitals = Field(default_factory=AdmissionVitals)
    exam_findings: str | None = T3000
    investigations: str | None = T3000
    complications: str | None = T1500
    treatment_given: str | None = T3000
    medications: list[AdmissionMed] = Field(default_factory=list, max_length=60)
    iv_fluids_oxygen: str | None = T1500
    procedures_supportive: str | None = T1500
    medication_changes: str | None = T1500
    response_to_treatment: str | None = T1500
    stay_complications: str | None = T1500
    discharge_condition: str | None = T1500
    treatment_completed: str | None = T1500
    discharge_medications: list[AdmissionMed] = Field(default_factory=list, max_length=60)
    discharge_instructions: str | None = T3000
    wound_rehab_instructions: str | None = T1500
    followup_date: date | None = None
    specialist_review: str | None = Field(default=None, max_length=200)
    recovery_status: str | None = T1500
    remaining_symptoms: str | None = T1500
    readmission_notes: str | None = T1500
    source: Source = "PATIENT_REPORTED"

    @model_validator(mode="after")
    def dates_make_sense(self):
        if self.admitted_at and self.admitted_at.date() > date.today():
            raise ValueError("The admission date cannot be in the future.")
        if self.admitted_at and self.discharged_at and self.discharged_at < self.admitted_at:
            raise ValueError("The discharge cannot be earlier than the admission.")
        if self.discharged_at and self.discharged_at.date() > date.today():
            raise ValueError("The discharge date cannot be in the future.")
        return self


class SurgeryIn(BaseModel):
    admission_id: int | None = None
    procedure_name: str = Field(min_length=2, max_length=200)
    reason: str | None = T1500
    body_site: str | None = Field(default=None, max_length=150)
    operation_date: date | None = None
    operation_year: int | None = Field(default=None, ge=1900)
    surgeon: str | None = Field(default=None, max_length=150)
    hospital: str | None = Field(default=None, max_length=200)
    anesthesia: str | None = Field(default=None, max_length=100)
    findings: str | None = T1500
    implant_used: bool | None = None                                         # None = not documented
    implant_type: str | None = Field(default=None, max_length=100)
    implant_material: str | None = Field(default=None, max_length=150)
    implant_serial: str | None = Field(default=None, max_length=100)
    postop_xray: str | None = T1500
    postop_treatment: str | None = T1500
    postop_complications: str | None = T1500
    recovery_progress: str | None = T1500
    source: Source = "PATIENT_REPORTED"

    @model_validator(mode="after")
    def check(self):
        if self.operation_date and self.operation_date > date.today():
            raise ValueError("The operation date cannot be in the future.")
        if self.operation_year is not None and self.operation_year > THIS_YEAR:
            raise ValueError("The operation year cannot be in the future.")
        if self.implant_used is False and any([self.implant_type, self.implant_material, self.implant_serial]):
            raise ValueError("Implant details were given although no implant was used.")
        return self
