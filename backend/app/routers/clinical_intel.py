"""Patient Clinical Intelligence & History Analyzer: the doctor's evidence-linked view of one patient.

Doctors only, and only for patients they are authorised for. Pharmacy, employees, administrators and patients get no access.
Opening the summary or an emergency record is written to the audit log. Nothing here changes an original record: a doctor's
corrections and interpretations are stored separately, with the doctor's name and the time."""
import json
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, get_accessible_patient, get_doctor_profile, require_roles
from app.database.connection import get_db
from app.database.models import ClinicalSummarySnapshot, EmergencyEvent, FollowUpTask, SummaryReview, User, utcnow
from app.schemas.clinical_intel import EmergencyIn, FollowUpIn, FollowUpUpdate, ReviewIn
from app.services import (
    ai_summary, audit_service, clinical_summary, clinical_timeline, emergency_review, follow_ups, medication_history, report_trends,
)

router = APIRouter(prefix="/api/doctor", tags=["clinical intelligence"])
doctor_only = require_roles(DOCTOR)


def _patient(db: Session, user: User, patient_id: int):
    return get_accessible_patient(db, user, patient_id, clinical=True)


# ------------------------------------------------------------------ the summary
@router.get("/patients/{patient_id}/clinical-summary")
def clinical_summary_view(patient_id: int, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    patient = _patient(db, user, patient_id)
    result = clinical_summary.build(db, patient)
    audit_service.log_action(db, user, audit_service.CLINICAL_SUMMARY_VIEWED, "patient", patient.id, request)
    last_ai = db.scalar(select(ClinicalSummarySnapshot).where(ClinicalSummarySnapshot.patient_id == patient.id).order_by(ClinicalSummarySnapshot.id.desc()))
    return {**result, "ai_available": ai_summary.available(),
            "ai_summary": ({**json.loads(last_ai.content_json), "generated_at": last_ai.created_at.isoformat(), "generated_by": last_ai.doctor.user.full_name} if last_ai else None)}


@router.post("/patients/{patient_id}/clinical-summary/generate")
def generate_ai_narrative(patient_id: int, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    """Ask the optional AI model to write a short narrative from the verified statements. Never required."""
    patient = _patient(db, user, patient_id)
    if not ai_summary.available():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No AI model is connected. The evidence-linked summary on this page was made by the system's own rules and does not need one.")
    narrative = ai_summary.generate(clinical_summary.build(db, patient))
    if narrative is None:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The AI model did not return a usable answer. The rule-based summary above is unchanged.")
    doctor = get_doctor_profile(db, user)
    row = ClinicalSummarySnapshot(patient_id=patient.id, generated_by=doctor.id, kind="AI", model=narrative["model"], content_json=json.dumps(narrative))
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, audit_service.CLINICAL_SUMMARY_AI, "patient", patient.id, request)
    return {**narrative, "generated_at": row.created_at.isoformat(), "generated_by": user.full_name}


@router.post("/patients/{patient_id}/clinical-summary/review", status_code=status.HTTP_201_CREATED)
def review_item(patient_id: int, data: ReviewIn, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    """A doctor marks an item reviewed, or adds an interpretation, a correction of an extraction error, or a missing-information flag.
    It is stored next to the item. The original record and the computer's statement are not changed."""
    patient = _patient(db, user, patient_id)
    row = SummaryReview(patient_id=patient.id, doctor_id=get_doctor_profile(db, user).id, item_key=data.item_key, action=data.action, text=data.text.strip() if data.text else None)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit_service.log_action(db, user, audit_service.SUMMARY_REVIEWED, "patient", patient.id, request, f"{data.action} {data.item_key}")
    return {"id": row.id, "item_key": row.item_key, "action": row.action, "text": row.text, "doctor": user.full_name, "at": row.created_at.isoformat()}


# ------------------------------------------------------------------ the parts
@router.get("/patients/{patient_id}/timeline")
def timeline(patient_id: int, q: str | None = None, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    return {"events": clinical_timeline.build(db, _patient(db, user, patient_id), q)}


@router.get("/patients/{patient_id}/report-trends")
def trends(patient_id: int, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    return report_trends.analyse(db, _patient(db, user, patient_id))


@router.get("/patients/{patient_id}/medication-history")
def medications(patient_id: int, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    return medication_history.build(db, _patient(db, user, patient_id))


@router.get("/patients/{patient_id}/follow-ups")
def follow_up_list(patient_id: int, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    return follow_ups.build(db, _patient(db, user, patient_id))


@router.post("/patients/{patient_id}/follow-ups", status_code=status.HTTP_201_CREATED)
def create_follow_up(patient_id: int, data: FollowUpIn, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    patient = _patient(db, user, patient_id)
    task = FollowUpTask(patient_id=patient.id, created_by=get_doctor_profile(db, user).id, title=data.title.strip(), details=data.details, due_date=data.due_date,
                        source_type=data.source_type, source_id=data.source_id)
    db.add(task)
    db.commit()
    audit_service.log_action(db, user, audit_service.FOLLOW_UP_CREATED, "patient", patient.id, request, data.title[:80])
    return follow_ups.build(db, patient)


@router.patch("/patients/{patient_id}/follow-ups/{task_id}")
def update_follow_up(patient_id: int, task_id: int, data: FollowUpUpdate, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    patient = _patient(db, user, patient_id)
    task = db.get(FollowUpTask, task_id)
    if task is None or task.patient_id != patient.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Follow-up task not found.")
    task.status = data.status
    task.outcome = data.outcome
    task.completed_at = utcnow() if data.status == "DONE" else None
    db.commit()
    audit_service.log_action(db, user, audit_service.FOLLOW_UP_UPDATED, "patient", patient.id, request, f"{data.status}: {task.title[:60]}")
    return follow_ups.build(db, patient)


# ------------------------------------------------------------------ emergency events
@router.get("/patients/{patient_id}/emergency-history")
def emergency_history(patient_id: int, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    return emergency_review.list_events(db, _patient(db, user, patient_id))


@router.post("/patients/{patient_id}/emergency-events", status_code=status.HTTP_201_CREATED)
def record_emergency(patient_id: int, data: EmergencyIn, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    patient = _patient(db, user, patient_id)
    event = emergency_review.create(db, patient, get_doctor_profile(db, user), data)
    audit_service.log_action(db, user, audit_service.EMERGENCY_RECORDED, "patient", patient.id, request)
    return emergency_review.review(db, patient, event)


@router.get("/emergency-events/{event_id}")
def emergency_event(event_id: int, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    event = db.get(EmergencyEvent, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency record not found.")
    patient = _patient(db, user, event.patient_id)                    # the same patient-access rule as everywhere else
    audit_service.log_action(db, user, audit_service.EMERGENCY_VIEWED, "patient", patient.id, request, f"event {event.id}")
    return emergency_review.review(db, patient, event)
