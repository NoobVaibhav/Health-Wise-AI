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
from app.core.permissions import DOCTOR, EMPLOYEE, LAB, PATIENT, get_accessible_patient, get_patient_profile, require_roles
from app.database.connection import get_db
from app.database.models import Prescription, User
from app.services import audit_service, lab_service, report_service
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
