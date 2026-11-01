"""Emergency: rapid registration (also of an unknown patient), triage, doctor assignment, timeline, orders and the outcome (discharge, admit, ICU, transfer).
Nothing here waits for AI or for any other module: a critical triage raises an alert from plain rules at once."""
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, NURSE, forbidden, get_accessible_patient, get_doctor_profile
from app.core.security import hash_password
from app.database.connection import get_db
from app.database.models import Bed, ClinicalAlert, ClinicalOrder, Doctor, EdTimelineEntry, EdVisit, Patient, User, VitalSet
from app.schemas.clinical import AssignIn, DispositionIn, EdVisitIn, OrderIn, TimelineIn, TriageIn
from app.services import audit_service, encounter_service as enc, grade_service, hospital_service, ipd_service as ipd, registry_service
from app.services.access_service import permissions_of, require_permission
from app.utils.validators import PathId

router = APIRouter(prefix="/api/emergency", tags=["emergency"])
register_perm = require_permission("ed.register")
triage_perm = require_permission("ed.triage")
treat_perm = require_permission("ed.treat")
board_perm = require_permission("ed.register", "ed.triage", "ed.treat")
CATEGORY = {1: "Resuscitation", 2: "Emergent", 3: "Urgent", 4: "Less urgent", 5: "Non-urgent"}


def _timeline(db: Session, visit: EdVisit, kind: str, text: str, user: User | None) -> None:
    db.add(EdTimelineEntry(ed_visit_id=visit.id, kind=kind, text=text[:500], created_by=user.id if user else None))


def create_unidentified(db: Session, data, user: User) -> Patient:
    """An unknown patient gets a real record at once (UHID included) so treatment is never delayed. The record has no login and no invented details."""
    branch = hospital_service.default_branch(db)
    stamp = datetime.now().strftime("%H%M")
    gender = data.gender
    login = User(email=f"unknown-{uuid.uuid4().hex[:10]}@ed.invalid", password_hash=hash_password(secrets.token_urlsafe(16)), full_name=f"Unknown {gender or 'person'} (ED {stamp})",
                 role="PATIENT", is_active=False, must_change_password=True)
    db.add(login)
    db.flush()
    note = "Unidentified at arrival." + (f" Approximate age {data.approx_age}." if data.approx_age is not None else "") + (f" {data.description}" if data.description else "")
    patient = Patient(user_id=login.id, patient_code=f"U-{uuid.uuid4().hex[:6].upper()}", gender=gender, branch_id=branch.id, uhid=registry_service.next_uhid(db, branch), medical_history_text=note)
    db.add(patient)
    db.flush()
    return patient


def visit_out(db: Session, v: EdVisit, detail: bool = False) -> dict:
    waited = int((enc.now() - v.arrival_at).total_seconds() // 60) if v.status != "DISPOSED" else None
    out = {"id": v.id, "encounter_id": v.encounter_id, "patient": enc.patient_line(v.patient), "unidentified": v.unidentified, "arrival_at": v.arrival_at.isoformat(), "arrival_mode": v.arrival_mode,
           "chief_complaint": v.chief_complaint, "triage_category": v.triage_category, "triage_label": CATEGORY.get(v.triage_category), "status": v.status, "waiting_minutes": waited,
           "assigned_doctor_id": v.assigned_doctor_id, "assigned_doctor": v.encounter.attending_doctor.user.full_name if v.encounter.attending_doctor else None,
           "disposition": v.disposition, "disposition_note": v.disposition_note, "admission_id": v.admission_id}
    if detail:
        timeline = db.scalars(select(EdTimelineEntry).where(EdTimelineEntry.ed_visit_id == v.id).order_by(EdTimelineEntry.id)).all()
        orders = db.scalars(select(ClinicalOrder).where(ClinicalOrder.encounter_id == v.encounter_id).order_by(ClinicalOrder.id)).all()
        vitals = db.scalars(select(VitalSet).where(VitalSet.encounter_id == v.encounter_id).order_by(VitalSet.recorded_at.desc())).all()
        alerts = db.scalars(select(ClinicalAlert).where(ClinicalAlert.encounter_id == v.encounter_id).order_by(ClinicalAlert.id.desc())).all()
        out.update({"timeline": [{"id": t.id, "kind": t.kind, "text": t.text, "by": t.author.full_name if t.author else None, "at": t.created_at.isoformat()} for t in timeline],
                    "orders": [{"id": o.id, "kind": o.kind, "text": o.text, "priority": o.priority, "status": o.status} for o in orders], "vitals": [enc.vitals_out(x) for x in vitals],
                    "alerts": [enc.alert_out(a) for a in alerts], "allergies": v.patient.allergies, "blood_group": v.patient.blood_group})
    return out


def _visit(db: Session, visit_id: int) -> EdVisit:
    v = db.get(EdVisit, visit_id)
    if v is None:
        raise HTTPException(404, "Emergency visit not found.")
    return v


def _clinical(db: Session, user: User, v: EdVisit, *, write: bool = False) -> None:
    """A nurse works with any current emergency patient; a doctor with their own, or an unassigned one (they claim it by assigning themselves)."""
    if user.role == NURSE:
        get_accessible_patient(db, user, v.patient_id, clinical=True)
    elif user.role == DOCTOR:
        me = get_doctor_profile(db, user)
        if v.assigned_doctor_id not in (None, me.id):
            raise forbidden()
    else:
        raise forbidden()


@router.post("/visits", status_code=status.HTTP_201_CREATED)
def register(data: EdVisitIn, request: Request, user: User = Depends(register_perm), db: Session = Depends(get_db)):
    """Rapid registration: a known patient, or an unidentified one. Arrival time is the moment of registration."""
    perms = permissions_of(db, user)
    if data.triage_category and "ed.triage" not in perms:
        raise HTTPException(403, "Only a nurse or doctor can set the triage category.")
    if data.patient_id:
        patient = db.get(Patient, data.patient_id)
        if patient is None or patient.merged_into_id:
            raise HTTPException(404, "Patient not found.")
        if db.scalar(select(EdVisit.id).where(EdVisit.patient_id == patient.id, EdVisit.status != "DISPOSED")):
            raise HTTPException(409, "This patient already has an open emergency visit.")
    else:
        patient = create_unidentified(db, data.unidentified, user)
    encounter = enc.open_encounter(db, patient, "ED", doctor=None, department_id=None, source="EMERGENCY", user=user)
    visit = EdVisit(encounter_id=encounter.id, patient_id=patient.id, arrival_mode=data.arrival_mode, chief_complaint=data.chief_complaint, status="WAITING", unidentified=data.unidentified is not None)
    db.add(visit)
    db.flush()
    _timeline(db, visit, "ARRIVAL", f"Arrived by {data.arrival_mode.lower().replace('_', ' ')}: {data.chief_complaint}", user)
    if data.triage_category:
        _apply_triage(db, visit, data.triage_category, None, user)
    db.commit()
    audit_service.log_action(db, user, audit_service.ED_REGISTERED, "ed_visit", visit.id, request, "unidentified" if visit.unidentified else "")
    return visit_out(db, visit)


def _apply_triage(db: Session, visit: EdVisit, category: int, note: str | None, user: User) -> None:
    visit.triage_category, visit.triaged_by, visit.triaged_at = category, user.id, enc.now()
    if visit.status == "WAITING":
        visit.status = "TRIAGED"
    _timeline(db, visit, "TRIAGE", f"Triage category {category} ({CATEGORY[category]})" + (f": {note}" if note else ""), user)
    if category <= 2:                                    # a plain rule, not AI: the board and the alert list show it at once
        db.add(ClinicalAlert(patient_id=visit.patient_id, encounter_id=visit.encounter_id, level="CRITICAL" if category == 1 else "WARNING",
                             message=f"Emergency triage category {category}: {CATEGORY[category]}"))


@router.get("/board")
def board(user: User = Depends(board_perm), db: Session = Depends(get_db)):
    """Everyone who is in the emergency department now, most urgent first, then by waiting time."""
    rows = list(db.scalars(select(EdVisit).where(EdVisit.status != "DISPOSED")))
    rows.sort(key=lambda v: (v.triage_category if v.triage_category else 9, v.arrival_at))
    return [visit_out(db, v) for v in rows]


@router.get("/visits/{visit_id}")
def visit_detail(visit_id: PathId, user: User = Depends(require_permission("ed.triage", "ed.treat")), db: Session = Depends(get_db)):
    v = _visit(db, visit_id)
    _clinical(db, user, v)
    return visit_out(db, v, detail=True)


@router.post("/visits/{visit_id}/triage")
def triage(visit_id: PathId, data: TriageIn, request: Request, user: User = Depends(triage_perm), db: Session = Depends(get_db)):
    v = _visit(db, visit_id)
    if v.status == "DISPOSED":
        raise HTTPException(409, "This visit is finished.")
    if user.role == DOCTOR:
        _clinical(db, user, v)
    else:
        get_accessible_patient(db, user, v.patient_id, clinical=True)
    if data.vitals is not None:
        enc.record_vitals(db, v.patient, data.vitals, user, encounter_id=v.encounter_id)
    _apply_triage(db, v, data.category, data.note, user)
    db.commit()
    audit_service.log_action(db, user, audit_service.ED_TRIAGED, "ed_visit", v.id, request, f"category {data.category}")
    return visit_out(db, v, detail=True)


@router.post("/visits/{visit_id}/assign")
def assign(visit_id: PathId, data: AssignIn, request: Request, user: User = Depends(treat_perm), db: Session = Depends(get_db)):
    v = _visit(db, visit_id)
    if v.status == "DISPOSED":
        raise HTTPException(409, "This visit is finished.")
    doctor = db.get(Doctor, data.doctor_id)
    if doctor is None or not doctor.user.is_active:
        raise HTTPException(422, "The selected doctor does not exist.")
    v.assigned_doctor_id = doctor.id
    v.encounter.attending_doctor_id = doctor.id
    v.encounter.department_id = v.encounter.department_id or doctor.department_id
    if v.status in ("WAITING", "TRIAGED"):
        v.status = "IN_TREATMENT"
    _timeline(db, v, "NOTE", f"Assigned to {doctor.user.full_name}", user)
    db.commit()
    audit_service.log_action(db, user, audit_service.ED_TRIAGED, "ed_visit", v.id, request, f"assigned to doctor {doctor.id}")
    return visit_out(db, v, detail=True)


@router.post("/visits/{visit_id}/timeline", status_code=status.HTTP_201_CREATED)
def add_timeline(visit_id: PathId, data: TimelineIn, request: Request, user: User = Depends(treat_perm), db: Session = Depends(get_db)):
    v = _visit(db, visit_id)
    _clinical(db, user, v)
    if v.status == "DISPOSED":
        raise HTTPException(409, "This visit is finished.")
    _timeline(db, v, data.kind, data.text, user)
    db.commit()
    audit_service.log_action(db, user, "ED_TIMELINE_ADDED", "ed_visit", v.id, request, data.kind)
    return visit_out(db, v, detail=True)


@router.post("/visits/{visit_id}/orders", status_code=status.HTTP_201_CREATED)
def add_order(visit_id: PathId, data: OrderIn, request: Request, user: User = Depends(require_permission("ed.treat")), db: Session = Depends(get_db)):
    v = _visit(db, visit_id)
    _clinical(db, user, v)
    if v.status == "DISPOSED":
        raise HTTPException(409, "This visit is finished.")
    doctor = get_doctor_profile(db, user)
    row = ClinicalOrder(encounter_id=v.encounter_id, patient_id=v.patient_id, kind=data.kind, text=data.text, priority=data.priority, ordered_by=user.id, status=grade_service.order_status(doctor))
    db.add(row)
    db.flush()
    if row.status == "DRAFT":
        grade_service.request_countersign(db, "ORDER", row.id, v.patient_id, doctor, f"Emergency {data.kind.lower()} order: {data.text}")
    _timeline(db, v, "ORDER", f"{data.kind.title()} ordered ({data.priority.lower()}): {data.text}", user)
    db.commit()
    audit_service.log_action(db, user, audit_service.ORDER_PLACED, "clinical_order", row.id, request, f"ED {data.kind} {data.priority}")
    return visit_out(db, v, detail=True)


@router.post("/visits/{visit_id}/disposition")
def disposition(visit_id: PathId, data: DispositionIn, request: Request, user: User = Depends(treat_perm), db: Session = Depends(get_db)):
    """The doctor decides the outcome. Admit or ICU opens an inpatient stay (and the bed if one is chosen) in the same transaction."""
    v = _visit(db, visit_id)
    _clinical(db, user, v)
    if v.status == "DISPOSED":
        raise HTTPException(409, "This visit is already finished.")
    me = get_doctor_profile(db, user)
    if me.current_grade == "INTERN":
        raise HTTPException(403, "An intern does not decide the outcome of an emergency visit. Please ask your consultant.")
    admission = None
    if data.disposition in ("ADMIT", "ICU"):
        doctor = db.get(Doctor, data.attending_doctor_id) if data.attending_doctor_id else (v.encounter.attending_doctor or me)
        if doctor is None or not doctor.user.is_active:
            raise HTTPException(422, "Please choose the attending doctor.")
        admission = ipd.admit(db, v.patient, doctor, data.department_id, data.diagnosis or v.chief_complaint, v.encounter_id, None, user)
        if data.bed_id:
            bed = db.get(Bed, data.bed_id)
            if bed is None:
                raise HTTPException(422, "The selected bed does not exist.")
            ipd.assign_bed(db, admission, bed, user, "From emergency")
        v.admission_id = admission.id
    v.status, v.disposition, v.disposition_at, v.disposition_note = "DISPOSED", data.disposition, enc.now(), data.note
    if v.assigned_doctor_id is None:
        v.assigned_doctor_id = me.id
        v.encounter.attending_doctor_id = me.id
    v.encounter.status, v.encounter.ended_at = "CLOSED", enc.now()
    _timeline(db, v, "DISPOSITION", f"{data.disposition.title()}" + (f": {data.note}" if data.note else "") + (f" (admission {admission.admission_no})" if admission else ""), user)
    db.commit()
    audit_service.log_action(db, user, audit_service.ED_DISPOSITION, "ed_visit", v.id, request, data.disposition)
    return visit_out(db, v, detail=True)
