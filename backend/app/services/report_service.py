"""Database operations for reports: save an analyzed report, list/load with access checks, doctor review.
Only reports that passed the whole analysis pipeline are ever saved here."""
import json
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import (
    ADMIN, DOCTOR, EMPLOYEE, PATIENT, doctor_can_access_patient, doctor_patient_ids, forbidden,
    get_doctor_profile, get_patient_profile,
)
from app.database.models import (
    DoctorNote, DoctorRecommendation, HealthParameter, HealthReport, Patient, Prescription, ReportComparison, User, utcnow,
)
from app.services.report_processor import ProcessedReport

REVIEW_DECISIONS = ("APPROVED", "MODIFIED", "CLARIFIED")


def effective_date(report: HealthReport) -> date:
    """Date used for ordering and trends: the date printed on the report, else the upload date."""
    return report.report_date or report.uploaded_at.date()


def save_report(db: Session, patient: Patient, uploader: User, doctor_id: int | None, filename: str,
                file_path: str, processed: ProcessedReport) -> HealthReport:
    report = HealthReport(
        patient_id=patient.id, uploaded_by=uploader.id, assigned_doctor_id=doctor_id, filename=filename,
        file_path=file_path, report_date=processed.report_date, processing_status="ANALYZED",
        doctor_review_status="PENDING", extracted_text=processed.text, processing_method=processed.method,
        ai_summary=processed.summary, report_type=processed.report_type, insights_json=json.dumps(processed.insights),
    )
    db.add(report)
    db.flush()  # gives the report an id
    for item in processed.parameters:
        p = item.extracted
        db.add(HealthParameter(
            report_id=report.id, test_name=p.test_name, normalized_name=p.normalized_name, value=p.value,
            unit=p.unit, reference_text=p.reference_text, reference_low=p.reference_low,
            reference_high=p.reference_high, status=item.status, ai_explanation=json.dumps(item.explanation),
        ))
    db.commit()
    db.refresh(report)
    return report


def list_reports_for_user(db: Session, user: User, patient_id: int | None = None) -> list[HealthReport]:
    """Reports the user is allowed to see, newest first."""
    query = select(HealthReport)
    if user.role == PATIENT:
        query = query.where(HealthReport.patient_id == get_patient_profile(db, user).id)
    elif user.role == DOCTOR:
        ids = doctor_patient_ids(db, get_doctor_profile(db, user))
        query = query.where(HealthReport.patient_id.in_(ids or {-1}))
    elif user.role not in (ADMIN, EMPLOYEE):
        raise forbidden()
    if patient_id is not None:
        query = query.where(HealthReport.patient_id == patient_id)
    reports = db.scalars(query).all()
    return sorted(reports, key=lambda r: (effective_date(r), r.id), reverse=True)


def get_report_for_user(db: Session, user: User, report_id: int) -> HealthReport:
    """Load a report only if this user may see it (404 if missing, 403 if not allowed)."""
    report = db.get(HealthReport, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    if user.role == PATIENT:
        if report.patient.user_id != user.id:
            raise forbidden()
    elif user.role == DOCTOR:
        if not doctor_can_access_patient(db, get_doctor_profile(db, user), report.patient):
            raise forbidden()
    elif user.role not in (ADMIN, EMPLOYEE):
        raise forbidden()
    return report


def can_delete(user: User, report: HealthReport) -> bool:
    """A doctor may delete a report of a patient they are authorised for (it was uploaded by mistake, or is the wrong file).
    An employee may delete only a report they uploaded themselves and only until the doctor has reviewed it.
    Patients and administrators never delete reports."""
    if user.role == DOCTOR:
        return True
    return user.role == EMPLOYEE and report.uploaded_by == user.id and report.doctor_review_status == "PENDING"


def delete_report(db: Session, report: HealthReport) -> str:
    """Remove the report, its results and its file. Notes, advice and prescriptions that were written about it stay in the
    patient's history (they just no longer point to the deleted report). Returns the file name for the audit log."""
    import os
    name, path = report.filename, report.file_path
    db.query(ReportComparison).filter((ReportComparison.previous_report_id == report.id)
                                      | (ReportComparison.latest_report_id == report.id)).delete(synchronize_session=False)
    for model in (DoctorNote, DoctorRecommendation, Prescription):
        db.query(model).filter(model.report_id == report.id).update({model.report_id: None}, synchronize_session=False)
    db.delete(report)                       # its test results are deleted with it (cascade)
    db.commit()
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass                            # the database is already clean; a leftover file is harmless
    return name


def refresh_insights(db: Session, report: HealthReport) -> HealthReport:
    """Build the insights again from the stored text / values (for example after an AI key was added)."""
    from app.services import insight_service, llm_service
    from app.services.serializers import effective_report_type, stored_insights  # local import: avoids a cycle

    if report.parameters:
        # lab report: rebuild from the stored, already-classified values (stored_insights does exactly that)
        saved, report.insights_json = report.insights_json, None
        insights = stored_insights(report)
        report.insights_json = saved
        kind = "LAB"
        insights["summary"] = report.ai_summary or insights["summary"]
    else:
        kind = effective_report_type(report)
        if kind == "LAB":
            kind = insight_service.detect_report_type(report.extracted_text or "")
        insights = insight_service.build_narrative_insights(report.extracted_text or "", kind)
    insights = llm_service.enhance_insights(report.extracted_text or "", kind, insights)
    report.report_type = kind
    report.insights_json = json.dumps(insights)
    if kind != "LAB":
        report.ai_summary = insights["summary"]
    db.commit()
    db.refresh(report)
    return report


def review_report(db: Session, report: HealthReport, doctor, decision: str, comment: str | None) -> HealthReport:
    """Doctor marks the report as reviewed. The decision is what the doctor did with the AI analysis."""
    if decision not in REVIEW_DECISIONS:
        raise HTTPException(422,
                            "Decision must be APPROVED, MODIFIED or CLARIFIED.")
    if decision != "APPROVED" and not (comment and comment.strip()):
        raise HTTPException(422,
                            "Please add a comment when you modify or clarify the AI analysis.")
    report.doctor_review_status = "REVIEWED"
    report.reviewed_by = doctor.id
    report.reviewed_at = utcnow()
    report.review_decision = decision
    report.review_comment = comment.strip() if comment else None
    db.commit()
    db.refresh(report)
    return report
