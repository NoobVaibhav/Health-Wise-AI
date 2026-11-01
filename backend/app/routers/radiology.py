"""Radiology (RIS): X-ray, ultrasound, CT, MRI, mammography, echo and ECG.
The technician schedules and does the scan and attaches the image or document (JPG, PNG or PDF; this is not DICOM or PACS). Only a radiologist writes and approves the report.
The ordering doctor sees the approved report and marks it as seen; only then does the patient see it. Comparison shows the patient's earlier approved studies of the same kind."""
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import DOCTOR, EMPLOYEE, PATIENT, RADIOLOGY, forbidden, get_accessible_patient, get_current_user, get_patient_profile, require_roles
from app.database.connection import get_db
from app.database.models import RadiologyAttachment, User
from app.services import audit_service, diagnostic_service
from app.utils.file_validation import detect_file_type, get_extension, safe_filename, validate_size
from app.utils.validators import PathId, SearchText

router = APIRouter(prefix="/api/radiology", tags=["radiology"])
staff_only = require_roles(RADIOLOGY)
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}


class ScheduleIn(BaseModel):
    scheduled_at: datetime


class ReportIn(BaseModel):
    technique: str | None = Field(default=None, max_length=300)
    findings: str = Field(min_length=3, max_length=8000)
    impression: str = Field(min_length=3, max_length=3000)


def _radiologist_only(db: Session, user: User) -> None:
    if diagnostic_service.radiology_type(db, user) != "RADIOLOGIST":
        raise forbidden()


@router.get("/dashboard")
def dashboard(user: User = Depends(staff_only), db: Session = Depends(get_db)):
    return diagnostic_service.radiology_dashboard(db)


@router.get("/worklist")
def worklist(status_filter: str | None = None, q: SearchText = None, user: User = Depends(require_roles(RADIOLOGY, EMPLOYEE)), db: Session = Depends(get_db)):
    """status_filter: OPEN, ORDERED, SCHEDULED, IN_PROGRESS, REPORTED, APPROVED, CANCELLED."""
    if status_filter and status_filter != "OPEN" and status_filter not in diagnostic_service.RADIOLOGY_LABELS:
        raise HTTPException(422, "Unknown status.")
    return {"studies": diagnostic_service.radiology_worklist(db, status_filter, q), "modalities": list(diagnostic_service.MODALITIES)}


@router.get("/orders/{order_id}")
def detail(order_id: PathId, user: User = Depends(staff_only), db: Session = Depends(get_db)):
    order = diagnostic_service.get_radiology(db, order_id)
    out = diagnostic_service.radiology_out(db, order, "RADIOLOGY")
    out["previous_studies"] = diagnostic_service.previous_studies(db, order)
    out["files"] = [{"id": f.id, "filename": f.filename} for f in order.attachments]
    return out


@router.post("/orders/{order_id}/schedule")
def schedule(order_id: PathId, data: ScheduleIn, request: Request, user: User = Depends(staff_only), db: Session = Depends(get_db)):
    order = diagnostic_service.get_radiology(db, order_id)
    diagnostic_service.schedule(db, order, user, data.scheduled_at)
    audit_service.log_action(db, user, "RADIOLOGY_SCHEDULED", "radiology_order", order.id, request, order.study)
    return diagnostic_service.radiology_out(db, order, "RADIOLOGY")


@router.post("/orders/{order_id}/start")
def start(order_id: PathId, request: Request, user: User = Depends(staff_only), db: Session = Depends(get_db)):
    order = diagnostic_service.get_radiology(db, order_id)
    diagnostic_service.start(db, order, user)
    audit_service.log_action(db, user, "RADIOLOGY_STARTED", "radiology_order", order.id, request, order.study)
    return diagnostic_service.radiology_out(db, order, "RADIOLOGY")


@router.post("/orders/{order_id}/files", status_code=status.HTTP_201_CREATED)
def add_file(order_id: PathId, request: Request, file: UploadFile = File(...), user: User = Depends(staff_only), db: Session = Depends(get_db)):
    order = diagnostic_service.get_radiology(db, order_id)
    if order.status in ("APPROVED", "CANCELLED"):
        raise diagnostic_service.conflict("Files cannot be added to an approved or cancelled study.")
    settings = get_settings()
    filename = safe_filename(Path(file.filename or "scan").name)
    if get_extension(filename) not in IMAGE_EXTENSIONS:
        raise HTTPException(422, "Please attach a JPG, PNG or PDF file.")
    content = file.file.read(settings.max_file_size + 1)
    validate_size(content, settings.max_file_size)
    detect_file_type(filename, content)                                           # the bytes must match the extension
    os.makedirs(settings.upload_dir, exist_ok=True)
    stored = os.path.join(settings.upload_dir, f"rad-{uuid.uuid4().hex}.{get_extension(filename)}")
    with open(stored, "wb") as handle:
        handle.write(content)
    row = RadiologyAttachment(order_id=order.id, filename=filename, stored_path=stored, uploaded_by=user.id)
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, "RADIOLOGY_FILE_ADDED", "radiology_order", order.id, request, filename)
    return {"id": row.id, "filename": row.filename}


@router.post("/orders/{order_id}/report")
def report(order_id: PathId, data: ReportIn, request: Request, user: User = Depends(staff_only), db: Session = Depends(get_db)):
    """Only a radiologist writes the report."""
    _radiologist_only(db, user)
    order = diagnostic_service.get_radiology(db, order_id)
    diagnostic_service.write_report(db, order, user, data.technique, data.findings, data.impression)
    audit_service.log_action(db, user, "RADIOLOGY_REPORTED", "radiology_order", order.id, request, order.study)
    return diagnostic_service.radiology_out(db, order, "RADIOLOGY")


@router.post("/orders/{order_id}/approve")
def approve(order_id: PathId, request: Request, user: User = Depends(staff_only), db: Session = Depends(get_db)):
    _radiologist_only(db, user)
    order = diagnostic_service.get_radiology(db, order_id)
    diagnostic_service.approve_radiology(db, order, user)
    audit_service.log_action(db, user, "RADIOLOGY_APPROVED", "radiology_order", order.id, request, order.study)
    return diagnostic_service.radiology_out(db, order, "RADIOLOGY")


@router.post("/orders/{order_id}/seen")
def doctor_seen(order_id: PathId, request: Request, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    order = diagnostic_service.get_radiology(db, order_id)
    get_accessible_patient(db, user, order.patient_id, clinical=True)
    diagnostic_service.mark_seen(db, order, "RADIOLOGY")
    audit_service.log_action(db, user, "RADIOLOGY_SEEN", "radiology_order", order.id, request, order.study)
    return diagnostic_service.radiology_out(db, order, "DOCTOR")


@router.get("/files/{file_id}")
def download(file_id: PathId, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The radiology team always; a doctor of the patient after approval; the patient after the doctor has seen the report."""
    row = db.get(RadiologyAttachment, file_id)
    if row is None:
        raise HTTPException(404, "File not found.")
    order = diagnostic_service.get_radiology(db, row.order_id)
    if user.role == RADIOLOGY:
        pass
    elif user.role == DOCTOR:
        get_accessible_patient(db, user, order.patient_id, clinical=True)
        if order.status != "APPROVED":
            raise forbidden()
    elif user.role == PATIENT:
        if get_patient_profile(db, user).id != order.patient_id or order.status != "APPROVED" or order.doctor_seen_at is None:
            raise forbidden()
    else:
        raise forbidden()
    if not os.path.exists(row.stored_path):
        raise HTTPException(404, "File not found.")
    audit_service.log_action(db, user, "RADIOLOGY_FILE_VIEWED", "radiology_order", order.id, request, row.filename)
    return FileResponse(row.stored_path, filename=row.filename)


@router.get("/my-studies")
def my_studies(user: User = Depends(require_roles(PATIENT)), db: Session = Depends(get_db)):
    patient = get_patient_profile(db, user)
    diagnostic_service.sync_clinical_orders(db)
    return diagnostic_service.patient_radiology(db, patient, "PATIENT")


@router.get("/patient/{patient_id}/studies")
def patient_studies(patient_id: PathId, user: User = Depends(require_roles(DOCTOR)), db: Session = Depends(get_db)):
    patient = get_accessible_patient(db, user, patient_id, clinical=True)
    diagnostic_service.sync_clinical_orders(db)
    return diagnostic_service.patient_radiology(db, patient, "DOCTOR")
