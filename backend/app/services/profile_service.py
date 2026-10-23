"""My profile: the details each role shows, what they may edit, and the profile picture.

Rules:
- the email, the role and anything the hospital assigns (department, specialization, designation, pharmacy or
  laboratory name, patient ID, doctor, clinical details) are read-only; only the person's own contact and
  professional details can be edited here
- a profile picture is checked by really opening it as an image (the file name and type sent by the browser are not
  trusted), turned into a 256 x 256 JPEG and stored privately; it is served only through the API
"""
import io
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import ADMIN, DOCTOR, EMPLOYEE, LAB, PATIENT, PHARMACY
from app.database.models import AuditLog, Doctor, Employee, LabStaff, Patient, PharmacyStaff, User
from app.schemas.profile import ProfileField, ProfileOut, ProfileUpdate, ProfileUser

ROLE_LABELS = {ADMIN: "Administrator", DOCTOR: "Doctor", EMPLOYEE: "Hospital employee", PATIENT: "Patient",
               PHARMACY: "Pharmacy staff", LAB: "Laboratory staff"}
PROFILE_MODEL = {DOCTOR: Doctor, EMPLOYEE: Employee, PATIENT: Patient, PHARMACY: PharmacyStaff, LAB: LabStaff}
PHONE_RE = re.compile(r"^[0-9+\-() ]{7,20}$")

MAX_AVATAR_BYTES = 5 * 1024 * 1024
MAX_AVATAR_PIXELS = 25_000_000
AVATAR_SIZE = 256
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


@dataclass(frozen=True)
class Spec:
    key: str
    label: str
    kind: str = "text"
    editable: bool = False
    help: str | None = None
    max_length: int = 150
    getter: Callable[[Any], Any] | None = None       # for values that are not a plain column


def _age(patient: Patient) -> str | None:
    dob = patient.date_of_birth
    if not dob:
        return None
    today = date.today()
    return f"{today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))} years"


FIELDS: dict[str, list[Spec]] = {
    ADMIN: [],
    DOCTOR: [
        Spec("phone", "Phone", editable=True, max_length=20),
        Spec("specialization", "Specialization", help="Set by the hospital admin."),
        Spec("department", "Department", help="Set by the hospital admin.", getter=lambda d: d.department.name if d.department else None),
        Spec("qualification", "Qualification (for example MBBS, MD)", editable=True),
        Spec("registration_number", "Medical registration number", editable=True, max_length=50),
        Spec("experience_years", "Years of experience", kind="number", editable=True),
    ],
    EMPLOYEE: [
        Spec("phone", "Phone", editable=True, max_length=20),
        Spec("designation", "Job title", help="Set by the hospital admin."),
        Spec("address", "Address", kind="textarea", editable=True, max_length=300),
    ],
    PHARMACY: [
        Spec("phone", "Phone", editable=True, max_length=20),
        Spec("pharmacy_name", "Pharmacy name", help="Set by the hospital admin."),
        Spec("license_number", "Drug licence number", editable=True, max_length=50),
        Spec("address", "Address", kind="textarea", editable=True, max_length=300),
    ],
    LAB: [
        Spec("phone", "Phone", editable=True, max_length=20),
        Spec("lab_name", "Laboratory name", help="Set by the hospital admin."),
        Spec("registration_number", "Registration number", editable=True, max_length=50),
        Spec("address", "Address", kind="textarea", editable=True, max_length=300),
    ],
    PATIENT: [
        Spec("patient_code", "Patient ID"),
        Spec("date_of_birth", "Date of birth", kind="date", help="To correct this, please ask hospital reception."),
        Spec("age", "Age", getter=_age),
        Spec("gender", "Gender"),
        Spec("phone", "Phone", editable=True, max_length=20),
        Spec("address", "Address", kind="textarea", editable=True, max_length=300),
        Spec("emergency_contact", "Emergency contact (name and phone)", editable=True),
        Spec("blood_group", "Blood group", help="Medical details are changed only by the doctor or reception."),
        Spec("allergies", "Allergies", kind="textarea"),
        Spec("current_medications", "Current medicines", kind="textarea"),
        Spec("assigned_doctor", "My doctor", getter=lambda p: p.assigned_doctor.user.full_name if p.assigned_doctor else None),
    ],
}


def _row(db: Session, user: User):
    model = PROFILE_MODEL.get(user.role)
    return db.scalar(select(model).where(model.user_id == user.id)) if model else None


def _value(spec: Spec, row) -> str | int | None:
    if row is None:
        return None
    raw = spec.getter(row) if spec.getter else getattr(row, spec.key, None)
    if isinstance(raw, date):
        return raw.isoformat()
    return raw


def avatar_version(user: User) -> str | None:
    return os.path.splitext(os.path.basename(user.avatar_path))[0] if user.avatar_path else None


def profile_user(db: Session, user: User) -> ProfileUser:
    last = db.scalar(select(func.max(AuditLog.timestamp)).where(AuditLog.user_id == user.id, AuditLog.action == "LOGIN"))
    return ProfileUser(id=user.id, email=user.email, full_name=user.full_name, role=user.role,
                       role_label=ROLE_LABELS.get(user.role, user.role), created_at=user.created_at, last_login=last,
                       has_avatar=bool(user.avatar_path), avatar_version=avatar_version(user))


def get_profile(db: Session, user: User) -> ProfileOut:
    row = _row(db, user)
    return ProfileOut(user=profile_user(db, user), fields=[
        ProfileField(key=s.key, label=s.label, kind=s.kind, value=_value(s, row), editable=s.editable, help=s.help)
        for s in FIELDS.get(user.role, [])])


def update_profile(db: Session, user: User, data: ProfileUpdate) -> ProfileOut:
    specs = {s.key: s for s in FIELDS.get(user.role, [])}
    row = _row(db, user)
    clean: dict[str, Any] = {}
    for key, raw in data.values.items():
        spec = specs.get(key)
        if spec is None or not spec.editable:
            raise HTTPException(422, f"'{key}' cannot be changed here.")
        text = ("" if raw is None else str(raw)).strip()
        if spec.kind == "number":
            if text == "":
                clean[key] = None
            elif not text.isdigit() or not 0 <= int(text) <= 70:
                raise HTTPException(422, f"{spec.label} must be a whole number from 0 to 70.")
            else:
                clean[key] = int(text)
            continue
        if len(text) > spec.max_length:
            raise HTTPException(422, f"{spec.label} is too long (at most {spec.max_length} characters).")
        if key == "phone" and text and not PHONE_RE.match(text):
            raise HTTPException(422, "Phone can have only digits, spaces and + - ( ) (7 to 20 characters).")
        clean[key] = text or None
    if clean and row is None:
        raise HTTPException(422, "This account has no extra details to edit.")
    for key, value in clean.items():
        setattr(row, key, value)
    if data.full_name is not None:
        user.full_name = " ".join(data.full_name.split())
    db.commit()
    db.refresh(user)
    return get_profile(db, user)


# ------------------------------------------------------------------ profile picture
def _avatar_dir() -> str:
    path = os.path.join(get_settings().upload_dir, "avatars")
    os.makedirs(path, exist_ok=True)
    return path


def avatar_file(user: User) -> str | None:
    if not user.avatar_path:
        return None
    path = os.path.join(get_settings().upload_dir, user.avatar_path)
    return path if os.path.isfile(path) else None


def set_avatar(db: Session, user: User, content: bytes) -> User:
    if not content:
        raise HTTPException(422, "Please choose a picture.")
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(413, "The picture is too big. Please use one under 5 MB.")
    bad = HTTPException(422, "This is not a usable picture. Please choose a JPG, PNG or WEBP photo.")
    try:
        probe = Image.open(io.BytesIO(content))
        if probe.format not in ALLOWED_FORMATS or probe.width * probe.height > MAX_AVATAR_PIXELS:
            raise bad
        probe.verify()
        image = Image.open(io.BytesIO(content))
        image = ImageOps.exif_transpose(image)
        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGBA")
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.getchannel("A"))
            image = background
        else:
            image = image.convert("RGB")
        image = ImageOps.fit(image, (AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise bad

    name = f"avatars/{uuid.uuid4().hex}.jpg"
    path = os.path.join(get_settings().upload_dir, name)
    _avatar_dir()
    image.save(path, "JPEG", quality=88, optimize=True)
    old = avatar_file(user)
    user.avatar_path = name
    db.commit()
    if old and os.path.abspath(old) != os.path.abspath(path):
        try:
            os.remove(old)
        except OSError:
            pass
    db.refresh(user)
    return user


def remove_avatar(db: Session, user: User) -> User:
    old = avatar_file(user)
    user.avatar_path = None
    db.commit()
    if old:
        try:
            os.remove(old)
        except OSError:
            pass
    db.refresh(user)
    return user


def may_view_avatar(viewer: User, target: User) -> bool:
    """A patient's picture is private to them, the admin and the hospital staff who care for patients."""
    if viewer.id == target.id or target.role != PATIENT:
        return True
    return viewer.role in (ADMIN, DOCTOR, EMPLOYEE)
