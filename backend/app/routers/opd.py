"""OPD: check-in, walk-in, tokens and the queue; and the doctor's consultation workspace for one visit."""
import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, forbidden, get_doctor_profile
from app.database.connection import get_db
from app.database.models import (
    Appointment, ClinicalOrder, Consultation, ConsultationAddendum, ConsultationTemplate, Department, Diagnosis, Doctor, Encounter, EncounterCharge, Patient, Prescription, QueueToken, User, VitalSet,
)
from app.schemas.clinical import AddendumIn, CheckInIn, ConsultationIn, DiagnosisIn, OrderIn, OrderStatusIn, TemplateIn, VitalsIn, WalkInIn
from app.services import audit_service, encounter_service as svc, grade_service
from app.services.access_service import permissions_of, require_permission
from app.utils.validators import PathId, QueryId
from app.utils.clock import hospital_today

router = APIRouter(prefix="/api/opd", tags=["opd"])
checkin_perm = require_permission("opd.checkin")
queue_perm = require_permission("opd.queue")
consult_perm = require_permission("consult.write")
vitals_perm = require_permission("vitals.record")
orders_perm = require_permission("orders.write")


# ------------------------------------------------------------------ reception: check-in, walk-in, queue
@router.post("/check-in", status_code=status.HTTP_201_CREATED)
def check_in(data: CheckInIn, request: Request, user: User = Depends(checkin_perm), db: Session = Depends(get_db)):
    """The patient has arrived for the appointment: a visit (encounter) is opened and a token is given."""
    appointment = db.get(Appointment, data.appointment_id)
    if appointment is None:
        raise HTTPException(404, "Appointment not found.")
    if appointment.status == "CANCELLED":
        raise HTTPException(409, "This appointment was cancelled.")
    if appointment.encounter_id:
        raise HTTPException(409, "This patient has already been checked in for this appointment.")
    patient, doctor = appointment.patient, appointment.doctor
    encounter = svc.open_encounter(db, patient, "OPD", doctor=doctor, department_id=appointment.department_id, source="APPOINTMENT", user=user, appointment=appointment)
    token = svc.issue_token(db, encounter, doctor, data.urgent)
    if appointment.status == "SCHEDULED":
        appointment.status = "CONFIRMED"
    db.commit()
    audit_service.log_action(db, user, audit_service.ENCOUNTER_OPENED, "encounter", encounter.id, request, f"token {token.number}")
    return svc.token_out(token)


@router.post("/walk-in", status_code=status.HTTP_201_CREATED)
def walk_in(data: WalkInIn, request: Request, user: User = Depends(checkin_perm), db: Session = Depends(get_db)):
    patient = db.get(Patient, data.patient_id)
    doctor = db.get(Doctor, data.doctor_id)
    if patient is None or patient.merged_into_id:
        raise HTTPException(404, "Patient not found.")
    if doctor is None or not doctor.user.is_active:
        raise HTTPException(404, "Doctor not found.")
    if data.department_id and db.get(Department, data.department_id) is None:
        raise HTTPException(422, "The selected department does not exist.")
    if db.scalar(select(Encounter.id).where(Encounter.patient_id == patient.id, Encounter.attending_doctor_id == doctor.id, Encounter.type == "OPD", Encounter.status == "OPEN")):
        raise HTTPException(409, "This patient is already in this doctor's queue.")
    encounter = svc.open_encounter(db, patient, "OPD", doctor=doctor, department_id=data.department_id, source="WALK_IN", user=user)
    token = svc.issue_token(db, encounter, doctor, data.urgent)
    db.commit()
    audit_service.log_action(db, user, audit_service.ENCOUNTER_OPENED, "encounter", encounter.id, request, f"walk-in token {token.number}")
    return svc.token_out(token)


@router.get("/queue")
def queue(day: date | None = None, doctor_id: QueryId = None, user: User = Depends(queue_perm), db: Session = Depends(get_db)):
    """The tokens of a day (today by default). A doctor sees only their own queue."""
    if user.role == DOCTOR:
        doctor_id = get_doctor_profile(db, user).id
    return svc.queue(db, day or hospital_today(), doctor_id)


def _token(db: Session, token_id: int) -> QueueToken:
    token = db.get(QueueToken, token_id)
    if token is None:
        raise HTTPException(404, "Token not found.")
    return token


@router.post("/queue/next")
def call_next(user: User = Depends(consult_perm), db: Session = Depends(get_db)):
    """The doctor calls the next waiting patient (urgent first, then by token number)."""
    doctor = get_doctor_profile(db, user)
    token = svc.next_waiting(db, doctor)
    if token is None:
        raise HTTPException(404, "Nobody is waiting.")
    return svc.token_out(svc.call_token(db, token))


@router.post("/queue/{token_id}/call")
def call(token_id: PathId, user: User = Depends(consult_perm), db: Session = Depends(get_db)):
    token = _token(db, token_id)
    if token.doctor_id != get_doctor_profile(db, user).id:
        raise forbidden()
    return svc.token_out(svc.call_token(db, token))


@router.post("/queue/{token_id}/{outcome}")
def close_token(token_id: PathId, outcome: str, request: Request, user: User = Depends(checkin_perm), db: Session = Depends(get_db)):
    """Reception marks a token as NO_SHOW or CANCELLED. The visit is closed with it."""
    if outcome not in ("no-show", "cancel"):
        raise HTTPException(404, "Not found.")
    token = _token(db, token_id)
    if token.status in ("DONE", "IN_CONSULTATION"):
        raise HTTPException(409, "This patient is already with the doctor or has been seen.")
    token.status, token.finished_at = ("NO_SHOW" if outcome == "no-show" else "CANCELLED"), svc.now()
    token.encounter.status, token.encounter.ended_at = "CANCELLED", svc.now()
    db.commit()
    audit_service.log_action(db, user, audit_service.ENCOUNTER_OPENED, "encounter", token.encounter_id, request, outcome)
    return svc.token_out(token)


# ------------------------------------------------------------------ the consultation workspace
@router.get("/templates")
def templates(department_id: QueryId = None, user: User = Depends(require_permission("consult.write", "template.manage")), db: Session = Depends(get_db)):
    if "template.manage" in permissions_of(db, user):
        rows = db.scalars(select(ConsultationTemplate).order_by(ConsultationTemplate.id))
        return [svc.template_out(t) for t in rows]
    return [svc.template_out(svc.template_for(db, department_id))] if svc.template_for(db, department_id) else []


@router.post("/templates", status_code=status.HTTP_201_CREATED)
def add_template(data: TemplateIn, request: Request, user: User = Depends(require_permission("template.manage")), db: Session = Depends(get_db)):
    if data.department_id and db.get(Department, data.department_id) is None:
        raise HTTPException(422, "The selected department does not exist.")
    keys = [f.key for f in data.fields]
    if len(set(keys)) != len(keys):
        raise HTTPException(422, "Two fields have the same key.")
    row = ConsultationTemplate(name=data.name, department_id=data.department_id, is_active=data.is_active, fields_json=json.dumps([f.model_dump() for f in data.fields]))
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, audit_service.HOSPITAL_CHANGED, "consultation_template", row.id, request, data.name[:100])
    return svc.template_out(row)


@router.put("/templates/{template_id}")
def update_template(template_id: PathId, data: TemplateIn, request: Request, user: User = Depends(require_permission("template.manage")), db: Session = Depends(get_db)):
    row = db.get(ConsultationTemplate, template_id)
    if row is None:
        raise HTTPException(404, "Template not found.")
    if data.department_id and db.get(Department, data.department_id) is None:
        raise HTTPException(422, "The selected department does not exist.")
    keys = [f.key for f in data.fields]
    if len(set(keys)) != len(keys):
        raise HTTPException(422, "Two fields have the same key.")
    row.name, row.department_id, row.is_active, row.fields_json, row.updated_at = data.name, data.department_id, data.is_active, json.dumps([f.model_dump() for f in data.fields]), svc.now()
    db.commit()
    audit_service.log_action(db, user, audit_service.HOSPITAL_CHANGED, "consultation_template", row.id, request, data.name[:100])
    return svc.template_out(row)


def _workspace(db: Session, encounter: Encounter) -> dict:
    patient = encounter.patient
    consultation = db.scalar(select(Consultation).where(Consultation.encounter_id == encounter.id))
    diagnoses = db.scalars(select(Diagnosis).where(Diagnosis.encounter_id == encounter.id, Diagnosis.is_active.is_(True)).order_by(Diagnosis.id)).all()
    orders = db.scalars(select(ClinicalOrder).where(ClinicalOrder.encounter_id == encounter.id).order_by(ClinicalOrder.id)).all()
    vitals = db.scalars(select(VitalSet).where(VitalSet.patient_id == patient.id).order_by(VitalSet.recorded_at.desc()).limit(10)).all()
    previous = db.scalars(select(Consultation).where(Consultation.patient_id == patient.id, Consultation.status == "SIGNED", Consultation.encounter_id != encounter.id)
                          .order_by(Consultation.signed_at.desc()).limit(5)).all()
    charges = db.scalars(select(EncounterCharge).where(EncounterCharge.encounter_id == encounter.id)).all()
    prescriptions = db.scalars(select(Prescription).where(Prescription.encounter_id == encounter.id)).all()
    addenda = db.scalars(select(ConsultationAddendum).where(ConsultationAddendum.consultation_id == (consultation.id if consultation else -1)).order_by(ConsultationAddendum.id)).all()
    return {
        "encounter": {"id": encounter.id, "type": encounter.type, "status": encounter.status, "source": encounter.source, "started_at": encounter.started_at.isoformat(),
                      "department_id": encounter.department_id, "department_name": encounter.department.name if encounter.department else None},
        "patient": {**svc.patient_line(patient), "allergies": patient.allergies, "blood_group": patient.blood_group, "current_medications": patient.current_medications},
        "consultation": svc.consultation_out(consultation),
        "template": svc.template_out(svc.template_for(db, encounter.department_id) if consultation is None or consultation.template_id is None else db.get(ConsultationTemplate, consultation.template_id)),
        "diagnoses": [{"id": d.id, "text": d.text, "code": d.code, "kind": d.kind} for d in diagnoses],
        "orders": [{"id": o.id, "kind": o.kind, "text": o.text, "priority": o.priority, "status": o.status, "ordered_at": o.ordered_at.isoformat(), "note": o.note} for o in orders],
        "vitals": [svc.vitals_out(v) for v in vitals],
        "previous_consultations": [{"id": c.id, "signed_at": c.signed_at.isoformat(), "doctor_name": c.doctor.user.full_name, "complaint": c.complaint, "assessment": c.assessment, "plan": c.plan} for c in previous],
        "prescriptions": [{"id": p.id, "date": p.prescription_date.isoformat(), "status": p.status} for p in prescriptions],
        "charges": [{"id": c.id, "description": c.description, "amount": c.amount, "gst_percent": c.gst_percent, "status": c.status} for c in charges],
        "addenda": [{"id": a.id, "text": a.text, "added_at": a.added_at.isoformat()} for a in addenda],
    }


@router.get("/encounters/{encounter_id}")
def workspace(encounter_id: PathId, user: User = Depends(require_permission("consult.write", "vitals.record")), db: Session = Depends(get_db)):
    encounter = svc.encounter_for_user(db, user, encounter_id)
    return _workspace(db, encounter)


@router.put("/encounters/{encounter_id}/consultation")
def save_consultation(encounter_id: PathId, data: ConsultationIn, user: User = Depends(consult_perm), db: Session = Depends(get_db)):
    """Saves the draft (the doctor may save as often as they like, so nothing typed is lost)."""
    encounter = svc.encounter_for_user(db, user, encounter_id, write=True)
    if encounter.status != "OPEN":
        raise HTTPException(409, "This visit is closed.")
    doctor = get_doctor_profile(db, user)
    consultation = svc.get_or_create_consultation(db, encounter, doctor)
    if consultation.doctor_id != doctor.id:
        raise forbidden()
    svc.save_consultation(db, consultation, data)
    db.commit()
    return svc.consultation_out(consultation)


@router.post("/encounters/{encounter_id}/sign")
def sign(encounter_id: PathId, request: Request, user: User = Depends(consult_perm), db: Session = Depends(get_db)):
    """The doctor reviews and signs. After this the consultation cannot be changed, only added to."""
    encounter = svc.encounter_for_user(db, user, encounter_id, write=True)
    doctor = get_doctor_profile(db, user)
    if not grade_service.can_sign_consultation(doctor):
        raise HTTPException(403, "An intern does not sign a consultation. Please save it as a draft for your consultant.")
    consultation = db.scalar(select(Consultation).where(Consultation.encounter_id == encounter.id))
    if consultation is None or consultation.doctor_id != doctor.id:
        raise HTTPException(409, "There is no consultation of yours to sign. Please save it first.")
    result = svc.sign_consultation(db, encounter, consultation, doctor, user)
    audit_service.log_action(db, user, audit_service.CONSULTATION_SIGNED, "consultation", consultation.id, request)
    return {**result, "consultation": svc.consultation_out(consultation)}


@router.post("/consultations/{consultation_id}/addenda", status_code=status.HTTP_201_CREATED)
def add_addendum(consultation_id: PathId, data: AddendumIn, request: Request, user: User = Depends(consult_perm), db: Session = Depends(get_db)):
    consultation = db.get(Consultation, consultation_id)
    if consultation is None:
        raise HTTPException(404, "Consultation not found.")
    if consultation.doctor_id != get_doctor_profile(db, user).id:
        raise forbidden()
    if consultation.status != "SIGNED":
        raise HTTPException(409, "Only a signed consultation receives an addendum. This one is still a draft.")
    row = ConsultationAddendum(consultation_id=consultation.id, text=data.text, added_by=user.id)
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, audit_service.CONSULTATION_SIGNED, "consultation", consultation.id, request, "addendum")
    return {"id": row.id, "text": row.text, "added_at": row.added_at.isoformat()}


@router.post("/encounters/{encounter_id}/vitals", status_code=status.HTTP_201_CREATED)
def add_vitals(encounter_id: PathId, data: VitalsIn, user: User = Depends(vitals_perm), db: Session = Depends(get_db)):
    encounter = svc.encounter_for_user(db, user, encounter_id)
    if encounter.status != "OPEN":
        raise HTTPException(409, "This visit is closed.")
    v, alerts = svc.record_vitals(db, encounter.patient, data, user, encounter_id=encounter.id)
    db.commit()
    return {"vitals": svc.vitals_out(v), "alerts": [{"level": a.level, "message": a.message} for a in alerts]}


@router.post("/encounters/{encounter_id}/diagnoses", status_code=status.HTTP_201_CREATED)
def add_diagnosis(encounter_id: PathId, data: DiagnosisIn, request: Request, user: User = Depends(consult_perm), db: Session = Depends(get_db)):
    encounter = svc.encounter_for_user(db, user, encounter_id, write=True)
    consultation = db.scalar(select(Consultation).where(Consultation.encounter_id == encounter.id))
    if consultation is not None and consultation.status == "SIGNED":
        raise HTTPException(409, "This consultation is signed. Please add an addendum.")
    doctor = get_doctor_profile(db, user)
    row = Diagnosis(encounter_id=encounter.id, patient_id=encounter.patient_id, text=data.text, code=data.code, kind=grade_service.diagnosis_kind(doctor, data.kind), added_by=doctor.id)
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, "DIAGNOSIS_ADDED", "diagnosis", row.id, request, f"{row.kind}: {row.text}"[:200])
    return {"id": row.id, "text": row.text, "code": row.code, "kind": row.kind}


@router.post("/diagnoses/{diagnosis_id}/withdraw")
def withdraw_diagnosis(diagnosis_id: PathId, request: Request, user: User = Depends(consult_perm), db: Session = Depends(get_db)):
    """A diagnosis is withdrawn (kept, marked) and never deleted."""
    row = db.get(Diagnosis, diagnosis_id)
    if row is None:
        raise HTTPException(404, "Diagnosis not found.")
    encounter = svc.encounter_for_user(db, user, row.encounter_id, write=True)
    consultation = db.scalar(select(Consultation).where(Consultation.encounter_id == encounter.id))
    if consultation is not None and consultation.status == "SIGNED":
        raise HTTPException(409, "This consultation is signed. Please add an addendum.")
    row.is_active = False
    db.commit()
    audit_service.log_action(db, user, "DIAGNOSIS_WITHDRAWN", "diagnosis", row.id, request, row.text[:200])
    return {"id": row.id, "is_active": False}


@router.post("/encounters/{encounter_id}/orders", status_code=status.HTTP_201_CREATED)
def add_order(encounter_id: PathId, data: OrderIn, request: Request, user: User = Depends(orders_perm), db: Session = Depends(get_db)):
    encounter = svc.encounter_for_user(db, user, encounter_id, write=True)
    if encounter.status != "OPEN":
        raise HTTPException(409, "This visit is closed.")
    doctor = get_doctor_profile(db, user)
    row = ClinicalOrder(encounter_id=encounter.id, patient_id=encounter.patient_id, kind=data.kind, text=data.text, priority=data.priority, ordered_by=user.id, status=grade_service.order_status(doctor))
    db.add(row)
    db.flush()
    if row.status == "DRAFT":                                  # an intern's order waits for the supervising consultant
        grade_service.request_countersign(db, "ORDER", row.id, encounter.patient_id, doctor, f"{data.kind.title()} order: {data.text}")
    db.commit()
    audit_service.log_action(db, user, audit_service.ORDER_PLACED, "clinical_order", row.id, request, f"{data.kind} {data.priority} {row.status}")
    return {"id": row.id, "kind": row.kind, "text": row.text, "priority": row.priority, "status": row.status}


@router.post("/orders/{order_id}/status")
def order_status(order_id: PathId, data: OrderStatusIn, request: Request, user: User = Depends(require_permission("orders.write", "nursing.chart")), db: Session = Depends(get_db)):
    row = db.get(ClinicalOrder, order_id)
    if row is None:
        raise HTTPException(404, "Order not found.")
    svc.encounter_for_user(db, user, row.encounter_id)
    if row.status in ("DONE", "CANCELLED"):
        raise HTTPException(409, "This order is already finished.")
    row.status, row.note = data.status, data.note
    if data.status in ("DONE", "CANCELLED"):
        row.completed_at, row.completed_by = svc.now(), user.id
    db.commit()
    audit_service.log_action(db, user, "ORDER_STATUS", "clinical_order", row.id, request, f"{row.kind} {data.status}")
    return {"id": row.id, "status": row.status}
