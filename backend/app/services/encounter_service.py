"""Encounters (the shared spine of OPD, emergency and inpatient care), the OPD queue, vitals with alert rules, consultations, diagnoses, orders and charges."""
import json
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, NURSE, forbidden, get_doctor_profile, get_accessible_patient
from app.database.models import (
    Appointment, Branch, ClinicalAlert, ClinicalOrder, Consultation, ConsultationAddendum, ConsultationTemplate, Department, Diagnosis, Doctor, Encounter, EncounterCharge,
    EscalationRule, FollowUpTask, Patient, QueueToken, ServiceCatalog, User, VitalSet,
)
from app.schemas.clinical import ConsultationIn, VitalsIn
from app.services import hospital_service
from app.services.health_history_service import age_of

DEFAULT_RULES = [   # the hospital reviews and changes these in the admin screen; they are plain numbers, no AI
    ("spo2", "LT", 90, "CRITICAL", "Oxygen level below 90 %"), ("spo2", "LT", 94, "WARNING", "Oxygen level below 94 %"),
    ("pulse", "GT", 130, "CRITICAL", "Pulse above 130"), ("pulse", "LT", 40, "CRITICAL", "Pulse below 40"), ("pulse", "GT", 110, "WARNING", "Pulse above 110"),
    ("bp_systolic", "LT", 90, "CRITICAL", "Upper blood pressure below 90"), ("bp_systolic", "GT", 180, "CRITICAL", "Upper blood pressure above 180"), ("bp_systolic", "GT", 160, "WARNING", "Upper blood pressure above 160"),
    ("resp_rate", "GT", 30, "CRITICAL", "Breathing rate above 30"), ("resp_rate", "LT", 8, "CRITICAL", "Breathing rate below 8"),
    ("temperature_f", "GT", 103, "CRITICAL", "Temperature above 103 F"), ("temperature_f", "GT", 100.4, "WARNING", "Fever (above 100.4 F)"),
    ("gcs", "LT", 9, "CRITICAL", "Glasgow coma score below 9"),
]


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def seed_rules(db: Session) -> None:
    if db.scalar(select(func.count(EscalationRule.id))) == 0:
        for parameter, comparison, threshold, level, message in DEFAULT_RULES:
            db.add(EscalationRule(parameter=parameter, comparison=comparison, threshold=threshold, level=level, message=message, is_active=True))
        db.commit()


DEFAULT_TEMPLATE = [{"key": "allergy_checked", "label": "Allergies confirmed with the patient", "kind": "choice", "options": ["Yes", "No allergies", "Not asked"]},
                    {"key": "general_exam", "label": "General examination", "kind": "longtext", "options": []}]
DEPARTMENT_TEMPLATES = {      # starting exam fields per department; the administrator changes or adds more
    "Cardiology": [("bp_both_arms", "Blood pressure, both arms", "text"), ("heart_sounds", "Heart sounds", "longtext"), ("peripheral_pulses", "Peripheral pulses", "text"), ("ecg_note", "ECG note", "text")],
    "Orthopedics": [("joint_exam", "Joint examination", "longtext"), ("range_of_motion", "Range of movement", "text"), ("neurovascular", "Neurovascular status", "text")],
    "Pediatrics": [("growth", "Growth and development", "longtext"), ("immunisation", "Immunisation status", "text"), ("feeding", "Feeding history", "text")],
    "Gynecology & Obstetrics": [("lmp", "Last menstrual period", "text"), ("obstetric_formula", "Obstetric formula (G P L A)", "text"), ("pelvic_exam", "Pelvic examination", "longtext")],
    "Ophthalmology": [("visual_acuity", "Visual acuity (right / left)", "text"), ("iop", "Eye pressure", "text"), ("slit_lamp", "Slit lamp findings", "longtext")],
    "ENT": [("ear_exam", "Ear examination", "longtext"), ("nose_exam", "Nose examination", "longtext"), ("throat_exam", "Throat examination", "longtext")],
    "Dermatology": [("lesion_description", "Description of the lesions", "longtext"), ("distribution", "Distribution", "text")],
    "Neurology": [("gcs_note", "Consciousness", "text"), ("cranial_nerves", "Cranial nerves", "longtext"), ("motor_power", "Motor power", "text"), ("reflexes", "Reflexes", "text")],
}


def seed_templates(db: Session) -> None:
    """Start-up: one default template, and a starting exam list for a few departments. Only when there is none yet; the administrator owns them afterwards."""
    if db.scalar(select(func.count(ConsultationTemplate.id))):
        return
    db.add(ConsultationTemplate(department_id=None, name="Default consultation", fields_json=json.dumps(DEFAULT_TEMPLATE), is_active=True))
    for name, fields in DEPARTMENT_TEMPLATES.items():
        dept = db.scalar(select(Department).where(func.lower(Department.name) == name.lower()))
        if dept:
            db.add(ConsultationTemplate(department_id=dept.id, name=f"{name} consultation", is_active=True,
                                        fields_json=json.dumps([{"key": k, "label": label, "kind": kind, "options": []} for k, label, kind in fields])))
    db.commit()


# ------------------------------------------------------------------ encounters and tokens
def open_encounter(db: Session, patient: Patient, enc_type: str, *, doctor: Doctor | None, department_id: int | None, source: str, user: User | None,
                   appointment: Appointment | None = None) -> Encounter:
    encounter = Encounter(patient_id=patient.id, branch_id=patient.branch_id or hospital_service.default_branch(db).id, department_id=department_id or (doctor.department_id if doctor else None),
                          type=enc_type, status="OPEN", source=source, attending_doctor_id=doctor.id if doctor else None, appointment_id=appointment.id if appointment else None,
                          created_by=user.id if user else None)
    db.add(encounter)
    db.flush()
    if appointment is not None:
        appointment.encounter_id = encounter.id
    return encounter


def issue_token(db: Session, encounter: Encounter, doctor: Doctor, urgent: bool = False) -> QueueToken:
    """The next number of this doctor for today. The unique rule (doctor, day, number) means two people checked in at the same moment can never get the same token;
    the loser of the race simply takes the next number."""
    today = date.today()
    for _ in range(5):
        number = (db.scalar(select(func.max(QueueToken.number)).where(QueueToken.doctor_id == doctor.id, QueueToken.token_date == today)) or 0) + 1
        token = QueueToken(encounter_id=encounter.id, doctor_id=doctor.id, branch_id=encounter.branch_id, token_date=today, number=number, urgent=urgent, status="WAITING")
        try:
            with db.begin_nested():
                db.add(token)
                db.flush()
            return token
        except IntegrityError:
            continue
    raise HTTPException(409, "Could not give a token. Please try again.")


def patient_line(p: Patient) -> dict:
    return {"id": p.id, "uhid": p.uhid, "patient_code": p.patient_code, "full_name": p.user.full_name, "age": age_of(p), "gender": p.gender}


def token_out(t: QueueToken) -> dict:
    enc = t.encounter
    waited = int((now() - t.created_at).total_seconds() // 60) if t.status == "WAITING" else None
    return {"id": t.id, "number": t.number, "status": t.status, "urgent": t.urgent, "doctor_id": t.doctor_id, "doctor_name": t.doctor.user.full_name, "encounter_id": t.encounter_id,
            "patient": patient_line(enc.patient), "checked_in_at": t.created_at.isoformat(), "waiting_minutes": waited, "source": enc.source,
            "appointment_time": enc.appointment.scheduled_at.isoformat() if getattr(enc, "appointment", None) else None}


def queue(db: Session, day: date, doctor_id: int | None) -> list[dict]:
    query = select(QueueToken).where(QueueToken.token_date == day).order_by(QueueToken.number)
    if doctor_id:
        query = query.where(QueueToken.doctor_id == doctor_id)
    rows = list(db.scalars(query))
    rank = {"IN_CONSULTATION": 0, "CALLED": 1, "WAITING": 2, "DONE": 3, "NO_SHOW": 4, "CANCELLED": 5}
    rows.sort(key=lambda t: (rank.get(t.status, 9), not t.urgent, t.number))
    return [token_out(t) for t in rows]


def call_token(db: Session, token: QueueToken) -> QueueToken:
    if token.status not in ("WAITING", "CALLED"):
        raise HTTPException(409, "This token is already finished.")
    token.status, token.called_at = "IN_CONSULTATION", now()
    db.commit()
    return token


def next_waiting(db: Session, doctor: Doctor) -> QueueToken | None:
    rows = db.scalars(select(QueueToken).where(QueueToken.doctor_id == doctor.id, QueueToken.token_date == date.today(), QueueToken.status == "WAITING")).all()
    rows.sort(key=lambda t: (not t.urgent, t.number))
    return rows[0] if rows else None


# ------------------------------------------------------------------ who may handle an encounter
def encounter_for_user(db: Session, user: User, encounter_id: int, *, write: bool = False) -> Encounter:
    """A doctor works on an encounter that is theirs (or one they may reach through a referral); a nurse on an open one. 404 for a missing one, 403 for another's."""
    encounter = db.get(Encounter, encounter_id)
    if encounter is None:
        raise HTTPException(404, "Visit not found.")
    if user.role == DOCTOR:
        doctor = get_doctor_profile(db, user)
        if write and encounter.attending_doctor_id not in (None, doctor.id):
            raise forbidden()
        get_accessible_patient(db, user, encounter.patient_id, clinical=True)
    elif user.role == NURSE:
        get_accessible_patient(db, user, encounter.patient_id, clinical=True)
    else:
        raise forbidden()
    return encounter


# ------------------------------------------------------------------ vitals and alert rules
def vitals_out(v: VitalSet) -> dict:
    return {"id": v.id, "recorded_at": v.recorded_at.isoformat(), "recorded_by": v.recorder.full_name if v.recorder else None, "pulse": v.pulse, "bp_systolic": v.bp_systolic,
            "bp_diastolic": v.bp_diastolic, "temperature_f": v.temperature_f, "resp_rate": v.resp_rate, "spo2": v.spo2, "weight_kg": v.weight_kg, "height_cm": v.height_cm,
            "pain_score": v.pain_score, "gcs": v.gcs, "note": v.note, "encounter_id": v.encounter_id, "admission_id": v.admission_id}


def record_vitals(db: Session, patient: Patient, data: VitalsIn, user: User, *, encounter_id: int | None = None, admission_id: int | None = None) -> tuple[VitalSet, list[ClinicalAlert]]:
    """Saves the set and raises alerts from the hospital's own threshold rules. A critical alert never depends on AI and never waits for anybody."""
    values = data.model_dump()
    note = values.pop("note")
    v = VitalSet(patient_id=patient.id, encounter_id=encounter_id, admission_id=admission_id, recorded_by=user.id, note=note, **values)
    db.add(v)
    db.flush()
    crossed: dict[str, EscalationRule] = {}                   # the most serious rule that this measurement crossed, one per measurement
    for rule in db.scalars(select(EscalationRule).where(EscalationRule.is_active.is_(True)).order_by(EscalationRule.id)):
        value = values.get(rule.parameter)
        if value is None or not (value < rule.threshold if rule.comparison == "LT" else value > rule.threshold):
            continue
        best = crossed.get(rule.parameter)
        if best is None or (rule.level == "CRITICAL" and best.level != "CRITICAL"):
            crossed[rule.parameter] = rule
    alerts = []
    for parameter, rule in crossed.items():
        alert = ClinicalAlert(patient_id=patient.id, encounter_id=encounter_id, admission_id=admission_id, vital_set_id=v.id, rule_id=rule.id, level=rule.level,
                              message=f"{rule.message} (measured {values[parameter]:g})")
        db.add(alert)
        alerts.append(alert)
    db.flush()
    return v, alerts


def alert_out(a: ClinicalAlert) -> dict:
    return {"id": a.id, "level": a.level, "message": a.message, "status": a.status, "patient_id": a.patient_id, "patient_name": a.patient.user.full_name, "uhid": a.patient.uhid,
            "admission_id": a.admission_id, "encounter_id": a.encounter_id, "created_at": a.created_at.isoformat(), "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
            "ack_note": a.ack_note}


# ------------------------------------------------------------------ consultation
def consultation_out(c: Consultation | None) -> dict | None:
    if c is None:
        return None
    return {"id": c.id, "encounter_id": c.encounter_id, "status": c.status, "complaint": c.complaint, "hpi": c.hpi, "past_history": c.past_history, "family_history": c.family_history,
            "examination": c.examination, "assessment": c.assessment, "plan": c.plan, "advice": c.advice, "follow_up_date": c.follow_up_date.isoformat() if c.follow_up_date else None,
            "template_id": c.template_id, "data": json.loads(c.data_json) if c.data_json else {}, "signed_at": c.signed_at.isoformat() if c.signed_at else None,
            "doctor_name": c.doctor.user.full_name, "updated_at": c.updated_at.isoformat()}


def template_for(db: Session, department_id: int | None) -> ConsultationTemplate | None:
    base = select(ConsultationTemplate).where(ConsultationTemplate.is_active.is_(True))
    return (department_id and db.scalar(base.where(ConsultationTemplate.department_id == department_id).order_by(ConsultationTemplate.id.desc()))) or \
        db.scalar(base.where(ConsultationTemplate.department_id.is_(None)).order_by(ConsultationTemplate.id.desc()))


def template_out(t: ConsultationTemplate | None) -> dict | None:
    return None if t is None else {"id": t.id, "name": t.name, "department_id": t.department_id, "fields": json.loads(t.fields_json), "is_active": t.is_active}


def get_or_create_consultation(db: Session, encounter: Encounter, doctor: Doctor) -> Consultation:
    c = db.scalar(select(Consultation).where(Consultation.encounter_id == encounter.id))
    if c is None:
        t = template_for(db, encounter.department_id)
        c = Consultation(encounter_id=encounter.id, patient_id=encounter.patient_id, doctor_id=doctor.id, template_id=t.id if t else None, status="DRAFT")
        db.add(c)
        db.flush()
    return c


def save_consultation(db: Session, c: Consultation, data: ConsultationIn) -> Consultation:
    if c.status == "SIGNED":
        raise HTTPException(409, "This consultation is signed. Please add a dated addendum instead of changing it.")
    if data.follow_up_date and data.follow_up_date < date.today():
        raise HTTPException(422, "The follow-up date cannot be in the past.")
    for key in ("complaint", "hpi", "past_history", "family_history", "examination", "assessment", "plan", "advice", "follow_up_date"):
        setattr(c, key, getattr(data, key))
    if data.template_id:
        if db.get(ConsultationTemplate, data.template_id) is None:
            raise HTTPException(422, "The selected template does not exist.")
        c.template_id = data.template_id
    c.data_json = json.dumps(data.data) if data.data else None
    c.updated_at = now()
    return c


def consultation_charge(db: Session, encounter: Encounter, user: User) -> EncounterCharge | None:
    """The consultation fee from the price list (the department's service, else the general one). No price in the list = no invented charge."""
    base = select(ServiceCatalog).where(ServiceCatalog.category == "CONSULTATION", ServiceCatalog.is_active.is_(True))
    service = (encounter.department_id and db.scalar(base.where(ServiceCatalog.department_id == encounter.department_id).order_by(ServiceCatalog.id))) or \
        db.scalar(base.where(ServiceCatalog.department_id.is_(None)).order_by(ServiceCatalog.id))
    if service is None:
        return None
    charge = EncounterCharge(encounter_id=encounter.id, patient_id=encounter.patient_id, service_id=service.id, description=service.name, amount=service.price,
                             gst_percent=service.gst_percent, status="PENDING", created_by=user.id)
    db.add(charge)
    return charge


def sign_consultation(db: Session, encounter: Encounter, c: Consultation, doctor: Doctor, user: User) -> dict:
    if c.status == "SIGNED":
        raise HTTPException(409, "This consultation is already signed.")
    missing = []
    if not (c.complaint or "").strip():
        missing.append("the complaint")
    has_diagnosis = db.scalar(select(Diagnosis.id).where(Diagnosis.encounter_id == encounter.id, Diagnosis.is_active.is_(True)).limit(1)) is not None
    if not has_diagnosis and not (c.assessment or "").strip():
        missing.append("a diagnosis or an assessment")
    if missing:
        raise HTTPException(422, "Before signing, please write " + " and ".join(missing) + ".")
    c.status, c.signed_at, c.updated_at = "SIGNED", now(), now()
    charge = consultation_charge(db, encounter, user)
    if encounter.type == "OPD":
        encounter.status, encounter.ended_at = "CLOSED", now()
        token = db.scalar(select(QueueToken).where(QueueToken.encounter_id == encounter.id))
        if token and token.status != "DONE":
            token.status, token.finished_at = "DONE", now()
    if c.follow_up_date:
        db.add(FollowUpTask(patient_id=c.patient_id, created_by=doctor.id, title="Follow-up visit", details=f"After the consultation of {now().date().isoformat()}", due_date=c.follow_up_date,
                            source_type="consultation", source_id=c.id, status="PENDING"))
    db.commit()
    return {"signed_at": c.signed_at.isoformat(), "charge": None if charge is None else {"description": charge.description, "amount": charge.amount}}
