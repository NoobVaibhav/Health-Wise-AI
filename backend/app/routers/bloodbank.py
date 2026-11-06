"""Blood bank: donors, donations and screening, units, requests from doctors, cross-match, issue with a second person, return, and transfusions at the bedside.
Everyone is separated on purpose: one person collects, another screens; one issues, another verifies; one nurse starts a transfusion, another checks it at the bedside."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, forbidden, get_accessible_patient, get_current_user, get_doctor_profile, nurse_can_access_patient
from app.database.connection import get_db
from app.database.models import BloodDonation, BloodDonor, BloodIssue, BloodRequest, BloodUnit, Patient, Transfusion, User
from app.services import audit_service, bloodbank_service as bb
from app.services.access_service import permissions_of, require_permission
from app.utils.validators import PathId, SearchText, opt_text, text
from app.utils.clock import hospital_today

router = APIRouter(prefix="/api/bloodbank", tags=["blood-bank"])
manage = require_permission("bloodbank.manage")
give = require_permission("transfusion.give")


class DonorIn(BaseModel):
    full_name: text(150, min_length=2)
    gender: str = Field(pattern="^(male|female|other)$")
    date_of_birth: date
    phone: opt_text(30) = None
    blood_group: str


class DonationIn(BaseModel):
    volume_ml: int = Field(ge=100, le=1000)
    haemoglobin: float = Field(gt=0, le=25)
    weight_kg: float = Field(gt=20, le=250)
    components: list[str] = Field(min_length=1, max_length=3)


class ScreeningIn(BaseModel):
    result: str = Field(pattern="^(CLEARED|REACTIVE)$")
    note: opt_text(300) = None


class ReasonIn(BaseModel):
    reason: text(300, min_length=3)


class RequestIn(BaseModel):
    patient_id: int = Field(ge=1)
    component: str
    units_requested: int = Field(ge=1, le=10)
    urgency: str = Field(default="ROUTINE", pattern="^(ROUTINE|URGENT|EMERGENCY)$")
    indication: text(300, min_length=3)
    blood_group: str | None = None


class CrossmatchIn(BaseModel):
    unit_id: int = Field(ge=1)
    result: str = Field(pattern="^(COMPATIBLE|INCOMPATIBLE)$")


class IssueIn(BaseModel):
    unit_id: int = Field(ge=1)


class ReturnIn(BaseModel):
    reason: text(300, min_length=3)
    cold_chain_ok: bool = False


class StartIn(BaseModel):
    patient_checked: bool
    unit_checked: bool


class EndIn(BaseModel):
    volume_given_ml: int = Field(ge=0, le=1000)
    reaction: bool = False
    reaction_note: opt_text(500) = None
    stopped: bool = False


def _get(db: Session, model, row_id: int, label: str):
    row = db.get(model, row_id)
    if row is None:
        raise HTTPException(404, f"{label} not found.")
    return row


# ------------------------------------------------------------------ donors and donations
@router.get("/rules")
def rules(user: User = Depends(manage)):
    return {"rules": bb.RULES, "shelf_life_days": bb.SHELF_LIFE_DAYS, "groups": list(bb.GROUPS), "components": list(bb.COMPONENTS),
            "note": "These limits are defaults. The blood bank medical officer must review and approve them for this hospital."}


@router.get("/donors")
def donors(q: SearchText = None, user: User = Depends(manage), db: Session = Depends(get_db)):
    query = select(BloodDonor).order_by(BloodDonor.id.desc()).limit(200)
    if q:
        query = query.where(or_(BloodDonor.full_name.ilike(f"%{q.strip()}%"), BloodDonor.donor_no.ilike(f"%{q.strip()}%"), BloodDonor.phone.ilike(f"%{q.strip()}%")))
    return [bb.donor_out(d) for d in db.scalars(query)]


@router.post("/donors", status_code=status.HTTP_201_CREATED)
def add_donor(data: DonorIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    if data.date_of_birth >= hospital_today():
        raise HTTPException(422, "The date of birth must be in the past.")
    donor = bb.register_donor(db, user, data.model_dump())
    audit_service.log_action(db, user, "DONOR_REGISTERED", "blood_donor", donor.id, request, donor.donor_no)
    return bb.donor_out(donor)


@router.post("/donors/{donor_id}/donations", status_code=status.HTTP_201_CREATED)
def donate(donor_id: PathId, data: DonationIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    donor = _get(db, BloodDonor, donor_id, "Donor")
    donation = bb.collect(db, user, donor, data.volume_ml, data.haemoglobin, data.weight_kg, data.components)
    audit_service.log_action(db, user, "BLOOD_COLLECTED", "blood_donation", donation.id, request, donor.donor_no)
    return {"id": donation.id, "screening": donation.screening, "units": [bb.unit_out(u) for u in donation.units]}


@router.get("/donations")
def donations(pending_only: bool = False, user: User = Depends(manage), db: Session = Depends(get_db)):
    query = select(BloodDonation).order_by(BloodDonation.id.desc()).limit(200)
    if pending_only:
        query = query.where(BloodDonation.screening == "PENDING")
    return [{"id": d.id, "donor_no": d.donor.donor_no, "donated_at": d.donated_at.isoformat(), "screening": d.screening, "collected_by": d.collected_by, "units": [bb.unit_out(u) for u in d.units]} for d in db.scalars(query)]


@router.post("/donations/{donation_id}/screening")
def screening(donation_id: PathId, data: ScreeningIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    donation = bb.screen(db, user, _get(db, BloodDonation, donation_id, "Donation"), data.result, data.note)
    audit_service.log_action(db, user, "BLOOD_SCREENED", "blood_donation", donation.id, request, data.result)
    return {"id": donation.id, "screening": donation.screening, "units": [bb.unit_out(u) for u in donation.units]}


# ------------------------------------------------------------------ units
@router.get("/stock")
def stock(user: User = Depends(manage), db: Session = Depends(get_db)):
    return bb.stock_summary(db)


@router.get("/units")
def units(component: str | None = None, blood_group: str | None = None, status_filter: str | None = None, user: User = Depends(manage), db: Session = Depends(get_db)):
    bb.refresh_expiry(db)
    query = select(BloodUnit).order_by(BloodUnit.expires_at).limit(300)
    if component:
        query = query.where(BloodUnit.component == component)
    if blood_group:
        query = query.where(BloodUnit.blood_group == blood_group)
    if status_filter:
        query = query.where(BloodUnit.status == status_filter)
    return [bb.unit_out(u) for u in db.scalars(query)]


@router.post("/units/{unit_id}/discard")
def discard(unit_id: PathId, data: ReasonIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    unit = bb.discard(db, _get(db, BloodUnit, unit_id, "Unit"), data.reason)
    audit_service.log_action(db, user, "BLOOD_UNIT_DISCARDED", "blood_unit", unit.id, request, data.reason[:150])
    return bb.unit_out(unit)


# ------------------------------------------------------------------ requests
@router.post("/requests", status_code=status.HTTP_201_CREATED)
def make_request(data: RequestIn, request: Request, user: User = Depends(require_permission("bloodbank.request")), db: Session = Depends(get_db)):
    if user.role != DOCTOR:
        raise forbidden()
    doctor = get_doctor_profile(db, user)
    patient = get_accessible_patient(db, user, data.patient_id, clinical=True)
    req = bb.create_request(db, doctor, patient, data.model_dump())
    audit_service.log_action(db, user, "BLOOD_REQUESTED", "blood_request", req.id, request, f"{req.units_requested} x {req.component}")
    return bb.request_out(db, req)


@router.get("/requests")
def requests_list(status_filter: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The blood bank sees every request; a doctor sees their own."""
    query = select(BloodRequest).order_by(BloodRequest.urgency.desc(), BloodRequest.id.desc()).limit(200)
    if status_filter:
        query = query.where(BloodRequest.status == status_filter)
    if "bloodbank.manage" not in permissions_of(db, user):
        if user.role != DOCTOR:
            raise forbidden()
        query = query.where(BloodRequest.requested_by == get_doctor_profile(db, user).id)
    return [bb.request_out(db, r) for r in db.scalars(query)]


@router.post("/requests/{request_id}/cancel")
def cancel_request(request_id: PathId, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = _get(db, BloodRequest, request_id, "Request")
    mine = user.role == DOCTOR and req.requested_by == get_doctor_profile(db, user).id
    if not mine and "bloodbank.manage" not in permissions_of(db, user):
        raise HTTPException(404, "Request not found.")
    bb.cancel_request(db, req)
    audit_service.log_action(db, user, "BLOOD_REQUEST_CANCELLED", "blood_request", req.id, request, "")
    return bb.request_out(db, req)


@router.post("/requests/{request_id}/reject")
def reject_request(request_id: PathId, data: ReasonIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    req = bb.reject_request(db, _get(db, BloodRequest, request_id, "Request"), data.reason)
    audit_service.log_action(db, user, "BLOOD_REQUEST_REJECTED", "blood_request", req.id, request, data.reason[:150])
    return bb.request_out(db, req)


@router.get("/requests/{request_id}/candidates")
def candidates(request_id: PathId, user: User = Depends(manage), db: Session = Depends(get_db)):
    """Available units that the ABO/Rh rule allows for this request (the technician still does the cross-match)."""
    req = _get(db, BloodRequest, request_id, "Request")
    bb.refresh_expiry(db)
    rows = db.scalars(select(BloodUnit).where(BloodUnit.status == "AVAILABLE", BloodUnit.component == req.component).order_by(BloodUnit.expires_at)).all()
    return [bb.unit_out(u) for u in rows if bb.compatible(u.blood_group, u.component, req.blood_group)]


@router.post("/requests/{request_id}/crossmatch", status_code=status.HTTP_201_CREATED)
def do_crossmatch(request_id: PathId, data: CrossmatchIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    req = _get(db, BloodRequest, request_id, "Request")
    row = bb.crossmatch(db, user, req, _get(db, BloodUnit, data.unit_id, "Unit"), data.result)
    audit_service.log_action(db, user, "BLOOD_CROSSMATCH", "blood_request", req.id, request, f"unit {data.unit_id} {row.result}")
    return bb.request_out(db, req)


@router.post("/requests/{request_id}/issue", status_code=status.HTTP_201_CREATED)
def issue(request_id: PathId, data: IssueIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    req = _get(db, BloodRequest, request_id, "Request")
    row = bb.issue(db, user, req, _get(db, BloodUnit, data.unit_id, "Unit"))
    audit_service.log_action(db, user, "BLOOD_ISSUED", "blood_issue", row.id, request, row.unit.unit_number)
    return {"issue_id": row.id, "verified": False, "request": bb.request_out(db, req)}


@router.post("/issues/{issue_id}/verify")
def verify(issue_id: PathId, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    row = bb.verify_issue(db, user, _get(db, BloodIssue, issue_id, "Issue"))
    audit_service.log_action(db, user, "BLOOD_ISSUE_VERIFIED", "blood_issue", row.id, request, row.unit.unit_number)
    return {"issue_id": row.id, "verified": True}


@router.post("/issues/{issue_id}/return")
def return_unit(issue_id: PathId, data: ReturnIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    row = bb.return_unit(db, _get(db, BloodIssue, issue_id, "Issue"), data.reason, data.cold_chain_ok)
    audit_service.log_action(db, user, "BLOOD_RETURNED", "blood_issue", row.id, request, row.unit.status)
    return {"issue_id": row.id, "unit_status": row.unit.status}


# ------------------------------------------------------------------ transfusion
def _may_transfuse(db: Session, user: User, patient: Patient) -> None:
    if user.role == DOCTOR:
        get_accessible_patient(db, user, patient.id, clinical=True)
    elif not nurse_can_access_patient(db, patient):                                  # a nurse or ward staff: the patient must be in the hospital now
        raise forbidden()


@router.get("/ready")
def ready(user: User = Depends(give), db: Session = Depends(get_db)):
    """Units that the blood bank verified and that wait for a bedside transfusion, for patients who are in the hospital now."""
    out = []
    for row in db.scalars(select(BloodIssue).where(BloodIssue.verified_by.is_not(None), BloodIssue.returned_at.is_(None)).order_by(BloodIssue.id.desc()).limit(100)):
        if db.scalar(select(Transfusion.id).where(Transfusion.issue_id == row.id)):
            continue
        patient = row.request.patient
        if nurse_can_access_patient(db, patient) or user.role == DOCTOR:
            out.append({"issue_id": row.id, "unit_number": row.unit.unit_number, "blood_group": row.unit.blood_group, "component": row.unit.component, "expires_at": row.unit.expires_at.isoformat(),
                        "patient_id": patient.id, "patient_name": patient.user.full_name, "patient_code": patient.patient_code, "patient_group": row.request.blood_group})
    return out


@router.get("/transfusions")
def active_transfusions(user: User = Depends(give), db: Session = Depends(get_db)):
    """Transfusions that wait for the bedside check or are running: the second person finds them here."""
    rows = db.scalars(select(Transfusion).where(Transfusion.status.in_(("AWAITING_CHECK", "IN_PROGRESS"))).order_by(Transfusion.id.desc()).limit(100))
    return [{**bb.transfusion_out(t), "patient_code": t.patient.patient_code, "started_by_me": t.started_by == user.id} for t in rows if nurse_can_access_patient(db, t.patient) or user.role == DOCTOR]


@router.post("/issues/{issue_id}/transfusion", status_code=status.HTTP_201_CREATED)
def start_transfusion(issue_id: PathId, data: StartIn, request: Request, user: User = Depends(give), db: Session = Depends(get_db)):
    row = _get(db, BloodIssue, issue_id, "Issue")
    _may_transfuse(db, user, row.request.patient)
    t = bb.start_transfusion(db, user, row, data.patient_checked, data.unit_checked)
    audit_service.log_action(db, user, "TRANSFUSION_STARTED", "transfusion", t.id, request, row.unit.unit_number)
    return bb.transfusion_out(t)


@router.post("/transfusions/{transfusion_id}/verify")
def verify_transfusion(transfusion_id: PathId, request: Request, user: User = Depends(give), db: Session = Depends(get_db)):
    t = _get(db, Transfusion, transfusion_id, "Transfusion")
    _may_transfuse(db, user, t.patient)
    bb.verify_transfusion(db, user, t)
    audit_service.log_action(db, user, "TRANSFUSION_VERIFIED", "transfusion", t.id, request, "")
    return bb.transfusion_out(t)


@router.post("/transfusions/{transfusion_id}/end")
def end_transfusion(transfusion_id: PathId, data: EndIn, request: Request, user: User = Depends(give), db: Session = Depends(get_db)):
    t = _get(db, Transfusion, transfusion_id, "Transfusion")
    _may_transfuse(db, user, t.patient)
    bb.end_transfusion(db, user, t, data.volume_given_ml, data.reaction, data.reaction_note, data.stopped)
    audit_service.log_action(db, user, "TRANSFUSION_ENDED", "transfusion", t.id, request, "reaction" if data.reaction else t.status)
    return bb.transfusion_out(t)


@router.get("/patient/{patient_id}/transfusions")
def patient_transfusions(patient_id: PathId, user: User = Depends(require_permission("bloodbank.request", "transfusion.give")), db: Session = Depends(get_db)):
    patient = get_accessible_patient(db, user, patient_id, clinical=True)
    return [bb.transfusion_out(t) for t in db.scalars(select(Transfusion).where(Transfusion.patient_id == patient.id).order_by(Transfusion.id.desc()))]
