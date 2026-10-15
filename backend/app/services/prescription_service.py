"""Prescriptions are created ONLY by doctors. The system never suggests medicines."""
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import (
    DOCTOR, PATIENT, PHARMACY, doctor_can_access_patient, forbidden, get_doctor_profile, get_patient_profile,
)
from app.database.models import Doctor, HealthReport, Patient, Prescription, PrescriptionItem, User
from app.schemas.prescription import PrescriptionCreate
from app.services.serializers import effective_status


def create_prescription(db: Session, doctor: Doctor, data: PrescriptionCreate) -> Prescription:
    patient = db.get(Patient, data.patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found.")
    if not doctor_can_access_patient(db, doctor, patient):
        raise forbidden()
    if data.report_id is not None:
        report = db.get(HealthReport, data.report_id)
        if report is None or report.patient_id != patient.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found for this patient.")
    rx = Prescription(
        patient_id=patient.id, doctor_id=doctor.id, report_id=data.report_id, prescription_date=date.today(),
        clinical_indication=data.clinical_indication, notes=data.notes, status="ACTIVE",
        tests_advised="\n".join(data.tests) or None,
    )
    rx.items = [PrescriptionItem(**item.model_dump(), dispense_status="PENDING") for item in data.items]
    db.add(rx)
    db.commit()
    db.refresh(rx)
    return rx


def list_prescriptions_for_user(db: Session, user: User, q: str | None = None,
                                patient_id: int | None = None) -> list[Prescription]:
    """Prescriptions this user may see, newest first.
    - patient: own      - doctor: the ones they wrote      - pharmacy: all except cancelled (search by q)"""
    query = select(Prescription)
    if user.role == PATIENT:
        query = query.where(Prescription.patient_id == get_patient_profile(db, user).id)
    elif user.role == DOCTOR:
        query = query.where(Prescription.doctor_id == get_doctor_profile(db, user).id)
    elif user.role == PHARMACY:
        query = query.where(Prescription.status != "CANCELLED")
    else:
        raise forbidden()
    if patient_id is not None:
        query = query.where(Prescription.patient_id == patient_id)
    rows = db.scalars(query.order_by(Prescription.id.desc())).all()
    if q:
        needle = q.strip().lower()
        rows = [r for r in rows if needle in f"rx-{r.id:05d}".lower() or needle in r.patient.patient_code.lower()
                or needle in r.patient.user.full_name.lower()]
    return rows


def get_prescription_for_user(db: Session, user: User, prescription_id: int) -> Prescription:
    rx = db.get(Prescription, prescription_id)
    if rx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active prescription found.")
    if user.role == PATIENT:
        if rx.patient.user_id != user.id:
            raise forbidden()
    elif user.role == DOCTOR:
        if rx.doctor_id != get_doctor_profile(db, user).id:
            raise forbidden()
    elif user.role == PHARMACY:
        if rx.status == "CANCELLED":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No active prescription found.")
    else:
        raise forbidden()
    return rx


def cancel_prescription(db: Session, rx: Prescription) -> Prescription:
    if rx.status == "DISPENSED":
        raise HTTPException(status.HTTP_409_CONFLICT, "A fully dispensed prescription cannot be cancelled.")
    rx.status = "CANCELLED"
    db.commit()
    db.refresh(rx)
    return rx


def is_open(rx: Prescription) -> bool:
    return effective_status(rx) in ("ACTIVE", "PARTIALLY_DISPENSED")
