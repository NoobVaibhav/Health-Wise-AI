"""Nursing: the ward worklist, an inpatient's chart (vitals, notes, medicines given, intake and output), alerts and the alert thresholds."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, NURSE, get_accessible_patient
from app.database.connection import get_db
from app.database.models import Admission, ClinicalAlert, EscalationRule, IntakeOutput, MarEntry, MedicationOrder, NursingNote, User
from app.schemas.clinical import AckIn, IntakeOutputIn, MarActIn, NursingNoteIn, RuleIn, VitalsIn
from app.services import audit_service, encounter_service as enc, ipd_service as ipd, nursing_service as nursing
from app.services.access_service import require_permission
from app.utils.validators import PathId

router = APIRouter(prefix="/api/nursing", tags=["nursing"])
chart_perm = require_permission("nursing.chart")
view_perm = require_permission("nursing.chart", "ipd.notes")
vitals_perm = require_permission("vitals.record")
ack_perm = require_permission("alert.ack")


def _admission(db: Session, user: User, admission_id: int) -> Admission:
    a = db.get(Admission, admission_id)
    if a is None:
        raise HTTPException(404, "Admission not found.")
    get_accessible_patient(db, user, a.patient_id, clinical=True)          # a nurse: an inpatient or open visit; a doctor: only a patient of theirs
    return a


@router.get("/dashboard")
def dashboard(user: User = Depends(chart_perm), db: Session = Depends(get_db)):
    """The nurse's first screen: open alerts, then inpatients with their overdue and pending medicines."""
    patients = []
    day = date.today()
    for a in db.scalars(select(Admission).where(Admission.status == "ADMITTED").order_by(Admission.admitted_at)):
        mar = nursing.mar_day(db, a, day)
        latest = db.scalar(select(enc.VitalSet).where(enc.VitalSet.admission_id == a.id).order_by(enc.VitalSet.recorded_at.desc()).limit(1))
        bed = ipd.active_assignment(db, a.id)
        patients.append({"admission_id": a.id, "admission_no": a.admission_no, "patient": enc.patient_line(a.patient), "bed": f"{bed.bed.ward.name} {bed.bed.code}" if bed else None,
                         "pending_doses": sum(1 for m in mar if m["status"] == "PENDING"), "overdue_doses": sum(1 for m in mar if m["overdue"]),
                         "last_vitals": enc.vitals_out(latest) if latest else None,
                         "open_alerts": db.query(ClinicalAlert).filter(ClinicalAlert.admission_id == a.id, ClinicalAlert.status == "OPEN").count()})
    patients.sort(key=lambda p: (-p["overdue_doses"], -p["open_alerts"], p["admission_no"]))
    alerts = db.scalars(select(ClinicalAlert).where(ClinicalAlert.status == "OPEN").order_by(ClinicalAlert.level, ClinicalAlert.id.desc()).limit(50)).all()
    return {"patients": patients, "alerts": [enc.alert_out(a) for a in alerts], "open_alerts": len(alerts)}


@router.get("/admissions/{admission_id}/chart")
def get_chart(admission_id: PathId, day: date | None = None, user: User = Depends(view_perm), db: Session = Depends(get_db)):
    a = _admission(db, user, admission_id)
    return {"admission": ipd.admission_out(db, a), **nursing.chart(db, a, day or date.today())}


@router.post("/admissions/{admission_id}/vitals", status_code=status.HTTP_201_CREATED)
def add_vitals(admission_id: PathId, data: VitalsIn, user: User = Depends(vitals_perm), db: Session = Depends(get_db)):
    a = _admission(db, user, admission_id)
    if a.status != "ADMITTED":
        raise HTTPException(409, "This patient has been discharged.")
    v, alerts = enc.record_vitals(db, a.patient, data, user, encounter_id=a.encounter_id, admission_id=a.id)
    db.commit()
    return {"vitals": enc.vitals_out(v), "alerts": [{"level": x.level, "message": x.message} for x in alerts]}


@router.post("/admissions/{admission_id}/notes", status_code=status.HTTP_201_CREATED)
def add_note(admission_id: PathId, data: NursingNoteIn, request: Request, user: User = Depends(chart_perm), db: Session = Depends(get_db)):
    a = _admission(db, user, admission_id)
    if a.status != "ADMITTED":
        raise HTTPException(409, "This patient has been discharged.")
    row = NursingNote(admission_id=a.id, encounter_id=a.encounter_id, patient_id=a.patient_id, kind=data.kind, shift=data.shift, text=data.text, created_by=user.id)
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, audit_service.NURSING_NOTE_ADDED, "admission", a.id, request, data.kind)
    return {"id": row.id, "kind": row.kind, "at": row.created_at.isoformat()}


@router.post("/admissions/{admission_id}/intake-output", status_code=status.HTTP_201_CREATED)
def add_intake_output(admission_id: PathId, data: IntakeOutputIn, user: User = Depends(chart_perm), db: Session = Depends(get_db)):
    a = _admission(db, user, admission_id)
    if a.status != "ADMITTED":
        raise HTTPException(409, "This patient has been discharged.")
    row = IntakeOutput(admission_id=a.id, patient_id=a.patient_id, kind=data.kind, item=data.item, amount_ml=data.amount_ml, recorded_by=user.id)
    db.add(row)
    db.commit()
    return {"id": row.id, "totals": nursing.totals(db, a.id, date.today())}


@router.post("/mar/{entry_id}/act")
def act(entry_id: PathId, data: MarActIn, request: Request, user: User = Depends(chart_perm), db: Session = Depends(get_db)):
    """The nurse records a dose: given, refused (with the reason) or held (with the reason). The name and the time are kept, and a recorded dose cannot be changed."""
    entry = db.get(MarEntry, entry_id)
    if entry is None:
        raise HTTPException(404, "Dose not found.")
    a = _admission(db, user, entry.order.admission_id)
    nursing.act_on_dose(db, entry, data.status, data.note, user)
    db.commit()
    audit_service.log_action(db, user, audit_service.MAR_ACTED, "admission", a.id, request, f"{entry.order.medicine_name[:60]} {data.status}")
    return nursing.mar_out(entry)


# ------------------------------------------------------------------ alerts
@router.get("/alerts")
def alerts(state: str = "OPEN", user: User = Depends(require_permission("alert.ack", "nursing.chart")), db: Session = Depends(get_db)):
    if state not in ("OPEN", "ACKNOWLEDGED"):
        raise HTTPException(422, "The state must be OPEN or ACKNOWLEDGED.")
    rows = db.scalars(select(ClinicalAlert).where(ClinicalAlert.status == state).order_by(ClinicalAlert.level, ClinicalAlert.id.desc()).limit(100)).all()
    if user.role == DOCTOR:
        from app.core.permissions import doctor_patient_ids, get_doctor_profile
        ids = doctor_patient_ids(db, get_doctor_profile(db, user))
        rows = [r for r in rows if r.patient_id in ids]
    return [enc.alert_out(a) for a in rows]


@router.post("/alerts/{alert_id}/ack")
def ack(alert_id: PathId, data: AckIn, request: Request, user: User = Depends(ack_perm), db: Session = Depends(get_db)):
    alert = db.get(ClinicalAlert, alert_id)
    if alert is None:
        raise HTTPException(404, "Alert not found.")
    get_accessible_patient(db, user, alert.patient_id, clinical=True)
    if alert.status == "OPEN":
        alert.status, alert.acknowledged_by, alert.acknowledged_at, alert.ack_note = "ACKNOWLEDGED", user.id, enc.now(), data.note
        db.commit()
        audit_service.log_action(db, user, audit_service.ALERT_ACKNOWLEDGED, "alert", alert.id, request, alert.level)
    return enc.alert_out(alert)


# ------------------------------------------------------------------ the thresholds (the hospital decides them)
def _rule_out(r: EscalationRule) -> dict:
    return {"id": r.id, "parameter": r.parameter, "comparison": r.comparison, "threshold": r.threshold, "level": r.level, "message": r.message, "is_active": r.is_active,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None}


@router.get("/escalation-rules")
def rules(user: User = Depends(require_permission("escalation.manage", "nursing.chart", "ipd.notes")), db: Session = Depends(get_db)):
    return [_rule_out(r) for r in db.scalars(select(EscalationRule).order_by(EscalationRule.parameter, EscalationRule.threshold))]


@router.post("/escalation-rules", status_code=status.HTTP_201_CREATED)
def add_rule(data: RuleIn, request: Request, user: User = Depends(require_permission("escalation.manage")), db: Session = Depends(get_db)):
    row = EscalationRule(**data.model_dump(), reviewed_by=user.id, reviewed_at=enc.now())
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, audit_service.HOSPITAL_CHANGED, "escalation_rule", row.id, request, f"{data.parameter} {data.comparison} {data.threshold}")
    return _rule_out(row)


@router.put("/escalation-rules/{rule_id}")
def update_rule(rule_id: PathId, data: RuleIn, request: Request, user: User = Depends(require_permission("escalation.manage")), db: Session = Depends(get_db)):
    row = db.get(EscalationRule, rule_id)
    if row is None:
        raise HTTPException(404, "Rule not found.")
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    row.reviewed_by, row.reviewed_at = user.id, enc.now()
    db.commit()
    audit_service.log_action(db, user, audit_service.HOSPITAL_CHANGED, "escalation_rule", row.id, request, f"{data.parameter} {data.comparison} {data.threshold}")
    return _rule_out(row)
