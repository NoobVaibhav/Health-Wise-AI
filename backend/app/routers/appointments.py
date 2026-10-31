"""Appointments: employees/admins manage all, doctors see their own, patients book/cancel their own."""
import json
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import (
    ADMIN, DOCTOR, EMPLOYEE, PATIENT, forbidden, get_current_user, get_doctor_profile, get_patient_profile,
)
from app.database.connection import get_db
from app.database.models import Appointment, Department, Doctor, Patient, User
from app.schemas.appointment import STATUSES, AppointmentCreate, AppointmentOut, AppointmentUpdate
from app.services import audit_service
from app.services.serializers import appointment_out
from app.utils.validators import PathId, QueryId, one_of
STATUS_FILTER = one_of("SCHEDULED", "CONFIRMED", "COMPLETED", "CANCELLED", name="status")

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def create_appointment(data: AppointmentCreate, request: Request, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    if user.role == PATIENT:
        patient = get_patient_profile(db, user)  # a patient can only book for themselves
    elif user.role in (EMPLOYEE, ADMIN):
        patient = db.get(Patient, data.patient_id) if data.patient_id else None
        if patient is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found.")
    else:
        raise forbidden()
    doctor = db.get(Doctor, data.doctor_id)
    if doctor is None or not doctor.user.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found.")
    if data.department_id and not db.get(Department, data.department_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found.")
    if data.scheduled_at < datetime.now() - timedelta(minutes=5):
        raise HTTPException(422, "The appointment time must be in the future.")
    clash = db.scalar(select(Appointment.id).where(
        Appointment.doctor_id == doctor.id, Appointment.scheduled_at == data.scheduled_at,
        Appointment.status.in_(["SCHEDULED", "CONFIRMED"])))
    if clash:
        raise HTTPException(status.HTTP_409_CONFLICT, "This doctor already has an appointment at that time.")
    appointment = Appointment(patient_id=patient.id, doctor_id=doctor.id, department_id=data.department_id,
                              scheduled_at=data.scheduled_at, reason=data.reason, status="SCHEDULED",
                              symptoms_json=json.dumps([s.strip() for s in data.symptoms if s.strip()]) if data.symptoms else None,
                              duration=data.duration, details=data.details, created_by=user.id)
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    audit_service.log_action(db, user, audit_service.APPOINTMENT_CREATED, "appointment", appointment.id, request)
    return appointment_out(appointment, user.role)


@router.get("", response_model=list[AppointmentOut])
def list_appointments(day: date | None = None, status_filter: STATUS_FILTER = None, patient_id: QueryId = None,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(Appointment)
    if user.role == PATIENT:
        query = query.where(Appointment.patient_id == get_patient_profile(db, user).id)
    elif user.role == DOCTOR:
        query = query.where(Appointment.doctor_id == get_doctor_profile(db, user).id)
    elif user.role in (ADMIN, EMPLOYEE):
        if patient_id is not None:
            query = query.where(Appointment.patient_id == patient_id)
    else:
        raise forbidden()
    if day is not None:
        start = datetime.combine(day, time.min)
        query = query.where(Appointment.scheduled_at >= start, Appointment.scheduled_at < start + timedelta(days=1))
    if status_filter:
        query = query.where(Appointment.status == status_filter.upper())
    return [appointment_out(a, user.role) for a in db.scalars(query.order_by(Appointment.scheduled_at.desc()))]


@router.put("/{appointment_id}", response_model=AppointmentOut)
def update_appointment(appointment_id: PathId, data: AppointmentUpdate, request: Request,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found.")

    new_status = data.status.upper() if data.status else None
    if new_status and new_status not in STATUSES:
        raise HTTPException(422, f"Status must be one of {', '.join(STATUSES)}.")

    if user.role == PATIENT:
        if appointment.patient.user_id != user.id:
            raise forbidden()
        if new_status not in (None, "CANCELLED") or data.scheduled_at or data.reason:
            raise forbidden()  # patients may only cancel their own appointment
    elif user.role == DOCTOR:
        if appointment.doctor_id != get_doctor_profile(db, user).id:
            raise forbidden()
        if data.scheduled_at or data.reason:
            raise forbidden()  # doctors update the status; rescheduling is done by reception
    elif user.role not in (ADMIN, EMPLOYEE):
        raise forbidden()

    if new_status:
        appointment.status = new_status
    if data.scheduled_at:
        appointment.scheduled_at = data.scheduled_at
    if data.reason is not None:
        appointment.reason = data.reason
    db.commit()
    audit_service.log_action(db, user, audit_service.APPOINTMENT_UPDATED, "appointment", appointment.id, request,
                             new_status)
    return appointment_out(appointment, user.role)
