"""Doctor module: patient history, report review, notes, recommendations.

Everything a doctor writes is labelled "Doctor's ..." so it can never be confused with AI-generated text."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import (
    ADMIN, DOCTOR, EMPLOYEE, PATIENT, doctor_can_access_patient, doctor_patient_ids, get_accessible_patient,
    get_doctor_profile, require_roles,
)
from app.database.connection import get_db
from app.database.models import (
    Doctor, DoctorNote, DoctorRecommendation, HealthReport, MedicalHistoryEntry, Patient, User,
)
from app.schemas.doctor import (
    DoctorOut, HistoryEntryCreate, NoteCreate, NoteOut, PRIORITIES, RecommendationCreate, RecommendationOut,
)
from app.schemas.patient import PatientFull
from app.schemas.report import ReportDetail, ReviewRequest
from app.services import audit_service, dashboard_service, report_service
from app.services.history_service import build_timeline
from app.services.prescription_service import list_prescriptions_for_user
from app.services.serializers import (
    note_out, patient_for_role, prescription_out, recommendation_out, report_detail, report_list_item,
)
from app.utils.validators import PathId, QueryId, SearchText

router = APIRouter(prefix="/api/doctor", tags=["doctor"])
directory = APIRouter(prefix="/api/doctors", tags=["doctors"])
doctor_only = require_roles(DOCTOR)


def _check_priority(priority: str) -> str:
    priority = priority.upper()
    if priority not in PRIORITIES:
        raise HTTPException(422, "Priority must be NORMAL, IMPORTANT or FOLLOW_UP_REQUIRED.")
    return priority


def _authorized_patient_and_report(db: Session, doctor: Doctor, patient_id: int, report_id: int | None) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found.")
    if not doctor_can_access_patient(db, doctor, patient):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to access this information.")
    if report_id is not None:
        report = db.get(HealthReport, report_id)
        if report is None or report.patient_id != patient.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found for this patient.")
    return patient


# ------------------------------------------------------------------ directory (for dropdowns)
@directory.get("", response_model=list[DoctorOut])
def list_doctors(_: User = Depends(require_roles(ADMIN, EMPLOYEE, PATIENT, DOCTOR)), db: Session = Depends(get_db)):
    rows = db.scalars(select(Doctor).join(User, Doctor.user_id == User.id).order_by(User.full_name)).all()
    return [DoctorOut(id=d.id, full_name=d.user.full_name, specialization=d.specialization,
                      department_id=d.department_id, department_name=d.department.name if d.department else None,
                      is_active=d.user.is_active) for d in rows if d.user.is_active]


# ------------------------------------------------------------------ dashboard and patients
@router.get("/dashboard")
def dashboard(user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    return dashboard_service.doctor_dashboard(db, user)


@router.get("/patients", response_model=list[PatientFull])
def my_patients(q: SearchText = None, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    doctor = get_doctor_profile(db, user)
    ids = doctor_patient_ids(db, doctor)
    patients = db.scalars(select(Patient).join(User, Patient.user_id == User.id)
                          .where(Patient.id.in_(ids or {-1})).order_by(User.full_name)).all()
    if q:
        needle = q.strip().lower()
        patients = [p for p in patients if needle in p.user.full_name.lower() or needle in p.patient_code.lower()]
    return [patient_for_role(p, DOCTOR) for p in patients]


@router.get("/patients/{patient_id}/history")
def patient_history(patient_id: PathId, q: SearchText = None, request: Request = None,
                    user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    """Everything a doctor needs before reviewing a new report: profile, timeline, reports, notes, prescriptions."""
    patient = get_accessible_patient(db, user, patient_id)
    reports = report_service.list_reports_for_user(db, user, patient_id=patient.id)
    notes = db.scalars(select(DoctorNote).where(DoctorNote.patient_id == patient.id)
                       .order_by(DoctorNote.id.desc())).all()
    recs = db.scalars(select(DoctorRecommendation).where(DoctorRecommendation.patient_id == patient.id)
                      .order_by(DoctorRecommendation.id.desc())).all()
    entries = db.scalars(select(MedicalHistoryEntry).where(MedicalHistoryEntry.patient_id == patient.id)
                         .order_by(MedicalHistoryEntry.entry_date.desc())).all()
    prescriptions = [p for p in list_prescriptions_for_user(db, user, patient_id=patient.id)]
    return {
        "patient": patient_for_role(patient, DOCTOR).model_dump(mode="json"),
        "timeline": build_timeline(db, patient, DOCTOR, q),
        "reports": [report_list_item(r).model_dump(mode="json") for r in reports],
        "notes": [note_out(n).model_dump(mode="json") for n in notes],
        "recommendations": [recommendation_out(r).model_dump(mode="json") for r in recs],
        "history_entries": [{"id": e.id, "entry_date": e.entry_date.isoformat(), "entry_type": e.entry_type,
                             "description": e.description, "doctor_name": e.doctor.user.full_name} for e in entries],
        "prescriptions": [prescription_out(p).model_dump(mode="json") for p in prescriptions],
    }


# ------------------------------------------------------------------ review, notes, recommendations
@router.put("/reports/{report_id}/review", response_model=ReportDetail)
def review(report_id: PathId, data: ReviewRequest, request: Request, user: User = Depends(doctor_only),
           db: Session = Depends(get_db)):
    """Approve, modify or clarify the AI analysis and mark the report as reviewed."""
    doctor = get_doctor_profile(db, user)
    report = report_service.get_report_for_user(db, user, report_id)
    report_service.review_report(db, report, doctor, data.decision.upper(), data.comment)
    audit_service.log_action(db, user, audit_service.REPORT_REVIEWED, "report", report.id, request, data.decision)
    return report_detail(report, DOCTOR)


@router.post("/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def add_note(data: NoteCreate, request: Request, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    doctor = get_doctor_profile(db, user)
    patient = _authorized_patient_and_report(db, doctor, data.patient_id, data.report_id)
    note = DoctorNote(patient_id=patient.id, doctor_id=doctor.id, report_id=data.report_id, note=data.note.strip(),
                      priority=_check_priority(data.priority))
    db.add(note)
    db.commit()
    db.refresh(note)
    audit_service.log_action(db, user, audit_service.NOTE_ADDED, "note", note.id, request)
    return note_out(note)


@router.get("/notes", response_model=list[NoteOut])
def my_notes(patient_id: QueryId = None, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    doctor = get_doctor_profile(db, user)
    query = select(DoctorNote).where(DoctorNote.doctor_id == doctor.id).order_by(DoctorNote.id.desc())
    if patient_id is not None:
        query = query.where(DoctorNote.patient_id == patient_id)
    return [note_out(n) for n in db.scalars(query)]


@router.post("/recommendations", response_model=RecommendationOut, status_code=status.HTTP_201_CREATED)
def add_recommendation(data: RecommendationCreate, request: Request, user: User = Depends(doctor_only),
                       db: Session = Depends(get_db)):
    doctor = get_doctor_profile(db, user)
    patient = _authorized_patient_and_report(db, doctor, data.patient_id, data.report_id)
    rec = DoctorRecommendation(
        patient_id=patient.id, doctor_id=doctor.id, report_id=data.report_id, title=data.title.strip(),
        recommendation=data.recommendation.strip(), follow_up_date=data.follow_up_date,
        priority=_check_priority(data.priority))
    db.add(rec)
    db.commit()
    db.refresh(rec)
    audit_service.log_action(db, user, audit_service.RECOMMENDATION_ADDED, "recommendation", rec.id, request)
    return recommendation_out(rec)


@router.get("/recommendations", response_model=list[RecommendationOut])
def my_recommendations(patient_id: QueryId = None, user: User = Depends(doctor_only),
                       db: Session = Depends(get_db)):
    doctor = get_doctor_profile(db, user)
    query = select(DoctorRecommendation).where(DoctorRecommendation.doctor_id == doctor.id) \
        .order_by(DoctorRecommendation.id.desc())
    if patient_id is not None:
        query = query.where(DoctorRecommendation.patient_id == patient_id)
    return [recommendation_out(r) for r in db.scalars(query)]


@router.post("/history-entries", status_code=status.HTTP_201_CREATED)
def add_history_entry(data: HistoryEntryCreate, user: User = Depends(doctor_only), db: Session = Depends(get_db)):
    """Doctor adds background history (past illness, surgery ...) to the patient's record."""
    doctor = get_doctor_profile(db, user)
    patient = _authorized_patient_and_report(db, doctor, data.patient_id, None)
    entry = MedicalHistoryEntry(patient_id=patient.id, doctor_id=doctor.id, entry_date=data.entry_date,
                                entry_type=data.entry_type.strip(), description=data.description.strip())
    db.add(entry)
    db.commit()
    return {"id": entry.id}
