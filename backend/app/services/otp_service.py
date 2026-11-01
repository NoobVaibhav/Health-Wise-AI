"""Sign-in with a mobile number: a 6-digit one-time code.

Rules:
- the same answer is given for a number that is registered and one that is not (nobody can find out which numbers exist)
- a number must belong to exactly ONE active account; a number shared by two accounts cannot be used (use the password)
- a code lives 5 minutes, is stored only as a hash, works once, and is cancelled after 5 wrong tries; at most 3 codes per number in 10 minutes
- the code is sent through an adapter. This build has no SMS provider: with OTP_DEMO_MODE=true (local demo only) the code is returned to the screen,
  otherwise it is not delivered anywhere until an SMS adapter is set up. The code is never written to the log.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models import Doctor, Employee, LabStaff, LoginOtp, Nurse, Patient, PharmacyStaff, RadiologyStaff, User, utcnow
from app.utils.validators import normalise_phone

VALID_MINUTES = 5
MAX_TRIES = 5
MAX_CODES = 3
WINDOW_MINUTES = 10
GENERIC = "If this number belongs to an account, a code has been sent."
BAD_CODE = "That code is incorrect or has expired."
PROFILES = (Patient, Doctor, Employee, PharmacyStaff, LabStaff, Nurse, RadiologyStaff)


def clean_phone(raw: str) -> str:
    try:
        return normalise_phone(raw)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please enter a valid mobile number.")


def users_with_phone(db: Session, phone: str) -> list[User]:
    """Active accounts whose saved phone is this number (saved numbers are written in many styles, so they are compared after cleaning)."""
    tail = phone[-4:]
    found: dict[int, User] = {}
    for model in PROFILES:
        for user_id, saved in db.execute(select(model.user_id, model.phone).where(model.phone.is_not(None), model.phone.like(f"%{tail}%"))):
            try:
                same = normalise_phone(saved) == phone
            except ValueError:
                same = False
            if same:
                user = db.get(User, user_id)
                if user is not None and user.is_active:
                    found[user.id] = user
    return list(found.values())


def _hash(code: str, otp_id: int) -> str:
    return hashlib.sha256(f"{code}:{otp_id}:{get_settings().jwt_secret}".encode()).hexdigest()


def request_code(db: Session, raw_phone: str, ip: str | None) -> dict:
    phone = clean_phone(raw_phone)
    users = users_with_phone(db, phone)
    out = {"message": GENERIC, "expires_in": VALID_MINUTES * 60}
    if len(users) != 1:
        return out                                                    # unknown or shared number: the same answer, nothing sent
    user = users[0]
    since = utcnow() - timedelta(minutes=WINDOW_MINUTES)
    recent = db.scalars(select(LoginOtp).where(LoginOtp.user_id == user.id, LoginOtp.created_at >= since).order_by(LoginOtp.created_at)).all()
    if len(recent) >= MAX_CODES:
        wait = max(1, int(((recent[0].created_at + timedelta(minutes=WINDOW_MINUTES)) - utcnow()).total_seconds() // 60) + 1)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many codes were asked for. Please try again in {wait} minute{'s' if wait != 1 else ''}.", headers={"Retry-After": str(wait * 60)})
    for old in db.scalars(select(LoginOtp).where(LoginOtp.user_id == user.id, LoginOtp.used.is_(False))):
        old.used = True                                               # a new code cancels the earlier one
    code = f"{secrets.randbelow(10 ** 6):06d}"
    row = LoginOtp(user_id=user.id, phone_tail=phone[-4:], code_hash="", expires_at=utcnow() + timedelta(minutes=VALID_MINUTES), ip_address=ip)
    db.add(row)
    db.flush()
    row.code_hash = _hash(code, row.id)
    db.commit()
    if get_settings().otp_demo_mode:
        out["demo_code"] = code                                       # local demo only: there is no SMS provider
    return out


def verify_code(db: Session, raw_phone: str, code: str) -> User:
    phone = clean_phone(raw_phone)
    users = users_with_phone(db, phone)
    if len(users) != 1:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, BAD_CODE)
    user = users[0]
    row = db.scalar(select(LoginOtp).where(LoginOtp.user_id == user.id, LoginOtp.used.is_(False)).order_by(LoginOtp.id.desc()).limit(1))
    if row is None or row.expires_at < utcnow() or row.attempts >= MAX_TRIES:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, BAD_CODE)
    if not hmac.compare_digest(row.code_hash, _hash(code, row.id)):
        row.attempts += 1
        if row.attempts >= MAX_TRIES:
            row.used = True
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, BAD_CODE)
    row.used = True
    db.commit()
    return user
