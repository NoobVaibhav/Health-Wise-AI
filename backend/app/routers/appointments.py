"""Appointments: employees/admins manage all, doctors see their own, patients book/cancel their own."""
import json
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.permissions import (
    ADMIN, DOCTOR, EMPLOYEE, PATIENT, forbidden, get_current_user, get_doctor_profile, get_patient_profile,
)
from app.database.connection import get_db
from app.database.models import Appointment, Department, Doctor, Patient, User
from app.schemas.appointment import STATUSES, AppointmentCreate, AppointmentOut, AppointmentUpdate
from app.services import appointment_rules as rules, audit_service
from app.utils import clock
from app.services.serializers import appointment_out
from app.utils.locking import lock
from app.utils.validators import PathId, QueryId, one_of

ACTIVE = ["SCHEDULED", "CONFIRMED"]


def ensure_free(db: Session, doctor: Doctor, when: datetime, ignore_id: int | None = None) -> None:
    """The doctor has nothing else at that time. The doctor's row is locked first, so two bookings made at the same moment take turns and the second one sees the first."""
    lock(db, doctor)
    query = select(Appointment.id).where(Appointment.doctor_id == doctor.id, Appointment.scheduled_at == when, Appointment.status.in_(ACTIVE))
    if ignore_id is not None:
        query = query.where(Appointment.id != ignore_id)
    if db.scalar(query):
        raise HTTPException(status.HTTP_409_CONFLICT, "This doctor already has an appointment at that time.")
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
    if not db.get(User, patient.user_id).is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found.")
    rules.check_bookable(data.scheduled_at)                 # past / slot / opening hours / how far ahead, in the hospital's time
    ensure_free(db, doctor, data.scheduled_at)
    lock(db, patient)
    rules.check_patient_free(db, patient.id, data.scheduled_at)
    appointment = Appointment(patient_id=patient.id, doctor_id=doctor.id, department_id=data.department_id,
                              scheduled_at=data.scheduled_at, reason=data.reason, status="SCHEDULED",
                              symptoms_json=json.dumps([s.strip() for s in data.symptoms if s.strip()]) if data.symptoms else None,
                              duration=data.duration, details=data.details, created_by=user.id)
    db.add(appointment)
    try:
        db.commit()
    except IntegrityError:                                   # the database's own rule (one open appointment per doctor and slot) caught a request that raced past the checks
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This doctor already has an appointment at that time.")
    db.refresh(appointment)
    audit_service.log_action(db, user, audit_service.APPOINTMENT_CREATED, "appointment", appointment.id, request)
    return appointment_out(appointment, user.role)


@router.get("/slots")
def appointment_slots(doctor_id: QueryId, day: date, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The day's slots of one doctor, each marked free or not (past, or taken). Used by the booking page; the server checks the same rules again when booking."""
    if doctor_id is None:
        raise HTTPException(422, "Choose a doctor.")
    doctor = db.get(Doctor, doctor_id)
    if doctor is None or not doctor.user.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found.")
    now = clock.hospital_now()
    taken = {a for a in db.scalars(select(Appointment.scheduled_at).where(
        Appointment.doctor_id == doctor.id, Appointment.status.in_(ACTIVE),
        Appointment.scheduled_at >= datetime.combine(day, time.min), Appointment.scheduled_at < datetime.combine(day, time.min) + timedelta(days=1)))}
    out = []
    for slot in rules.slot_times(day):
        try:
            rules.check_bookable(slot)
            reason = "taken" if slot in taken else None
        except HTTPException:
            reason = "taken" if slot in taken else "unavailable"
        out.append({"time": slot.strftime("%H:%M"), "at": slot.isoformat(), "available": reason is None, "reason": reason})
    return {"doctor_id": doctor.id, "day": day.isoformat(), "now": now.isoformat(timespec="minutes"), "slots": out}


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

    lock(db, appointment)                                    # two people changing the same appointment take turns
    moving = data.scheduled_at is not None and data.scheduled_at != appointment.scheduled_at
    rules.check_status_change(appointment.status, new_status, data.scheduled_at if moving else appointment.scheduled_at)
    if moving:
        rules.check_can_reschedule(appointment.status)
        if new_status and new_status not in rules.ACTIVE:
            raise HTTPException(422, "An appointment cannot be moved and closed in the same step.")
        rules.check_bookable(data.scheduled_at)
        ensure_free(db, appointment.doctor, data.scheduled_at, ignore_id=appointment.id)
        rules.check_patient_free(db, appointment.patient_id, data.scheduled_at, ignore_id=appointment.id)
    if new_status:
        appointment.status = new_status
    if moving:
        appointment.scheduled_at = data.scheduled_at
    if data.reason is not None:
        appointment.reason = data.reason
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This doctor already has an appointment at that time.")
    audit_service.log_action(db, user, audit_service.APPOINTMENT_UPDATED, "appointment", appointment.id, request,
                             new_status)
    return appointment_out(appointment, user.role)
