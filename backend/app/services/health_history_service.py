"""The health-history form: load it, save it, tell how complete it is, and build the one-page emergency card.
Employees and administrators never reach this (the router only lets the patient and authorised doctors in)."""
import json
import re
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Appointment, ClinicalAssessment, DoctorNote, DoctorRecommendation, HealthParameter, HealthReport, Patient, PatientHistory, PatientMedication, Prescription, User, utcnow,
)
from app.schemas.health_history import AssessmentIn, HistoryIn
from app.services import past_history_service as past
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
    history["conditions"] = past.legacy_conditions(db, patient)       # illnesses and operations live in their own records now
    history["surgeries"] = past.legacy_surgeries(db, patient)
    history.update({key: bool(stored.get(key, False)) for key in FLAG_KEYS})
    history.update({key: stored.get(key) for key in TEXT_KEYS})
    history["habits"] = stored.get("habits", {})
    history["baseline"] = stored.get("baseline", {})
    history["current_problem"] = stored.get("current_problem", {"complaint": None, "duration": None, "symptoms": [], "denies": [], "details": None})
    history["height_cm"] = row.height_cm if row else None
    history["weight_kg"] = row.weight_kg if row else None
    history["medications"] = [past.medication_dict(db, m) for m in past.active_medications(db, patient)]
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
    stored = json.loads(row.data_json) if row.data_json else {}
    row.height_cm, row.weight_kg = payload["height_cm"], payload["weight_kg"]
    kept = {k: payload[k] for k in (*FLAG_KEYS, *TEXT_KEYS, "family", "allergies", "habits", "baseline", "current_problem")}
    for old_key in ("conditions", "surgeries"):                       # the earlier lists stay exactly as they were (they are now managed as records)
        if old_key in stored:
            kept[old_key] = stored[old_key]
    row.data_json = json.dumps(kept)
    row.updated_by, row.updated_at = user.id, utcnow()
    # illnesses, operations and medicines are matched to the existing records: changed, added or hidden (never deleted), with a change log
    past.sync_conditions(db, patient, payload["conditions"], payload["no_known_conditions"], user)
    past.sync_surgeries(db, patient, payload["surgeries"], payload["no_past_surgery"], user)
    past.sync_medications(db, patient, payload["medications"], payload["no_regular_medicines"], user)
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


DIABETES_LAB = re.compile(r"glucose|hba1c|sugar", re.IGNORECASE)


def _same_amount(a: str | None, b: str | None) -> bool:
    norm = lambda x: re.sub(r"[^a-z0-9.]", "", (x or "").lower())
    return norm(a) == norm(b)


def reconciliation(db: Session, patient: Patient, history: dict) -> dict:
    """Medicines in the history (what the patient says they take) against the open prescriptions of this hospital. Differences are
    listed for the doctor to confirm with the patient. Nothing is merged or assumed."""
    from app.services import medication_history                          # imported here: that module itself reads this one
    meds = medication_history.build(db, patient)
    prescribed = {}
    for m in meds["medicines"]:
        if m["status"] == "OPEN":
            last = m["entries"][-1]
            prescribed[medication_history.base_name(m["name"])] = {"name": m["name"], "dose": last["dose"], "frequency": last["frequency"], "prescribed_on": last["prescribed_on"],
                                                                  "doctor": last["doctor"], "code": last["prescription_code"]}
    rows, seen = [], set()
    for h in history["medications"]:
        if not h["is_current"]:
            continue
        key = medication_history.base_name(h["name"])
        seen.add(key)
        rx = prescribed.get(key)
        if rx is None:
            rows.append({"name": h["name"], "history": h, "prescribed": None, "verdict": "IN_HISTORY_ONLY",
                         "note": "In the history but not on an open prescription here. Confirm that the patient still takes it."})
        elif h.get("dose") and rx["dose"] and not _same_amount(h["dose"], rx["dose"]):
            rows.append({"name": h["name"], "history": h, "prescribed": rx, "verdict": "DOSE_DIFFERS",
                         "note": f"The history says {h['dose']}, the prescription says {rx['dose']}. Confirm with the patient which one is taken."})
        else:
            rows.append({"name": h["name"], "history": h, "prescribed": rx, "verdict": "MATCHES", "note": "Same medicine in the history and on an open prescription."})
    for key, rx in prescribed.items():
        if key not in seen:
            rows.append({"name": rx["name"], "history": None, "prescribed": rx, "verdict": "PRESCRIBED_ONLY",
                         "note": "On an open prescription but not in the history. Confirm that it is being taken and add it to the history."})
    return {"rows": rows, "allergy_flags": meds["allergy_flags"], "duplicates": meds["duplicates"],
            "needs_attention": sum(1 for r in rows if r["verdict"] != "MATCHES") + len(meds["allergy_flags"])}


def follow_up_block(db: Session, patient: Patient) -> dict:
    """What happens next, from the hospital's own records: advice with dates, upcoming appointments, recent doctor's notes, open prescriptions."""
    recs = db.scalars(select(DoctorRecommendation).where(DoctorRecommendation.patient_id == patient.id).order_by(DoctorRecommendation.id.desc()).limit(5)).all()
    notes = db.scalars(select(DoctorNote).where(DoctorNote.patient_id == patient.id).order_by(DoctorNote.id.desc()).limit(3)).all()
    appts = db.scalars(select(Appointment).where(Appointment.patient_id == patient.id, Appointment.status.in_(["SCHEDULED", "CONFIRMED"]),
                                                 Appointment.scheduled_at >= datetime.now()).order_by(Appointment.scheduled_at).limit(3)).all()
    rxs = db.scalars(select(Prescription).where(Prescription.patient_id == patient.id, Prescription.status.in_(["ACTIVE", "PARTIALLY_DISPENSED"])).order_by(Prescription.id.desc()).limit(3)).all()
    return {
        "recommendations": [{"title": r.title, "text": r.recommendation, "follow_up_date": r.follow_up_date.isoformat() if r.follow_up_date else None,
                             "created_at": r.created_at.isoformat(), "doctor": r.doctor.user.full_name} for r in recs],
        "notes": [{"text": n.note, "priority": n.priority, "created_at": n.created_at.isoformat(), "doctor": n.doctor.user.full_name} for n in notes],
        "appointments": [{"scheduled_at": a.scheduled_at.isoformat(), "doctor": a.doctor.user.full_name, "reason": a.reason} for a in appts],
        "prescriptions": [{"code": f"RX-{x.id:05d}", "date": x.prescription_date.isoformat(), "doctor": x.doctor.user.full_name, "indication": x.clinical_indication,
                           "items": [{"name": i.medicine_name, "dose": i.dosage, "frequency": i.frequency, "duration": i.duration, "instructions": i.instructions} for i in x.items],
                           "tests": [t.strip() for t in (x.tests_advised or "").splitlines() if t.strip()]} for x in rxs],
    }


def doctor_view(db: Session, patient: Patient) -> dict:
    """Everything the doctor sees: the form, the emergency card, the 'points to check' and earlier assessments."""
    history = load_history(db, patient)
    assessments = list_assessments(db, patient)
    latest_vitals = assessments[0]["vitals"] if assessments else None
    points = points_to_check(history, age_of(patient), latest_vitals)
    labs = latest_labs(db, patient, reviewed_only=False)
    return {"history": history, "completeness": completeness(history), "card": emergency_card(db, patient, history),
            "points_to_check": points, "suggested_tests": suggested_tests(points), "assessments": assessments,
            "latest_labs": labs, "appointment_problem": appointment_problem(db, patient),
            "past": past.detailed(db, patient), "reconciliation": reconciliation(db, patient, history), "follow_up": follow_up_block(db, patient),
            "diabetes_labs": [l for l in latest_labs(db, patient, reviewed_only=False, limit=200) if DIABETES_LAB.search(l["name"])]}
