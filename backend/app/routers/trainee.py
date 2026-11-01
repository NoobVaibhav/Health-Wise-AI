"""Trainee workspace (intern / PG student): patients to work on, history drafts, doctor suggestion, referrals.
A trainee never prescribes, orders tests or sees reports, billing or other departments' patients. The administrator can only look at the referrals."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ADMIN, DOCTOR, get_junior_profile as get_trainee_profile, require_roles
from app.database.connection import get_db
from app.database.models import Department, Doctor, Patient, Referral, TraineeHistory, User
from app.schemas.trainee import ReferralCreate, TraineeHistorySave, TraineeHistoryStart
from app.services import audit_service, trainee_service as service
from app.utils.validators import PathId, QueryId, SearchText

router = APIRouter(prefix="/api/trainee", tags=["trainee"])
trainee_only = require_roles(DOCTOR)             # the junior-doctor check (a grade other than consultant) is get_junior_profile


@router.get("/dashboard")
def dashboard(user: User = Depends(trainee_only), db: Session = Depends(get_db)):
    return service.trainee_dashboard(db, get_trainee_profile(db, user))


@router.get("/patients")
def patients(q: SearchText = None, user: User = Depends(trainee_only), db: Session = Depends(get_db)):
    """The patients this trainee may take a history for (basic details only)."""
    trainee = get_trainee_profile(db, user)
    query = service.scope_query(trainee).order_by(Patient.id.desc()).limit(200)
    rows = db.scalars(query).all()
    if q:
        needle = q.strip().lower()
        rows = [p for p in rows if needle in p.user.full_name.lower() or needle in p.patient_code.lower() or needle in (p.phone or "")]
    return [service.basic_patient(p) for p in rows]


@router.get("/histories")
def histories(patient_id: QueryId = None, user: User = Depends(trainee_only), db: Session = Depends(get_db)):
    trainee = get_trainee_profile(db, user)
    query = select(TraineeHistory).where(TraineeHistory.trainee_id == trainee.id).order_by(TraineeHistory.updated_at.desc()).limit(100)
    if patient_id is not None:
        query = query.where(TraineeHistory.patient_id == patient_id)
    return [service.history_out(h) for h in db.scalars(query)]


@router.post("/histories", status_code=status.HTTP_201_CREATED)
def start_history(data: TraineeHistoryStart, request: Request, user: User = Depends(trainee_only), db: Session = Depends(get_db)):
    """Open a draft for a patient (or continue the one that is already open)."""
    trainee = get_trainee_profile(db, user)
    patient = service.patient_in_scope(db, trainee, data.patient_id)
    history, created = service.start_history(db, trainee, patient)
    if created:
        audit_service.log_action(db, user, audit_service.TRAINEE_HISTORY_STARTED, "trainee_history", history.id, request)
    return {**service.history_out(history), "patient": service.basic_patient(patient)}


@router.get("/histories/{history_id}")
def get_history(history_id: PathId, user: User = Depends(trainee_only), db: Session = Depends(get_db)):
    history = service.own_history(db, get_trainee_profile(db, user), history_id)
    return {**service.history_out(history), "patient": service.basic_patient(history.patient)}


@router.put("/histories/{history_id}")
def save_history(history_id: PathId, data: TraineeHistorySave, request: Request, user: User = Depends(trainee_only), db: Session = Depends(get_db)):
    """Autosave. A draft may be half empty; a completed history can still be corrected until a doctor verifies it."""
    history = service.own_history(db, get_trainee_profile(db, user), history_id)
    was_complete = history.status == "COMPLETE"
    history = service.save_history(db, history, data.data, user)
    if was_complete:
        audit_service.log_action(db, user, audit_service.TRAINEE_HISTORY_EDITED, "trainee_history", history.id, request)
    return service.history_out(history)


@router.post("/histories/{history_id}/complete")
def complete_history(history_id: PathId, request: Request, user: User = Depends(trainee_only), db: Session = Depends(get_db)):
    history = service.complete_history(db, service.own_history(db, get_trainee_profile(db, user), history_id))
    audit_service.log_action(db, user, audit_service.TRAINEE_HISTORY_COMPLETED, "trainee_history", history.id, request)
    return service.history_out(history)


@router.get("/histories/{history_id}/suggestion")
def suggestion(history_id: PathId, user: User = Depends(trainee_only), db: Session = Depends(get_db)):
    """The department that fits the complaint, why, and its doctors with today's load."""
    history = service.own_history(db, get_trainee_profile(db, user), history_id)
    return service.suggestion(db, history)


@router.get("/departments/{department_id}/doctors")
def department_doctors(department_id: PathId, user: User = Depends(trainee_only), db: Session = Depends(get_db)):
    """Doctors of a department (for the manual choice), with today's load."""
    if db.get(Department, department_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found.")
    return service.doctors_of_department(db, department_id)


@router.post("/referrals", status_code=status.HTTP_201_CREATED)
def create_referral(data: ReferralCreate, request: Request, user: User = Depends(trainee_only), db: Session = Depends(get_db)):
    trainee = get_trainee_profile(db, user)
    history = service.own_history(db, trainee, data.history_id)
    doctor = db.get(Doctor, data.doctor_id)
    if doctor is None:
        raise HTTPException(422, "The selected doctor does not exist.")
    if data.suggested_department_id is not None and db.get(Department, data.suggested_department_id) is None:
        raise HTTPException(422, "The suggested department does not exist.")
    referral = service.create_referral(db, trainee, history, doctor, data.reason, data.urgent, data.suggested_department_id, data.book_at, user)
    audit_service.log_action(db, user, audit_service.REFERRAL_CREATED, "referral", referral.id, request, "urgent" if referral.urgent else None)
    return service.referral_out(referral)


@router.get("/referrals")
def my_referrals(user: User = Depends(trainee_only), db: Session = Depends(get_db)):
    trainee = get_trainee_profile(db, user)
    rows = db.scalars(select(Referral).where(Referral.trainee_id == trainee.id).order_by(Referral.id.desc()).limit(200)).all()
    return [service.referral_out(r) for r in rows]


@router.get("/admin/overview")
def admin_overview(_: User = Depends(require_roles(ADMIN)), db: Session = Depends(get_db)):
    """Read-only for the administrator: who the trainees are and the referrals they sent (no medical content)."""
    trainees = db.scalars(select(Doctor).where(Doctor.grade.in_(("INTERN", "PG_RESIDENT", "SENIOR_RESIDENT")))).all()
    referrals = db.scalars(select(Referral).order_by(Referral.id.desc()).limit(100)).all()
    return {"trainees": [{"id": t.id, "full_name": t.user.full_name, "type": t.current_grade, "grade": t.current_grade, "year_branch": t.pg_branch,
                          "department_name": t.department.name if t.department else None, "supervisor": t.supervisor_name} for t in trainees],
            "referrals": [service.referral_out(r) for r in referrals]}
