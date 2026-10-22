"""Health-history form. The patient fills in and keeps their own history; the doctors who are authorised for the patient
can read it (and add to it) so that a doctor who has never met the patient knows the medicines, allergies and illnesses.
Employees and administrators have no access."""
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, PATIENT, get_accessible_patient, get_current_user, get_doctor_profile, get_patient_profile, require_roles
from app.database.connection import get_db
from app.database.models import User
from pydantic import BaseModel

from app.schemas.health_history import AssessmentIn, HistoryIn, Vitals
from app.services import audit_service, health_history_service as service
from app.services.history_insights import points_to_check, suggested_tests

router = APIRouter(prefix="/api/health-history", tags=["health history"])


def _patient_view(db: Session, patient) -> dict:
    history = service.load_history(db, patient)
    return {"history": history, "completeness": service.completeness(history), "card": service.emergency_card(db, patient, history)}


@router.get("/me")
def my_history(user: User = Depends(require_roles(PATIENT)), db: Session = Depends(get_db)):
    return _patient_view(db, get_patient_profile(db, user))


@router.put("/me")
def save_my_history(data: HistoryIn, request: Request, user: User = Depends(require_roles(PATIENT)), db: Session = Depends(get_db)):
    patient = get_patient_profile(db, user)
    service.save_history(db, patient, data, user)
    audit_service.log_action(db, user, audit_service.HISTORY_UPDATED, "patient", patient.id, request)
    return _patient_view(db, patient)


class PreviewIn(BaseModel):
    history: HistoryIn
    vitals: Vitals = Vitals()


@router.post("/patient/{patient_id}/preview")
def preview_points(patient_id: int, data: PreviewIn, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    """The points to check for a history that is still being typed. Nothing is saved."""
    patient = get_accessible_patient(db, user, patient_id, clinical=True)
    history = {**data.history.model_dump(), "medications": [m.model_dump() for m in data.history.medications]}
    points = points_to_check(history, service.age_of(patient), data.vitals.model_dump())
    return {"points_to_check": points, "suggested_tests": suggested_tests(points)}


@router.get("/patient/{patient_id}")
def patient_history(patient_id: int, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient = get_accessible_patient(db, user, patient_id, clinical=True)
    audit_service.log_action(db, user, audit_service.HISTORY_VIEWED, "patient", patient.id, request)
    return service.doctor_view(db, patient)


@router.put("/patient/{patient_id}")
def save_patient_history(patient_id: int, data: HistoryIn, request: Request, user: User = Depends(require_roles(DOCTOR)),
                         db: Session = Depends(get_db)):
    patient = get_accessible_patient(db, user, patient_id, clinical=True)
    service.save_history(db, patient, data, user)
    audit_service.log_action(db, user, audit_service.HISTORY_UPDATED, "patient", patient.id, request, "by doctor")
    return service.doctor_view(db, patient)


@router.post("/patient/{patient_id}/assessments", status_code=status.HTTP_201_CREATED)
def add_assessment(patient_id: int, data: AssessmentIn, request: Request, user: User = Depends(require_roles(DOCTOR)),
                   db: Session = Depends(get_db)):
    patient = get_accessible_patient(db, user, patient_id, clinical=True)
    result = service.add_assessment(db, patient, get_doctor_profile(db, user), data)
    audit_service.log_action(db, user, audit_service.ASSESSMENT_ADDED, "patient", patient.id, request)
    return result
