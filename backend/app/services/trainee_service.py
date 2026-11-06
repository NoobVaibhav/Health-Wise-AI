"""Junior doctors (interns and residents): which patients they may work on, the history drafts, the doctor suggestion and the referral."""
import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.permissions import forbidden
from app.database.models import (
    Appointment, Department, Doctor, Patient, Referral, TraineeHistory, TraineeHistoryRevision, User,
)
from app.schemas.trainee import TraineeHistoryData
from app.services import referral_rules
from app.services.health_history_service import age_of
from app.utils.clock import hospital_today

OPEN_APPOINTMENT = ("SCHEDULED", "CONFIRMED")
STATUS_LABEL = {"SENT": "Sent", "SEEN": "Seen by doctor", "COMPLETED": "Completed"}


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def type_label(trainee: Doctor) -> str:
    return {"INTERN": "Intern", "PG_RESIDENT": "PG Resident", "SENIOR_RESIDENT": "Senior Resident"}.get(trainee.current_grade, "Consultant")


# ------------------------------------------------------------------ who the trainee may work on
def scope_query(trainee: Doctor):
    """Patients of the trainee's department (their doctor works in it), patients with no doctor yet (just registered by reception), and anybody the
    trainee already started a history for."""
    own = Patient.id.in_(select(TraineeHistory.patient_id).where(TraineeHistory.trainee_id == trainee.id))
    conditions = [Patient.assigned_doctor_id.is_(None), own]
    if trainee.department_id:
        conditions.append(Patient.assigned_doctor_id.in_(select(Doctor.id).where(Doctor.department_id == trainee.department_id)))
    return select(Patient).where(or_(*conditions))


def patient_in_scope(db: Session, trainee: Doctor, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found.")
    if db.scalar(scope_query(trainee).where(Patient.id == patient.id)) is None:
        raise forbidden()
    return patient


def basic_patient(patient: Patient) -> dict:
    """Only what is needed to take a history. No address, no medicines, no reports, no allergies from the record."""
    return {"id": patient.id, "patient_code": patient.patient_code, "full_name": patient.user.full_name, "age": age_of(patient),
            "gender": patient.gender, "phone": patient.phone}


# ------------------------------------------------------------------ histories
def history_out(h: TraineeHistory) -> dict:
    return {
        "id": h.id, "patient_id": h.patient_id, "patient_name": h.patient.user.full_name, "patient_code": h.patient.patient_code,
        "trainee_id": h.trainee_id, "trainee_name": h.trainee.user.full_name, "trainee_type": h.trainee.current_grade, "grade": h.trainee.current_grade, "status": h.status,
        "data": json.loads(h.data_json) if h.data_json else TraineeHistoryData().model_dump(),
        "doctor_notes": h.doctor_notes, "created_at": h.created_at.isoformat(), "updated_at": h.updated_at.isoformat(),
        "completed_at": h.completed_at.isoformat() if h.completed_at else None,
        "verified_by": h.verifier.user.full_name if h.verifier else None, "verified_at": h.verified_at.isoformat() if h.verified_at else None,
        "taken_by": f"{h.trainee.user.full_name} ({type_label(h.trainee)})", "pending_review": h.status == "COMPLETE",
    }


def own_history(db: Session, trainee: Doctor, history_id: int) -> TraineeHistory:
    """A history of this trainee only; somebody else's gives the same 404 as one that does not exist (no way to probe ids)."""
    h = db.get(TraineeHistory, history_id)
    if h is None or h.trainee_id != trainee.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "History not found.")
    return h


def start_history(db: Session, trainee: Doctor, patient: Patient) -> tuple[TraineeHistory, bool]:
    """The open draft of this trainee for this patient (a second tap continues it), else a new one."""
    existing = db.scalar(select(TraineeHistory).where(TraineeHistory.trainee_id == trainee.id, TraineeHistory.patient_id == patient.id,
                                                      TraineeHistory.status == "DRAFT").order_by(TraineeHistory.id.desc()))
    if existing:
        return existing, False
    h = TraineeHistory(patient_id=patient.id, trainee_id=trainee.id, status="DRAFT", data_json=TraineeHistoryData().model_dump_json())
    db.add(h)
    db.commit()
    db.refresh(h)
    return h, True


def missing_for_complete(data: TraineeHistoryData) -> list[str]:
    missing = []
    if not data.chief_complaint:
        missing.append("the main complaint")
    if not data.duration:
        missing.append("how long it has been going on")
    if data.allergies is None:
        missing.append("the allergy answer (choose None if there are no allergies)")
    elif data.allergies == "YES" and not data.allergy_details:
        missing.append("what the patient is allergic to")
    return missing


def save_history(db: Session, h: TraineeHistory, data: TraineeHistoryData, user: User) -> TraineeHistory:
    if h.status == "VERIFIED":
        raise HTTPException(status.HTTP_409_CONFLICT, "A doctor has already verified this history, so it can no longer be changed.")
    if h.status == "COMPLETE":                                       # keep what was there before
        db.add(TraineeHistoryRevision(history_id=h.id, changed_by=user.id, data_json=h.data_json))
    h.data_json = data.model_dump_json()
    h.updated_at = now()
    db.commit()
    db.refresh(h)
    return h


def complete_history(db: Session, h: TraineeHistory) -> TraineeHistory:
    if h.status == "VERIFIED":
        raise HTTPException(status.HTTP_409_CONFLICT, "A doctor has already verified this history.")
    data = TraineeHistoryData(**json.loads(h.data_json or "{}"))
    missing = missing_for_complete(data)
    if missing:
        raise HTTPException(422, "Before completing the history, please fill in " + "; ".join(missing) + ".")
    h.status = "COMPLETE"
    h.completed_at = h.completed_at or now()
    h.updated_at = now()
    db.commit()
    db.refresh(h)
    return h


# ------------------------------------------------------------------ suggestion and referral
def _day_range() -> tuple[datetime, datetime]:
    start = datetime.combine(hospital_today(), datetime.min.time())
    return start, start + timedelta(days=1)


def doctor_card(db: Session, doctor: Doctor) -> dict:
    start, end = _day_range()
    today = db.scalar(select(func.count(Appointment.id)).where(Appointment.doctor_id == doctor.id, Appointment.scheduled_at >= start,
                                                                Appointment.scheduled_at < end, Appointment.status != "CANCELLED")) or 0
    waiting = db.scalar(select(func.count(Referral.id)).where(Referral.doctor_id == doctor.id, Referral.status == "SENT")) or 0
    return {"id": doctor.id, "full_name": doctor.user.full_name, "department_id": doctor.department_id,
            "department_name": doctor.department.name if doctor.department else None, "specialization_name": doctor.specialization_name,
            "today_appointments": today, "waiting_referrals": waiting, "availability": "Busy today" if today + waiting >= 12 else "Available"}


def doctors_of_department(db: Session, department_id: int) -> list[dict]:
    rows = db.scalars(select(Doctor).join(User, Doctor.user_id == User.id).where(Doctor.department_id == department_id, User.is_active.is_(True),
                                                                              or_(Doctor.grade == "CONSULTANT", Doctor.grade.is_(None))).order_by(User.full_name)).all()
    return [doctor_card(db, d) for d in rows]          # patients are referred to consultants


def suggestion(db: Session, h: TraineeHistory) -> dict:
    data = json.loads(h.data_json or "{}")
    rule = referral_rules.suggest_department(data.get("chief_complaint"), data.get("symptoms"), age_of(h.patient), h.patient.gender)
    department = db.scalar(select(Department).where(func.lower(Department.name) == rule["department"].lower(), Department.is_active.is_not(False)))
    if department is None:                                           # the hospital switched that department off: use General Medicine
        department = db.scalar(select(Department).where(func.lower(Department.name) == "general medicine"))
    doctors = doctors_of_department(db, department.id) if department else []
    if rule["specialization"]:
        doctors.sort(key=lambda d: rule["specialization"].lower() not in (d["specialization_name"] or "").lower())
    return {"department_id": department.id if department else None, "department_name": department.name if department else rule["department"],
            "specialization": rule["specialization"], "reason": rule["reason"], "matched": rule["matched"], "doctors": doctors}


def create_referral(db: Session, trainee: Doctor, h: TraineeHistory, doctor: Doctor, reason: str, urgent: bool, suggested_department_id: int | None,
                    book_at: datetime | None, user: User) -> Referral:
    if h.status not in ("COMPLETE", "VERIFIED"):
        raise HTTPException(409, "Please complete the history before choosing a doctor.")
    if not doctor.user.is_active:
        raise HTTPException(422, "The selected doctor is not available.")
    if db.scalar(select(Referral.id).where(Referral.history_id == h.id, Referral.status != "COMPLETED")):
        raise HTTPException(status.HTTP_409_CONFLICT, "This history has already been sent to a doctor.")
    patient = h.patient
    appointment = None
    if book_at is not None:
        from app.services import appointment_rules
        from app.utils.clock import to_hospital_time
        book_at = to_hospital_time(book_at)
        appointment_rules.check_bookable(book_at)                      # the same rules as every other booking
        appointment_rules.check_patient_free(db, patient.id, book_at)
        if db.scalar(select(Appointment.id).where(Appointment.doctor_id == doctor.id, Appointment.scheduled_at == book_at,
                                                  Appointment.status.in_(OPEN_APPOINTMENT))):
            raise HTTPException(status.HTTP_409_CONFLICT, "This doctor already has an appointment at that time.")
        appointment = Appointment(patient_id=patient.id, doctor_id=doctor.id, department_id=doctor.department_id, scheduled_at=book_at,
                                  reason=reason[:300], status="SCHEDULED", created_by=user.id)
        db.add(appointment)
        db.flush()
    if patient.assigned_doctor_id is None:
        patient.assigned_doctor_id = doctor.id
    referral = Referral(patient_id=patient.id, trainee_id=trainee.id, doctor_id=doctor.id, history_id=h.id, reason=reason, urgent=urgent, status="SENT",
                        suggested_department_id=suggested_department_id,
                        overridden=suggested_department_id is not None and suggested_department_id != doctor.department_id,
                        appointment_id=appointment.id if appointment else None)
    db.add(referral)
    db.flush()
    from app.services import encounter_service as enc
    from app.database.models import Encounter
    visit = db.scalar(select(Encounter).where(Encounter.patient_id == patient.id, Encounter.attending_doctor_id == doctor.id, Encounter.type == "OPD", Encounter.status == "OPEN"))
    if visit is None:                                      # the referred patient is now in the doctor's OPD queue (an urgent referral first)
        visit = enc.open_encounter(db, patient, "OPD", doctor=doctor, department_id=doctor.department_id, source="TRAINEE_REFERRAL", user=user, appointment=appointment)
        enc.issue_token(db, visit, doctor, urgent)
    referral.encounter_id = visit.id
    db.commit()
    db.refresh(referral)
    return referral


def referral_out(r: Referral) -> dict:
    return {
        "id": r.id, "patient_id": r.patient_id, "patient_name": r.patient.user.full_name, "patient_code": r.patient.patient_code,
        "trainee_name": r.trainee.user.full_name, "trainee_type": r.trainee.current_grade, "grade": r.trainee.current_grade, "doctor_id": r.doctor_id, "doctor_name": r.doctor.user.full_name,
        "history_id": r.history_id, "reason": r.reason, "urgent": r.urgent, "status": r.status, "status_label": STATUS_LABEL[r.status],
        "overridden": r.overridden, "appointment_id": r.appointment_id, "created_at": r.created_at.isoformat(),
        "seen_at": r.seen_at.isoformat() if r.seen_at else None, "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "supervisor_reviewed_at": r.supervisor_reviewed_at.isoformat() if r.supervisor_reviewed_at else None, "supervisor_note": r.supervisor_note,
        "history_status": r.history.status, "taken_by": f"{r.trainee.user.full_name} ({type_label(r.trainee)})",
    }


def trainee_dashboard(db: Session, trainee: Doctor) -> dict:
    start, _ = _day_range()
    seen_today = select(TraineeHistory.patient_id).where(TraineeHistory.trainee_id == trainee.id, TraineeHistory.created_at >= start)
    waiting = db.scalars(scope_query(trainee).where(~Patient.id.in_(seen_today)).order_by(Patient.id.desc()).limit(10)).all()
    taken_today = db.scalar(select(func.count(TraineeHistory.id)).where(TraineeHistory.trainee_id == trainee.id, TraineeHistory.status != "DRAFT",
                                                                      TraineeHistory.completed_at >= start)) or 0
    drafts = db.scalars(select(TraineeHistory).where(TraineeHistory.trainee_id == trainee.id, TraineeHistory.status == "DRAFT")
                        .order_by(TraineeHistory.updated_at.desc()).limit(10)).all()
    referrals_today = db.scalar(select(func.count(Referral.id)).where(Referral.trainee_id == trainee.id, Referral.created_at >= start)) or 0
    recent = db.scalars(select(Referral).where(Referral.trainee_id == trainee.id).order_by(Referral.id.desc()).limit(5)).all()
    return {"waiting_patients": [basic_patient(p) for p in waiting], "waiting_count": len(waiting), "histories_today": taken_today, "referrals_today": referrals_today,
            "drafts": [history_out(d) for d in drafts], "recent_referrals": [referral_out(r) for r in recent],
            "trainee": {"type": trainee.current_grade, "grade": trainee.current_grade, "pg_year": trainee.pg_year, "department_id": trainee.department_id, "department_name": trainee.department.name if trainee.department else None,
                        "year_branch": trainee.pg_branch, "supervisor": trainee.supervisor_name}}
