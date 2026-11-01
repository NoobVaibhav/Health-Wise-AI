"""Phase 8: integrations. The status list (honest), the notification outbox and reminders, and the FHIR-shaped export."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, PATIENT, get_accessible_patient, get_patient_profile, require_roles
from app.database.connection import get_db
from app.database.models import NotificationOutbox, User
from app.services import audit_service, integration_service
from app.services.access_service import require_permission
from app.utils.validators import PathId

router = APIRouter(prefix="/api/integrations", tags=["integrations"])
manage = require_permission("integration.manage")


class RemindersIn(BaseModel):
    hours_ahead: int = Field(default=24, ge=1, le=168)


@router.get("/status")
def status(user: User = Depends(manage), db: Session = Depends(get_db)):
    return integration_service.status_list(db)


@router.get("/outbox")
def outbox(status_filter: str | None = None, user: User = Depends(manage), db: Session = Depends(get_db)):
    query = select(NotificationOutbox).order_by(NotificationOutbox.id.desc()).limit(200)
    if status_filter:
        query = query.where(NotificationOutbox.status == status_filter)
    return [{"id": r.id, "channel": r.channel, "address": r.address, "template": r.template_key, "subject": r.subject, "status": r.status, "attempts": r.attempts, "error": r.error,
             "created_at": r.created_at.isoformat(), "sent_at": r.sent_at.isoformat() if r.sent_at else None} for r in db.scalars(query)]


@router.post("/reminders/run")
def run_reminders(data: RemindersIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    made = integration_service.queue_appointment_reminders(db, data.hours_ahead)
    audit_service.log_action(db, user, "REMINDERS_QUEUED", "notification", None, request, f"{made['queued']} queued")
    return made


@router.post("/outbox/dispatch")
def dispatch(request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    result = integration_service.dispatch(db)
    audit_service.log_action(db, user, "OUTBOX_DISPATCHED", "notification", None, request, str(result))
    return result


@router.get("/fhir/patients/{patient_id}/bundle")
def fhir_for_doctor(patient_id: PathId, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    """The clinical export of a patient the doctor is authorised for."""
    patient = get_accessible_patient(db, user, patient_id, clinical=True)
    audit_service.log_action(db, user, "FHIR_EXPORT", "patient", patient.id, request, "doctor")
    return integration_service.fhir_bundle(db, patient, released_only=False)


@router.get("/fhir/my-bundle")
def fhir_mine(request: Request, user: User = Depends(require_roles(PATIENT)), db: Session = Depends(get_db)):
    """The patient's own copy: results and scans appear only after the doctor has seen them."""
    patient = get_patient_profile(db, user)
    audit_service.log_action(db, user, "FHIR_EXPORT", "patient", patient.id, request, "patient")
    return integration_service.fhir_bundle(db, patient, released_only=True)
