"""Laboratory: the tests the doctors have advised, followed from order to result.
Laboratory staff work the list (take a sample, test it, upload the result, or reject the sample). Hospital employees can read the list.
Doctors see the progress of their patients' tests and patients see their own, in plain words. The pharmacy never sees any of this
(see prescription_out(include_tests=False)); laboratory staff never see medicines or other reports."""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import DOCTOR, EMPLOYEE, LAB, PATIENT, forbidden, get_accessible_patient, get_patient_profile, require_roles
from app.database.connection import get_db
from app.database.models import DiagnosticTest, LabTestOrder, Prescription, User
from app.services import audit_service, diagnostic_service, lab_service, report_service
from app.services.report_parser import names_match
from app.services.report_processor import process_report
from app.services.serializers import tests_of
from app.utils.file_validation import get_extension, validate_size
from app.utils.validators import PathId, SearchText

router = APIRouter(prefix="/api/lab", tags=["lab"])
lab_only = require_roles(LAB)


class StatusIn(BaseModel):
    status: str = Field(pattern="^(SAMPLE_COLLECTED|IN_PROGRESS|REJECTED|ORDERED)$")
    note: str | None = Field(default=None, max_length=500)
    sample_type: str | None = Field(default=None, max_length=40)


class UrgentIn(BaseModel):
    urgent: bool


@router.get("/test-orders")
def test_orders(q: SearchText = None, user: User = Depends(require_roles(LAB, EMPLOYEE)), db: Session = Depends(get_db)):
    """Newest first. Search by patient name, patient ID, prescription code (RX-00001) or test name."""
    rows = db.scalars(
        select(Prescription).where(Prescription.tests_advised.is_not(None), Prescription.status != "CANCELLED")
        .order_by(Prescription.id.desc()).limit(300)
    ).all()
    result = []
    needle = (q or "").strip().lower()
    for rx in rows:
        tests = tests_of(rx)
        if not tests:
            continue
        code = f"RX-{rx.id:05d}"
        haystack = " ".join([rx.patient.user.full_name, rx.patient.patient_code, code, *tests]).lower()
        if needle and needle not in haystack:
            continue
        result.append({
            "id": rx.id, "code": code, "patient_name": rx.patient.user.full_name,
            "patient_code": rx.patient.patient_code, "doctor_name": rx.doctor.user.full_name,
            "date": rx.prescription_date.isoformat(), "reason": rx.clinical_indication, "tests": tests,
        })
    return result


@router.get("/dashboard")
def dashboard(user: User = Depends(lab_only), db: Session = Depends(get_db)):
    return lab_service.dashboard(db)


@router.get("/worklist")
def worklist(status_filter: str | None = None, q: SearchText = None, urgent: bool = False, user: User = Depends(require_roles(LAB, EMPLOYEE)), db: Session = Depends(get_db)):
    """One row per advised test. status_filter: OPEN, ORDERED, SAMPLE_COLLECTED, IN_PROGRESS, COMPLETED, REJECTED, CANCELLED."""
    if status_filter and status_filter != "OPEN" and status_filter not in lab_service.LABELS:
        raise HTTPException(422, "Unknown status.")
    return {"tests": lab_service.worklist(db, status_filter, q, urgent), "sample_types": lab_service.SAMPLE_TYPES}


@router.post("/tests/{order_id}/status")
def change_status(order_id: PathId, data: StatusIn, request: Request, user: User = Depends(lab_only), db: Session = Depends(get_db)):
    order = lab_service.get_order(db, order_id)
    old = order.status
    lab_service.change_status(db, order, data.status, user, data.note, data.sample_type)
    audit_service.log_action(db, user, "LAB_TEST_STATUS", "lab_test", order.id, request, f"{old} -> {order.status}")
    return lab_service.order_out(order)


@router.post("/tests/{order_id}/urgent")
def mark_urgent(order_id: PathId, data: UrgentIn, request: Request, user: User = Depends(lab_only), db: Session = Depends(get_db)):
    order = lab_service.get_order(db, order_id)
    lab_service.set_urgent(db, order, data.urgent, user)
    audit_service.log_action(db, user, "LAB_TEST_URGENT", "lab_test", order.id, request, "urgent" if data.urgent else "not urgent")
    return lab_service.order_out(order)


@router.post("/tests/{order_id}/result")
def upload_result(order_id: PathId, request: Request, file: UploadFile = File(...), confirm_mismatch: bool = Form(default=False),
                  user: User = Depends(lab_only), db: Session = Depends(get_db)):
    """Attach the result. It is read and analysed like any report, sent to the prescribing doctor for review, and the test is marked done.
    If the name printed on the result is not the patient's, nothing is saved unless the lab confirms it on purpose."""
    order = lab_service.get_order(db, order_id)
    if order.status not in ("SAMPLE_COLLECTED", "IN_PROGRESS"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Take the sample first: a result can be added only after the sample is taken." if order.status == "ORDERED"
                            else f"This test is {lab_service.LABELS[order.status].lower()}, so a result cannot be added.")
    settings = get_settings()
    filename = Path(file.filename or "result").name
    content = file.file.read(settings.max_file_size + 1)
    validate_size(content, settings.max_file_size)
    processed = process_report(filename, content)                       # a clear error if the file cannot be read
    if processed.patient_name and not names_match(processed.patient_name, order.patient.user.full_name) and not confirm_mismatch:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "NAME_MISMATCH", "message": f'The name on this result ("{processed.patient_name}") is not the patient\'s ("{order.patient.user.full_name}"). '
                                                                                                    "Please check that it belongs to this patient."})
    os.makedirs(settings.upload_dir, exist_ok=True)
    stored = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}.{get_extension(filename)}")
    with open(stored, "wb") as handle:
        handle.write(content)
    try:
        report = report_service.save_report(db, order.patient, user, order.doctor_id, filename, stored, processed)
        lab_service.attach_result(db, order, user, report)
    except Exception:
        db.rollback()
        os.remove(stored)
        raise
    audit_service.log_action(db, user, audit_service.REPORT_UPLOADED, "report", report.id, request, f"lab result for {order.test_name}")
    audit_service.log_action(db, user, "LAB_RESULT_UPLOADED", "lab_test", order.id, request, f"report {report.id}")
    return {**lab_service.order_out(order), "parameters_found": len(processed.parameters), "mismatch_confirmed": bool(confirm_mismatch and processed.patient_name and not names_match(processed.patient_name, order.patient.user.full_name))}


@router.get("/my-tests")
def my_tests(user: User = Depends(require_roles(PATIENT)), db: Session = Depends(get_db)):
    return lab_service.for_patient(db, get_patient_profile(db, user), as_doctor=False)


@router.get("/patient/{patient_id}/tests")
def patient_tests(patient_id: PathId, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    return lab_service.for_patient(db, get_accessible_patient(db, user, patient_id, clinical=True), as_doctor=True)


# ------------------------------------------------------------------ Phase 4: structured results, pathologist approval
class ResultItem(BaseModel):
    analyte_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, max_length=100)
    value: str = Field(min_length=1, max_length=100)
    unit: str | None = Field(default=None, max_length=30)
    method: str | None = Field(default=None, max_length=100)
    ref_low: float | None = Field(default=None, ge=-1e9, le=1e9)       # only for a value that is not in the catalogue: written from the report of the machine
    ref_high: float | None = Field(default=None, ge=-1e9, le=1e9)
    comment: str | None = Field(default=None, max_length=300)


class ResultsIn(BaseModel):
    results: list[ResultItem] = Field(max_length=60)
    submit: bool = False


class NoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class ReturnIn(BaseModel):
    comment: str = Field(min_length=3, max_length=500)


@router.get("/pending-approval")
def pending_approval(user: User = Depends(lab_only), db: Session = Depends(get_db)):
    """Results the technicians have sent on, waiting for a pathologist."""
    diagnostic_service.sync_clinical_orders(db)
    rows = db.scalars(select(LabTestOrder).where(LabTestOrder.result_status == "PENDING_APPROVAL").order_by(LabTestOrder.has_critical.desc(), LabTestOrder.id)).all()
    return [diagnostic_service.lab_detail(db, o, "LAB") for o in rows]


@router.get("/tests/{order_id}")
def test_detail(order_id: PathId, user: User = Depends(lab_only), db: Session = Depends(get_db)):
    order = lab_service.get_order(db, order_id)
    out = diagnostic_service.lab_detail(db, order, "LAB")
    out["analytes"] = [{"id": a.id, "name": a.name, "unit": a.unit, "method": a.method, "ref_low": a.ref_low, "ref_high": a.ref_high, "critical_low": a.critical_low, "critical_high": a.critical_high}
                       for a in (order.test_id and db.get(DiagnosticTest, order.test_id).analytes or [])]
    return out


@router.post("/tests/{order_id}/results")
def enter_results(order_id: PathId, data: ResultsIn, request: Request, user: User = Depends(lab_only), db: Session = Depends(get_db)):
    """The technician enters the values (save as a draft, or send on for approval). The limits, unit and method come from the hospital's catalogue."""
    order = lab_service.get_order(db, order_id)
    diagnostic_service.save_results(db, order, user, [i.model_dump() for i in data.results], data.submit)
    audit_service.log_action(db, user, "LAB_RESULT_ENTERED", "lab_test", order.id, request, "sent for approval" + (" (critical value)" if order.has_critical else "") if data.submit else "draft saved")
    return diagnostic_service.lab_detail(db, order, "LAB")


@router.post("/tests/{order_id}/approve")
def approve(order_id: PathId, data: NoteIn, request: Request, user: User = Depends(lab_only), db: Session = Depends(get_db)):
    if not diagnostic_service.is_pathologist(db, user):
        raise forbidden()
    order = lab_service.get_order(db, order_id)
    diagnostic_service.approve_result(db, order, user, data.note)
    audit_service.log_action(db, user, "LAB_RESULT_APPROVED", "lab_test", order.id, request, order.test_name)
    return diagnostic_service.lab_detail(db, order, "LAB")


@router.post("/tests/{order_id}/return")
def send_back(order_id: PathId, data: ReturnIn, request: Request, user: User = Depends(lab_only), db: Session = Depends(get_db)):
    if not diagnostic_service.is_pathologist(db, user):
        raise forbidden()
    order = lab_service.get_order(db, order_id)
    diagnostic_service.return_result(db, order, user, data.comment)
    audit_service.log_action(db, user, "LAB_RESULT_RETURNED", "lab_test", order.id, request, order.test_name)
    return diagnostic_service.lab_detail(db, order, "LAB")


@router.post("/tests/{order_id}/seen")
def doctor_seen(order_id: PathId, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    """The doctor has looked at the approved result. From now on the patient can see it too."""
    order = lab_service.get_order(db, order_id)
    get_accessible_patient(db, user, order.patient_id, clinical=True)
    diagnostic_service.mark_seen(db, order, "LAB")
    audit_service.log_action(db, user, "LAB_RESULT_SEEN", "lab_test", order.id, request, order.test_name)
    return diagnostic_service.lab_detail(db, order, "DOCTOR")
