"""The consultant's countersign queue and the junior doctor's list of what is waiting. A consultant approves, edits and approves (the junior doctor's version is kept),
or returns with a comment. Nothing a junior doctor prepared reaches the pharmacy, the lab or the patient until then (unless an administrator allowed independent prescribing)."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import CONSULTANT, DOCTOR, forbidden, get_doctor_profile, require_roles
from app.database.connection import get_db
from app.database.models import ClinicalOrder, CountersignRequest, DischargeSummary, Doctor, Prescription, PrescriptionItem, User
from app.schemas.prescription import PrescriptionItemCreate
from app.services import audit_service, grade_service
from app.utils.validators import PathId, opt_text, text

router = APIRouter(prefix="/api/countersign", tags=["countersign"])
doctor_only = require_roles(DOCTOR)


class ApproveIn(BaseModel):
    comment: opt_text(500) = None
    items: list[PrescriptionItemCreate] | None = Field(default=None, min_length=1, max_length=30)      # edit-and-approve a prescription


class ReturnIn(BaseModel):
    comment: text(500, min_length=3)


def _row(db: Session, request_id: int) -> CountersignRequest:
    row = db.get(CountersignRequest, request_id)
    if row is None:
        raise HTTPException(404, "Request not found.")
    return row


@router.get("/awaiting")
def awaiting(state: str = "PENDING", user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    """For a consultant: what the junior doctors under them prepared. state=PENDING or DECIDED."""
    me = get_doctor_profile(db, user)
    if state not in ("PENDING", "DECIDED"):
        raise HTTPException(422, "The state must be PENDING or DECIDED.")
    if me.current_grade != CONSULTANT:
        raise forbidden()
    query = select(CountersignRequest).where(or_(CountersignRequest.supervisor_id == me.id, CountersignRequest.supervisor_id.is_(None)))
    query = query.where(CountersignRequest.status == "PENDING") if state == "PENDING" else query.where(CountersignRequest.status != "PENDING")
    rows = [r for r in db.scalars(query.order_by(CountersignRequest.id.desc()).limit(200)) if grade_service.may_decide(db, me, r) or (state == "DECIDED" and r.decided_by == me.id)]
    return [grade_service.countersign_out(r) for r in rows]


@router.get("/mine")
def mine(user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    """For a junior doctor: what they sent to the consultant, with the status and the consultant's comment."""
    me = get_doctor_profile(db, user)
    rows = db.scalars(select(CountersignRequest).where(CountersignRequest.requested_by == me.id).order_by(CountersignRequest.id.desc()).limit(200)).all()
    return [grade_service.countersign_out(r) for r in rows]


def _decide_row(db: Session, user: User, request_id: int) -> tuple[CountersignRequest, Doctor]:
    me = get_doctor_profile(db, user)
    row = _row(db, request_id)
    if not grade_service.may_decide(db, me, row):
        raise HTTPException(404, "Request not found.")                    # not yours looks the same as not existing
    if row.status != "PENDING":
        raise HTTPException(409, "This request has already been decided.")
    return row, me


@router.get("/{request_id}")
def detail(request_id: PathId, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    """What is waiting, in full (the medicines of a prescription), for the supervising consultant who must decide, and for the junior doctor who sent it."""
    me = get_doctor_profile(db, user)
    row = _row(db, request_id)
    if row.requested_by != me.id and not grade_service.may_decide(db, me, row) and row.decided_by != me.id:
        raise HTTPException(404, "Request not found.")
    out = grade_service.countersign_out(row)
    if row.kind == "PRESCRIPTION":
        rx = db.get(Prescription, row.item_id)
        if rx is not None:
            out["prescription"] = {"id": rx.id, "indication": rx.clinical_indication, "notes": rx.notes, "tests": [t for t in (rx.tests_advised or "").splitlines() if t],
                                   "items": [{"medicine_name": i.medicine_name, "dosage": i.dosage, "frequency": i.frequency, "duration": i.duration, "quantity": i.quantity,
                                              "instructions": i.instructions} for i in rx.items]}
    return out


@router.post("/{request_id}/approve")
def approve(request_id: PathId, data: ApproveIn, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    row, me = _decide_row(db, user, request_id)
    edited = False
    if row.kind == "PRESCRIPTION":
        rx = db.get(Prescription, row.item_id)
        if rx is None or rx.status != "PENDING_COUNTERSIGN":
            raise HTTPException(409, "This prescription is no longer waiting.")
        if data.items is not None:                                       # the consultant corrects the medicines: the junior doctor's version stays in the request
            for old in list(rx.items):
                db.delete(old)
            db.flush()
            rx.items = [PrescriptionItem(**item.model_dump(), dispense_status="PENDING") for item in data.items]
            edited = True
        rx.status = "ACTIVE"
    elif row.kind == "ORDER":
        order = db.get(ClinicalOrder, row.item_id)
        if order is None or order.status != "DRAFT":
            raise HTTPException(409, "This order is no longer waiting.")
        order.status = "ORDERED"
    elif row.kind == "DISCHARGE_SUMMARY":
        summary = db.get(DischargeSummary, row.item_id)
        if summary is None or summary.status == "APPROVED":
            raise HTTPException(409, "This discharge summary is no longer waiting.")
        missing = [label for label, value in (("the final diagnosis", summary.final_diagnosis), ("the hospital course", summary.hospital_course), ("the follow-up", summary.follow_up)) if not (value or "").strip()]
        if missing:
            raise HTTPException(422, "Before approving, the summary needs " + ", ".join(missing) + ".")
        summary.status, summary.approved_by, summary.approved_at = "APPROVED", me.id, grade_service.now()
    row.status, row.decided_by, row.decided_at, row.comment = "EDITED" if edited else "APPROVED", me.id, grade_service.now(), data.comment
    db.commit()
    audit_service.log_action(db, user, audit_service.COUNTERSIGNED, "countersign", row.id, request, f"{row.kind} {'edited and approved' if edited else 'approved'}")
    return grade_service.countersign_out(row)


@router.post("/{request_id}/return")
def return_with_comment(request_id: PathId, data: ReturnIn, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    row, me = _decide_row(db, user, request_id)
    if row.kind == "PRESCRIPTION":
        rx = db.get(Prescription, row.item_id)
        if rx is not None and rx.status == "PENDING_COUNTERSIGN":
            rx.status = "RETURNED"
    elif row.kind == "ORDER":
        order = db.get(ClinicalOrder, row.item_id)
        if order is not None and order.status == "DRAFT":
            order.status, order.note = "CANCELLED", f"Returned: {data.comment}"[:300]
    row.status, row.decided_by, row.decided_at, row.comment = "RETURNED", me.id, grade_service.now(), data.comment
    db.commit()
    audit_service.log_action(db, user, audit_service.COUNTERSIGNED, "countersign", row.id, request, f"{row.kind} returned")
    return grade_service.countersign_out(row)
