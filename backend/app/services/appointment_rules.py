"""The rules of an appointment time and of its status, in one place so the booking, rescheduling and referral paths cannot disagree.
Times are the hospital's wall-clock time (see app/utils/clock.py). Every rule here is enforced by the server; the pages only help the person choose."""
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models import Appointment
from app.utils import clock
from app.utils.appointment_time import bookable_problem, day_window, slot_times  # noqa: F401  (slot_times is used by the slots endpoint)

ACTIVE = ("SCHEDULED", "CONFIRMED")
# the only ways a status may change: forward in order, or cancelled while it is still open
NEXT_STATUS = {"SCHEDULED": {"CONFIRMED", "CANCELLED"}, "CONFIRMED": {"COMPLETED", "CANCELLED"}, "COMPLETED": set(), "CANCELLED": set()}


def check_bookable(when: datetime) -> None:
    """422 with a plain message when the time is not one that can be booked right now."""
    problem = bookable_problem(when)
    if problem:
        raise HTTPException(422, problem)


def check_patient_free(db: Session, patient_id: int, when: datetime, ignore_id: int | None = None) -> None:
    """One person cannot be in two places: no other open appointment of the same patient (with any doctor) at that slot."""
    query = select(Appointment.id).where(Appointment.patient_id == patient_id, Appointment.scheduled_at == when, Appointment.status.in_(ACTIVE))
    if ignore_id is not None:
        query = query.where(Appointment.id != ignore_id)
    if db.scalar(query):
        raise HTTPException(status.HTTP_409_CONFLICT, "This patient already has another appointment at that time.")


def check_status_change(current: str, new: str | None, scheduled_at: datetime) -> None:
    """Forward only: SCHEDULED -> CONFIRMED -> COMPLETED, or CANCELLED while open. A visit cannot be completed before its time."""
    if not new or new == current:
        return
    if new not in NEXT_STATUS.get(current, set()):
        allowed = ", ".join(sorted(NEXT_STATUS.get(current, set()))) or "nothing (it is final)"
        raise HTTPException(status.HTTP_409_CONFLICT, f"A {current.lower()} appointment cannot become {new.lower()}. From here it can become: {allowed}.")
    if new == "COMPLETED" and scheduled_at > clock.hospital_now() + timedelta(minutes=get_settings().appointment_grace_minutes):
        raise HTTPException(422, "This appointment is in the future, so it cannot be completed yet.")


def check_can_reschedule(current: str) -> None:
    if current not in ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A {current.lower()} appointment cannot be moved. Book a new one instead.")
