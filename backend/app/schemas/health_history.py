"""Shapes of the health-history form (what the patient or doctor sends and what comes back)."""
from typing import Literal

from pydantic import BaseModel, Field
from app.utils.validators import opt_text, text, PULSE, SYSTOLIC, DIASTOLIC, SPO2, TEMPERATURE_F, RESP_RATE, HEIGHT_CM, WEIGHT_KG

Text120 = Field(default=None, max_length=120)


class ConditionItem(BaseModel):
    name: text(120, min_length=2)          # e.g. Hypertension, Diabetes, Asthma
    since: opt_text(40) = None   # e.g. "25 years" or "2003"
    on_treatment: bool = False
    notes: opt_text(300) = None


class SurgeryItem(BaseModel):
    what: text(150, min_length=2)
    year: opt_text(20) = None
    hospital: opt_text(150) = None


class FamilyItem(BaseModel):
    relation: text(40, min_length=2)       # Father, Mother, Brother ...
    condition: text(150, min_length=2)


class AllergyItem(BaseModel):
    name: text(120, min_length=2)
    kind: Literal["DRUG", "FOOD", "OTHER"] = "DRUG"
    reaction: opt_text(200) = None


class MedicationItem(BaseModel):
    name: text(200, min_length=2)
    dose: opt_text(100) = None
    frequency: opt_text(100) = None    # e.g. once daily at night
    reason: opt_text(200) = None       # what it is for
    since: opt_text(60) = None
    notes: opt_text(300) = None
    is_current: bool = True


class Habits(BaseModel):
    tobacco: Literal["NONE", "SMOKER", "CHEWER", "FORMER"] | None = None
    tobacco_years: int | None = Field(default=None, ge=0, le=90)
    alcohol: Literal["NONE", "OCCASIONAL", "REGULAR", "FORMER"] | None = None
    alcohol_years: int | None = Field(default=None, ge=0, le=90)
    diet: Literal["VEG", "NONVEG", "MIXED", "VEGAN"] | None = None
    appetite: Literal["ADEQUATE", "POOR", "INCREASED"] | None = None
    sleep: Literal["ADEQUATE", "POOR", "EXCESS"] | None = None
    bowel_bladder: Literal["REGULAR", "IRREGULAR"] | None = None
    exercise: opt_text(150) = None


class CurrentProblem(BaseModel):
    """Why the patient is worried now (the 'chief complaint' on the hospital form)."""
    complaint: opt_text(300) = None
    duration: opt_text(60) = None
    symptoms: list[text(120)] = Field(default_factory=list, max_length=30)   # ticked: fever, chest pain, giddiness ...
    denies: list[text(120)] = Field(default_factory=list, max_length=30)     # "no" answers are useful too
    details: opt_text(1500, multiline=True) = None


class OtherValue(BaseModel):
    name: text(80, min_length=2)      # e.g. Uric acid, TSH, Vitamin D
    value: text(40, min_length=1)
    unit: opt_text(20) = None


class Baseline(BaseModel):
    """The patient's usual values when well. A doctor compares today's reading with these."""
    pulse: PULSE = None
    bp_systolic: SYSTOLIC = None
    bp_diastolic: DIASTOLIC = None
    spo2: SPO2 = None
    sugar_fasting: float | None = Field(default=None, ge=20, le=700)        # mg/dL
    sugar_post_meal: float | None = Field(default=None, ge=20, le=900)      # mg/dL
    hba1c: float | None = Field(default=None, ge=3, le=20)                  # %
    hemoglobin: float | None = Field(default=None, ge=2, le=25)             # g/dL
    creatinine: float | None = Field(default=None, ge=0.1, le=20)           # mg/dL
    others: list[OtherValue] = Field(default_factory=list, max_length=20)
    noted_on: opt_text(30) = None               # when these were measured
    note: opt_text(300) = None


class HistoryIn(BaseModel):
    height_cm: HEIGHT_CM = None
    weight_kg: WEIGHT_KG = None
    conditions: list[ConditionItem] = Field(default_factory=list, max_length=40)
    surgeries: list[SurgeryItem] = Field(default_factory=list, max_length=40)
    family: list[FamilyItem] = Field(default_factory=list, max_length=40)
    allergies: list[AllergyItem] = Field(default_factory=list, max_length=40)
    medications: list[MedicationItem] = Field(default_factory=list, max_length=60)
    habits: Habits = Field(default_factory=Habits)
    baseline: Baseline = Field(default_factory=Baseline)
    current_problem: CurrentProblem = Field(default_factory=CurrentProblem)
    # "none" answers: an empty list can mean "not filled in yet", so these say "I checked, there is nothing"
    no_known_conditions: bool = False
    no_known_allergies: bool = False
    no_regular_medicines: bool = False
    no_past_surgery: bool = False
    no_family_history: bool = False
    immunization: opt_text(500, multiline=True) = None
    birth_history: opt_text(500, multiline=True) = None          # for children
    developmental_history: opt_text(500, multiline=True) = None  # for children
    socioeconomic: opt_text(500, multiline=True) = None          # work, who the patient lives with
    menstrual_obstetric: opt_text(500, multiline=True) = None    # periods, pregnancies (women)


class Vitals(BaseModel):
    pulse: PULSE = None
    bp_systolic: SYSTOLIC = None
    bp_diastolic: DIASTOLIC = None
    temperature_f: TEMPERATURE_F = None
    resp_rate: RESP_RATE = None
    spo2: SPO2 = None
    weight_kg: WEIGHT_KG = None
    height_cm: HEIGHT_CM = None


class Examination(BaseModel):
    consciousness: opt_text(200) = None
    general: opt_text(600, multiline=True) = None          # pallor, oedema, cyanosis, clubbing, lymph nodes
    respiratory: opt_text(600, multiline=True) = None
    cardiovascular: opt_text(600, multiline=True) = None
    abdomen: opt_text(600, multiline=True) = None
    nervous_system: opt_text(600, multiline=True) = None


class AssessmentIn(BaseModel):
    chief_complaint: opt_text(600, multiline=True) = None
    history_of_present_illness: opt_text(3000, multiline=True) = None
    vitals: Vitals = Field(default_factory=Vitals)
    examination: Examination = Field(default_factory=Examination)
    provisional_diagnosis: opt_text(600, multiline=True) = None
    investigations_advised: opt_text(600, multiline=True) = None
    plan_type: Literal["MEDICAL", "SURGICAL", "BOTH"] | None = None
    plan_details: opt_text(1500, multiline=True) = None
    special_note: opt_text(1500, multiline=True) = None
