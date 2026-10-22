"""Shapes of the health-history form (what the patient or doctor sends and what comes back)."""
from typing import Literal

from pydantic import BaseModel, Field

Text120 = Field(default=None, max_length=120)


class ConditionItem(BaseModel):
    name: str = Field(min_length=2, max_length=120)          # e.g. Hypertension, Diabetes, Asthma
    since: str | None = Field(default=None, max_length=40)   # e.g. "25 years" or "2003"
    on_treatment: bool = False
    notes: str | None = Field(default=None, max_length=300)


class SurgeryItem(BaseModel):
    what: str = Field(min_length=2, max_length=150)
    year: str | None = Field(default=None, max_length=20)
    hospital: str | None = Field(default=None, max_length=150)


class FamilyItem(BaseModel):
    relation: str = Field(min_length=2, max_length=40)       # Father, Mother, Brother ...
    condition: str = Field(min_length=2, max_length=150)


class AllergyItem(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    kind: Literal["DRUG", "FOOD", "OTHER"] = "DRUG"
    reaction: str | None = Field(default=None, max_length=200)


class MedicationItem(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    dose: str | None = Field(default=None, max_length=100)
    frequency: str | None = Field(default=None, max_length=100)    # e.g. once daily at night
    reason: str | None = Field(default=None, max_length=200)       # what it is for
    since: str | None = Field(default=None, max_length=60)
    notes: str | None = Field(default=None, max_length=300)
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
    exercise: str | None = Field(default=None, max_length=150)


class CurrentProblem(BaseModel):
    """Why the patient is worried now (the 'chief complaint' on the hospital form)."""
    complaint: str | None = Field(default=None, max_length=300)
    duration: str | None = Field(default=None, max_length=60)
    symptoms: list[str] = Field(default_factory=list, max_length=30)   # ticked: fever, chest pain, giddiness ...
    denies: list[str] = Field(default_factory=list, max_length=30)     # "no" answers are useful too
    details: str | None = Field(default=None, max_length=1500)


class OtherValue(BaseModel):
    name: str = Field(min_length=2, max_length=80)      # e.g. Uric acid, TSH, Vitamin D
    value: str = Field(min_length=1, max_length=40)
    unit: str | None = Field(default=None, max_length=20)


class Baseline(BaseModel):
    """The patient's usual values when well. A doctor compares today's reading with these."""
    pulse: int | None = Field(default=None, ge=20, le=250)
    bp_systolic: int | None = Field(default=None, ge=50, le=260)
    bp_diastolic: int | None = Field(default=None, ge=30, le=160)
    spo2: int | None = Field(default=None, ge=50, le=100)
    sugar_fasting: float | None = Field(default=None, ge=20, le=700)        # mg/dL
    sugar_post_meal: float | None = Field(default=None, ge=20, le=900)      # mg/dL
    hba1c: float | None = Field(default=None, ge=3, le=20)                  # %
    hemoglobin: float | None = Field(default=None, ge=2, le=25)             # g/dL
    creatinine: float | None = Field(default=None, ge=0.1, le=20)           # mg/dL
    others: list[OtherValue] = Field(default_factory=list, max_length=20)
    noted_on: str | None = Field(default=None, max_length=30)               # when these were measured
    note: str | None = Field(default=None, max_length=300)


class HistoryIn(BaseModel):
    height_cm: float | None = Field(default=None, ge=30, le=250)
    weight_kg: float | None = Field(default=None, ge=1, le=400)
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
    immunization: str | None = Field(default=None, max_length=500)
    birth_history: str | None = Field(default=None, max_length=500)          # for children
    developmental_history: str | None = Field(default=None, max_length=500)  # for children
    socioeconomic: str | None = Field(default=None, max_length=500)          # work, who the patient lives with
    menstrual_obstetric: str | None = Field(default=None, max_length=500)    # periods, pregnancies (women)


class Vitals(BaseModel):
    pulse: int | None = Field(default=None, ge=10, le=300)
    bp_systolic: int | None = Field(default=None, ge=30, le=300)
    bp_diastolic: int | None = Field(default=None, ge=20, le=200)
    temperature_f: float | None = Field(default=None, ge=80, le=115)
    resp_rate: int | None = Field(default=None, ge=4, le=80)
    spo2: int | None = Field(default=None, ge=30, le=100)
    weight_kg: float | None = Field(default=None, ge=1, le=400)
    height_cm: float | None = Field(default=None, ge=30, le=250)


class Examination(BaseModel):
    consciousness: str | None = Field(default=None, max_length=200)
    general: str | None = Field(default=None, max_length=600)          # pallor, oedema, cyanosis, clubbing, lymph nodes
    respiratory: str | None = Field(default=None, max_length=600)
    cardiovascular: str | None = Field(default=None, max_length=600)
    abdomen: str | None = Field(default=None, max_length=600)
    nervous_system: str | None = Field(default=None, max_length=600)


class AssessmentIn(BaseModel):
    chief_complaint: str | None = Field(default=None, max_length=600)
    history_of_present_illness: str | None = Field(default=None, max_length=3000)
    vitals: Vitals = Field(default_factory=Vitals)
    examination: Examination = Field(default_factory=Examination)
    provisional_diagnosis: str | None = Field(default=None, max_length=600)
    investigations_advised: str | None = Field(default=None, max_length=600)
    plan_type: Literal["MEDICAL", "SURGICAL", "BOTH"] | None = None
    plan_details: str | None = Field(default=None, max_length=1500)
    special_note: str | None = Field(default=None, max_length=1500)
