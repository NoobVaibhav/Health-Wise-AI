"""Patient portal: a patient sees ONLY their own data (reports appear fully after doctor review)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import PATIENT, get_patient_profile, require_roles
from app.database.connection import get_db
from app.database.models import DoctorNote, DoctorRecommendation, MedicalHistoryEntry, User
from app.schemas.doctor import NoteOut, RecommendationOut
from app.schemas.patient import PatientFull
from app.schemas.prescription import PrescriptionOut
from app.schemas.report import ReportListItem
from app.services import dashboard_service, prescription_service, report_service
from app.services.history_service import build_timeline
from app.services.serializers import (
    note_out, patient_for_role, prescription_out, recommendation_out, report_list_item,
)
from app.utils.validators import SearchText

router = APIRouter(prefix="/api/patient", tags=["patient"])
patient_only = require_roles(PATIENT)


@router.get("/dashboard")
def dashboard(user: User = Depends(patient_only), db: Session = Depends(get_db)):
    return dashboard_service.patient_dashboard(db, user)


@router.get("/profile", response_model=PatientFull)
def profile(user: User = Depends(patient_only), db: Session = Depends(get_db)):
    return patient_for_role(get_patient_profile(db, user), PATIENT)


@router.get("/reports", response_model=list[ReportListItem])
def my_reports(user: User = Depends(patient_only), db: Session = Depends(get_db)):
    return [report_list_item(r) for r in report_service.list_reports_for_user(db, user)]


@router.get("/history")
def my_history(q: SearchText = None, user: User = Depends(patient_only), db: Session = Depends(get_db)):
    patient = get_patient_profile(db, user)
    entries = db.scalars(select(MedicalHistoryEntry).where(MedicalHistoryEntry.patient_id == patient.id)
                         .order_by(MedicalHistoryEntry.entry_date.desc())).all()
    return {
        "timeline": build_timeline(db, patient, PATIENT, q),
        "history_entries": [{"id": e.id, "entry_date": e.entry_date.isoformat(), "entry_type": e.entry_type,
                             "description": e.description, "doctor_name": e.doctor.user.full_name}
                            for e in entries],
    }


@router.get("/notes", response_model=list[NoteOut])
def my_notes(user: User = Depends(patient_only), db: Session = Depends(get_db)):
    patient = get_patient_profile(db, user)
    return [note_out(n) for n in db.scalars(select(DoctorNote).where(DoctorNote.patient_id == patient.id)
                                            .order_by(DoctorNote.id.desc()))]


@router.get("/recommendations", response_model=list[RecommendationOut])
def my_recommendations(user: User = Depends(patient_only), db: Session = Depends(get_db)):
    patient = get_patient_profile(db, user)
    return [recommendation_out(r) for r in db.scalars(
        select(DoctorRecommendation).where(DoctorRecommendation.patient_id == patient.id)
        .order_by(DoctorRecommendation.id.desc()))]


@router.get("/prescriptions", response_model=list[PrescriptionOut])
def my_prescriptions(user: User = Depends(patient_only), db: Session = Depends(get_db)):
    return [prescription_out(r) for r in prescription_service.list_prescriptions_for_user(db, user)]
