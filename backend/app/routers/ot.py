"""Operation theatre: theatres, bookings, and the record of each operation.
Surgeons and anaesthetists are doctors; OT staff (a permission, not a login role) help with bookings and the checklists."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, forbidden, get_accessible_patient, get_current_user, get_doctor_profile
from app.database.connection import get_db
from app.database.models import Doctor, OperationTheatre, Patient, Surgery, User
from app.services import audit_service, ot_service
from app.services.access_service import permissions_of, require_permission
from app.utils.validators import PathId, SearchText, opt_text, text

router = APIRouter(prefix="/api/ot", tags=["operation-theatre"])
view = require_permission("ot.view", "ot.schedule", "ot.record")
schedule_perm = require_permission("ot.schedule")


class TheatreIn(BaseModel):
    name: text(80, min_length=2)


class BookIn(BaseModel):
    patient_id: int = Field(ge=1)
    admission_id: int | None = Field(default=None, ge=1)
    theatre_id: int = Field(ge=1)
    procedure: text(200, min_length=3)
    priority: str = Field(default="ELECTIVE", pattern="^(ELECTIVE|URGENT|EMERGENCY)$")
    surgeon_id: int = Field(ge=1)
    anaesthetist_id: int | None = Field(default=None, ge=1)
    service_id: int | None = Field(default=None, ge=1)
    scheduled_start: datetime
    scheduled_end: datetime


class RescheduleIn(BaseModel):
    theatre_id: int | None = Field(default=None, ge=1)
    surgeon_id: int | None = Field(default=None, ge=1)
    anaesthetist_id: int | None = Field(default=None, ge=1)
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None


class CancelIn(BaseModel):
    reason: text(300, min_length=3)


class PreopIn(BaseModel):
    fit: bool
    notes: opt_text(2000) = None


class ConsentIn(BaseModel):
    given: bool
    by_name: text(150, min_length=2)
    note: opt_text(300) = None


class ChecklistIn(BaseModel):
    phase: str = Field(pattern="^(SIGN_IN|TIME_OUT|SIGN_OUT)$")
    items: list[str] = Field(min_length=1, max_length=10)


class AnaesthesiaIn(BaseModel):
    type: str = Field(max_length=30)
    notes: opt_text(3000) = None


class OpNoteIn(BaseModel):
    findings: text(4000, min_length=3)
    procedure_done: text(4000, min_length=3)
    complications: opt_text(2000) = None
    blood_loss_ml: int | None = Field(default=None, ge=0, le=20000)
    final: bool = False


class EventIn(BaseModel):
    text: text(500, min_length=3)


class ConsumableIn(BaseModel):
    inventory_item_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=10000)


class RecoveryIn(BaseModel):
    notes: opt_text(2000) = None


def _write_access(db: Session, user: User, surgery: Surgery) -> None:
    """Who may fill the theatre records: OT staff, and the surgeon or anaesthetist of this surgery."""
    if "ot.record" in permissions_of(db, user):
        return
    if user.role == DOCTOR:
        doctor_id = ot_service._doctor_id(db, user)
        if doctor_id in (surgery.surgeon_id, surgery.anaesthetist_id):
            return
    raise forbidden()


def _get_for_view(db: Session, user: User, surgery_id: int) -> Surgery:
    """A doctor sees the surgeries they are in, or of a patient they are authorised for; OT staff see the whole schedule."""
    surgery = ot_service.get(db, surgery_id)
    if user.role == DOCTOR:
        if ot_service._doctor_id(db, user) not in (surgery.surgeon_id, surgery.anaesthetist_id):
            get_accessible_patient(db, user, surgery.patient_id, clinical=True)
        return surgery
    if permissions_of(db, user) & {"ot.record", "ot.schedule", "ot.view"}:
        return surgery
    raise forbidden()


# ------------------------------------------------------------------ theatres and the schedule
@router.get("/theatres")
def theatres(user: User = Depends(view), db: Session = Depends(get_db)):
    return [{"id": t.id, "name": t.name, "is_active": t.is_active} for t in db.scalars(select(OperationTheatre).order_by(OperationTheatre.name))]


@router.get("/patients")
def find_patients(q: SearchText = None, user: User = Depends(schedule_perm), db: Session = Depends(get_db)):
    """A short list to pick a patient for a booking: a doctor sees their own patients, OT staff search all (name, patient ID or UHID only)."""
    query = select(Patient).join(User, Patient.user_id == User.id).order_by(Patient.id.desc()).limit(15)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.where(User.full_name.ilike(like) | Patient.patient_code.ilike(like) | Patient.uhid.ilike(like))
    elif user.role != DOCTOR:
        return []                                                                  # OT staff must type something: no list of every patient
    if user.role == DOCTOR:
        from app.core.permissions import doctor_patient_ids
        query = query.where(Patient.id.in_(doctor_patient_ids(db, get_doctor_profile(db, user)) or [0]))
    return [{"id": p.id, "full_name": p.user.full_name, "patient_code": p.patient_code, "uhid": p.uhid} for p in db.scalars(query)]


@router.post("/theatres", status_code=status.HTTP_201_CREATED)
def add_theatre(data: TheatreIn, request: Request, user: User = Depends(require_permission("ward.manage")), db: Session = Depends(get_db)):
    if db.scalar(select(OperationTheatre.id).where(OperationTheatre.name == data.name.strip())):
        raise HTTPException(status.HTTP_409_CONFLICT, "This theatre already exists.")
    row = OperationTheatre(name=data.name.strip())
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, "THEATRE_ADDED", "operation_theatre", row.id, request, row.name)
    return {"id": row.id, "name": row.name}


@router.get("/surgeries")
def surgeries(day: str | None = None, status_filter: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """OT staff see the whole schedule; a doctor sees the surgeries they are in."""
    perms = permissions_of(db, user)
    query = select(Surgery).order_by(Surgery.scheduled_start).limit(300)
    if status_filter:
        query = query.where(Surgery.status == status_filter)
    if day:
        try:
            d = datetime.strptime(day, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(422, "The day must look like 2026-11-30.")
        from datetime import timedelta
        query = query.where(Surgery.scheduled_start >= d, Surgery.scheduled_start < d + timedelta(days=1))
    if not perms & {"ot.view", "ot.schedule", "ot.record"}:
        raise forbidden()
    if user.role == DOCTOR and "ot.record" not in perms:
        me = ot_service._doctor_id(db, user)
        query = query.where((Surgery.surgeon_id == me) | (Surgery.anaesthetist_id == me))
    return [ot_service.out(db, s) for s in db.scalars(query)]


@router.post("/surgeries", status_code=status.HTTP_201_CREATED)
def book(data: BookIn, request: Request, user: User = Depends(schedule_perm), db: Session = Depends(get_db)):
    patient = db.get(Patient, data.patient_id)
    if patient is None:
        raise HTTPException(404, "Patient not found.")
    if user.role == DOCTOR:
        get_accessible_patient(db, user, patient.id, clinical=True)
    surgery = ot_service.book(db, user, patient.id, data.model_dump())
    audit_service.log_action(db, user, "SURGERY_BOOKED", "surgery", surgery.id, request, surgery.procedure[:150])
    return ot_service.out(db, surgery, detail=True)


@router.get("/surgeries/{surgery_id}")
def detail(surgery_id: PathId, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ot_service.out(db, _get_for_view(db, user, surgery_id), detail=True)


@router.put("/surgeries/{surgery_id}")
def reschedule(surgery_id: PathId, data: RescheduleIn, request: Request, user: User = Depends(schedule_perm), db: Session = Depends(get_db)):
    surgery = _get_for_view(db, user, surgery_id)
    ot_service.reschedule(db, surgery, data.model_dump(exclude_unset=True))
    audit_service.log_action(db, user, "SURGERY_RESCHEDULED", "surgery", surgery.id, request, "")
    return ot_service.out(db, surgery, detail=True)


@router.post("/surgeries/{surgery_id}/cancel")
def cancel(surgery_id: PathId, data: CancelIn, request: Request, user: User = Depends(schedule_perm), db: Session = Depends(get_db)):
    surgery = _get_for_view(db, user, surgery_id)
    ot_service.cancel(db, surgery, data.reason)
    audit_service.log_action(db, user, "SURGERY_CANCELLED", "surgery", surgery.id, request, data.reason[:150])
    return ot_service.out(db, surgery, detail=True)


# ------------------------------------------------------------------ the records
@router.post("/surgeries/{surgery_id}/preop")
def preop(surgery_id: PathId, data: PreopIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != DOCTOR:
        raise forbidden()
    surgery = ot_service.get(db, surgery_id)
    ot_service.record_preop(db, surgery, user, data.fit, data.notes)
    audit_service.log_action(db, user, "SURGERY_PREOP", "surgery", surgery.id, request, "fit" if data.fit else "not fit")
    return ot_service.out(db, surgery, detail=True)


@router.post("/surgeries/{surgery_id}/consent")
def consent(surgery_id: PathId, data: ConsentIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    surgery = ot_service.get(db, surgery_id)
    _write_access(db, user, surgery)
    ot_service.record_consent(db, surgery, user, data.given, data.by_name, data.note)
    audit_service.log_action(db, user, "SURGERY_CONSENT", "surgery", surgery.id, request, "given" if data.given else "refused")
    return ot_service.out(db, surgery, detail=True)


@router.post("/surgeries/{surgery_id}/checklist")
def checklist(surgery_id: PathId, data: ChecklistIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    surgery = ot_service.get(db, surgery_id)
    _write_access(db, user, surgery)
    ot_service.tick_checklist(db, surgery, user, data.phase, data.items)
    audit_service.log_action(db, user, "SURGERY_CHECKLIST", "surgery", surgery.id, request, data.phase)
    return ot_service.out(db, surgery, detail=True)


@router.post("/surgeries/{surgery_id}/start")
def start(surgery_id: PathId, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    surgery = ot_service.get(db, surgery_id)
    _write_access(db, user, surgery)
    ot_service.start(db, surgery)
    audit_service.log_action(db, user, "SURGERY_STARTED", "surgery", surgery.id, request, "")
    return ot_service.out(db, surgery, detail=True)


@router.post("/surgeries/{surgery_id}/anaesthesia")
def anaesthesia(surgery_id: PathId, data: AnaesthesiaIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != DOCTOR:
        raise forbidden()
    surgery = ot_service.get(db, surgery_id)
    ot_service.record_anaesthesia(db, surgery, user, data.type, data.notes)
    audit_service.log_action(db, user, "SURGERY_ANAESTHESIA", "surgery", surgery.id, request, data.type)
    return ot_service.out(db, surgery, detail=True)


@router.post("/surgeries/{surgery_id}/op-note")
def op_note(surgery_id: PathId, data: OpNoteIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != DOCTOR:
        raise forbidden()
    surgery = ot_service.get(db, surgery_id)
    ot_service.record_op_note(db, surgery, user, data.model_dump(), data.final)
    audit_service.log_action(db, user, "SURGERY_OP_NOTE", "surgery", surgery.id, request, "final" if data.final else "draft")
    return ot_service.out(db, surgery, detail=True)


@router.post("/surgeries/{surgery_id}/events")
def event(surgery_id: PathId, data: EventIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    surgery = ot_service.get(db, surgery_id)
    _write_access(db, user, surgery)
    ot_service.add_event(db, surgery, user, data.text)
    audit_service.log_action(db, user, "SURGERY_EVENT", "surgery", surgery.id, request, data.text[:100])
    return ot_service.out(db, surgery, detail=True)


@router.post("/surgeries/{surgery_id}/consumables")
def consumable(surgery_id: PathId, data: ConsumableIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    surgery = ot_service.get(db, surgery_id)
    _write_access(db, user, surgery)
    ot_service.use_consumable(db, surgery, user, data.inventory_item_id, data.quantity)
    audit_service.log_action(db, user, "SURGERY_CONSUMABLE", "surgery", surgery.id, request, f"item {data.inventory_item_id} x{data.quantity}")
    return ot_service.out(db, surgery, detail=True)


@router.post("/surgeries/{surgery_id}/recovery")
def recovery(surgery_id: PathId, data: RecoveryIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    surgery = ot_service.get(db, surgery_id)
    _write_access(db, user, surgery)
    ot_service.to_recovery(db, surgery, data.notes)
    audit_service.log_action(db, user, "SURGERY_RECOVERY", "surgery", surgery.id, request, "")
    return ot_service.out(db, surgery, detail=True)


@router.post("/surgeries/{surgery_id}/complete")
def complete(surgery_id: PathId, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    surgery = ot_service.get(db, surgery_id)
    _write_access(db, user, surgery)
    ot_service.complete(db, surgery, user)
    audit_service.log_action(db, user, "SURGERY_COMPLETED", "surgery", surgery.id, request, "")
    return ot_service.out(db, surgery, detail=True)
