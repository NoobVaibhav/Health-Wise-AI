"""The doctor's side of the trainee workflow: referrals sent to the doctor (urgent first), reading, verifying or correcting the history a trainee took,
and the supervising doctor's approval of a PG student's referral. Nothing a trainee wrote is overwritten: every change keeps the earlier version."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, forbidden, get_accessible_patient, get_doctor_profile, require_roles
from app.database.connection import get_db
from app.database.models import Doctor, Referral, Trainee, TraineeHistory, TraineeHistoryRevision, User
from app.schemas.trainee import DoctorHistoryEdit, SupervisorReview
from app.services import audit_service, trainee_service as service
from app.utils.validators import PathId

router = APIRouter(prefix="/api/referrals", tags=["referrals"])
doctor_only = require_roles(DOCTOR)


def _is_supervisor(doctor: Doctor, trainee: Trainee) -> bool:
    return trainee.supervisor_id == doctor.id


def _referral_for(db: Session, doctor: Doctor, referral_id: int) -> Referral:
    r = db.get(Referral, referral_id)
    if r is None or not (r.doctor_id == doctor.id or _is_supervisor(doctor, r.trainee)):
        raise HTTPException(404, "Referral not found.")                   # not yours looks the same as not existing
    return r


def _history_for(db: Session, doctor: Doctor, history_id: int) -> TraineeHistory:
    """A history the doctor may handle: it was sent to this doctor, or the trainee is this doctor's student."""
    h = db.get(TraineeHistory, history_id)
    allowed = h is not None and (_is_supervisor(doctor, h.trainee) or db.scalar(
        select(Referral.id).where(Referral.history_id == h.id, Referral.doctor_id == doctor.id).limit(1)) is not None)
    if not allowed:
        raise HTTPException(404, "History not found.")
    return h


@router.get("")
def my_referrals(user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    """Referrals sent to this doctor, and those of the doctor's own trainees. Urgent and not yet seen first."""
    doctor = get_doctor_profile(db, user)
    rows = db.scalars(select(Referral).join(Trainee, Referral.trainee_id == Trainee.id)
                      .where(or_(Referral.doctor_id == doctor.id, Trainee.supervisor_id == doctor.id)).order_by(Referral.id.desc()).limit(200)).all()
    rows.sort(key=lambda r: (r.status == "COMPLETED", not r.urgent, r.status != "SENT"))
    return [{**service.referral_out(r), "mine": r.doctor_id == doctor.id, "as_supervisor": _is_supervisor(doctor, r.trainee)} for r in rows]


@router.get("/patient/{patient_id}")
def histories_of_patient(patient_id: PathId, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    """The histories trainees took for a patient this doctor is authorised for (shown on the patient page)."""
    patient = get_accessible_patient(db, user, patient_id, clinical=True)
    rows = db.scalars(select(TraineeHistory).where(TraineeHistory.patient_id == patient.id, TraineeHistory.status != "DRAFT")
                      .order_by(TraineeHistory.id.desc())).all()
    return [service.history_out(h) for h in rows]


@router.get("/{referral_id}")
def get_referral(referral_id: PathId, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    doctor = get_doctor_profile(db, user)
    r = _referral_for(db, doctor, referral_id)
    revisions = db.scalars(select(TraineeHistoryRevision).where(TraineeHistoryRevision.history_id == r.history_id).order_by(TraineeHistoryRevision.id)).all()
    return {**service.referral_out(r), "mine": r.doctor_id == doctor.id, "as_supervisor": _is_supervisor(doctor, r.trainee), "history": service.history_out(r.history), "patient": service.basic_patient(r.patient),
            "revisions": [{"id": v.id, "changed_at": v.changed_at.isoformat(), "data": json.loads(v.data_json or "{}")} for v in revisions]}


@router.post("/{referral_id}/seen")
def mark_seen(referral_id: PathId, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    doctor = get_doctor_profile(db, user)
    r = _referral_for(db, doctor, referral_id)
    if r.doctor_id != doctor.id:
        raise forbidden()
    if r.status == "SENT":
        r.status, r.seen_at = "SEEN", service.now()
        db.commit()
        audit_service.log_action(db, user, audit_service.REFERRAL_UPDATED, "referral", r.id, request, "seen")
    return service.referral_out(r)


@router.post("/{referral_id}/complete")
def mark_completed(referral_id: PathId, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    doctor = get_doctor_profile(db, user)
    r = _referral_for(db, doctor, referral_id)
    if r.doctor_id != doctor.id:
        raise forbidden()
    if r.status != "COMPLETED":
        r.status, r.completed_at = "COMPLETED", service.now()
        r.seen_at = r.seen_at or r.completed_at
        db.commit()
        audit_service.log_action(db, user, audit_service.REFERRAL_UPDATED, "referral", r.id, request, "completed")
    return service.referral_out(r)


@router.post("/{referral_id}/review")
def supervisor_review(referral_id: PathId, data: SupervisorReview, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    """The supervising doctor of a PG student approves the referral or corrects it (a note, and optionally another doctor)."""
    doctor = get_doctor_profile(db, user)
    r = _referral_for(db, doctor, referral_id)
    if not _is_supervisor(doctor, r.trainee):
        raise forbidden()
    if data.doctor_id is not None and data.doctor_id != r.doctor_id:
        new = db.get(Doctor, data.doctor_id)
        if new is None or not new.user.is_active:
            raise HTTPException(422, "The selected doctor does not exist.")
        r.doctor_id, r.overridden = new.id, True
        if r.patient.assigned_doctor_id in (None, doctor.id):
            r.patient.assigned_doctor_id = new.id
    r.supervisor_reviewed_at, r.supervisor_note = service.now(), data.note or ("Approved" if data.approved else "Corrected")
    db.commit()
    audit_service.log_action(db, user, audit_service.REFERRAL_UPDATED, "referral", r.id, request, "supervisor " + ("approved" if data.approved else "corrected"))
    return service.referral_out(r)


@router.post("/histories/{history_id}/verify")
def verify_history(history_id: PathId, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    """The doctor confirms the history. From now on the trainee can no longer change it."""
    doctor = get_doctor_profile(db, user)
    h = _history_for(db, doctor, history_id)
    if h.status == "DRAFT":
        raise HTTPException(409, "The trainee has not completed this history yet.")
    if h.status != "VERIFIED":
        h.status, h.verified_by, h.verified_at = "VERIFIED", doctor.id, service.now()
        db.commit()
        audit_service.log_action(db, user, audit_service.TRAINEE_HISTORY_VERIFIED, "trainee_history", h.id, request)
    return service.history_out(h)


@router.put("/histories/{history_id}")
def doctor_edit_history(history_id: PathId, data: DoctorHistoryEdit, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    """The doctor corrects the history and/or adds a note. The trainee's original is kept in the revisions."""
    doctor = get_doctor_profile(db, user)
    h = _history_for(db, doctor, history_id)
    if h.status == "DRAFT":
        raise HTTPException(409, "The trainee has not completed this history yet.")
    if data.data is not None:
        db.add(TraineeHistoryRevision(history_id=h.id, changed_by=user.id, data_json=h.data_json))
        h.data_json = data.data.model_dump_json()
    if data.note is not None:
        h.doctor_notes = data.note or None
    h.updated_at = service.now()
    db.commit()
    audit_service.log_action(db, user, audit_service.TRAINEE_HISTORY_EDITED, "trainee_history", h.id, request, "by doctor")
    return service.history_out(h)
