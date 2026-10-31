"""The hospital itself: profile, branches, settings and the price list. The letterhead of prescriptions and bills reads the profile from here
(and falls back to the .env values when no profile has been saved yet)."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.connection import SessionLocal
from app.database.models import Branch, HospitalProfile, HospitalSetting

# key -> (default, kind, low, high). The hospital can change these without a code change.
SETTINGS: dict[str, tuple[str, str, float | None, float | None]] = {
    "break_glass_minutes": ("60", "int", 5, 240),
    "appointment_slot_minutes": ("15", "int", 5, 120),
    "working_hours_start": ("09:00", "time", None, None),
    "working_hours_end": ("17:00", "time", None, None),
    "currency": ("INR", "text", None, None),
    "invoice_prefix": ("INV", "text", None, None),
    "duplicate_check": ("on", "choice:on,off", None, None),
}

def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def invalidate() -> None:
    """Kept for the callers that change the profile (nothing is cached: a letterhead is read from the database every time, one small query)."""


def profile_text(key: str) -> str | None:
    """name / address / phone / email for the letterhead: the saved profile first, then the .env value."""
    with SessionLocal() as db:
        row = db.scalar(select(HospitalProfile).limit(1))
        saved = (getattr(row, key, "") or "").strip() if row else ""
    if saved:
        return saved
    return (getattr(get_settings(), f"hospital_{key}", "") or "").strip() or None


def get_profile(db: Session) -> HospitalProfile:
    row = db.scalar(select(HospitalProfile).limit(1))
    if row is None:
        s = get_settings()
        row = HospitalProfile(name=s.hospital_name or None, address=s.hospital_address or None, phone=s.hospital_phone or None, email=s.hospital_email or None)
        db.add(row)
        db.commit()
    return row


def default_branch(db: Session) -> Branch:
    branch = db.scalar(select(Branch).where(Branch.is_active.is_(True)).order_by(Branch.id).limit(1)) or db.scalar(select(Branch).order_by(Branch.id).limit(1))
    if branch is None:
        branch = Branch(code="HW", name="Main Branch", is_active=True)
        db.add(branch)
        db.commit()
    return branch


def setting_value(db: Session, key: str, branch_id: int | None = None) -> str:
    """A branch value, else the hospital-wide value, else the default."""
    for scope in ([branch_id] if branch_id else []) + [None]:
        row = db.scalar(select(HospitalSetting).where(HospitalSetting.key == key, HospitalSetting.branch_id.is_(None) if scope is None else HospitalSetting.branch_id == scope))
        if row:
            return row.value
    return SETTINGS[key][0]


def check_setting(key: str, value: str) -> str:
    """The cleaned value, or a ValueError with a sentence (the router turns it into a 422)."""
    if key not in SETTINGS:
        raise ValueError(f"Unknown setting: {key}.")
    _, kind, low, high = SETTINGS[key]
    value = str(value).strip()
    if kind == "int":
        if not value.isdigit() or not (low <= int(value) <= high):
            raise ValueError(f"{key} must be a whole number from {int(low)} to {int(high)}.")
    elif kind == "time":
        parts = value.split(":")
        if len(parts) != 2 or not all(p.isdigit() for p in parts) or not (0 <= int(parts[0]) < 24 and 0 <= int(parts[1]) < 60) or len(parts[0]) != 2 or len(parts[1]) != 2:
            raise ValueError(f"{key} must be a time like 09:00.")
    elif kind.startswith("choice:"):
        if value not in kind.split(":", 1)[1].split(","):
            raise ValueError(f"{key} must be one of: {kind.split(':', 1)[1].replace(',', ', ')}.")
    elif not value or len(value) > 20:
        raise ValueError(f"{key} must be 1 to 20 characters.")
    return value
