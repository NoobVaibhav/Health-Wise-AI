"""Step 2 of the validation pass: gaps found by reading every request schema for fields that bypass the shared rules. Each test states the rule that SHOULD hold;
a failing test is a confirmed gap. Pure model checks (no database). Data is invented."""
from datetime import date, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.clinical import AdmitIn, ConsultationIn, MedicationOrderIn
from app.schemas.clinical_intel import FollowUpIn, TimelineEntryIn
from app.schemas.doctor import RecommendationCreate
from app.schemas.past_history import AdmissionIn, ConditionIn, SurgeryIn

TODAY = date.today()
IMPLAUSIBLE = [date(1, 1, 1), date(1899, 12, 31), date(9999, 12, 31), TODAY + timedelta(days=366 * 5)]


def refused(model, **data):
    try:
        model(**data)
    except ValidationError:
        return True
    return False


# ----------------------------------------------------- dates a doctor sets ahead (follow-up, expected discharge, due date)
@pytest.mark.parametrize("bad", IMPLAUSIBLE)
def test_follow_up_and_discharge_dates_must_be_plausible(bad):
    assert refused(ConsultationIn, follow_up_date=bad)
    assert refused(RecommendationCreate, patient_id=1, title="Review", recommendation="Come back", follow_up_date=bad)
    assert refused(FollowUpIn, title="Call the patient", due_date=bad)
    assert refused(AdmitIn, patient_id=1, expected_discharge=bad)


def test_reasonable_dates_still_accepted():
    soon = TODAY + timedelta(days=14)
    assert not refused(ConsultationIn, follow_up_date=soon)
    assert not refused(RecommendationCreate, patient_id=1, title="Review", recommendation="Come back", follow_up_date=soon)
    assert not refused(FollowUpIn, title="Call the patient", due_date=soon)
    assert not refused(AdmitIn, patient_id=1, expected_discharge=soon)


# ----------------------------------------------------- a free text where a fixed list belongs
def test_recommendation_priority_is_one_of_the_fixed_words():
    assert refused(RecommendationCreate, patient_id=1, title="Review", recommendation="Come back", priority="<b>whatever</b>")
    assert refused(RecommendationCreate, patient_id=1, title="Review", recommendation="Come back", priority="x" * 5000)
    assert not refused(RecommendationCreate, patient_id=1, title="Review", recommendation="Come back", priority="IMPORTANT")


# ----------------------------------------------------- years
@pytest.mark.parametrize("year", [TODAY.year + 1, 2999, 99999])
def test_a_diagnosis_or_operation_year_is_not_in_the_future(year):
    assert refused(ConditionIn, kind="DIABETES", diagnosis_year=year)
    assert refused(SurgeryIn, procedure_name="Appendectomy", operation_year=year)


# ----------------------------------------------------- a history written after the fact: not in the future, order of events
def test_timeline_and_admission_times_are_not_in_the_future_and_discharge_follows_admission():
    tomorrow = datetime.now() + timedelta(days=2)
    assert refused(TimelineEntryIn, occurred_at=tomorrow, text="Arrived by ambulance")
    assert refused(AdmissionIn, admitted_at=tomorrow)
    assert refused(AdmissionIn, admitted_at=datetime(2024, 5, 10, 9), discharged_at=datetime(2024, 5, 1, 9))
    assert not refused(AdmissionIn, admitted_at=datetime(2024, 5, 1, 9), discharged_at=datetime(2024, 5, 10, 9))


def test_medication_order_end_is_not_before_start():
    assert refused(MedicationOrderIn, medicine_name="Paracetamol", dose="500 mg", times=["08:00"], start_date=TODAY, end_date=TODAY - timedelta(days=3))
    assert not refused(MedicationOrderIn, medicine_name="Paracetamol", dose="500 mg", times=["08:00"], start_date=TODAY, end_date=TODAY + timedelta(days=3))
