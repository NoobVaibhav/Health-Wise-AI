"""Create DEMO ACCOUNTS for a college demonstration.   Run:  python -m app.seed_demo

It creates only people and a few medicines (so you can log in as each role).
It does NOT create reports, analysis, notes, prescriptions or history: those must come from real uploads
and real actions in the application. Safe to run more than once.
"""
from datetime import date, timedelta

from sqlalchemy import select

from app.core.permissions import DOCTOR, EMPLOYEE, LAB, NURSE, PHARMACY
from app.database.connection import SessionLocal, init_db
from app.database.models import Department, Doctor, MedicineInventory, Bed, ServiceCatalog, Specialization, User, Ward
from app.schemas.auth import StaffCreate
from app.schemas.patient import PatientCreate
from app.services import catalog_service, user_service

DEMO_PASSWORD = "Demo@12345"  # demo accounts only. Change/remove them before any real use.


def main() -> None:
    init_db()
    with SessionLocal() as db:
        def exists(email: str) -> bool:
            return db.scalar(select(User).where(User.email == email)) is not None

        if not exists("admin@healthwise.demo.com"):
            user_service.create_admin(db, "admin@healthwise.demo.com", "Hospital Admin", DEMO_PASSWORD)

        catalog_service.ensure_catalog(db)
        department = db.scalar(select(Department).where(Department.name == "General Medicine"))
        general = db.scalar(select(Specialization).where(Specialization.department_id == department.id, Specialization.name == "General Physician"))

        if not exists("anjali.sharma@healthwise.demo.com"):
            user_service.create_staff(db, DOCTOR, StaffCreate(
                email="anjali.sharma@healthwise.demo.com", full_name="Dr. Anjali Sharma", password=DEMO_PASSWORD,
                department_id=department.id, specialization_id=general.id))
        if not exists("priya.joshi@healthwise.demo.com"):
            user_service.create_staff(db, EMPLOYEE, StaffCreate(
                email="priya.joshi@healthwise.demo.com", full_name="Priya Joshi", password=DEMO_PASSWORD,
                designation="Lab assistant"))
        if not exists("pharmacy@healthwise.demo.com"):
            user_service.create_staff(db, PHARMACY, StaffCreate(
                email="pharmacy@healthwise.demo.com", full_name="MediCare Pharmacy Staff", password=DEMO_PASSWORD,
                pharmacy_name="MediCare Pharmacy"))
        if not exists("lab@healthwise.demo.com"):
            user_service.create_staff(db, LAB, StaffCreate(
                email="lab@healthwise.demo.com", full_name="City Lab Technician", password=DEMO_PASSWORD,
                lab_name="City Diagnostic Lab"))
        anjali = db.scalar(select(Doctor).join(User, Doctor.user_id == User.id).where(User.email == "anjali.sharma@healthwise.demo.com"))
        if not exists("nurse@healthwise.demo.com"):
            user_service.create_staff(db, NURSE, StaffCreate(email="nurse@healthwise.demo.com", full_name="Meera Pawar", password=DEMO_PASSWORD, designation="Staff nurse"))
        if db.scalar(select(Ward.id).limit(1)) is None:                      # a small demo ward layout (the real one is entered by the administrator)
            from app.services import hospital_service
            branch = hospital_service.default_branch(db)
            for name, kind, codes in (("General Ward", "GENERAL", ("G1", "G2", "G3", "G4")), ("ICU", "ICU", ("I1", "I2")), ("Private Rooms", "PRIVATE", ("P1", "P2"))):
                ward = Ward(branch_id=branch.id, name=name, ward_type=kind, is_active=True)
                db.add(ward)
                db.flush()
                for code in codes:
                    db.add(Bed(ward_id=ward.id, code=code, status="AVAILABLE", is_active=True))
            db.commit()
        if not exists("intern@healthwise.demo.com"):
            user_service.create_staff(db, DOCTOR, StaffCreate(
                email="intern@healthwise.demo.com", full_name="Neha Kulkarni", password=DEMO_PASSWORD,
                department_id=department.id, grade="INTERN", supervisor_id=anjali.id if anjali else None))
        if not exists("pg.student@healthwise.demo.com"):
            user_service.create_staff(db, DOCTOR, StaffCreate(
                email="pg.student@healthwise.demo.com", full_name="Dr. Arjun Deshmukh", password=DEMO_PASSWORD,
                department_id=department.id, grade="PG_RESIDENT", pg_year=2, pg_branch="MD Medicine", supervisor_id=anjali.id if anjali else None))
        if not exists("rahul.patil@healthwise.demo.com"):
            doctor = db.scalar(select(Doctor).join(User, Doctor.user_id == User.id)
                               .where(User.email == "anjali.sharma@healthwise.demo.com"))
            user_service.create_patient(db, PatientCreate(
                email="rahul.patil@healthwise.demo.com", full_name="Rahul Patil", password=DEMO_PASSWORD,
                gender="male", date_of_birth=date(1998, 5, 14), phone="9000000001",
                assigned_doctor_id=doctor.id if doctor else None))

        if db.scalar(select(ServiceCatalog.id).limit(1)) is None:            # a small demo price list (the real one is entered by the administrator)
            for code, name, category, price in (("OPD-GEN", "OPD consultation, General Medicine", "CONSULTATION", 500), ("OPD-FU", "Follow-up consultation", "CONSULTATION", 300),
                                                ("LAB-CBC", "Complete blood count", "LAB", 350), ("XRAY-CH", "X-ray chest", "RADIOLOGY", 600)):
                db.add(ServiceCatalog(code=code, name=name, category=category, price=price, gst_percent=0, is_active=True))
            db.commit()

        if db.scalar(select(MedicineInventory.id).limit(1)) is None:
            for name, qty, price in (("Medicine A", 100, 2.5), ("Medicine B", 60, 4.0)):
                db.add(MedicineInventory(medicine_name=name, batch_number="DEMO-1", quantity=qty,
                                         expiry_date=date.today() + timedelta(days=365), manufacturer="Demo Pharma",
                                         unit_price=price))
            db.commit()

    print("Demo accounts ready (password for all: %s)" % DEMO_PASSWORD)
    for role, email in (("Admin", "admin@healthwise.demo.com"), ("Doctor", "anjali.sharma@healthwise.demo.com"),
                        ("Employee", "priya.joshi@healthwise.demo.com"), ("Patient", "rahul.patil@healthwise.demo.com"),
                        ("Pharmacy", "pharmacy@healthwise.demo.com"), ("Lab", "lab@healthwise.demo.com"),
                        ("Nurse", "nurse@healthwise.demo.com"), ("Intern", "intern@healthwise.demo.com"), ("PG resident", "pg.student@healthwise.demo.com")):
        print(f"  {role:9s} {email}")


if __name__ == "__main__":
    main()
