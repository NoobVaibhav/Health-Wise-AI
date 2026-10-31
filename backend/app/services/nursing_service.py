"""Nursing: the medication administration record (MAR), intake and output, and the chart of one inpatient."""
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    Admission, ClinicalAlert, IntakeOutput, MarEntry, MedicationOrder, NursingNote, VitalSet,
)
from app.services import encounter_service as enc

OVERDUE_AFTER_MINUTES = 30


def med_order_out(m: MedicationOrder) -> dict:
    return {"id": m.id, "admission_id": m.admission_id, "medicine_name": m.medicine_name, "dose": m.dose, "route": m.route, "times": m.times.split(","), "instructions": m.instructions,
            "start_date": m.start_date.isoformat(), "end_date": m.end_date.isoformat() if m.end_date else None, "status": m.status, "ordered_at": m.ordered_at.isoformat()}


def generate_mar(db: Session, admission: Admission, day: date) -> int:
    """Makes the dose rows of the day from the active orders. Repeating it changes nothing (a dose exists once)."""
    made = 0
    for order in db.scalars(select(MedicationOrder).where(MedicationOrder.admission_id == admission.id, MedicationOrder.status == "ACTIVE")):
        if day < order.start_date or (order.end_date and day > order.end_date):
            continue
        for clock in order.times.split(","):
            hour, minute = (int(x) for x in clock.split(":"))
            when = datetime.combine(day, time(hour, minute))
            if db.scalar(select(MarEntry.id).where(MarEntry.medication_order_id == order.id, MarEntry.scheduled_at == when)) is None:
                db.add(MarEntry(medication_order_id=order.id, scheduled_at=when, status="PENDING"))
                made += 1
    db.flush()
    return made


def mar_out(e: MarEntry) -> dict:
    overdue = e.status == "PENDING" and e.scheduled_at < datetime.now() - timedelta(minutes=OVERDUE_AFTER_MINUTES)     # dose times are the ward's clock (local), not UTC
    return {"id": e.id, "order_id": e.medication_order_id, "medicine_name": e.order.medicine_name, "dose": e.order.dose, "route": e.order.route, "instructions": e.order.instructions,
            "scheduled_at": e.scheduled_at.isoformat(), "status": e.status, "overdue": overdue, "acted_at": e.acted_at.isoformat() if e.acted_at else None, "note": e.note,
            "order_status": e.order.status}


def mar_day(db: Session, admission: Admission, day: date) -> list[dict]:
    if admission.status == "ADMITTED":
        generate_mar(db, admission, day)
        db.commit()
    start, end = datetime.combine(day, time.min), datetime.combine(day, time.max)
    rows = db.scalars(select(MarEntry).join(MedicationOrder, MedicationOrder.id == MarEntry.medication_order_id)
                      .where(MedicationOrder.admission_id == admission.id, MarEntry.scheduled_at >= start, MarEntry.scheduled_at <= end).order_by(MarEntry.scheduled_at, MarEntry.id)).all()
    return [mar_out(e) for e in rows]


def act_on_dose(db: Session, entry: MarEntry, status: str, note: str | None, user) -> MarEntry:
    if entry.status != "PENDING":
        raise HTTPException(409, f"This dose was already recorded as {entry.status.lower()}.")
    if entry.order.status != "ACTIVE":
        raise HTTPException(409, "The doctor has stopped this medicine.")
    if entry.scheduled_at > datetime.now() + timedelta(hours=1):
        raise HTTPException(409, "This dose is not due yet.")
    entry.status, entry.acted_by, entry.acted_at, entry.note = status, user.id, enc.now(), note
    return entry


def totals(db: Session, admission_id: int, day: date) -> dict:
    start, end = datetime.combine(day, time.min), datetime.combine(day, time.max)
    out = {}
    for kind in ("INTAKE", "OUTPUT"):
        out[kind.lower()] = db.scalar(select(func.coalesce(func.sum(IntakeOutput.amount_ml), 0)).where(IntakeOutput.admission_id == admission_id, IntakeOutput.kind == kind,
                                                                                                    IntakeOutput.recorded_at >= start, IntakeOutput.recorded_at <= end)) or 0
    out["balance"] = out["intake"] - out["output"]
    return out


def chart(db: Session, admission: Admission, day: date) -> dict:
    vitals = db.scalars(select(VitalSet).where(VitalSet.admission_id == admission.id).order_by(VitalSet.recorded_at.desc()).limit(30)).all()
    notes = db.scalars(select(NursingNote).where(NursingNote.admission_id == admission.id).order_by(NursingNote.id.desc()).limit(40)).all()
    io = db.scalars(select(IntakeOutput).where(IntakeOutput.admission_id == admission.id).order_by(IntakeOutput.id.desc()).limit(40)).all()
    alerts = db.scalars(select(ClinicalAlert).where(ClinicalAlert.admission_id == admission.id, ClinicalAlert.status == "OPEN")).all()
    plan = next((n for n in notes if n.kind == "CARE_PLAN"), None)
    handover = next((n for n in notes if n.kind == "HANDOVER"), None)
    mar = mar_day(db, admission, day)
    return {
        "vitals": [enc.vitals_out(v) for v in vitals],
        "notes": [{"id": n.id, "kind": n.kind, "shift": n.shift, "text": n.text, "by": n.author.full_name, "at": n.created_at.isoformat()} for n in notes],
        "care_plan": None if plan is None else {"text": plan.text, "by": plan.author.full_name, "at": plan.created_at.isoformat()},
        "handover": None if handover is None else {"shift": handover.shift, "text": handover.text, "by": handover.author.full_name, "at": handover.created_at.isoformat()},
        "mar": mar, "pending_doses": sum(1 for m in mar if m["status"] == "PENDING"), "overdue_doses": sum(1 for m in mar if m["overdue"]),
        "intake_output": [{"id": r.id, "kind": r.kind, "item": r.item, "amount_ml": r.amount_ml, "at": r.recorded_at.isoformat()} for r in io], "totals": totals(db, admission.id, day),
        "alerts": [enc.alert_out(a) for a in alerts],
    }
