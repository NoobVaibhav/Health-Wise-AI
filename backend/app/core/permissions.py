"""Role-based access control (RBAC).

Two layers:
1. require_roles(...)  : "may this ROLE call this endpoint at all?"
2. can_access_patient  : "may this specific user see THIS patient's data?"
   (a patient sees only themself; a doctor only patients who are theirs; staff as listed in the matrix)
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token, password_fingerprint
from app.database.connection import get_db
from app.database.models import Appointment, Doctor, HealthReport, Patient, Referral, Trainee, User

ADMIN = "ADMIN"
DOCTOR = "DOCTOR"
EMPLOYEE = "EMPLOYEE"
PATIENT = "PATIENT"
PHARMACY = "PHARMACY"
LAB = "LAB"   # laboratory staff: sees the tests doctors advise, never medicines or reports
TRAINEE = "TRAINEE"   # intern or PG student: takes histories and refers patients, never prescribes or orders tests
ALL_ROLES = (ADMIN, DOCTOR, EMPLOYEE, PATIENT, PHARMACY, LAB, TRAINEE)

FORBIDDEN_MESSAGE = "You do not have permission to access this information."

bearer_scheme = HTTPBearer(auto_error=False)


def forbidden() -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN_MESSAGE)


# A user who still has a temporary password may only look at their own account and change the password.
TEMP_PASSWORD_PATHS = ("/api/auth/me", "/api/auth/change-password")
MUST_CHANGE_MESSAGE = "Please change your temporary password first."


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Reads the JWT, loads the user from the database and rejects inactive accounts, tokens issued before the last
    password change, and (except for the password pages) accounts that still have a temporary password."""
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Please log in to continue.", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    decoded = decode_token(credentials.credentials)
    user = db.get(User, decoded[0]) if decoded else None
    if user is None or not user.is_active or decoded[1] != password_fingerprint(user.password_hash):
        raise unauthorized
    if user.must_change_password and request.url.path not in TEMP_PASSWORD_PATHS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, MUST_CHANGE_MESSAGE)
    return user


def require_roles(*roles: str):
    """Dependency factory:  user: User = Depends(require_roles(DOCTOR, ADMIN))"""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise forbidden()
        return user

    return checker


# ------------------------------------------------------------------ role profile helpers
def get_doctor_profile(db: Session, user: User) -> Doctor:
    doctor = db.scalar(select(Doctor).where(Doctor.user_id == user.id))
    if doctor is None:
        raise forbidden()
    return doctor


def get_patient_profile(db: Session, user: User) -> Patient:
    patient = db.scalar(select(Patient).where(Patient.user_id == user.id))
    if patient is None:
        raise forbidden()
    return patient


# ------------------------------------------------------------------ patient-level access
def doctor_can_access_patient(db: Session, doctor: Doctor, patient: Patient) -> bool:
    """A doctor is authorized for a patient if the patient is assigned to them, has an appointment with them,
    or has a report sent to them for review."""
    if patient.assigned_doctor_id == doctor.id:
        return True
    has_appointment = db.scalar(
        select(Appointment.id).where(Appointment.patient_id == patient.id, Appointment.doctor_id == doctor.id).limit(1)
    )
    if has_appointment:
        return True
    has_report = db.scalar(
        select(HealthReport.id).where(
            HealthReport.patient_id == patient.id, HealthReport.assigned_doctor_id == doctor.id
        ).limit(1)
    )
    if has_report is not None:
        return True
    return db.scalar(select(Referral.id).where(Referral.patient_id == patient.id, Referral.doctor_id == doctor.id).limit(1)) is not None   # referred by a trainee


def get_trainee_profile(db: Session, user: User) -> Trainee:
    trainee = db.scalar(select(Trainee).where(Trainee.user_id == user.id))
    if trainee is None:
        raise forbidden()
    return trainee


def get_accessible_patient(db: Session, user: User, patient_id: int, clinical: bool = True) -> Patient:
    """Return the patient if `user` may see them, else raise 403/404.

    clinical=True  -> clinical data (reports, notes, history): ADMIN is NOT allowed, EMPLOYEE is NOT allowed.
    clinical=False -> basic info only: ADMIN and EMPLOYEE are allowed as well.
    """
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found.")

    if user.role == PATIENT:
        if patient.user_id != user.id:
            raise forbidden()
    elif user.role == DOCTOR:
        if not doctor_can_access_patient(db, get_doctor_profile(db, user), patient):
            raise forbidden()
    elif user.role in (ADMIN, EMPLOYEE):
        if clinical:
            raise forbidden()
    else:
        raise forbidden()
    return patient


def doctor_patient_ids(db: Session, doctor: Doctor) -> set[int]:
    """All patient ids this doctor is authorized for (same rule as doctor_can_access_patient, but in bulk)."""
    ids: set[int] = set()
    ids.update(db.scalars(select(Patient.id).where(Patient.assigned_doctor_id == doctor.id)))
    ids.update(db.scalars(select(Appointment.patient_id).where(Appointment.doctor_id == doctor.id)))
    ids.update(db.scalars(select(HealthReport.patient_id).where(HealthReport.assigned_doctor_id == doctor.id)))
    ids.update(db.scalars(select(Referral.patient_id).where(Referral.doctor_id == doctor.id)))
    return ids
