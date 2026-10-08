"""Creating users together with their role profile (patient / doctor / employee / pharmacy)."""
import secrets
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import ADMIN, DOCTOR, EMPLOYEE, PATIENT, PHARMACY
from app.core.security import hash_password
from app.database.models import Department, Doctor, Employee, Patient, PharmacyStaff, User
from app.schemas.auth import StaffCreate
from app.schemas.patient import PatientCreate


def generate_password() -> str:
    """Random temporary password (shown once to the creator; the user must change it at first login)."""
    return secrets.token_urlsafe(9)


def _ensure_email_free(db: Session, email: str) -> str:
    email = email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    return email


def _new_user(db: Session, email: str, full_name: str, role: str, password: str | None) -> tuple[User, str | None]:
    """Create the user row. Returns (user, temporary_password or None if the creator chose the password)."""
    email = _ensure_email_free(db, email)
    temporary = None if password else generate_password()
    user = User(
        email=email, full_name=full_name.strip(), role=role,
        password_hash=hash_password(password or temporary), must_change_password=password is None,
    )
    db.add(user)
    db.flush()
    return user, temporary


def create_admin(db: Session, email: str, full_name: str, password: str) -> User:
    user, _ = _new_user(db, email, full_name, ADMIN, password)
    db.commit()
    db.refresh(user)
    return user


def create_staff(db: Session, role: str, data: StaffCreate) -> tuple[User, str | None]:
    """Create a doctor, employee or pharmacy staff account."""
    if role == DOCTOR and data.department_id and not db.get(Department, data.department_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found.")
    user, temporary = _new_user(db, data.email, data.full_name, role, data.password)
    if role == DOCTOR:
        db.add(Doctor(user_id=user.id, department_id=data.department_id, specialization=data.specialization,
                      phone=data.phone))
    elif role == EMPLOYEE:
        db.add(Employee(user_id=user.id, designation=data.designation, phone=data.phone))
    elif role == PHARMACY:
        db.add(PharmacyStaff(user_id=user.id, pharmacy_name=data.pharmacy_name, phone=data.phone))
    db.commit()
    db.refresh(user)
    return user, temporary


def next_patient_code(db: Session) -> str:
    count = db.scalar(select(func.count(Patient.id))) or 0
    code = f"P-{count + 1:04d}"
    while db.scalar(select(Patient.id).where(Patient.patient_code == code)):  # in case of deleted rows
        count += 1
        code = f"P-{count + 1:04d}"
    return code


def create_patient(db: Session, data: PatientCreate) -> tuple[Patient, str | None]:
    if data.assigned_doctor_id and not db.get(Doctor, data.assigned_doctor_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found.")
    user, temporary = _new_user(db, data.email, data.full_name, PATIENT, data.password)
    patient = Patient(
        user_id=user.id, patient_code=next_patient_code(db),
        **data.model_dump(exclude={"email", "full_name", "password"}),
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient, temporary


def age_from_dob(dob: date | None) -> int | None:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
