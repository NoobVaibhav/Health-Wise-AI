"""Create DEMO ACCOUNTS for a college demonstration.   Run:  python -m app.seed_demo

It creates only people and a few medicines (so you can log in as each role).
It does NOT create reports, analysis, notes, prescriptions or history: those must come from real uploads
and real actions in the application. Safe to run more than once.
"""
from datetime import date, timedelta

from sqlalchemy import select

from app.core.permissions import ADMIN, DOCTOR, EMPLOYEE, PHARMACY
from app.database.connection import SessionLocal, init_db
from app.database.models import Department, Doctor, MedicineInventory, Patient, User
from app.schemas.auth import StaffCreate
from app.schemas.patient import PatientCreate
from app.services import user_service

DEMO_PASSWORD = "Demo@12345"  # demo accounts only. Change/remove them before any real use.


def main() -> None:
    init_db()
    with SessionLocal() as db:
        def exists(email: str) -> bool:
            return db.scalar(select(User).where(User.email == email)) is not None

        if not exists("admin@healthwise.demo.com"):
            user_service.create_admin(db, "admin@healthwise.demo.com", "Hospital Admin", DEMO_PASSWORD)

        department = db.scalar(select(Department).where(Department.name == "General Medicine"))
        if department is None:
            department = Department(name="General Medicine")
            db.add(department)
            db.commit()

        if not exists("anjali.sharma@healthwise.demo.com"):
            user_service.create_staff(db, DOCTOR, StaffCreate(
                email="anjali.sharma@healthwise.demo.com", full_name="Dr. Anjali Sharma", password=DEMO_PASSWORD,
                department_id=department.id, specialization="General Physician"))
        if not exists("priya.joshi@healthwise.demo.com"):
            user_service.create_staff(db, EMPLOYEE, StaffCreate(
                email="priya.joshi@healthwise.demo.com", full_name="Priya Joshi", password=DEMO_PASSWORD,
                designation="Lab assistant"))
        if not exists("pharmacy@healthwise.demo.com"):
            user_service.create_staff(db, PHARMACY, StaffCreate(
                email="pharmacy@healthwise.demo.com", full_name="MediCare Pharmacy Staff", password=DEMO_PASSWORD,
                pharmacy_name="MediCare Pharmacy"))
        if not exists("rahul.patil@healthwise.demo.com"):
            doctor = db.scalar(select(Doctor).join(User, Doctor.user_id == User.id)
                               .where(User.email == "anjali.sharma@healthwise.demo.com"))
            user_service.create_patient(db, PatientCreate(
                email="rahul.patil@healthwise.demo.com", full_name="Rahul Patil", password=DEMO_PASSWORD,
                gender="male", date_of_birth=date(1998, 5, 14), phone="9000000001",
                assigned_doctor_id=doctor.id if doctor else None))

        if db.scalar(select(MedicineInventory.id).limit(1)) is None:
            for name, qty, price in (("Medicine A", 100, 2.5), ("Medicine B", 60, 4.0)):
                db.add(MedicineInventory(medicine_name=name, batch_number="DEMO-1", quantity=qty,
                                         expiry_date=date.today() + timedelta(days=365), manufacturer="Demo Pharma",
                                         unit_price=price))
            db.commit()

    print("Demo accounts ready (password for all: %s)" % DEMO_PASSWORD)
    for role, email in (("Admin", "admin@healthwise.demo.com"), ("Doctor", "anjali.sharma@healthwise.demo.com"),
                        ("Employee", "priya.joshi@healthwise.demo.com"), ("Patient", "rahul.patil@healthwise.demo.com"),
                        ("Pharmacy", "pharmacy@healthwise.demo.com")):
        print(f"  {role:9s} {email}")


if __name__ == "__main__":
    main()
