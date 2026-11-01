"""Laboratory work: follow every test a doctor advised from order to result.

waiting for the sample -> sample taken (a label code is made) -> being tested -> done (the result report is attached)
A test can also be rejected (for example a bad sample, a reason is required) and then ordered again.
The result is an ordinary report: it goes to the doctor for review, and the patient sees it only after that."""
from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import HealthReport, LabTestOrder, Patient, Prescription, User, utcnow
from app.services import diagnostic_service
from app.services.serializers import tests_of

LABELS = {"ORDERED": "Waiting for the sample", "SAMPLE_COLLECTED": "Sample taken", "IN_PROGRESS": "Being tested", "COMPLETED": "Result ready",
          "REJECTED": "Sample rejected", "CANCELLED": "Cancelled"}
# what the patient is told, in plain words
PATIENT_LABELS = {"ORDERED": "Please go to the laboratory to give the sample", "SAMPLE_COLLECTED": "Sample taken, the test will start soon", "IN_PROGRESS": "Your sample is being tested",
                  "COMPLETED": "Result ready: your doctor will review it", "REJECTED": "The sample could not be used: please give it again", "CANCELLED": "Cancelled by the doctor"}
OPEN = ("ORDERED", "SAMPLE_COLLECTED", "IN_PROGRESS")
SAMPLE_TYPES = ["Blood", "Urine", "Stool", "Sputum", "Swab", "Other"]
# "COMPLETED" is never set by hand: it happens only when the result report is uploaded
TRANSITIONS = {"ORDERED": {"SAMPLE_COLLECTED", "REJECTED"}, "SAMPLE_COLLECTED": {"IN_PROGRESS", "REJECTED"}, "IN_PROGRESS": {"REJECTED"}, "REJECTED": {"ORDERED"}}


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def sync_orders(db: Session) -> None:
    """Make one order row for every test written on a prescription (once), and cancel open orders of cancelled prescriptions."""
    rxs = db.scalars(select(Prescription).where(Prescription.tests_advised.is_not(None), Prescription.status.notin_(("PENDING_COUNTERSIGN", "RETURNED"))).order_by(Prescription.id.desc()).limit(500)).all()
    if not rxs:
        return
    existing = {(o.prescription_id, o.test_name.lower()): o for o in db.scalars(select(LabTestOrder).where(LabTestOrder.prescription_id.in_([r.id for r in rxs])))}
    changed = False
    for rx in rxs:
        seen = set()
        for name in tests_of(rx):
            key = (rx.id, name.lower())
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            order = existing.get(key)
            if order is None:
                db.add(LabTestOrder(prescription_id=rx.id, patient_id=rx.patient_id, doctor_id=rx.doctor_id, test_name=name, status="CANCELLED" if rx.status == "CANCELLED" else "ORDERED",
                                    created_at=rx.created_at or utcnow()))
                changed = True
            elif rx.status == "CANCELLED" and order.status in OPEN:
                order.status, order.updated_at = "CANCELLED", utcnow()
                changed = True
    if changed:
        try:
            db.commit()
        except IntegrityError:                                          # another request made the same rows a moment ago: that is fine
            db.rollback()


def get_order(db: Session, order_id: int) -> LabTestOrder:
    order = db.get(LabTestOrder, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test not found.")
    return order


def _next_sample_code(db: Session) -> str:
    stamp = date.today().strftime("%Y%m%d")
    count = len(db.scalars(select(LabTestOrder.id).where(LabTestOrder.sample_code.like(f"LAB-{stamp}-%"))).all())
    while True:
        count += 1
        code = f"LAB-{stamp}-{count:04d}"
        if not db.scalar(select(LabTestOrder.id).where(LabTestOrder.sample_code == code)):
            return code


def change_status(db: Session, order: LabTestOrder, new: str, user: User, note: str | None = None, sample_type: str | None = None) -> LabTestOrder:
    if order.status in ("COMPLETED", "CANCELLED"):
        raise conflict(f"This test is {LABELS[order.status].lower()} and cannot be changed.")
    if new not in TRANSITIONS.get(order.status, set()):
        raise conflict(f"A test that is '{LABELS[order.status].lower()}' cannot be moved to '{LABELS.get(new, new).lower()}'.")
    now = utcnow()
    if new == "SAMPLE_COLLECTED":
        if sample_type and sample_type not in SAMPLE_TYPES:
            raise HTTPException(422, "Please choose the sample type from the list.")
        order.sample_type, order.collected_at, order.collected_by = sample_type or "Blood", now, user.id
        order.sample_code = _next_sample_code(db)
        order.rejection_reason = None
    elif new == "IN_PROGRESS":
        order.started_at = now
    elif new == "REJECTED":
        if not note or len(note.strip()) < 3:
            raise HTTPException(422, "Please write why the sample is rejected.")
        order.rejection_reason = note.strip()
    elif new == "ORDERED":                                              # a rejected test is ordered again: the new sample gets a new label
        order.sample_type = order.sample_code = order.collected_at = order.collected_by = order.started_at = None
    if note and new != "REJECTED":
        order.note = note.strip()
    order.status, order.updated_at, order.updated_by = new, now, user.id
    db.commit()
    return order


def attach_result(db: Session, order: LabTestOrder, user: User, report: HealthReport) -> LabTestOrder:
    now = utcnow()
    order.status, order.report_id, order.completed_at, order.completed_by, order.updated_at, order.updated_by = "COMPLETED", report.id, now, user.id, now, user.id
    if order.started_at is None:
        order.started_at = now
    db.commit()
    return order


def set_urgent(db: Session, order: LabTestOrder, urgent: bool, user: User) -> LabTestOrder:
    if order.status not in OPEN:
        raise conflict("Only a test that is still open can be marked urgent.")
    order.urgent, order.updated_at, order.updated_by = urgent, utcnow(), user.id
    db.commit()
    return order


def _hours(since: datetime | None, until: datetime | None = None) -> float | None:
    return round(((until or utcnow()) - since).total_seconds() / 3600, 1) if since else None


def order_out(o: LabTestOrder, for_lab: bool = True) -> dict:
    out = {"id": o.id, "test_name": o.test_name, "status": o.status, "status_label": LABELS[o.status], "urgent": bool(o.urgent), "sample_type": o.sample_type, "sample_code": o.sample_code,
           "collected_at": o.collected_at.isoformat() if o.collected_at else None, "started_at": o.started_at.isoformat() if o.started_at else None,
           "completed_at": o.completed_at.isoformat() if o.completed_at else None, "rejection_reason": o.rejection_reason, "note": o.note,
           "ordered_on": o.created_at.date().isoformat(), "waiting_hours": _hours(o.created_at) if o.status in OPEN else None,
           "prescription_code": f"RX-{o.prescription_id:05d}" if o.prescription_id else "Encounter order", "doctor_name": o.doctor.user.full_name,
           "result_status": o.result_status, "has_critical": bool(o.has_critical)}
    if for_lab:
        out.update({"patient_name": o.patient.user.full_name, "patient_code": o.patient.patient_code, "reason": o.prescription.clinical_indication if o.prescription else None, "transitions": sorted(TRANSITIONS.get(o.status, set()))})
    return out


def worklist(db: Session, status_filter: str | None, q: str | None, urgent_only: bool = False) -> list[dict]:
    sync_orders(db)
    diagnostic_service.sync_clinical_orders(db)
    query = select(LabTestOrder).order_by(LabTestOrder.urgent.desc(), LabTestOrder.id.desc()).limit(500)
    if status_filter == "OPEN":
        query = query.where(LabTestOrder.status.in_(OPEN))
    elif status_filter:
        query = query.where(LabTestOrder.status == status_filter)
    if urgent_only:
        query = query.where(LabTestOrder.urgent.is_(True))
    needle = (q or "").strip().lower()
    rows = []
    for o in db.scalars(query):
        out = order_out(o)
        if needle and needle not in " ".join([out["patient_name"], out["patient_code"], out["prescription_code"], out["test_name"], out["sample_code"] or ""]).lower():
            continue
        rows.append(out)
    return rows


def dashboard(db: Session) -> dict:
    sync_orders(db)
    diagnostic_service.sync_clinical_orders(db)
    rows = db.scalars(select(LabTestOrder)).all()
    counts = {k: 0 for k in LABELS}
    for o in rows:
        counts[o.status] += 1
    today = date.today()
    since = utcnow() - timedelta(days=30)
    done = [o for o in rows if o.status == "COMPLETED" and o.completed_at and o.completed_at >= since and o.collected_at]
    oldest = max((_hours(o.created_at) or 0 for o in rows if o.status in OPEN), default=None)
    return {"counts": counts, "open": sum(counts[k] for k in OPEN), "urgent_open": sum(1 for o in rows if o.urgent and o.status in OPEN),
            "done_today": sum(1 for o in rows if o.completed_at and o.completed_at.date() == today),
            "oldest_waiting_hours": oldest, "average_turnaround_hours": round(sum(_hours(o.collected_at, o.completed_at) or 0 for o in done) / len(done), 1) if done else None,
            "rejected_open": counts["REJECTED"]}


def for_patient(db: Session, patient: Patient, as_doctor: bool) -> list[dict]:
    """A patient's tests. The patient gets plain wording and a link to the result only after the doctor has reviewed it."""
    sync_orders(db)
    diagnostic_service.sync_clinical_orders(db)
    out = []
    for o in db.scalars(select(LabTestOrder).where(LabTestOrder.patient_id == patient.id).order_by(LabTestOrder.id.desc())):
        row = order_out(o, for_lab=False)
        report = db.get(HealthReport, o.report_id) if o.report_id else None
        reviewed = bool(report and report.doctor_review_status == "REVIEWED")
        row["report_id"] = report.id if report and (as_doctor or reviewed) else None
        row["result_reviewed"] = reviewed
        detail = diagnostic_service.lab_detail(db, o, "DOCTOR" if as_doctor else "PATIENT")
        row.update({k: detail[k] for k in ("result_status", "has_critical", "doctor_seen_at", "results")})
        structured = o.result_status == "APPROVED"
        row["patient_message"] = PATIENT_LABELS[o.status] if not (o.status == "COMPLETED" and (reviewed or (structured and o.doctor_seen_at))) else "Result reviewed by your doctor"
        if structured and not as_doctor and not o.doctor_seen_at:
            row["patient_message"] = "Result ready: your doctor will review it"
        if not as_doctor:
            for k in ("sample_code", "note"):
                row.pop(k, None)
        out.append(row)
    return out
