"""Add DEMO DOCTORS in every department, for a college demonstration.   Run:  python -m app.seed_doctors   (also called by python -m app.seed_demo)

All people are FICTIONAL. Doctors are created through the same schema (StaffCreate) and service (create_staff) as the admin screen, so every validation applies.
Safe to run more than once: a doctor is matched by e-mail and an existing one is never touched. A few future appointments are added for existing demo patients
(valid slots in the hospital's time, never in the past). The doctor's working days and fee are NOT stored by this application, so none are seeded.
"""
import os
from datetime import datetime, time, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.permissions import DOCTOR
from app.database.connection import SessionLocal, init_db
from app.database.models import Appointment, Department, Doctor, Patient, Specialization, User
from app.schemas.appointment import AppointmentCreate
from app.schemas.auth import StaffCreate
from app.services import appointment_rules as rules, catalog_service, user_service
from app.utils import clock

DOMAIN = "healthwise.demo.com"

# (first name, last name, department, specialization, grade, supervisor e-mail, PG year, PG branch)
CONSULTANT, SENIOR, PG = "CONSULTANT", "SENIOR_RESIDENT", "PG_RESIDENT"
DOCTORS = (
    ("Vivek", "Oak", "General Medicine", "Family Medicine", CONSULTANT, None, None, None),
    ("Kavya", "Menon", "Cardiology", "Cardiac Electrophysiologist", CONSULTANT, None, None, None),
    ("Tarun", "Bose", "Cardiology", "Interventional Cardiologist", SENIOR, "kavya.menon", None, "DM Cardiology"),
    ("Aarav", "Iyer", "Neurology", "Neurologist", CONSULTANT, None, None, None),
    ("Nisha", "Pillai", "Neurology", "Neurologist", PG, "aarav.iyer", 2, "MD Medicine"),
    ("Harpreet", "Gill", "Orthopedics", "Joint Replacement", CONSULTANT, None, None, None),
    ("Ananya", "Rao", "Pediatrics", "Neonatologist", CONSULTANT, None, None, None),
    ("Pooja", "Hegde", "Pediatrics", "Neonatologist", SENIOR, "ananya.rao", None, "MD Pediatrics"),
    ("Lakshmi", "Narayanan", "Gynecology & Obstetrics", "Obstetrician", CONSULTANT, None, None, None),
    ("Siddharth", "Malhotra", "Dermatology", "Dermatologist", CONSULTANT, None, None, None),
    ("Deepa", "Chandran", "ENT", "Otolaryngologist", CONSULTANT, None, None, None),
    ("Manoj", "Varma", "Ophthalmology", "Ophthalmologist", CONSULTANT, None, None, None),
    ("Shruti", "Banerjee", "Psychiatry", "Psychiatrist", CONSULTANT, None, None, None),
    ("Yash", "Saxena", "Pulmonology", "Pulmonologist", CONSULTANT, None, None, None),
    ("Ganesh", "Pawar", "Gastroenterology", "Gastroenterologist", CONSULTANT, None, None, None),
    ("Tanvi", "Desai", "Nephrology", "Nephrologist", CONSULTANT, None, None, None),
    ("Kunal", "Bhide", "Urology", "Urologist", CONSULTANT, None, None, None),
    ("Mitali", "Ghosh", "Endocrinology", "Diabetologist", CONSULTANT, None, None, None),
    ("Rajeev", "Nambiar", "Oncology", "Medical Oncologist", CONSULTANT, None, None, None),
    ("Zoya", "Fernandes", "Dentistry", "Orthodontist", CONSULTANT, None, None, None),
    ("Abhay", "Joglekar", "Radiology", "Radiologist", CONSULTANT, None, None, None),
    ("Charu", "Mittal", "Pathology", "Pathologist", CONSULTANT, None, None, None),
    ("Naveen", "Reddy", "Emergency Medicine", "Emergency Physician", CONSULTANT, None, None, None),
    ("Prakash", "Wagh", "General Surgery", "General Surgeon", CONSULTANT, None, None, None),
    ("Sunita", "Kamat", "General Surgery", "Laparoscopic Surgeon", CONSULTANT, None, None, None),
)
FIRST_PHONE = 9000000201                      # 9000000201, 9000000202 ... the reserved fake range the other demo accounts use

# consultants who get a future appointment with an existing demo patient, so their dashboards are not empty
BOOKED = ("vivek.oak", "kavya.menon", "aarav.iyer", "harpreet.gill", "ananya.rao", "siddharth.malhotra", "yash.saxena", "mitali.ghosh")
BOOKING_REASONS = ("Demo: first consultation", "Demo: follow-up visit")
FIRST_SLOT = time(10, 0)


def assert_demo_seed_allowed() -> None:
    """Demo accounts share a published password. They may only be created on a local (SQLite) database, or when ALLOW_DEMO_SEED=1 is set on purpose."""
    if not get_settings().database_url.startswith("sqlite") and os.environ.get("ALLOW_DEMO_SEED") != "1":
        raise SystemExit("Refusing to create demo accounts on a non-SQLite database. Set ALLOW_DEMO_SEED=1 only for a throw-away demo database.")


def email_of(first: str, last: str) -> str:
    return f"{first}.{last}@{DOMAIN}".lower()


def seed_doctors(db, password: str) -> dict:
    """Creates the missing doctors. Returns the counts: added, skipped (already there), and the departments that now have a doctor."""
    catalog_service.ensure_catalog(db)
    catalog_service.ensure_additional_departments(db)
    added = skipped = 0
    for index, (first, last, dept_name, spec_name, grade, supervisor, pg_year, branch) in enumerate(DOCTORS):
        email = email_of(first, last)
        if db.scalar(select(User.id).where(User.email == email)) is not None:
            skipped += 1
            continue
        department = db.scalar(select(Department).where(Department.name == dept_name))
        specialization = db.scalar(select(Specialization).where(Specialization.department_id == department.id, Specialization.name == spec_name))
        boss = None
        if supervisor:
            boss = db.scalar(select(Doctor).join(User, Doctor.user_id == User.id).where(User.email == f"{supervisor}@{DOMAIN}"))
        data = StaffCreate(email=email, full_name=f"Dr. {first} {last}", password=password, phone=str(FIRST_PHONE + index), department_id=department.id,
                           specialization_id=specialization.id, grade=grade, pg_year=pg_year, pg_branch=branch, supervisor_id=boss.id if boss else None)
        user_service.create_staff(db, DOCTOR, data)
        added += 1
    covered = {d.name for d in db.scalars(select(Department).join(Doctor, Doctor.department_id == Department.id).distinct())}
    return {"added": added, "skipped": skipped, "departments_with_a_doctor": len(covered), "departments": len(db.scalars(select(Department.id)).all())}


def seed_appointments(db) -> int:
    """One or two future appointments for some of the new consultants with existing demo patients. Each goes through AppointmentCreate (slot, opening hours, not in the past)."""
    patients = db.scalars(select(Patient).join(User, Patient.user_id == User.id).where(User.email.like(f"%@{DOMAIN}")).order_by(Patient.id)).all()
    if not patients:
        return 0
    created = 0
    day = clock.hospital_now().date()
    for number, key in enumerate(BOOKED):
        doctor = db.scalar(select(Doctor).join(User, Doctor.user_id == User.id).where(User.email == f"{key}@{DOMAIN}"))
        if doctor is None:
            continue
        for visit, reason in enumerate(BOOKING_REASONS[: 2 if number < 3 else 1]):
            patient = patients[(number + visit) % len(patients)]
            if db.scalar(select(Appointment.id).where(Appointment.doctor_id == doctor.id, Appointment.patient_id == patient.id, Appointment.reason == reason)):
                continue                                            # already seeded
            when = datetime.combine(day + timedelta(days=1 + number % 5 + 2 * visit), FIRST_SLOT) + timedelta(minutes=15 * (number % 8))
            while when in {a for a in db.scalars(select(Appointment.scheduled_at).where(Appointment.doctor_id == doctor.id, Appointment.status.in_(["SCHEDULED", "CONFIRMED"])))} or \
                    db.scalar(select(Appointment.id).where(Appointment.patient_id == patient.id, Appointment.scheduled_at == when, Appointment.status.in_(["SCHEDULED", "CONFIRMED"]))):
                when += timedelta(minutes=15)
            data = AppointmentCreate(patient_id=patient.id, doctor_id=doctor.id, department_id=doctor.department_id, scheduled_at=when, reason=reason)
            rules.check_bookable(data.scheduled_at)
            db.add(Appointment(patient_id=patient.id, doctor_id=doctor.id, department_id=doctor.department_id, scheduled_at=data.scheduled_at, reason=data.reason, status="SCHEDULED"))
            db.commit()
            created += 1
    return created


def run(db, password: str) -> dict:
    result = seed_doctors(db, password)
    result["appointments_added"] = seed_appointments(db)
    return result


def main() -> None:
    assert_demo_seed_allowed()
    from app.seed_demo import DEMO_PASSWORD
    init_db()
    with SessionLocal() as db:
        result = run(db, DEMO_PASSWORD)
    print("Demo doctors: %(added)d added, %(skipped)d already existed; %(departments_with_a_doctor)d of %(departments)d departments have a doctor; %(appointments_added)d appointments added." % result)


if __name__ == "__main__":
    main()
