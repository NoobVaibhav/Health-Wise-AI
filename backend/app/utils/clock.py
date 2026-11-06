"""The hospital's clock. Appointment times are stored as the hospital's wall-clock time (naive, e.g. 2026-11-05 10:15 means 10:15 in India),
so what is stored does not depend on the time zone of the server or the browser. Everything that needs 'now' asks here, so tests can freeze it
(patch `_utc_now`)."""
from datetime import datetime, timedelta, timezone, tzinfo

from app.core.config import get_settings

_INDIA = timezone(timedelta(hours=5, minutes=30))      # India has no daylight saving, so this is exact if the time-zone database is missing


def hospital_tz() -> tzinfo:
    name = get_settings().hospital_timezone
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:                                      # no tz database on this machine (common on Windows)
        return _INDIA


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hospital_now() -> datetime:
    """Now in the hospital's time zone, without the zone attached (the same shape as the stored appointment times)."""
    return _utc_now().astimezone(hospital_tz()).replace(tzinfo=None)


def to_hospital_time(value: datetime) -> datetime:
    """A time with an offset (2026-11-05T10:00:00Z, ...+05:30) becomes the hospital's wall-clock time; a time without one already is."""
    if value.tzinfo is None:
        return value
    try:
        return value.astimezone(hospital_tz()).replace(tzinfo=None)
    except (OverflowError, ValueError, OSError):
        return value.replace(tzinfo=None)


def hospital_today():
    """Today's date at the hospital (the server's own date can still be 'yesterday' for five and a half hours of every Indian morning)."""
    return hospital_now().date()
