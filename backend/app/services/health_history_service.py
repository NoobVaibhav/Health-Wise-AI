"""The health-history form: load it, save it, tell how complete it is, and build the one-page emergency card.
Employees and administrators never reach this (the router only lets the patient and authorised doctors in)."""
import json
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Appointment, ClinicalAssessment, HealthParameter, HealthReport, Patient, PatientHistory, PatientMedication, User, utcnow,
)
from app.schemas.health_history import AssessmentIn, HistoryIn
from app.services.history_insights import points_to_check, suggested_tests

LIST_KEYS = ("conditions", "surgeries", "family", "allergies")
FLAG_KEYS = ("no_known_conditions", "no_known_allergies", "no_regular_medicines", "no_past_surgery", "no_family_history")
TEXT_KEYS = ("immunization", "birth_history", "developmental_history", "socioeconomic", "menstrual_obstetric")


def age_of(patient: Patient) -> int | None:
    dob = patient.date_of_birth
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _medication_dict(m: PatientMedication) -> dict:
    return {"id": m.id, "name": m.name, "dose": m.dose, "frequency": m.frequency, "reason": m.reason, "since": m.since,
            "notes": m.notes, "is_current": m.is_current}


def load_history(db: Session, patient: Patient) -> dict:
    """The stored history as one dict shaped like the form (empty lists and flags when nothing was saved yet)."""
    row = db.scalar(select(PatientHistory).where(PatientHistory.patient_id == patient.id))
    stored = json.loads(row.data_json) if row and row.data_json else {}
    history = {key: stored.get(key, []) for key in LIST_KEYS}
    history.update({key: bool(stored.get(key, False)) for key in FLAG_KEYS})
    history.update({key: stored.get(key) for key in TEXT_KEYS})
    history["habits"] = stored.get("habits", {})
    history["baseline"] = stored.get("baseline", {})
    history["current_problem"] = stored.get("current_problem", {"complaint": None, "duration": None, "symptoms": [], "denies": [], "details": None})
    history["height_cm"] = row.height_cm if row else None
    history["weight_kg"] = row.weight_kg if row else None
    history["medications"] = [_medication_dict(m) for m in db.scalars(
        select(PatientMedication).where(PatientMedication.patient_id == patient.id).order_by(PatientMedication.id))]
    history["updated_at"] = row.updated_at.isoformat() if row else None
    history["updated_by_name"] = row.editor.full_name if row and row.editor else None
    history["saved_before"] = row is not None
    return history


def save_history(db: Session, patient: Patient, data: HistoryIn, user: User) -> dict:
    row = db.scalar(select(PatientHistory).where(PatientHistory.patient_id == patient.id))
    if row is None:
        row = PatientHistory(patient_id=patient.id)
        db.add(row)
    payload = data.model_dump()
    row.height_cm, row.weight_kg = payload["height_cm"], payload["weight_kg"]
    row.data_json = json.dumps({k: payload[k] for k in (*LIST_KEYS, *FLAG_KEYS, *TEXT_KEYS, "habits", "baseline", "current_problem")})
    row.updated_by, row.updated_at = user.id, utcnow()
    # the medicine list is replaced as a whole: what the form shows is what is stored
    for old in db.scalars(select(PatientMedication).where(PatientMedication.patient_id == patient.id)):
        db.delete(old)
    for item in payload["medications"]:
        db.add(PatientMedication(patient_id=patient.id, updated_at=utcnow(), **item))
    # the older single-line fields on the patient profile stay in step, so other screens show the same facts
    patient.allergies = ", ".join(a["name"] for a in payload["allergies"]) or patient.allergies
    patient.current_medications = ", ".join(m["name"] for m in payload["medications"] if m["is_current"]) or patient.current_medications
    db.commit()
    return load_history(db, patient)


BASELINE_KEYS = ("pulse", "bp_systolic", "sugar_fasting", "sugar_post_meal", "hba1c", "hemoglobin", "creatinine")


def has_baseline(baseline: dict | None) -> bool:
    baseline = baseline or {}
    return any(baseline.get(k) is not None for k in BASELINE_KEYS) or bool(baseline.get("others"))


def latest_labs(db: Session, patient: Patient, reviewed_only: bool, limit: int = 16) -> list[dict]:
    """The newest value of every test that appears in the patient's reports (from the reports themselves, never typed in).
    Values outside the printed range come first."""
    query = (select(HealthParameter, HealthReport).join(HealthReport, HealthParameter.report_id == HealthReport.id)
             .where(HealthReport.patient_id == patient.id))
    if reviewed_only:
        query = query.where(HealthReport.doctor_review_status == "REVIEWED")
    newest: dict[str, dict] = {}
    for param, report in db.execute(query):
        when = report.report_date or report.uploaded_at.date()
        key = param.normalized_name
        if key not in newest or when > newest[key]["date"]:
            newest[key] = {"name": key, "value": param.value, "unit": param.unit, "status": param.status, "range": param.reference_text,
                           "date": when, "report_id": report.id}
    rows = sorted(newest.values(), key=lambda r: (r["status"] not in ("ABOVE_RANGE", "BELOW_RANGE"), r["name"]))
    return [{**r, "date": r["date"].isoformat()} for r in rows[:limit]]


def completeness(history: dict) -> dict:
    """Which parts of the form are filled in. A part counts when it has entries OR the patient said 'none'."""
    habits = history.get("habits") or {}
    parts = [
        ("Height and weight", bool(history.get("height_cm") and history.get("weight_kg"))),
        ("Medicines", bool(history["medications"]) or history["no_regular_medicines"]),
        ("Allergies", bool(history["allergies"]) or history["no_known_allergies"]),
        ("Illnesses", bool(history["conditions"]) or history["no_known_conditions"]),
        ("Past operations", bool(history["surgeries"]) or history["no_past_surgery"]),
        ("Family history", bool(history["family"]) or history["no_family_history"]),
        ("Habits", bool(habits.get("tobacco") or habits.get("alcohol"))),
        ("Usual values", has_baseline(history.get("baseline"))),
    ]
    done = sum(1 for _, ok in parts if ok)
    return {"percent": round(100 * done / len(parts)), "parts": [{"name": n, "done": ok} for n, ok in parts]}


def emergency_card(db: Session, patient: Patient, history: dict | None = None) -> dict:
    """The facts a doctor at any hospital needs first: who, allergies, medicines, illnesses, operations, contact."""
    history = history or load_history(db, patient)
    habits = history.get("habits") or {}
    bmi = None
    if history.get("height_cm") and history.get("weight_kg"):
        bmi = round(history["weight_kg"] / ((history["height_cm"] / 100) ** 2), 1)
    return {
        "name": patient.user.full_name, "patient_code": patient.patient_code, "age": age_of(patient), "gender": patient.gender,
        "blood_group": patient.blood_group, "phone": patient.phone, "emergency_contact": patient.emergency_contact,
        "allergies": history["allergies"], "no_known_allergies": history["no_known_allergies"],
        "medicines": [m for m in history["medications"] if m["is_current"]], "no_regular_medicines": history["no_regular_medicines"],
        "conditions": history["conditions"], "no_known_conditions": history["no_known_conditions"],
        "surgeries": history["surgeries"], "habits": habits, "height_cm": history.get("height_cm"),
        "weight_kg": history.get("weight_kg"), "bmi": bmi, "usual_values": history.get("baseline") or {},
        "latest_labs": latest_labs(db, patient, reviewed_only=True, limit=8), "updated_at": history.get("updated_at"),
        "updated_by_name": history.get("updated_by_name"),
    }


# ------------------------------------------------------------------ doctor's assessment
def _assessment_out(a: ClinicalAssessment) -> dict:
    return {"id": a.id, "doctor_name": a.doctor.user.full_name, "created_at": a.created_at.isoformat(),
            "chief_complaint": a.chief_complaint, "history_of_present_illness": a.history_of_present_illness,
            "vitals": json.loads(a.vitals_json) if a.vitals_json else {},
            "examination": json.loads(a.examination_json) if a.examination_json else {},
            "provisional_diagnosis": a.provisional_diagnosis, "investigations_advised": a.investigations_advised,
            "plan_type": a.plan_type, "plan_details": a.plan_details, "special_note": a.special_note}


def add_assessment(db: Session, patient: Patient, doctor, data: AssessmentIn) -> dict:
    row = ClinicalAssessment(
        patient_id=patient.id, doctor_id=doctor.id, chief_complaint=data.chief_complaint,
        history_of_present_illness=data.history_of_present_illness, vitals_json=json.dumps(data.vitals.model_dump()),
        examination_json=json.dumps(data.examination.model_dump()), provisional_diagnosis=data.provisional_diagnosis,
        investigations_advised=data.investigations_advised, plan_type=data.plan_type, plan_details=data.plan_details,
        special_note=data.special_note)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _assessment_out(row)


def list_assessments(db: Session, patient: Patient) -> list[dict]:
    rows = db.scalars(select(ClinicalAssessment).where(ClinicalAssessment.patient_id == patient.id)
                      .order_by(ClinicalAssessment.id.desc())).all()
    return [_assessment_out(r) for r in rows]


def appointment_problem(db: Session, patient: Patient) -> dict | None:
    """What the patient wrote when booking the nearest open appointment: the doctor can start from it."""
    today = datetime.combine(date.today(), time.min)                 # an appointment that has already passed is not "the next one"
    rows = db.scalars(select(Appointment).where(Appointment.patient_id == patient.id, Appointment.status.in_(["SCHEDULED", "CONFIRMED"]),
                                                Appointment.scheduled_at >= today).order_by(Appointment.scheduled_at)).all()
    for a in rows:
        if a.reason or a.symptoms_json or a.details:
            return {"appointment_id": a.id, "scheduled_at": a.scheduled_at.isoformat(), "reason": a.reason, "duration": a.duration,
                    "symptoms": json.loads(a.symptoms_json) if a.symptoms_json else [], "details": a.details}
    return None


def doctor_view(db: Session, patient: Patient) -> dict:
    """Everything the doctor sees: the form, the emergency card, the 'points to check' and earlier assessments."""
    history = load_history(db, patient)
    assessments = list_assessments(db, patient)
    latest_vitals = assessments[0]["vitals"] if assessments else None
    points = points_to_check(history, age_of(patient), latest_vitals)
    return {"history": history, "completeness": completeness(history), "card": emergency_card(db, patient, history),
            "points_to_check": points, "suggested_tests": suggested_tests(points), "assessments": assessments,
            "latest_labs": latest_labs(db, patient, reviewed_only=False), "appointment_problem": appointment_problem(db, patient)}
