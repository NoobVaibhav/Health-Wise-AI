"""The pure rules for WHEN an appointment may start (no database): a slot, inside opening hours, not in the past, not too far ahead. Times are the hospital's
wall-clock time (see clock.py). Used by the request schemas (so a bad time is a 422 from the model itself), and again by the booking, rescheduling and referral paths."""
from datetime import date, datetime, time, timedelta

from app.core.config import get_settings
from app.utils import clock


def _clock_time(text: str) -> time:
    hour, minute = text.split(":")
    return time(int(hour), int(minute))


def day_window() -> tuple[time, time, int]:
    s = get_settings()
    return _clock_time(s.appointment_day_start), _clock_time(s.appointment_day_end), max(5, s.appointment_slot_minutes)


def slot_times(day: date) -> list[datetime]:
    """Every bookable start time of a day."""
    start, end, step = day_window()
    out, cursor = [], datetime.combine(day, start)
    limit = datetime.combine(day, end)
    while cursor + timedelta(minutes=step) <= limit:
        out.append(cursor)
        cursor += timedelta(minutes=step)
    return out


def bookable_problem(when: datetime) -> str | None:
    """None when the time can be booked right now, otherwise a plain message saying why not."""
    s = get_settings()
    start, end, step = day_window()
    now = clock.hospital_now()
    if when.second or when.microsecond or (when.hour * 60 + when.minute) % step:
        return f"Appointments start on a {step}-minute slot (for example 10:00, 10:{step:02d}). Please choose a time from the list."
    if when.time() < start or when + timedelta(minutes=step) > datetime.combine(when.date(), end):
        return f"The doctor sees patients between {start:%H:%M} and {end:%H:%M}. Please choose a time in that period."
    if when < now - timedelta(minutes=s.appointment_grace_minutes):
        return f"That time has already passed (it is {now:%d %b %Y, %H:%M} at the hospital now). Please choose a time that is still ahead."
    if when > now + timedelta(days=s.appointment_max_advance_days):
        return f"Appointments can be booked up to {s.appointment_max_advance_days} days ahead, until {(now + timedelta(days=s.appointment_max_advance_days)):%d %b %Y}."
    return None


def check_appointment_time(when: datetime) -> datetime:
    """For the request schemas: a ValueError (so FastAPI answers 422 naming the field) when the time cannot be booked."""
    problem = bookable_problem(when)
    if problem:
        raise ValueError(problem)
    return when
