"""Upload, list and view reports.

IMPORTANT: a report is saved (file + database rows) ONLY after the whole analysis pipeline succeeded.
Failed or non-health files are rejected and leave nothing behind."""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.core.config import from_backend_dir
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import (
    ADMIN, DOCTOR, EMPLOYEE, PATIENT, doctor_can_access_patient, forbidden, get_current_user,
    get_doctor_profile, require_roles,
)
from app.database.connection import get_db
from app.database.models import Doctor, Patient, User
from app.schemas.report import ReportDetail, ReportListItem
from app.services import audit_service, report_service
from app.services.report_parser import names_match
from app.services.report_processor import process_report
from app.services.serializers import analysis_visible_to, report_detail, report_list_item
from app.utils.file_validation import get_extension, safe_filename, validate_size
from app.utils.paging import DEFAULT_PAGE, page_of_list
from app.utils.validators import Offset, PageSize, PathId, QueryId, SearchText

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/upload", response_model=ReportDetail, status_code=status.HTTP_201_CREATED)
def upload_report(
    request: Request,
    file: UploadFile = File(...),
    patient_id: int = Form(...),
    doctor_id: int | None = Form(default=None),
    user: User = Depends(require_roles(EMPLOYEE, DOCTOR)),
    db: Session = Depends(get_db),
):
    """Employee or authorized doctor uploads a report for a patient. The file is REALLY read and analyzed."""
    settings = get_settings()
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found.")

    # Who reviews this report? The doctor uploading it, or the chosen doctor, or the patient's assigned doctor.
    if user.role == DOCTOR:
        doctor = get_doctor_profile(db, user)
        if not doctor_can_access_patient(db, doctor, patient):
            raise forbidden()
        review_doctor_id = doctor.id
    else:
        review_doctor_id = doctor_id or patient.assigned_doctor_id
        if review_doctor_id is None:
            raise HTTPException(422,
                                "Please choose the doctor who should review this report.")
        if db.get(Doctor, review_doctor_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found.")

    filename = safe_filename(file.filename)
    content = file.file.read(settings.max_file_size + 1)
    validate_size(content, settings.max_file_size)

    # Real processing. Raises a ReportError (with a clear message) if the file cannot be analyzed.
    processed = process_report(filename, content)

    # Success: only now store the file and the database rows.
    os.makedirs(settings.upload_dir, exist_ok=True)
    stored_path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}.{get_extension(filename)}")
    with open(stored_path, "wb") as f:
        f.write(content)
    try:
        report = report_service.save_report(db, patient, user, review_doctor_id, filename, stored_path, processed)
    except Exception:
        db.rollback()
        os.remove(stored_path)  # no orphan file if the database write fails
        raise

    audit_service.log_action(db, user, audit_service.REPORT_UPLOADED, "report", report.id, request, filename)
    audit_service.log_action(db, user, audit_service.REPORT_ANALYZED, "report", report.id, request,
                             f"{len(processed.parameters)} parameters via {processed.method}")

    warnings = []
    if processed.patient_name and not names_match(processed.patient_name, patient.user.full_name):
        warnings.append(f'The name printed on the report ("{processed.patient_name}") does not match the selected '
                        f'patient ("{patient.user.full_name}"). Please check that the report belongs to this patient.')
    return report_detail(report, user.role, warnings)


@router.get("", response_model=list[ReportListItem])
def list_reports(response: Response, patient_id: QueryId = None, needs_review: bool = False, q: SearchText = None,
                 limit: PageSize = DEFAULT_PAGE, offset: Offset = 0,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Newest first. `needs_review` keeps the reports still waiting for a doctor, `q` searches the patient's name or ID and the file name.
    Paged: `limit` and `offset`, the whole count is in X-Total-Count."""
    reports = report_service.list_reports_for_user(db, user, patient_id)
    if needs_review:
        reports = [r for r in reports if r.doctor_review_status == "PENDING"]
    if q:
        needle = q.strip().lower()
        reports = [r for r in reports if needle in r.patient.user.full_name.lower() or needle in r.filename.lower() or needle in r.patient.patient_code.lower()]
    return [report_list_item(r) for r in page_of_list(response, reports, limit, offset)]


@router.get("/{report_id}", response_model=ReportDetail)
def get_report(report_id: PathId, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = report_service.get_report_for_user(db, user, report_id)
    return report_detail(report, user.role)


@router.get("/{report_id}/analysis", response_model=ReportDetail)
def get_analysis(report_id: PathId, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_report(report_id, user, db)


@router.post("/{report_id}/insights/refresh", response_model=ReportDetail)
def refresh_insights(report_id: PathId, request: Request, user: User = Depends(require_roles(DOCTOR)),
                     db: Session = Depends(get_db)):
    """The doctor asks for the suggestions to be generated again (for example after an AI key was added)."""
    report = report_service.get_report_for_user(db, user, report_id)
    report_service.refresh_insights(db, report)
    audit_service.log_action(db, user, audit_service.INSIGHTS_REFRESHED, "report", report.id, request)
    return report_detail(report, user.role)


@router.delete("/{report_id}")
def delete_report(report_id: PathId, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a report that was uploaded by mistake (wrong patient or wrong file). The action is written to the audit log."""
    report = report_service.get_report_for_user(db, user, report_id)
    if not report_service.can_delete(user, report):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "You can delete a report only if you are the doctor, or if you uploaded it and the doctor has not reviewed it yet.")
    patient_name = report.patient.user.full_name
    name = report_service.delete_report(db, report)
    audit_service.log_action(db, user, audit_service.REPORT_DELETED, "report", report_id, request, f"{name} (patient {patient_name})")
    return {"deleted": True, "id": report_id, "filename": name}


@router.get("/{report_id}/file")
def download_file(report_id: PathId, request: Request, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """The original file is private: it is only served to authorized users through this endpoint."""
    report = report_service.get_report_for_user(db, user, report_id)
    if user.role == ADMIN:
        raise forbidden()  # admins manage the system; they do not need clinical documents
    if user.role == EMPLOYEE and report.uploaded_by != user.id:
        raise forbidden()  # an employee can reopen only the files they uploaded themselves
    if user.role == PATIENT and not analysis_visible_to(user.role, report):
        raise forbidden()  # patients get the file after the doctor has reviewed the report
    path = from_backend_dir(report.file_path) if report.file_path else None
    if not path or not os.path.exists(path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The original file is no longer available.")
    audit_service.log_action(db, user, audit_service.REPORT_FILE_VIEWED, "report", report.id, request)
    return FileResponse(path, filename=report.filename)
