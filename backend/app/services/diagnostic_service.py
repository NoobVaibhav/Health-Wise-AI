"""Phase 4 diagnostics: structured laboratory results, critical values, pathologist approval, radiology orders and reports, and comparison with earlier results.

Rules that never depend on AI:
- the reference and critical limits come from the hospital's catalogue (an analyte without limits is shown as UNRATED, never guessed)
- a critical value raises an alert for the ordering doctor the moment the technician sends the result on
- only a pathologist (lab) or a radiologist (radiology) approves; an approved result or report is never edited
- the doctor sees a result only after approval; the patient sees it only after the doctor has seen it
"""
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import (
    ClinicalAlert, ClinicalOrder, Doctor, DiagnosticAnalyte, DiagnosticTest, LabResult, LabStaff, LabTestOrder, Patient, RadiologyOrder, RadiologyReport, RadiologyStaff, User, utcnow,
)

LAB_CATEGORIES = ("HAEMATOLOGY", "BIOCHEMISTRY", "CLINICAL_PATHOLOGY", "MICROBIOLOGY", "SEROLOGY", "IMMUNOLOGY", "HISTOPATHOLOGY", "URINE", "CARDIAC_MARKERS")
MODALITIES = ("XRAY", "ULTRASOUND", "CT", "MRI", "MAMMOGRAPHY", "ECHO", "ECG", "OTHER")
RADIOLOGY_LABELS = {"ORDERED": "Waiting to be scheduled", "SCHEDULED": "Scheduled", "IN_PROGRESS": "Scan being done", "REPORTED": "Waiting for the radiologist to approve",
                    "APPROVED": "Report ready", "CANCELLED": "Cancelled"}
RADIOLOGY_OPEN = ("ORDERED", "SCHEDULED", "IN_PROGRESS", "REPORTED")
FLAG_TEXT = {"NORMAL": "Normal", "LOW": "Low", "HIGH": "High", "CRITICAL_LOW": "Critically low", "CRITICAL_HIGH": "Critically high", "UNRATED": "No range set"}


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


# ------------------------------------------------------------------ migration of an older database
def migrate(db: Session) -> None:
    """lab_test_orders.prescription_id used to be required. A test ordered inside an encounter has no prescription, so the column must allow empty.
    SQLite cannot change that in place, so the table is rebuilt once (rows are copied as they are)."""
    bind = db.get_bind()
    if bind.dialect.name != "sqlite":
        if bind.dialect.name == "postgresql":
            db.execute(text("ALTER TABLE lab_test_orders ALTER COLUMN prescription_id DROP NOT NULL"))
            db.commit()
        return
    info = db.execute(text("PRAGMA table_info(lab_test_orders)")).all()
    if not any(row[1] == "prescription_id" and row[3] == 1 for row in info):
        return
    columns = ", ".join(f'"{row[1]}"' for row in info)
    db.commit()
    connection = db.connection()
    connection.execute(text("PRAGMA legacy_alter_table=ON"))
    connection.execute(text("PRAGMA foreign_keys=OFF"))
    for name, in connection.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='lab_test_orders' AND sql IS NOT NULL")).all():
        connection.execute(text(f'DROP INDEX "{name}"'))
    connection.execute(text("ALTER TABLE lab_test_orders RENAME TO lab_test_orders_old"))
    LabTestOrder.__table__.create(connection)
    connection.execute(text(f"INSERT INTO lab_test_orders ({columns}) SELECT {columns} FROM lab_test_orders_old"))
    connection.execute(text("DROP TABLE lab_test_orders_old"))
    connection.execute(text("PRAGMA foreign_keys=ON"))
    connection.execute(text("PRAGMA legacy_alter_table=OFF"))
    db.commit()


# ------------------------------------------------------------------ who is who
def is_pathologist(db: Session, user: User) -> bool:
    staff = db.scalar(select(LabStaff).where(LabStaff.user_id == user.id))
    return bool(staff and staff.staff_type == "PATHOLOGIST")


def radiology_type(db: Session, user: User) -> str:
    staff = db.scalar(select(RadiologyStaff).where(RadiologyStaff.user_id == user.id))
    return staff.staff_type if staff else "TECHNICIAN"


def match_test(db: Session, kind: str, name: str) -> DiagnosticTest | None:
    needle = name.strip().lower()
    tests = db.scalars(select(DiagnosticTest).where(DiagnosticTest.kind == kind, DiagnosticTest.is_active.is_(True))).all()
    for t in tests:
        if t.name.lower() == needle:
            return t
    for t in tests:                                                     # "CBC" written by the doctor, "CBC (Complete blood count)" in the catalogue
        if t.name.lower() in needle or needle in t.name.lower():
            return t
    return None


# ------------------------------------------------------------------ encounter orders become lab and radiology work
def sync_clinical_orders(db: Session) -> None:
    """Every LAB and RADIOLOGY order a doctor placed in an encounter becomes a lab test or a radiology order, once. A cancelled order cancels the open work."""
    rows = db.scalars(select(ClinicalOrder).where(ClinicalOrder.kind.in_(("LAB", "RADIOLOGY")), ClinicalOrder.status.in_(("ORDERED", "IN_PROGRESS", "CANCELLED")))
                      .order_by(ClinicalOrder.id.desc()).limit(500)).all()
    if not rows:
        return
    lab = {o.clinical_order_id: o for o in db.scalars(select(LabTestOrder).where(LabTestOrder.clinical_order_id.in_([r.id for r in rows])))}
    rad = {o.clinical_order_id: o for o in db.scalars(select(RadiologyOrder).where(RadiologyOrder.clinical_order_id.in_([r.id for r in rows])))}
    from app.database.models import Encounter
    changed = False
    for r in rows:
        existing = lab.get(r.id) or rad.get(r.id)
        if existing is not None:
            if r.status == "CANCELLED":
                if isinstance(existing, LabTestOrder) and existing.status in ("ORDERED", "SAMPLE_COLLECTED", "IN_PROGRESS"):
                    existing.status, existing.updated_at = "CANCELLED", utcnow()
                    changed = True
                if isinstance(existing, RadiologyOrder) and existing.status in RADIOLOGY_OPEN:
                    existing.status, existing.updated_at = "CANCELLED", utcnow()
                    changed = True
            continue
        if r.status == "CANCELLED":
            continue
        ordering = db.scalar(select(Doctor.id).where(Doctor.user_id == r.ordered_by))
        encounter = db.get(Encounter, r.encounter_id)
        doctor_id = ordering or (encounter.attending_doctor_id if encounter else None)
        if doctor_id is None:
            continue
        if r.kind == "LAB":
            test = match_test(db, "LAB", r.text)
            db.add(LabTestOrder(clinical_order_id=r.id, encounter_id=r.encounter_id, patient_id=r.patient_id, doctor_id=doctor_id, test_name=r.text, test_id=test.id if test else None,
                                urgent=r.priority in ("URGENT", "STAT"), status="ORDERED", created_at=r.ordered_at or utcnow()))
        else:
            test = match_test(db, "RADIOLOGY", r.text)
            db.add(RadiologyOrder(clinical_order_id=r.id, encounter_id=r.encounter_id, patient_id=r.patient_id, doctor_id=doctor_id, test_id=test.id if test else None, study=r.text,
                                  modality=test.category if test else "OTHER", priority=r.priority, clinical_info=r.note, created_at=r.ordered_at or utcnow()))
        changed = True
    if changed:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()


# ------------------------------------------------------------------ laboratory results
def flag_for(value: float | None, low: float | None, high: float | None, crit_low: float | None, crit_high: float | None) -> str:
    if value is None or (low is None and high is None and crit_low is None and crit_high is None):
        return "UNRATED"
    if crit_low is not None and value < crit_low:
        return "CRITICAL_LOW"
    if crit_high is not None and value > crit_high:
        return "CRITICAL_HIGH"
    if low is not None and value < low:
        return "LOW"
    if high is not None and value > high:
        return "HIGH"
    return "NORMAL"


def _number(text_value: str) -> float | None:
    try:
        return float(text_value.replace(",", "").strip())
    except ValueError:
        return None


def save_results(db: Session, order: LabTestOrder, user: User, items: list[dict], submit: bool) -> LabTestOrder:
    """The technician enters the measured values. Limits, unit and method are copied from the catalogue at this moment. Send on = submit for the pathologist."""
    if order.result_status in ("PENDING_APPROVAL", "APPROVED"):
        raise conflict("This result has already been sent for approval and cannot be changed." if order.result_status == "PENDING_APPROVAL" else "An approved result cannot be changed.")
    if order.status not in ("SAMPLE_COLLECTED", "IN_PROGRESS"):
        raise conflict("Take the sample first: a result can be entered only after the sample is taken." if order.status == "ORDERED" else f"This test is {order.status.lower()}, so a result cannot be entered.")
    analytes = {a.id: a for a in db.scalars(select(DiagnosticAnalyte).where(DiagnosticAnalyte.test_id == order.test_id))} if order.test_id else {}
    prepared = []
    seen = set()
    for item in items:
        analyte = analytes.get(item.get("analyte_id")) if item.get("analyte_id") else None
        if item.get("analyte_id") and analyte is None:
            raise HTTPException(422, "That value does not belong to this test.")
        name = analyte.name if analyte else (item.get("name") or "").strip()
        if not name:
            raise HTTPException(422, "Every value needs a name.")
        if name.lower() in seen:
            raise HTTPException(422, f"{name} is entered twice.")
        seen.add(name.lower())
        value_text = str(item.get("value", "")).strip()
        if not value_text:
            raise HTTPException(422, f"Please enter the value of {name}.")
        number = _number(value_text)
        if analyte is not None and number is None:
            raise HTTPException(422, f"The value of {name} must be a number.")
        low, high = (analyte.ref_low, analyte.ref_high) if analyte else (item.get("ref_low"), item.get("ref_high"))
        crit_low, crit_high = (analyte.critical_low, analyte.critical_high) if analyte else (None, None)
        prepared.append(LabResult(order_id=order.id, analyte_id=analyte.id if analyte else None, analyte_name=name, value_text=value_text, value_num=number,
                                  unit=(analyte.unit if analyte else item.get("unit")), method=(analyte.method if analyte else item.get("method")), ref_low=low, ref_high=high,
                                  flag=flag_for(number, low, high, crit_low, crit_high), comment=(item.get("comment") or None), entered_by=user.id))
    if submit and not prepared:
        raise HTTPException(422, "Enter at least one value before sending the result for approval.")
    for old in list(order.results):
        db.delete(old)
    db.flush()
    for r in prepared:
        db.add(r)
    now = utcnow()
    order.assigned_to = user.id
    order.status = "IN_PROGRESS"
    order.started_at = order.started_at or now
    order.has_critical = any(r.flag.startswith("CRITICAL") for r in prepared)
    order.result_status = "PENDING_APPROVAL" if submit else "DRAFT"
    order.updated_at, order.updated_by = now, user.id
    if submit and order.has_critical:
        critical = [r for r in prepared if r.flag.startswith("CRITICAL")]
        message = "Critical lab value: " + ", ".join(f"{r.analyte_name} {r.value_text} {r.unit or ''}".strip() for r in critical) + f" ({order.test_name}). Please act now; the result still waits for the pathologist."
        db.add(ClinicalAlert(patient_id=order.patient_id, encounter_id=order.encounter_id, level="CRITICAL", message=message[:300]))
    db.commit()
    return order


def approve_result(db: Session, order: LabTestOrder, user: User, note: str | None) -> LabTestOrder:
    if order.result_status != "PENDING_APPROVAL":
        raise conflict("Only a result that was sent for approval can be approved." if order.result_status != "APPROVED" else "This result is already approved.")
    if order.assigned_to == user.id:
        raise conflict("The person who entered the result cannot approve it: a second person must check it.")
    now = utcnow()
    order.result_status, order.status = "APPROVED", "COMPLETED"
    order.approved_by, order.approved_at, order.approval_note = user.id, now, (note or None)
    order.completed_at, order.completed_by, order.updated_at, order.updated_by = now, user.id, now, user.id
    db.commit()
    return order


def return_result(db: Session, order: LabTestOrder, user: User, comment: str) -> LabTestOrder:
    if order.result_status != "PENDING_APPROVAL":
        raise conflict("Only a result waiting for approval can be sent back.")
    order.result_status, order.approval_note, order.updated_at, order.updated_by = "DRAFT", comment.strip(), utcnow(), user.id
    db.commit()
    return order


def previous_value(db: Session, order: LabTestOrder, result: LabResult) -> dict | None:
    """The patient's latest earlier APPROVED value of the same analyte in the same unit. A different unit is not compared."""
    query = select(LabResult, LabTestOrder).join(LabTestOrder, LabResult.order_id == LabTestOrder.id).where(
        LabTestOrder.patient_id == order.patient_id, LabTestOrder.result_status == "APPROVED", LabTestOrder.id != order.id)
    if order.approved_at:
        query = query.where(LabTestOrder.approved_at < order.approved_at)
    rows = db.execute(query.order_by(LabTestOrder.approved_at.desc())).all()
    for r, o in rows:
        if r.analyte_name.lower() == result.analyte_name.lower() and (r.unit or "") == (result.unit or "") and r.value_num is not None:
            change = None
            if result.value_num is not None:
                change = "up" if result.value_num > r.value_num else "down" if result.value_num < r.value_num else "same"
            return {"value": r.value_text, "unit": r.unit, "date": o.approved_at.date().isoformat(), "flag": r.flag, "change": change}
    return None


def result_rows(db: Session, order: LabTestOrder) -> list[dict]:
    return [{"id": r.id, "name": r.analyte_name, "value": r.value_text, "unit": r.unit, "method": r.method, "ref_low": r.ref_low, "ref_high": r.ref_high, "flag": r.flag,
             "flag_text": FLAG_TEXT[r.flag], "comment": r.comment, "previous": previous_value(db, order, r)} for r in order.results]


def lab_detail(db: Session, order: LabTestOrder, audience: str) -> dict:
    """audience: LAB (everything), DOCTOR (approved results only), PATIENT (approved and seen by the doctor)."""
    from app.services import lab_service
    out = lab_service.order_out(order, for_lab=audience == "LAB")
    out.update({"result_status": order.result_status, "has_critical": bool(order.has_critical), "approval_note": order.approval_note if audience == "LAB" else None,
                "approved_at": order.approved_at.isoformat() if order.approved_at else None, "doctor_seen_at": order.doctor_seen_at.isoformat() if order.doctor_seen_at else None})
    visible = audience == "LAB" or (order.result_status == "APPROVED" and (audience == "DOCTOR" or order.doctor_seen_at is not None))
    out["results"] = result_rows(db, order) if visible else []
    if audience == "LAB":
        out["approved_by"] = db.get(User, order.approved_by).full_name if order.approved_by else None
        out["entered_by"] = db.get(User, order.assigned_to).full_name if order.assigned_to else None
    return out


# ------------------------------------------------------------------ radiology
def get_radiology(db: Session, order_id: int) -> RadiologyOrder:
    order = db.get(RadiologyOrder, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Study not found.")
    return order


def previous_studies(db: Session, order: RadiologyOrder) -> list[dict]:
    rows = db.scalars(select(RadiologyOrder).where(RadiologyOrder.patient_id == order.patient_id, RadiologyOrder.modality == order.modality, RadiologyOrder.status == "APPROVED",
                                                   RadiologyOrder.id != order.id).order_by(RadiologyOrder.approved_at.desc()).limit(5)).all()
    return [{"id": o.id, "study": o.study, "date": o.approved_at.date().isoformat(), "impression": o.report.impression if o.report else None} for o in rows]


def radiology_out(db: Session, o: RadiologyOrder, audience: str) -> dict:
    """audience: RADIOLOGY (everything), DOCTOR (approved report only), PATIENT (approved and seen by the doctor)."""
    out = {"id": o.id, "study": o.study, "modality": o.modality, "priority": o.priority, "status": o.status, "status_label": RADIOLOGY_LABELS[o.status], "clinical_info": o.clinical_info,
           "ordered_on": o.created_at.date().isoformat(), "scheduled_at": o.scheduled_at.isoformat() if o.scheduled_at else None, "performed_at": o.performed_at.isoformat() if o.performed_at else None,
           "approved_at": o.approved_at.isoformat() if o.approved_at else None, "doctor_name": o.doctor.user.full_name, "doctor_seen_at": o.doctor_seen_at.isoformat() if o.doctor_seen_at else None}
    if audience == "RADIOLOGY":
        out.update({"patient_id": o.patient_id, "patient_name": o.patient.user.full_name, "patient_code": o.patient.patient_code,
                    "technician": db.get(User, o.technician_id).full_name if o.technician_id else None, "radiologist": db.get(User, o.radiologist_id).full_name if o.radiologist_id else None})
    visible = audience == "RADIOLOGY" or (o.status == "APPROVED" and (audience == "DOCTOR" or o.doctor_seen_at is not None))
    out["report"] = {"technique": o.report.technique, "findings": o.report.findings, "impression": o.report.impression, "reported_at": o.report.reported_at.isoformat()} if (o.report and visible) else None
    out["files"] = [{"id": f.id, "filename": f.filename} for f in o.attachments] if visible else []
    out["previous_studies"] = previous_studies(db, o) if visible else []
    return out


def radiology_worklist(db: Session, status_filter: str | None, q: str | None) -> list[dict]:
    sync_clinical_orders(db)
    query = select(RadiologyOrder).order_by(RadiologyOrder.id.desc()).limit(500)
    if status_filter == "OPEN":
        query = query.where(RadiologyOrder.status.in_(RADIOLOGY_OPEN))
    elif status_filter:
        query = query.where(RadiologyOrder.status == status_filter)
    needle = (q or "").strip().lower()
    rows = []
    for o in db.scalars(query):
        out = radiology_out(db, o, "RADIOLOGY")
        if needle and needle not in " ".join([out["patient_name"], out["patient_code"], o.study, o.modality]).lower():
            continue
        rows.append(out)
    return rows


def radiology_dashboard(db: Session) -> dict:
    sync_clinical_orders(db)
    rows = db.scalars(select(RadiologyOrder)).all()
    counts = {k: 0 for k in RADIOLOGY_LABELS}
    for o in rows:
        counts[o.status] += 1
    today = datetime.now().date()
    return {"counts": counts, "open": sum(counts[k] for k in RADIOLOGY_OPEN), "stat_open": sum(1 for o in rows if o.priority in ("URGENT", "STAT") and o.status in RADIOLOGY_OPEN),
            "waiting_for_report": counts["REPORTED"], "done_today": sum(1 for o in rows if o.approved_at and o.approved_at.date() == today)}


def schedule(db: Session, order: RadiologyOrder, user: User, when: datetime) -> RadiologyOrder:
    if order.status not in ("ORDERED", "SCHEDULED"):
        raise conflict(f"A study that is '{RADIOLOGY_LABELS[order.status].lower()}' cannot be scheduled.")
    order.scheduled_at, order.status, order.technician_id, order.updated_at = when, "SCHEDULED", user.id, utcnow()
    db.commit()
    return order


def start(db: Session, order: RadiologyOrder, user: User) -> RadiologyOrder:
    if order.status not in ("ORDERED", "SCHEDULED"):
        raise conflict(f"A study that is '{RADIOLOGY_LABELS[order.status].lower()}' cannot be started.")
    order.status, order.technician_id, order.performed_at, order.updated_at = "IN_PROGRESS", user.id, utcnow(), utcnow()
    db.commit()
    return order


def write_report(db: Session, order: RadiologyOrder, user: User, technique: str | None, findings: str, impression: str) -> RadiologyOrder:
    if order.status not in ("IN_PROGRESS", "REPORTED"):
        raise conflict("The scan must be done before it is reported." if order.status in ("ORDERED", "SCHEDULED") else f"This study is {RADIOLOGY_LABELS[order.status].lower()}, so it cannot be reported.")
    if order.report is None:
        order.report = RadiologyReport(technique=technique, findings=findings.strip(), impression=impression.strip(), reported_by=user.id)
    else:
        order.report.technique, order.report.findings, order.report.impression, order.report.reported_by, order.report.reported_at = technique, findings.strip(), impression.strip(), user.id, utcnow()
    order.status, order.radiologist_id, order.updated_at = "REPORTED", user.id, utcnow()
    db.commit()
    return order


def approve_radiology(db: Session, order: RadiologyOrder, user: User) -> RadiologyOrder:
    if order.status != "REPORTED" or order.report is None:
        raise conflict("Only a reported study can be approved." if order.status != "APPROVED" else "This report is already approved.")
    now = utcnow()
    order.status, order.approved_by, order.approved_at, order.updated_at = "APPROVED", user.id, now, now
    db.commit()
    return order


def mark_seen(db: Session, order, kind: str) -> None:
    approved = order.result_status == "APPROVED" if kind == "LAB" else order.status == "APPROVED"
    if not approved:
        raise conflict("Only an approved result can be marked as seen.")
    if order.doctor_seen_at is None:
        order.doctor_seen_at = utcnow()
        db.commit()


# ------------------------------------------------------------------ catalogue
def catalogue(db: Session, kind: str | None) -> list[dict]:
    query = select(DiagnosticTest).where(DiagnosticTest.is_active.is_(True)).order_by(DiagnosticTest.kind, DiagnosticTest.category, DiagnosticTest.name)
    if kind:
        query = query.where(DiagnosticTest.kind == kind)
    return [{"id": t.id, "kind": t.kind, "name": t.name, "category": t.category, "sample_type": t.sample_type,
             "analytes": [{"id": a.id, "name": a.name, "unit": a.unit, "method": a.method, "ref_low": a.ref_low, "ref_high": a.ref_high, "critical_low": a.critical_low, "critical_high": a.critical_high} for a in t.analytes]}
            for t in db.scalars(query)]


def patient_lab(db: Session, patient: Patient, audience: str) -> list[dict]:
    return [lab_detail(db, o, audience) for o in db.scalars(select(LabTestOrder).where(LabTestOrder.patient_id == patient.id).order_by(LabTestOrder.id.desc()))
            if o.result_status == "APPROVED" or audience != "PATIENT"]


def patient_radiology(db: Session, patient: Patient, audience: str) -> list[dict]:
    return [radiology_out(db, o, audience) for o in db.scalars(select(RadiologyOrder).where(RadiologyOrder.patient_id == patient.id).order_by(RadiologyOrder.id.desc()))]
