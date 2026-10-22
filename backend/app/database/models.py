"""Database tables. One class = one table.

Design notes (useful for the viva):
- Every person logs in through the `users` table. The `role` column decides what they may do.
- Extra details of each role live in their own table (patients, doctors, employees, pharmacy_staff).
- The patient timeline is NOT stored: it is built from these tables when requested.
"""
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # stored as naive UTC


# ------------------------------------------------------------------ users and roles
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(20), index=True)  # ADMIN / DOCTOR / EMPLOYEE / PATIENT / PHARMACY / LAB
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_path: Mapped[str | None] = mapped_column(String(255))   # profile picture, inside the private upload folder
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    patient_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # e.g. P-0001
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(30))
    phone: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(String(300))
    emergency_contact: Mapped[str | None] = mapped_column(String(150))
    # Voluntary clinical details. Employees do not see these (see schemas/patient.py).
    blood_group: Mapped[str | None] = mapped_column(String(10))
    allergies: Mapped[str | None] = mapped_column(Text)
    medical_history_text: Mapped[str | None] = mapped_column(Text)
    current_medications: Mapped[str | None] = mapped_column(Text)
    assigned_doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[User] = relationship()
    assigned_doctor: Mapped["Doctor | None"] = relationship()


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    specialization: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(30))
    qualification: Mapped[str | None] = mapped_column(String(150))
    registration_number: Mapped[str | None] = mapped_column(String(50))
    experience_years: Mapped[int | None] = mapped_column(Integer)

    user: Mapped[User] = relationship()
    department: Mapped[Department | None] = relationship()


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    designation: Mapped[str | None] = mapped_column(String(100))  # receptionist, lab assistant ...
    phone: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(String(300))

    user: Mapped[User] = relationship()


class PharmacyStaff(Base):
    __tablename__ = "pharmacy_staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    pharmacy_name: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30))
    license_number: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(String(300))

    user: Mapped[User] = relationship()


class LabStaff(Base):
    __tablename__ = "lab_staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    lab_name: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30))
    registration_number: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(String(300))

    user: Mapped[User] = relationship()


# ------------------------------------------------------------------ appointments
class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    reason: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="SCHEDULED")  # SCHEDULED/CONFIRMED/COMPLETED/CANCELLED
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    patient: Mapped[Patient] = relationship()
    doctor: Mapped[Doctor] = relationship()
    department: Mapped[Department | None] = relationship()


# ------------------------------------------------------------------ reports
class HealthReport(Base):
    __tablename__ = "health_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(String(500))
    report_date: Mapped[date | None] = mapped_column(Date)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    processing_status: Mapped[str] = mapped_column(String(20), default="ANALYZED")  # only successes are stored
    doctor_review_status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING / REVIEWED
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_decision: Mapped[str | None] = mapped_column(String(20))  # APPROVED / MODIFIED / CLARIFIED
    review_comment: Mapped[str | None] = mapped_column(Text)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    processing_method: Mapped[str | None] = mapped_column(String(20))  # pdf_text / ocr / text
    ai_summary: Mapped[str | None] = mapped_column(Text)
    report_type: Mapped[str | None] = mapped_column(String(30))   # LAB / IMAGING / ECG / PATHOLOGY / DISCHARGE / ...
    insights_json: Mapped[str | None] = mapped_column(Text)       # doctor suggestions + patient tips (see insight_service)

    patient: Mapped[Patient] = relationship()
    uploader: Mapped[User] = relationship(foreign_keys=[uploaded_by])
    assigned_doctor: Mapped["Doctor | None"] = relationship(foreign_keys=[assigned_doctor_id])
    reviewer: Mapped["Doctor | None"] = relationship(foreign_keys=[reviewed_by])
    parameters: Mapped[list["HealthParameter"]] = relationship(
        back_populates="report", cascade="all, delete-orphan", order_by="HealthParameter.id"
    )


class HealthParameter(Base):
    __tablename__ = "health_parameters"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("health_reports.id"), index=True)
    test_name: Mapped[str] = mapped_column(String(200))        # exactly as printed in the report
    normalized_name: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(50))
    reference_text: Mapped[str | None] = mapped_column(String(120))
    reference_low: Mapped[float | None] = mapped_column(Float)
    reference_high: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20))            # WITHIN_RANGE / ABOVE_RANGE / BELOW_RANGE / UNKNOWN
    ai_explanation: Mapped[str | None] = mapped_column(Text)  # JSON text
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    report: Mapped[HealthReport] = relationship(back_populates="parameters")


class ReportComparison(Base):
    __tablename__ = "report_comparisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    previous_report_id: Mapped[int] = mapped_column(ForeignKey("health_reports.id"))
    latest_report_id: Mapped[int] = mapped_column(ForeignKey("health_reports.id"))
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ------------------------------------------------------------------ doctor content (always labelled "Doctor's ...")
class DoctorNote(Base):
    __tablename__ = "doctor_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    report_id: Mapped[int | None] = mapped_column(ForeignKey("health_reports.id"))
    note: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(25), default="NORMAL")  # NORMAL / IMPORTANT / FOLLOW_UP_REQUIRED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    doctor: Mapped[Doctor] = relationship()
    patient: Mapped[Patient] = relationship()


class DoctorRecommendation(Base):
    __tablename__ = "doctor_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    report_id: Mapped[int | None] = mapped_column(ForeignKey("health_reports.id"))
    title: Mapped[str] = mapped_column(String(200))
    recommendation: Mapped[str] = mapped_column(Text)
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(String(25), default="NORMAL")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    doctor: Mapped[Doctor] = relationship()
    patient: Mapped[Patient] = relationship()


class MedicalHistoryEntry(Base):
    """Background history added by a doctor (past illness, surgery, allergy note ...)."""
    __tablename__ = "medical_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    entry_date: Mapped[date] = mapped_column(Date)
    entry_type: Mapped[str] = mapped_column(String(40))  # e.g. Past illness, Surgery, Allergy, Other
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    doctor: Mapped[Doctor] = relationship()


# ------------------------------------------------------------------ prescriptions and pharmacy
class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("health_reports.id"))
    prescription_date: Mapped[date] = mapped_column(Date)
    clinical_indication: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(25), default="ACTIVE")  # ACTIVE/PARTIALLY_DISPENSED/DISPENSED/CANCELLED/EXPIRED
    notes: Mapped[str | None] = mapped_column(Text)
    tests_advised: Mapped[str | None] = mapped_column(Text)  # tests the doctor wants done, one per line; NEVER shown to the pharmacy
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    patient: Mapped[Patient] = relationship()
    doctor: Mapped[Doctor] = relationship()
    items: Mapped[list["PrescriptionItem"]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan", order_by="PrescriptionItem.id"
    )


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id"), index=True)
    medicine_name: Mapped[str] = mapped_column(String(200))
    dosage: Mapped[str] = mapped_column(String(100))
    frequency: Mapped[str] = mapped_column(String(100))
    duration: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer)
    instructions: Mapped[str | None] = mapped_column(Text)
    dispense_status: Mapped[str] = mapped_column(String(25), default="PENDING")  # PENDING/PARTIALLY_DISPENSED/DISPENSED/UNAVAILABLE

    prescription: Mapped[Prescription] = relationship(back_populates="items")
    dispensings: Mapped[list["MedicineDispensing"]] = relationship(back_populates="item")


class MedicineInventory(Base):
    __tablename__ = "medicine_inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    medicine_name: Mapped[str] = mapped_column(String(200), index=True)
    batch_number: Mapped[str | None] = mapped_column(String(50))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    manufacturer: Mapped[str | None] = mapped_column(String(150))
    unit_price: Mapped[float | None] = mapped_column(Float)       # selling price of ONE unit, before GST
    barcode: Mapped[str | None] = mapped_column(String(64), index=True)   # printed on the pack (or made by the system)
    gst_percent: Mapped[float | None] = mapped_column(Float)


class Sale(Base):
    """One bill handed to a customer."""
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    bill_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    pharmacy_staff_id: Mapped[int] = mapped_column(ForeignKey("pharmacy_staff.id"))
    prescription_id: Mapped[int | None] = mapped_column(ForeignKey("prescriptions.id"))
    customer_name: Mapped[str | None] = mapped_column(String(150))
    customer_phone: Mapped[str | None] = mapped_column(String(30))
    payment_method: Mapped[str] = mapped_column(String(10), default="CASH")   # CASH / UPI / CARD
    subtotal: Mapped[float] = mapped_column(Float, default=0)
    discount: Mapped[float] = mapped_column(Float, default=0)
    tax: Mapped[float] = mapped_column(Float, default=0)
    total: Mapped[float] = mapped_column(Float, default=0)

    pharmacy_staff: Mapped[PharmacyStaff] = relationship()
    items: Mapped[list["SaleItem"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan", order_by="SaleItem.id")


class SaleItem(Base):
    """One line of a bill. The price, GST and batch are copied here so an old bill never changes."""
    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), index=True)
    inventory_id: Mapped[int | None] = mapped_column(ForeignKey("medicine_inventory.id"))
    prescription_item_id: Mapped[int | None] = mapped_column(ForeignKey("prescription_items.id"), index=True)
    medicine_name: Mapped[str] = mapped_column(String(200))
    batch_number: Mapped[str | None] = mapped_column(String(50))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)
    gst_percent: Mapped[float] = mapped_column(Float, default=0)
    line_total: Mapped[float] = mapped_column(Float)     # quantity x price, before GST
    tax_amount: Mapped[float] = mapped_column(Float, default=0)

    sale: Mapped[Sale] = relationship(back_populates="items")


class MedicineDispensing(Base):
    __tablename__ = "medicine_dispensing"

    id: Mapped[int] = mapped_column(primary_key=True)
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id"), index=True)
    prescription_item_id: Mapped[int] = mapped_column(ForeignKey("prescription_items.id"))
    pharmacy_staff_id: Mapped[int] = mapped_column(ForeignKey("pharmacy_staff.id"))
    quantity_prescribed: Mapped[int] = mapped_column(Integer)
    quantity_dispensed: Mapped[int] = mapped_column(Integer)  # amount given in THIS transaction
    dispensed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(25))  # item status after this transaction
    notes: Mapped[str | None] = mapped_column(Text)

    item: Mapped[PrescriptionItem] = relationship(back_populates="dispensings")
    pharmacy_staff: Mapped[PharmacyStaff] = relationship()


# ------------------------------------------------------------------ health history form (patient + doctor)
class PatientHistory(Base):
    """The standing medical history of one patient: conditions, allergies, surgeries, family history, habits ...
    One row per patient. The lists live in `data_json`; the medicines have their own table (PatientMedication)."""
    __tablename__ = "patient_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), unique=True, index=True)
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    data_json: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    patient: Mapped[Patient] = relationship()
    editor: Mapped["User | None"] = relationship(foreign_keys=[updated_by])


class PatientMedication(Base):
    """A medicine the patient takes (or took). Kept as rows so a doctor can read it at once and so it can be searched."""
    __tablename__ = "patient_medications"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    dose: Mapped[str | None] = mapped_column(String(100))
    frequency: Mapped[str | None] = mapped_column(String(100))
    reason: Mapped[str | None] = mapped_column(String(200))      # what it is taken for
    since: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(String(300))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ClinicalAssessment(Base):
    """A doctor's assessment of the patient on one visit (like the hospital's initial assessment sheet)."""
    __tablename__ = "clinical_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    chief_complaint: Mapped[str | None] = mapped_column(Text)
    history_of_present_illness: Mapped[str | None] = mapped_column(Text)
    vitals_json: Mapped[str | None] = mapped_column(Text)
    examination_json: Mapped[str | None] = mapped_column(Text)
    provisional_diagnosis: Mapped[str | None] = mapped_column(Text)   # written by the doctor, never by the system
    investigations_advised: Mapped[str | None] = mapped_column(Text)
    plan_type: Mapped[str | None] = mapped_column(String(20))          # MEDICAL / SURGICAL / BOTH
    plan_details: Mapped[str | None] = mapped_column(Text)
    special_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    doctor: Mapped[Doctor] = relationship()


# ------------------------------------------------------------------ audit
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[str | None] = mapped_column(String(300))
    ip_address: Mapped[str | None] = mapped_column(String(60))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    user: Mapped[User | None] = relationship()
