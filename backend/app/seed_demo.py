"""Create DEMO ACCOUNTS for a college demonstration.   Run:  python -m app.seed_demo

It creates only people and a few medicines (so you can log in as each role).
It does NOT create reports, analysis, notes, prescriptions or history: those must come from real uploads
and real actions in the application. Safe to run more than once.
"""
from datetime import date, timedelta

from sqlalchemy import select

from app.core.permissions import DOCTOR, EMPLOYEE, LAB, NURSE, PHARMACY, RADIOLOGY
from app.database.connection import SessionLocal, init_db
from app.database.models import Department, Doctor, MedicineInventory, Bed, ServiceCatalog, Specialization, User, Ward
from app.schemas.auth import StaffCreate
from app.schemas.patient import PatientCreate
from app.services import access_service, catalog_service, user_service

DEMO_PASSWORD = "Demo@12345"  # demo accounts only. Change/remove them before any real use.


# Typical adult limits so the demo shows flags. They are demo values, NOT medical advice: a hospital sets its own limits (Admin, Diagnostics) with its pathologist.
DEMO_TESTS = (
    ("Complete Blood Count", "HAEMATOLOGY", "Blood", (("Haemoglobin", "g/dL", "Automated analyser", 12.0, 16.0, 7.0, 20.0), ("WBC count", "x10^3/uL", "Automated analyser", 4.0, 11.0, 2.0, 30.0),
                                                       ("Platelet count", "x10^3/uL", "Automated analyser", 150, 450, 50, 1000))),
    ("Serum Electrolytes", "BIOCHEMISTRY", "Blood", (("Sodium", "mmol/L", "ISE", 135, 145, 120, 160), ("Potassium", "mmol/L", "ISE", 3.5, 5.0, 2.8, 6.0))),
    ("Blood Glucose (Fasting)", "BIOCHEMISTRY", "Blood", (("Glucose (fasting)", "mg/dL", "GOD-POD", 70, 100, 40, 500),)),
    ("Serum Creatinine", "BIOCHEMISTRY", "Blood", (("Creatinine", "mg/dL", "Jaffe", 0.6, 1.3, None, 10.0),)),
    ("Troponin I", "CARDIAC_MARKERS", "Blood", (("Troponin I", "ng/mL", "CLIA", None, 0.04, None, 0.4),)),
    ("Urine Routine", "URINE", "Urine", ()),
)
DEMO_SCANS = (("Chest X-ray", "XRAY"), ("Ultrasound Abdomen", "ULTRASOUND"), ("CT Head", "CT"), ("MRI Brain", "MRI"), ("Mammography", "MAMMOGRAPHY"), ("2D Echo", "ECHO"), ("ECG", "ECG"))


def seed_diagnostic_catalogue(db) -> None:
    from app.database.models import DiagnosticAnalyte, DiagnosticTest
    if db.scalar(select(DiagnosticTest.id).limit(1)) is not None:
        return
    for name, category, sample, analytes in DEMO_TESTS:
        test = DiagnosticTest(kind="LAB", name=name, category=category, sample_type=sample)
        db.add(test)
        db.flush()
        for order, (aname, unit, method, low, high, clow, chigh) in enumerate(analytes):
            db.add(DiagnosticAnalyte(test_id=test.id, name=aname, unit=unit, method=method, ref_low=low, ref_high=high, critical_low=clow, critical_high=chigh, sort_order=order))
    for name, modality in DEMO_SCANS:
        db.add(DiagnosticTest(kind="RADIOLOGY", name=name, category=modality))
    db.commit()


def seed_operations(db) -> None:
    """Phase 5 demo data: staff with the store, theatre and blood bank permissions, a supplier, a few store items, two theatres."""
    from app.database.models import InventoryItem, OperationTheatre, Role, Supplier, UserRole
    for email, name, designation, role_code in (("inventory@healthwise.demo.com", "Ila Joshi", "Store manager", "INVENTORY_MANAGER"), ("ot@healthwise.demo.com", "Omkar Patil", "OT technician", "OT_STAFF"),
                                                ("bloodbank@healthwise.demo.com", "Bela Kulkarni", "Blood bank technician", "BLOOD_BANK_STAFF"),
                                                ("bloodbank2@healthwise.demo.com", "Bimal Rao", "Blood bank technician", "BLOOD_BANK_STAFF"),
                                                ("billing@healthwise.demo.com", "Bina Shah", "Billing executive", "BILLING_EXECUTIVE"), ("billing2@healthwise.demo.com", "Bhanu Mehta", "Billing executive", "BILLING_EXECUTIVE"),
                                                ("accounts@healthwise.demo.com", "Asha Nair", "Accountant", "ACCOUNTANT"), ("tpa@healthwise.demo.com", "Indu Verma", "Insurance and TPA desk", "INSURANCE_EXECUTIVE")):
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user_service.create_staff(db, EMPLOYEE, StaffCreate(email=email, full_name=name, password=DEMO_PASSWORD, designation=designation))
            user = db.scalar(select(User).where(User.email == email))
        role = db.scalar(select(Role).where(Role.code == role_code))
        if role and not db.scalar(select(UserRole.id).where(UserRole.user_id == user.id, UserRole.role_id == role.id)):
            db.add(UserRole(user_id=user.id, role_id=role.id, granted_by=access_service.first_admin_id(db)))
    if db.scalar(select(Supplier.id).limit(1)) is None:
        db.add(Supplier(name="MediSupply Pvt Ltd (demo)", contact_person="Demo contact", phone="9000000001"))
    if db.scalar(select(InventoryItem.id).limit(1)) is None:
        for code, name, category, unit, minimum in (("GLV-01", "Sterile surgical gloves", "CONSUMABLE", "pair", 50), ("SUT-01", "Suture 2-0", "CONSUMABLE", "piece", 20), ("DRP-01", "Surgical drape", "SUPPLY", "piece", 10)):
            db.add(InventoryItem(code=code, name=name, category=category, unit=unit, quantity=0, min_level=minimum, reorder_quantity=minimum * 5))
    from app.database.models import BillingPackage
    for code, name, category, price, gst in (("LAB-ELEC", "Serum Electrolytes", "LAB", 400, 5), ("LAB-CBC", "Complete Blood Count", "LAB", 350, 5), ("RAD-CXR", "Chest X-ray", "RADIOLOGY", 300, 12),
                                             ("BED-GEN", "General ward bed per day", "BED", 1000, 0), ("BED-ICU", "ICU bed per day", "BED", 5000, 0)):   # demo prices: the hospital sets its own
        if db.scalar(select(ServiceCatalog.id).where(ServiceCatalog.code == code)) is None:
            db.add(ServiceCatalog(code=code, name=name, category=category, price=price, gst_percent=gst, is_active=True))
    if db.scalar(select(BillingPackage.id).limit(1)) is None:
        db.add(BillingPackage(name="Health check package (demo)", price=2500, gst_percent=0, inclusions="Consultation, blood count, chest X-ray"))
    for name in ("OT 1", "OT 2"):
        if db.scalar(select(OperationTheatre.id).where(OperationTheatre.name == name)) is None:
            db.add(OperationTheatre(name=name))
    db.commit()


# One mobile number per demo account, so the "mobile code" sign-in can be tried (fake numbers; the patient Rahul already has 9000000001).
DEMO_PHONES = {
    "admin@healthwise.demo.com": "9000000100", "anjali.sharma@healthwise.demo.com": "9000000101", "priya.joshi@healthwise.demo.com": "9000000102", "pharmacy@healthwise.demo.com": "9000000103",
    "lab@healthwise.demo.com": "9000000104", "nurse@healthwise.demo.com": "9000000105", "intern@healthwise.demo.com": "9000000106", "pg.student@healthwise.demo.com": "9000000107",
    "pathologist@healthwise.demo.com": "9000000108", "radiology.tech@healthwise.demo.com": "9000000109", "radiologist@healthwise.demo.com": "9000000110", "inventory@healthwise.demo.com": "9000000111",
    "ot@healthwise.demo.com": "9000000112", "bloodbank@healthwise.demo.com": "9000000113", "bloodbank2@healthwise.demo.com": "9000000114", "billing@healthwise.demo.com": "9000000115",
    "billing2@healthwise.demo.com": "9000000116", "accounts@healthwise.demo.com": "9000000117", "tpa@healthwise.demo.com": "9000000118", "rahul.patil@healthwise.demo.com": "9000000001",
}


def seed_demo_phones(db) -> None:
    from app.database.models import Employee, LabStaff, Nurse, Patient, PharmacyStaff, RadiologyStaff
    for email, phone in DEMO_PHONES.items():
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            continue
        for model in (Patient, Doctor, Employee, PharmacyStaff, LabStaff, Nurse, RadiologyStaff):
            row = db.scalar(select(model).where(model.user_id == user.id))
            if row is not None and not row.phone:
                row.phone = phone
    db.commit()


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
        if not exists("pathologist@healthwise.demo.com"):
            user_service.create_staff(db, LAB, StaffCreate(email="pathologist@healthwise.demo.com", full_name="Dr. Kavita Rane", password=DEMO_PASSWORD, lab_name="City Diagnostic Lab", staff_type="PATHOLOGIST"))
        if not exists("radiology.tech@healthwise.demo.com"):
            user_service.create_staff(db, RADIOLOGY, StaffCreate(email="radiology.tech@healthwise.demo.com", full_name="Sunil Gaikwad", password=DEMO_PASSWORD, staff_type="TECHNICIAN"))
        if not exists("radiologist@healthwise.demo.com"):
            user_service.create_staff(db, RADIOLOGY, StaffCreate(email="radiologist@healthwise.demo.com", full_name="Dr. Vikram Nair", password=DEMO_PASSWORD, staff_type="RADIOLOGIST"))
        seed_diagnostic_catalogue(db)
        seed_operations(db)
        seed_demo_phones(db)
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
                        ("Pharmacy", "pharmacy@healthwise.demo.com"), ("Lab", "lab@healthwise.demo.com"), ("Pathologist", "pathologist@healthwise.demo.com"), ("Radiology tech", "radiology.tech@healthwise.demo.com"), ("Radiologist", "radiologist@healthwise.demo.com"), ("Store", "inventory@healthwise.demo.com"), ("OT staff", "ot@healthwise.demo.com"), ("Blood bank", "bloodbank@healthwise.demo.com"), ("Blood bank 2", "bloodbank2@healthwise.demo.com"), ("Billing", "billing@healthwise.demo.com"), ("Billing 2", "billing2@healthwise.demo.com"), ("Accountant", "accounts@healthwise.demo.com"), ("TPA desk", "tpa@healthwise.demo.com"),
                        ("Nurse", "nurse@healthwise.demo.com"), ("Intern", "intern@healthwise.demo.com"), ("PG resident", "pg.student@healthwise.demo.com")):
        print(f"  {role:9s} {email}")


if __name__ == "__main__":
    main()
