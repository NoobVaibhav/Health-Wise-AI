"""Doctor A asks another department for an opinion. The doctor who accepts opens a consult visit and sees the patient's records while the request is open;
their consult note is the "updated plan" that comes back to the referring doctor."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import forbidden, get_accessible_patient, get_doctor_profile
from app.database.connection import get_db
from app.database.models import Consultation, Department, Doctor, Encounter, Patient, ReferralRequest, User
from app.schemas.clinical import ReferralRequestIn, ReferralResponseIn
from app.services import audit_service, encounter_service as enc
from app.services.access_service import require_permission
from app.utils.validators import PathId

router = APIRouter(prefix="/api/referral-requests", tags=["referral requests"])
ask_perm = require_permission("referral.request")
answer_perm = require_permission("referral.respond")


def _out(db: Session, r: ReferralRequest, detail: bool = False, viewer_id: int | None = None) -> dict:
    out = {"id": r.id, "patient": enc.patient_line(r.patient), "from_doctor": r.from_doctor.user.full_name, "from_doctor_id": r.from_doctor_id, "to_department_id": r.to_department_id,
           "to_department": r.to_department.name, "to_doctor_id": r.to_doctor_id, "reason": r.reason, "urgency": r.urgency, "status": r.status, "response_note": r.response_note,
           "consult_encounter_id": r.consult_encounter_id, "created_at": r.created_at.isoformat(), "responded_at": r.responded_at.isoformat() if r.responded_at else None}
    if detail:
        consult = db.scalar(select(Consultation).where(Consultation.encounter_id == r.consult_encounter_id)) if r.consult_encounter_id else None
        origin = db.scalar(select(Consultation).where(Consultation.encounter_id == r.from_encounter_id)) if r.from_encounter_id else None
        out["origin_consultation"] = None if origin is None or viewer_id not in (r.from_doctor_id, r.to_doctor_id) else {"complaint": origin.complaint, "assessment": origin.assessment, "plan": origin.plan, "status": origin.status}
        out["consult_note"] = None if consult is None else {"assessment": consult.assessment, "plan": consult.plan, "advice": consult.advice, "status": consult.status,
                                                          "doctor_name": consult.doctor.user.full_name, "signed_at": consult.signed_at.isoformat() if consult.signed_at else None}
    return out


def _mine(db: Session, doctor: Doctor, r: ReferralRequest) -> bool:
    """The asking doctor, the doctor it was sent to, or (while still unanswered) any doctor of the department it was sent to."""
    if doctor.id in (r.from_doctor_id, r.to_doctor_id):
        return True
    return r.to_doctor_id is None and r.status == "REQUESTED" and doctor.department_id == r.to_department_id


@router.post("", status_code=status.HTTP_201_CREATED)
def ask(data: ReferralRequestIn, request: Request, user: User = Depends(ask_perm), db: Session = Depends(get_db)):
    me = get_doctor_profile(db, user)
    patient = get_accessible_patient(db, user, data.patient_id, clinical=True)
    if db.get(Department, data.to_department_id) is None:
        raise HTTPException(422, "The selected department does not exist.")
    if data.to_doctor_id:
        target = db.get(Doctor, data.to_doctor_id)
        if target is None or not target.user.is_active or target.department_id != data.to_department_id:
            raise HTTPException(422, "The selected doctor does not work in that department.")
        if target.id == me.id:
            raise HTTPException(422, "You cannot refer a patient to yourself.")
    if data.from_encounter_id:
        origin = db.get(Encounter, data.from_encounter_id)
        if origin is None or origin.patient_id != patient.id:
            raise HTTPException(422, "The visit does not belong to this patient.")
    if db.scalar(select(ReferralRequest.id).where(ReferralRequest.patient_id == patient.id, ReferralRequest.from_doctor_id == me.id, ReferralRequest.to_department_id == data.to_department_id,
                                                  ReferralRequest.status.in_(("REQUESTED", "ACCEPTED")))):
        raise HTTPException(409, "You have already referred this patient to this department.")
    row = ReferralRequest(patient_id=patient.id, from_encounter_id=data.from_encounter_id, from_doctor_id=me.id, to_department_id=data.to_department_id, to_doctor_id=data.to_doctor_id,
                          reason=data.reason, urgency=data.urgency, status="REQUESTED")
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, audit_service.REFERRAL_REQUESTED, "referral_request", row.id, request, data.urgency)
    return _out(db, row)


@router.get("")
def mine(box: str = "incoming", user: User = Depends(require_permission("referral.request", "referral.respond")), db: Session = Depends(get_db)):
    """box=incoming: sent to me or to my department and waiting; box=outgoing: the ones I asked."""
    if box not in ("incoming", "outgoing"):
        raise HTTPException(422, "The box must be incoming or outgoing.")
    me = get_doctor_profile(db, user)
    if box == "outgoing":
        query = select(ReferralRequest).where(ReferralRequest.from_doctor_id == me.id)
    else:
        query = select(ReferralRequest).where(or_(ReferralRequest.to_doctor_id == me.id, (ReferralRequest.to_doctor_id.is_(None)) & (ReferralRequest.to_department_id == me.department_id)))
    rows = list(db.scalars(query.order_by(ReferralRequest.id.desc()).limit(200)))
    rows.sort(key=lambda r: (r.status in ("COMPLETED", "DECLINED"), r.urgency != "URGENT"))
    return [_out(db, r) for r in rows]


@router.get("/{request_id}")
def detail(request_id: PathId, user: User = Depends(require_permission("referral.request", "referral.respond")), db: Session = Depends(get_db)):
    r = db.get(ReferralRequest, request_id)
    me = get_doctor_profile(db, user)
    if r is None or not _mine(db, me, r):
        raise HTTPException(404, "Referral not found.")
    return _out(db, r, detail=True, viewer_id=me.id)


def _answerable(db: Session, user: User, request_id: int) -> tuple[ReferralRequest, Doctor]:
    me = get_doctor_profile(db, user)
    r = db.get(ReferralRequest, request_id)
    if r is None or not _mine(db, me, r) or me.id == r.from_doctor_id:
        raise HTTPException(404, "Referral not found.")
    return r, me


@router.post("/{request_id}/accept")
def accept(request_id: PathId, request: Request, user: User = Depends(answer_perm), db: Session = Depends(get_db)):
    """The specialist takes the referral: a consult visit and a token are made for them, and they can now see the patient's records."""
    r, me = _answerable(db, user, request_id)
    if r.status != "REQUESTED":
        raise HTTPException(409, "This referral has already been answered.")
    encounter = enc.open_encounter(db, r.patient, "OPD", doctor=me, department_id=me.department_id or r.to_department_id, source="REFERRAL", user=user)
    enc.issue_token(db, encounter, me, urgent=r.urgency == "URGENT")
    r.status, r.to_doctor_id, r.responded_by, r.responded_at, r.consult_encounter_id = "ACCEPTED", me.id, me.id, enc.now(), encounter.id
    db.commit()
    audit_service.log_action(db, user, audit_service.REFERRAL_RESPONDED, "referral_request", r.id, request, "accepted")
    return _out(db, r, detail=True, viewer_id=me.id)


@router.post("/{request_id}/decline")
def decline(request_id: PathId, data: ReferralResponseIn, request: Request, user: User = Depends(answer_perm), db: Session = Depends(get_db)):
    r, me = _answerable(db, user, request_id)
    if r.status != "REQUESTED":
        raise HTTPException(409, "This referral has already been answered.")
    if not data.note:
        raise HTTPException(422, "Please write why the referral is declined.")
    r.status, r.responded_by, r.responded_at, r.response_note = "DECLINED", me.id, enc.now(), data.note
    db.commit()
    audit_service.log_action(db, user, audit_service.REFERRAL_RESPONDED, "referral_request", r.id, request, "declined")
    return _out(db, r)


@router.post("/{request_id}/complete")
def complete(request_id: PathId, data: ReferralResponseIn, request: Request, user: User = Depends(answer_perm), db: Session = Depends(get_db)):
    """The specialist finishes: the signed consult note (and an optional summary) goes back to the referring doctor as the updated plan."""
    r, me = _answerable(db, user, request_id)
    if r.status != "ACCEPTED" or r.to_doctor_id != me.id:
        raise HTTPException(409, "Please accept the referral first.")
    consult = db.scalar(select(Consultation).where(Consultation.encounter_id == r.consult_encounter_id))
    if consult is None or consult.status != "SIGNED":
        raise HTTPException(409, "Please sign your consultation first. It is the updated plan the referring doctor receives.")
    r.status, r.responded_at, r.response_note = "COMPLETED", enc.now(), data.note or r.response_note
    db.commit()
    audit_service.log_action(db, user, audit_service.REFERRAL_RESPONDED, "referral_request", r.id, request, "completed")
    return _out(db, r, detail=True, viewer_id=me.id)
