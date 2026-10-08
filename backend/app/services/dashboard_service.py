"""Numbers and lists for each role's dashboard. Everything is counted from the database."""
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import doctor_patient_ids, get_doctor_profile, get_patient_profile
from app.database.models import (
    Appointment, Doctor, DoctorNote, DoctorRecommendation, Employee, HealthReport, MedicineDispensing,
    MedicineInventory, Patient, PharmacyStaff, Prescription, User,
)
from app.services import report_service
from app.services.history_service import build_timeline
from app.services.serializers import (
    appointment_out, note_out, prescription_out, recommendation_out, report_list_item,
)

PATIENT_ROLE = "PATIENT"


def _today_range() -> tuple[datetime, datetime]:
    start = datetime.combine(date.today(), time.min)
    return start, start + timedelta(days=1)


def _count(db: Session, model, *conditions) -> int:
    return db.scalar(select(func.count(model.id)).where(*conditions)) or 0


# ------------------------------------------------------------------ admin
def admin_dashboard(db: Session) -> dict:
    start, end = _today_range()
    methods = dict(db.execute(select(HealthReport.processing_method, func.count(HealthReport.id))
                              .group_by(HealthReport.processing_method)).all())
    return {
        "total_patients": _count(db, Patient),
        "total_doctors": _count(db, Doctor),
        "total_employees": _count(db, Employee),
        "total_pharmacy_staff": _count(db, PharmacyStaff),
        "total_reports": _count(db, HealthReport),
        "reports_pending_review": _count(db, HealthReport, HealthReport.doctor_review_status == "PENDING"),
        "appointments_today": _count(db, Appointment, Appointment.scheduled_at >= start, Appointment.scheduled_at < end),
        "active_prescriptions": _count(db, Prescription, Prescription.status.in_(["ACTIVE", "PARTIALLY_DISPENSED"])),
        "total_prescriptions": _count(db, Prescription),
        "medicines_dispensed": db.scalar(select(func.coalesce(func.sum(MedicineDispensing.quantity_dispensed), 0))) or 0,
        "report_processing": {
            "by_method": {(k or "unknown"): v for k, v in methods.items()},
            "reviewed": _count(db, HealthReport, HealthReport.doctor_review_status == "REVIEWED"),
            "pending": _count(db, HealthReport, HealthReport.doctor_review_status == "PENDING"),
        },
    }


# ------------------------------------------------------------------ doctor
def doctor_dashboard(db: Session, user: User) -> dict:
    doctor = get_doctor_profile(db, user)
    patient_ids = doctor_patient_ids(db, doctor)
    start, end = _today_range()
    todays = db.scalars(select(Appointment).where(
        Appointment.doctor_id == doctor.id, Appointment.scheduled_at >= start, Appointment.scheduled_at < end,
        Appointment.status != "CANCELLED").order_by(Appointment.scheduled_at)).all()
    reports = report_service.list_reports_for_user(db, user)
    waiting = [r for r in reports if r.doctor_review_status == "PENDING"]
    follow_ups = db.scalars(select(DoctorRecommendation).where(
        DoctorRecommendation.doctor_id == doctor.id, DoctorRecommendation.follow_up_date >= date.today())
        .order_by(DoctorRecommendation.follow_up_date).limit(10)).all()
    notes = db.scalars(select(DoctorNote).where(DoctorNote.doctor_id == doctor.id)
                       .order_by(DoctorNote.id.desc()).limit(5)).all()
    prescriptions = db.scalars(select(Prescription).where(Prescription.doctor_id == doctor.id)
                               .order_by(Prescription.id.desc()).limit(5)).all()
    return {
        "todays_appointments": [appointment_out(a).model_dump(mode="json") for a in todays],
        "my_patients_count": len(patient_ids),
        "reports_waiting_count": len(waiting),
        "reports_waiting": [report_list_item(r).model_dump(mode="json") for r in waiting[:10]],
        "recent_reports": [report_list_item(r).model_dump(mode="json") for r in reports[:5]],
        "pending_follow_ups": [recommendation_out(f).model_dump(mode="json") for f in follow_ups],
        "recent_prescriptions": [prescription_out(p).model_dump(mode="json") for p in prescriptions],
        "recent_notes": [note_out(n).model_dump(mode="json") for n in notes],
    }


# ------------------------------------------------------------------ employee
def employee_dashboard(db: Session, user: User) -> dict:
    start, end = _today_range()
    todays = db.scalars(select(Appointment).where(
        Appointment.scheduled_at >= start, Appointment.scheduled_at < end).order_by(Appointment.scheduled_at)).all()
    uploads = db.scalars(select(HealthReport).where(HealthReport.uploaded_by == user.id)
                         .order_by(HealthReport.id.desc()).limit(10)).all()
    awaiting = db.scalars(select(HealthReport).where(HealthReport.doctor_review_status == "PENDING")
                          .order_by(HealthReport.id.desc()).limit(10)).all()
    return {
        "patients_count": _count(db, Patient),
        "appointments_today_count": len(todays),
        "appointments_today": [appointment_out(a).model_dump(mode="json") for a in todays],
        "my_recent_uploads": [report_list_item(r).model_dump(mode="json") for r in uploads],
        "awaiting_review_count": _count(db, HealthReport, HealthReport.doctor_review_status == "PENDING"),
        "awaiting_review": [report_list_item(r).model_dump(mode="json") for r in awaiting],
    }


# ------------------------------------------------------------------ patient
def patient_dashboard(db: Session, user: User) -> dict:
    patient = get_patient_profile(db, user)
    upcoming = db.scalars(select(Appointment).where(
        Appointment.patient_id == patient.id, Appointment.scheduled_at >= datetime.now(),
        Appointment.status.in_(["SCHEDULED", "CONFIRMED"])).order_by(Appointment.scheduled_at).limit(1)).first()
    reports = report_service.list_reports_for_user(db, user)
    notes = db.scalars(select(DoctorNote).where(DoctorNote.patient_id == patient.id)
                       .order_by(DoctorNote.id.desc()).limit(3)).all()
    recs = db.scalars(select(DoctorRecommendation).where(DoctorRecommendation.patient_id == patient.id)
                      .order_by(DoctorRecommendation.id.desc()).limit(3)).all()
    active = db.scalars(select(Prescription).where(
        Prescription.patient_id == patient.id, Prescription.status.in_(["ACTIVE", "PARTIALLY_DISPENSED"]))
        .order_by(Prescription.id.desc())).all()
    return {
        "patient_name": user.full_name,
        "patient_code": patient.patient_code,
        "next_appointment": appointment_out(upcoming).model_dump(mode="json") if upcoming else None,
        "latest_report": report_list_item(reports[0]).model_dump(mode="json") if reports else None,
        "doctor_notes": [note_out(n).model_dump(mode="json") for n in notes],
        "recommendations": [recommendation_out(r).model_dump(mode="json") for r in recs],
        "active_prescriptions": [prescription_out(p).model_dump(mode="json") for p in active],
        "recent_history": build_timeline(db, patient, PATIENT_ROLE)[:6],
    }


# ------------------------------------------------------------------ pharmacy
def pharmacy_dashboard(db: Session) -> dict:
    soon = date.today() + timedelta(days=30)
    low_stock = db.scalars(select(MedicineInventory).where(MedicineInventory.quantity <= 10)
                           .order_by(MedicineInventory.quantity).limit(10)).all()
    expiring = db.scalars(select(MedicineInventory).where(
        MedicineInventory.expiry_date.is_not(None), MedicineInventory.expiry_date <= soon,
        MedicineInventory.quantity > 0).order_by(MedicineInventory.expiry_date).limit(10)).all()
    return {
        "todays_prescriptions": _count(db, Prescription, Prescription.prescription_date == date.today(),
                                       Prescription.status != "CANCELLED"),
        "pending_prescriptions": _count(db, Prescription, Prescription.status == "ACTIVE"),
        "partially_dispensed": _count(db, Prescription, Prescription.status == "PARTIALLY_DISPENSED"),
        "dispensed": _count(db, Prescription, Prescription.status == "DISPENSED"),
        "low_stock": [{"id": i.id, "medicine_name": i.medicine_name, "quantity": i.quantity} for i in low_stock],
        "expiring_soon": [{"id": i.id, "medicine_name": i.medicine_name, "quantity": i.quantity,
                           "expiry_date": i.expiry_date.isoformat()} for i in expiring],
    }
