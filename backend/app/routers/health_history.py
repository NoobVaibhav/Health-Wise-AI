"""Health history. It is the patient's PERMANENT medical record, and only doctors write to it: the doctors who are authorised for
the patient can read and change it. The patient can read it and print the emergency card, but cannot change it.
Employees and administrators have no access."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, PATIENT, get_accessible_patient, get_current_user, get_doctor_profile, get_patient_profile, require_roles
from app.database.connection import get_db
from app.database.models import User
from pydantic import BaseModel

from app.schemas.health_history import AssessmentIn, HistoryIn, Vitals
from app.schemas.past_history import AdmissionIn, ConditionIn, PastMedicationIn, SurgeryIn
from app.services import audit_service, health_history_service as service, past_history_service as past
from app.services.history_insights import points_to_check, suggested_tests
from app.utils.validators import PathId

router = APIRouter(prefix="/api/health-history", tags=["health history"])


def _patient_view(db: Session, patient) -> dict:
    history = service.load_history(db, patient)
    return {"history": history, "completeness": service.completeness(history), "card": service.emergency_card(db, patient, history),
            "past": past.detailed(db, patient)}


@router.get("/me")
def my_history(user: User = Depends(require_roles(PATIENT)), db: Session = Depends(get_db)):
    return _patient_view(db, get_patient_profile(db, user))


@router.put("/me")
def patient_cannot_change_history(_: User = Depends(get_current_user)):
    """The permanent history is the doctors' record. A patient who wants something changed tells the doctor."""
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Only your doctor can change your medical history. Please tell your doctor what has changed.")


class PreviewIn(BaseModel):
    history: HistoryIn
    vitals: Vitals = Vitals()


@router.post("/patient/{patient_id}/preview")
def preview_points(patient_id: PathId, data: PreviewIn, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    """The points to check for a history that is still being typed. Nothing is saved."""
    patient = get_accessible_patient(db, user, patient_id, clinical=True)
    history = {**data.history.model_dump(), "medications": [m.model_dump() for m in data.history.medications]}
    points = points_to_check(history, service.age_of(patient), data.vitals.model_dump())
    return {"points_to_check": points, "suggested_tests": suggested_tests(points)}


@router.get("/patient/{patient_id}")
def patient_history(patient_id: PathId, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient = get_accessible_patient(db, user, patient_id, clinical=True)
    audit_service.log_action(db, user, audit_service.HISTORY_VIEWED, "patient", patient.id, request)
    return service.doctor_view(db, patient)


@router.put("/patient/{patient_id}")
def save_patient_history(patient_id: PathId, data: HistoryIn, request: Request, user: User = Depends(require_roles(DOCTOR)),
                         db: Session = Depends(get_db)):
    patient = get_accessible_patient(db, user, patient_id, clinical=True)
    service.save_history(db, patient, data, user)
    audit_service.log_action(db, user, audit_service.HISTORY_UPDATED, "patient", patient.id, request, "by doctor")
    return service.doctor_view(db, patient)


@router.post("/patient/{patient_id}/assessments", status_code=status.HTTP_201_CREATED)
def add_assessment(patient_id: PathId, data: AssessmentIn, request: Request, user: User = Depends(require_roles(DOCTOR)),
                   db: Session = Depends(get_db)):
    patient = get_accessible_patient(db, user, patient_id, clinical=True)
    result = service.add_assessment(db, patient, get_doctor_profile(db, user), data)
    audit_service.log_action(db, user, audit_service.ASSESSMENT_ADDED, "patient", patient.id, request)
    return result



# ------------------------------------------------------------------ detailed past history (illnesses, medicines, admissions, operations)
# Only doctors authorised for the patient write here. Every answer is the whole, updated detailed history.
def _doctor_patient(db: Session, user: User, patient_id: PathId):
    patient = get_accessible_patient(db, user, patient_id, clinical=True)
    return patient, get_doctor_profile(db, user)


def _done(db: Session, user: User, patient, request: Request, what: str) -> dict:
    audit_service.log_action(db, user, audit_service.HISTORY_UPDATED, "patient", patient.id, request, what)
    return {"past": past.detailed(db, patient)}


@router.get("/patient/{patient_id}/past")
def get_past(patient_id: PathId, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient = get_accessible_patient(db, user, patient_id, clinical=True)
    audit_service.log_action(db, user, audit_service.HISTORY_VIEWED, "patient", patient.id, request, "past history")
    return {"past": past.detailed(db, patient)}


@router.get("/patient/{patient_id}/revisions")
def get_revisions(patient_id: PathId, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    """The change log: who changed what and how it looked before. Nothing in it can be edited."""
    return {"revisions": past.revisions(db, get_accessible_patient(db, user, patient_id, clinical=True))}


@router.post("/patient/{patient_id}/conditions", status_code=status.HTTP_201_CREATED)
def add_condition(patient_id: PathId, data: ConditionIn, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient, doctor = _doctor_patient(db, user, patient_id)
    past.create_condition(db, patient, data, user, doctor)
    return _done(db, user, patient, request, "illness added")


@router.put("/patient/{patient_id}/conditions/{condition_id}")
def change_condition(patient_id: PathId, condition_id: PathId, data: ConditionIn, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient, doctor = _doctor_patient(db, user, patient_id)
    past.update_condition(db, patient, condition_id, data, user, doctor)
    return _done(db, user, patient, request, "illness changed")


@router.delete("/patient/{patient_id}/conditions/{condition_id}")
def remove_condition(patient_id: PathId, condition_id: PathId, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient, _ = _doctor_patient(db, user, patient_id)
    past.delete_condition(db, patient, condition_id, user)
    return _done(db, user, patient, request, "illness hidden")


@router.post("/patient/{patient_id}/medicines", status_code=status.HTTP_201_CREATED)
def add_medicine(patient_id: PathId, data: PastMedicationIn, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient, doctor = _doctor_patient(db, user, patient_id)
    past.create_medication(db, patient, data, user, doctor)
    return _done(db, user, patient, request, "medicine added")


@router.put("/patient/{patient_id}/medicines/{medication_id}")
def change_medicine(patient_id: PathId, medication_id: PathId, data: PastMedicationIn, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient, doctor = _doctor_patient(db, user, patient_id)
    past.update_medication(db, patient, medication_id, data, user, doctor)
    return _done(db, user, patient, request, "medicine changed")


@router.delete("/patient/{patient_id}/medicines/{medication_id}")
def remove_medicine(patient_id: PathId, medication_id: PathId, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient, _ = _doctor_patient(db, user, patient_id)
    past.delete_medication(db, patient, medication_id, user)
    return _done(db, user, patient, request, "medicine hidden")


@router.post("/patient/{patient_id}/admissions", status_code=status.HTTP_201_CREATED)
def add_admission(patient_id: PathId, data: AdmissionIn, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient, doctor = _doctor_patient(db, user, patient_id)
    past.create_admission(db, patient, data, user, doctor)
    return _done(db, user, patient, request, "admission added")


@router.put("/patient/{patient_id}/admissions/{admission_id}")
def change_admission(patient_id: PathId, admission_id: PathId, data: AdmissionIn, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient, doctor = _doctor_patient(db, user, patient_id)
    past.update_admission(db, patient, admission_id, data, user, doctor)
    return _done(db, user, patient, request, "admission changed")


@router.delete("/patient/{patient_id}/admissions/{admission_id}")
def remove_admission(patient_id: PathId, admission_id: PathId, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient, _ = _doctor_patient(db, user, patient_id)
    past.delete_admission(db, patient, admission_id, user)
    return _done(db, user, patient, request, "admission hidden")


@router.post("/patient/{patient_id}/surgeries", status_code=status.HTTP_201_CREATED)
def add_surgery(patient_id: PathId, data: SurgeryIn, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient, doctor = _doctor_patient(db, user, patient_id)
    past.create_surgery(db, patient, data, user, doctor)
    return _done(db, user, patient, request, "operation added")


@router.put("/patient/{patient_id}/surgeries/{surgery_id}")
def change_surgery(patient_id: PathId, surgery_id: PathId, data: SurgeryIn, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient, doctor = _doctor_patient(db, user, patient_id)
    past.update_surgery(db, patient, surgery_id, data, user, doctor)
    return _done(db, user, patient, request, "operation changed")


@router.delete("/patient/{patient_id}/surgeries/{surgery_id}")
def remove_surgery(patient_id: PathId, surgery_id: PathId, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient, _ = _doctor_patient(db, user, patient_id)
    past.delete_surgery(db, patient, surgery_id, user)
    return _done(db, user, patient, request, "operation hidden")


@router.post("/patient/{patient_id}/verify/{entity}/{entity_id}")
def verify_record(patient_id: PathId, entity: str, entity_id: PathId, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    """The doctor confirms a record (for example one told by the patient). The doctor's name and the time are kept."""
    patient, doctor = _doctor_patient(db, user, patient_id)
    past.verify(db, patient, entity, entity_id, user, doctor)
    return _done(db, user, patient, request, f"{entity} verified")
