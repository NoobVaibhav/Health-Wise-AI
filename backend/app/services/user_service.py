"""Creating users together with their role profile (patient / doctor / employee / pharmacy)."""
import os
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import ADMIN, DOCTOR, EMPLOYEE, LAB, PATIENT, PHARMACY, NURSE, RADIOLOGY
from app.core.security import hash_password
from app.database.models import (
    AuditLog, Doctor, Employee, HistoryRevision, LabStaff, Patient, PatientAssistantConversation, PharmacyStaff, Nurse, RadiologyStaff, User,
)
from app.schemas.auth import StaffCreate
from app.services import catalog_service, grade_service
from app.schemas.patient import PatientCreate
from app.utils.clock import hospital_today


def generate_password() -> str:
    """The starting password of a new account (DEFAULT_PASSWORD in the settings). The user must change it at first login."""
    return get_settings().default_password


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
    if role == DOCTOR:
        catalog_service.check_choice(db, data.department_id, data.specialization_id)
        grade_service.check_grade_fields(db, data.grade, data.department_id, data.pg_year, data.pg_branch, data.supervisor_id)
    user, temporary = _new_user(db, data.email, data.full_name, role, data.password)
    if role == DOCTOR:
        grade = data.grade or "CONSULTANT"
        junior = grade != "CONSULTANT"
        doctor = Doctor(user_id=user.id, department_id=data.department_id, specialization_id=None if grade == "INTERN" else data.specialization_id,
                        specialization=None if (data.specialization_id or grade == "INTERN") else data.specialization, phone=data.phone, grade=grade,
                        pg_year=data.pg_year if grade == "PG_RESIDENT" else None, pg_branch=data.pg_branch if grade in ("PG_RESIDENT", "SENIOR_RESIDENT") else None,
                        supervisor_id=data.supervisor_id if junior else None, can_prescribe_independently=bool(data.can_prescribe_independently) and junior)
        db.add(doctor)
        if not data.specialization_id:
            db.flush()
            catalog_service.backfill_doctors(db)         # old-style free text that matches a listed specialization gets its id
    elif role == EMPLOYEE:
        db.add(Employee(user_id=user.id, designation=data.designation, phone=data.phone))
    elif role == PHARMACY:
        db.add(PharmacyStaff(user_id=user.id, pharmacy_name=data.pharmacy_name, phone=data.phone))
    elif role == LAB:
        if data.staff_type == "RADIOLOGIST":
            raise HTTPException(422, "A laboratory staff member is a technician or a pathologist.")
        db.add(LabStaff(user_id=user.id, lab_name=data.lab_name, phone=data.phone, staff_type=data.staff_type or "TECHNICIAN"))
    elif role == RADIOLOGY:
        if data.staff_type == "PATHOLOGIST":
            raise HTTPException(422, "Radiology staff are technicians or radiologists.")
        db.add(RadiologyStaff(user_id=user.id, phone=data.phone, staff_type=data.staff_type or "TECHNICIAN"))
    elif role == NURSE:
        from app.services import hospital_service
        db.add(Nurse(user_id=user.id, branch_id=hospital_service.default_branch(db).id, designation=data.designation, phone=data.phone))
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
    from app.database.models import Branch
    from app.services import hospital_service, registry_service
    branch = db.get(Branch, data.branch_id) if data.branch_id else hospital_service.default_branch(db)
    if branch is None or not branch.is_active:
        raise HTTPException(422, "The selected branch does not exist.")
    user, temporary = _new_user(db, data.email, data.full_name, PATIENT, data.password)
    patient = Patient(
        user_id=user.id, patient_code=next_patient_code(db), branch_id=branch.id, uhid=registry_service.next_uhid(db, branch),
        **data.model_dump(exclude={"email", "full_name", "password", "allow_duplicate", "branch_id"}),
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient, temporary


def age_from_dob(dob: date | None) -> int | None:
    if not dob:
        return None
    today = hospital_today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


# ------------------------------------------------------------------ deleting an account
# An account can be deleted only when NOTHING is linked to it. A person with reports, prescriptions, history, appointments, bills ...
# can only be deactivated: the medical and billing records must never lose their author or their patient.
PROFILE_MODELS = (("patients", Patient), ("doctors", Doctor), ("employees", Employee), ("pharmacy_staff", PharmacyStaff), ("lab_staff", LabStaff), ("radiology_staff", RadiologyStaff), ("nurses", Nurse))
# links that do not count: the audit trail is kept (its user link is cleared), and these belong to the patient and are removed with them
NOT_BLOCKING = {("audit_logs", "user_id"), ("history_revisions", "patient_id"), ("patient_assistant_conversations", "patient_id")}
WORDS = {"health_reports": "reports", "health_parameters": "test results", "appointments": "appointments", "prescriptions": "prescriptions", "doctor_notes": "doctor's notes",
         "doctor_recommendations": "recommendations", "medical_history": "history entries", "patient_history": "health history", "patient_medications": "regular medicines",
         "clinical_assessments": "assessments", "chronic_conditions": "illness records", "hospital_admissions": "hospital admissions", "surgery_records": "operations",
         "emergency_events": "emergency visits", "follow_up_tasks": "follow-up tasks", "lab_test_orders": "laboratory tests", "lab_results": "lab results", "radiology_orders": "scans", "radiology_reports": "radiology reports", "radiology_attachments": "scan files", "sales": "bills", "medicine_dispensing": "dispensed medicines",
         "history_revisions": "history changes", "trainee_histories": "histories taken", "referrals": "referrals", "encounters": "visits", "vital_sets": "vital signs", "admissions": "admissions", "consultations": "consultations", "nursing_notes": "nursing notes", "summary_reviews": "summary reviews", "report_comparisons": "comparisons"}


def _links(db: Session, user: User) -> dict[str, int]:
    """Counts of records that point to this account or to its role profile (any table, found from the database model itself)."""
    from app.database.connection import Base
    ids = {"users": user.id}
    for table, model in PROFILE_MODELS:
        row = db.scalar(select(model).where(model.user_id == user.id))
        if row is not None:
            ids[table] = row.id
    found: dict[str, int] = {}
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            target = fk.column.table.name
            if target not in ids or (table.name, fk.parent.name) in NOT_BLOCKING:
                continue
            if table.name in ids and fk.parent.name == "user_id":      # the profile row itself
                continue
            count = db.scalar(select(func.count()).select_from(table).where(fk.parent == ids[target])) or 0
            if count:
                label = WORDS.get(table.name, table.name.replace("_", " "))
                found[label] = found.get(label, 0) + count
    return found


def delete_check(db: Session, user: User, admin: User) -> dict:
    """Can this account be deleted? If not, why (in plain words)."""
    reasons = []
    if user.id == admin.id:
        reasons.append("You cannot delete your own account.")
    if user.role == ADMIN and not db.scalar(select(User.id).where(User.role == ADMIN, User.is_active.is_(True), User.id != user.id)):
        reasons.append("This is the only active administrator.")
    links = _links(db, user)
    if links:
        shown = ", ".join(f"{n} {label}" for label, n in sorted(links.items(), key=lambda kv: -kv[1])[:6])
        reasons.append(f"Records are linked to this account ({shown}). To keep the medical and billing records safe it cannot be deleted. Deactivate it instead.")
    return {"can_delete": not reasons, "reasons": reasons, "linked_records": links}


def delete_user(db: Session, user: User, admin: User) -> dict:
    check = delete_check(db, user, admin)
    if not check["can_delete"]:
        raise HTTPException(status.HTTP_409_CONFLICT, " ".join(check["reasons"]))
    summary = {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role}
    patient = db.scalar(select(Patient).where(Patient.user_id == user.id))
    if patient is not None:                                              # the patient's own chats and their change log go with the empty account
        for conv in db.scalars(select(PatientAssistantConversation).where(PatientAssistantConversation.patient_id == patient.id)):
            db.delete(conv)
        for rev in db.scalars(select(HistoryRevision).where(HistoryRevision.patient_id == patient.id)):
            db.delete(rev)
    for _, model in PROFILE_MODELS:
        row = db.scalar(select(model).where(model.user_id == user.id))
        if row is not None:
            db.delete(row)
    db.flush()
    for entry in db.scalars(select(AuditLog).where(AuditLog.user_id == user.id)):
        entry.user_id = None                                             # the trail stays; only the link to the removed account is cleared
    avatar = os.path.join(get_settings().upload_dir, user.avatar_path) if user.avatar_path else None
    db.delete(user)
    db.commit()
    if avatar and os.path.exists(avatar):
        try:
            os.remove(avatar)
        except OSError:
            pass
    return summary
