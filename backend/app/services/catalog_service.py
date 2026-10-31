"""Departments and specializations: the default list, the move of old free-text specializations, and the id checks."""
from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database.models import Department, Doctor, Specialization

DEFAULT_CATALOG: dict[str, list[str]] = {
    "General Medicine": ["General Physician", "Internal Medicine", "Family Medicine"],
    "Cardiology": ["Interventional Cardiologist", "Cardiac Electrophysiologist"],
    "Neurology": ["Neurologist", "Neurosurgeon"],
    "Orthopedics": ["Joint Replacement", "Spine Surgeon", "Sports Medicine"],
    "Pediatrics": ["Neonatologist", "Pediatric Surgeon"],
    "Gynecology & Obstetrics": ["Obstetrician", "Gynecologist", "Fertility Specialist"],
    "Dermatology": ["Dermatologist", "Cosmetologist"],
    "ENT": ["Otolaryngologist", "Head and Neck Surgeon"],
    "Ophthalmology": ["Ophthalmologist", "Retina Specialist"],
    "Psychiatry": ["Psychiatrist", "Child Psychiatrist"],
    "Pulmonology": ["Pulmonologist", "Critical Care Specialist"],
    "Gastroenterology": ["Gastroenterologist", "Hepatologist"],
    "Nephrology": ["Nephrologist", "Transplant Nephrologist"],
    "Urology": ["Urologist", "Andrologist"],
    "Endocrinology": ["Endocrinologist", "Diabetologist"],
    "Oncology": ["Medical Oncologist", "Surgical Oncologist", "Radiation Oncologist"],
    "Dentistry": ["Dentist", "Orthodontist", "Oral Surgeon"],
    "Radiology": ["Radiologist", "Interventional Radiologist"],
    "Pathology": ["Pathologist", "Microbiologist"],
    "Emergency Medicine": ["Emergency Physician", "Trauma Specialist"],
}


def name_key(name: str) -> str:
    return " ".join(name.split()).lower()


def ensure_catalog(db: Session) -> None:
    """Safe to run at every start: marks old rows active, adds the default list only when there are no specializations yet
    (existing departments are reused, so nothing is duplicated), then moves old doctors onto the new ids."""
    db.execute(update(Department).where(Department.is_active.is_(None)).values(is_active=True))
    db.execute(update(Specialization).where(Specialization.is_active.is_(None)).values(is_active=True))
    if db.scalar(select(func.count(Specialization.id))) == 0:
        for department_name, names in DEFAULT_CATALOG.items():
            department = db.scalar(select(Department).where(func.lower(Department.name) == department_name.lower()))
            if department is None:
                department = Department(name=department_name, is_active=True)
                db.add(department)
                db.flush()
            for name in names:
                db.add(Specialization(name=name, name_key=name_key(name), department_id=department.id, is_active=True))
        db.flush()
    backfill_doctors(db)
    db.commit()


def backfill_doctors(db: Session) -> None:
    """A doctor with only the old text gets the matching specialization id (ignoring case). With no match, the old text stays and is shown
    as "Other (legacy)". A doctor without a department takes the department of the matching specialization."""
    for doctor in db.scalars(select(Doctor).where(Doctor.specialization_id.is_(None), Doctor.specialization.is_not(None))):
        key = name_key(doctor.specialization or "")
        if not key:
            continue
        query = select(Specialization).where(Specialization.name_key == key)
        if doctor.department_id:
            query = query.where(Specialization.department_id == doctor.department_id)
        matches = db.scalars(query).all()
        if len(matches) == 1:
            doctor.specialization_id = matches[0].id
            if not doctor.department_id:
                doctor.department_id = matches[0].department_id


def check_choice(db: Session, department_id: int | None, specialization_id: int | None, current: Doctor | None = None) -> None:
    """422 with a clear message when the pair is not allowed. A doctor may keep a department or specialization that was deactivated since."""
    if department_id is not None:
        department = db.get(Department, department_id)
        if department is None:
            raise HTTPException(422, "The selected department does not exist.")
        if department.is_active is False and not (current and current.department_id == department_id):
            raise HTTPException(422, "The selected department is no longer in use.")
    if specialization_id is not None:
        if department_id is None:
            raise HTTPException(422, "Please choose a department before choosing a specialization.")
        specialization = db.get(Specialization, specialization_id)
        if specialization is None:
            raise HTTPException(422, "The selected specialization does not exist.")
        if specialization.department_id != department_id:
            raise HTTPException(422, "The selected specialization does not belong to the selected department.")
        if specialization.is_active is False and not (current and current.specialization_id == specialization_id):
            raise HTTPException(422, "The selected specialization is no longer in use.")


def doctors_using_department(db: Session, department_id: int) -> int:
    return db.scalar(select(func.count(Doctor.id)).where(Doctor.department_id == department_id)) or 0


def doctors_using_specialization(db: Session, specialization_id: int) -> int:
    return db.scalar(select(func.count(Doctor.id)).where(Doctor.specialization_id == specialization_id)) or 0
