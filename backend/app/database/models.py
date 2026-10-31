"""Database tables. One class = one table.

Design notes (useful for the viva):
- Every person logs in through the `users` table. The `role` column decides what they may do.
- Extra details of each role live in their own table (patients, doctors, employees, pharmacy_staff).
- The patient timeline is NOT stored: it is built from these tables when requested.
"""
from datetime import date, datetime, timezone

from sqlalchemy import UniqueConstraint, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
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
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)     # nullable so old databases can add the column


class Specialization(Base):
    """A medical specialization inside one department (for example Cardiology -> Interventional Cardiologist)."""
    __tablename__ = "specializations"
    __table_args__ = (UniqueConstraint("department_id", "name_key", name="uq_specialization_department_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    name_key: Mapped[str] = mapped_column(String(100))                        # lower-cased name, so duplicates are found ignoring case
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)

    department: Mapped["Department"] = relationship()


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
    specialization: Mapped[str | None] = mapped_column(String(120))        # legacy free text, kept for old rows ("Other (legacy)")
    specialization_id: Mapped[int | None] = mapped_column(ForeignKey("specializations.id"))
    phone: Mapped[str | None] = mapped_column(String(30))
    qualification: Mapped[str | None] = mapped_column(String(150))
    registration_number: Mapped[str | None] = mapped_column(String(50))
    experience_years: Mapped[int | None] = mapped_column(Integer)

    user: Mapped[User] = relationship()
    department: Mapped[Department | None] = relationship()
    specialization_ref: Mapped["Specialization | None"] = relationship()

    @property
    def specialization_name(self) -> str | None:
        """The chosen specialization, else the old free text."""
        return self.specialization_ref.name if self.specialization_ref else (self.specialization or None)


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
    # what is happening, told by the patient when booking (the doctor reads it before the visit)
    symptoms_json: Mapped[str | None] = mapped_column(Text)
    duration: Mapped[str | None] = mapped_column(String(60))
    details: Mapped[str | None] = mapped_column(Text)
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
    manufacture_date: Mapped[date | None] = mapped_column(Date)      # optional; the expiry must be after it
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
    # detailed medication history (all optional)
    route: Mapped[str | None] = mapped_column(String(40))              # oral, injection, inhaled ...
    prescriber: Mapped[str | None] = mapped_column(String(150))
    adherence: Mapped[str | None] = mapped_column(String(20))          # REGULAR / SOMETIMES_MISSED / OFTEN_MISSED / UNKNOWN
    condition_id: Mapped[int | None] = mapped_column(ForeignKey("chronic_conditions.id"))   # the illness it is taken for
    source: Mapped[str | None] = mapped_column(String(20))
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_deleted: Mapped[bool | None] = mapped_column(Boolean, default=False)   # removed from the list but kept (and recoverable)


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


# ------------------------------------------------------------------ clinical intelligence (emergency events, follow-ups, reviews)
class EmergencyEvent(Base):
    """One emergency visit, as written by a doctor from the hospital's own records. Every field is optional: a record can be
    incomplete, and the review says so. The system never fills a gap or names a cause that the clinician did not write."""
    __tablename__ = "emergency_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    recorded_by: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    event_at: Mapped[datetime | None] = mapped_column(DateTime)             # when it happened (None = date not recorded)
    arrival_method: Mapped[str | None] = mapped_column(String(40))
    chief_complaint: Mapped[str | None] = mapped_column(Text)
    symptoms_json: Mapped[str | None] = mapped_column(Text)
    onset_text: Mapped[str | None] = mapped_column(String(120))
    duration_text: Mapped[str | None] = mapped_column(String(120))
    vitals_json: Mapped[str | None] = mapped_column(Text)
    recent_medication_changes: Mapped[str | None] = mapped_column(Text)
    exam_findings: Mapped[str | None] = mapped_column(Text)
    investigations_ordered: Mapped[str | None] = mapped_column(Text)
    investigation_results: Mapped[str | None] = mapped_column(Text)
    clinician_assessment: Mapped[str | None] = mapped_column(Text)          # the treating clinician's own assessment
    documented_cause: Mapped[str | None] = mapped_column(Text)              # a cause only if the clinician wrote one
    contributing_json: Mapped[str | None] = mapped_column(Text)             # factors the clinician recorded as relevant
    treatment_given: Mapped[str | None] = mapped_column(Text)
    response_to_treatment: Mapped[str | None] = mapped_column(Text)
    disposition: Mapped[str | None] = mapped_column(String(20))             # ADMITTED / DISCHARGED / TRANSFERRED / OTHER
    discharge_instructions: Mapped[str | None] = mapped_column(Text)
    follow_up_recommendations: Mapped[str | None] = mapped_column(Text)
    treating_clinician: Mapped[str | None] = mapped_column(String(150))
    source_report_ids_json: Mapped[str | None] = mapped_column(Text)        # reports that belong to this event
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    recorder: Mapped[Doctor] = relationship()
    timeline: Mapped[list["EmergencyTimelineEntry"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", order_by="EmergencyTimelineEntry.occurred_at")


class EmergencyTimelineEntry(Base):
    """One timestamped step of an emergency visit (arrival, vitals, tests ordered, results, assessment, treatment ...)."""
    __tablename__ = "emergency_timeline_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("emergency_events.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    kind: Mapped[str] = mapped_column(String(30))        # ARRIVAL / VITALS / INVESTIGATION / RESULT / ASSESSMENT / TREATMENT / REASSESSMENT / DISPOSITION / OTHER
    text: Mapped[str] = mapped_column(Text)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    event: Mapped[EmergencyEvent] = relationship(back_populates="timeline")


class FollowUpTask(Base):
    """Something that must still happen: a visit, a test, a check. A doctor creates it, and a doctor closes it with an outcome."""
    __tablename__ = "follow_up_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    title: Mapped[str] = mapped_column(String(200))
    details: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date)
    source_type: Mapped[str | None] = mapped_column(String(30))   # where it came from: recommendation / emergency / assessment ...
    source_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")   # PENDING / DONE / CANCELLED
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    outcome: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    creator: Mapped[Doctor] = relationship()


class SummaryReview(Base):
    """A doctor's own words about one item of the clinical summary: reviewed, an interpretation, a correction of an extraction
    error, or a flag that something is missing. The original records and the computer's text are never overwritten."""
    __tablename__ = "summary_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    item_key: Mapped[str] = mapped_column(String(80), index=True)     # e.g. "report:12", "statement:S3", "section:missing"
    action: Mapped[str] = mapped_column(String(20))                   # REVIEWED / INTERPRETATION / CORRECTION / MISSING_FLAG
    text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    doctor: Mapped[Doctor] = relationship()


class ClinicalSummarySnapshot(Base):
    """A narrative written by the optional AI model from the verified evidence, kept apart from every clinician's text."""
    __tablename__ = "clinical_summary_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    generated_by: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    kind: Mapped[str] = mapped_column(String(10))                     # AI
    model: Mapped[str | None] = mapped_column(String(80))
    content_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    doctor: Mapped[Doctor] = relationship()


# ------------------------------------------------------------------ laboratory work (one row per test a doctor advised)
class LabTestOrder(Base):
    """One advised test, followed from order to result: waiting for the sample -> sample taken -> being tested -> done (result report
    attached), or rejected (for example a bad sample). Rows are made from the tests written on prescriptions; the lab only changes their
    progress. The result itself is an ordinary report that the doctor reviews before the patient sees it."""
    __tablename__ = "lab_test_orders"
    __table_args__ = (UniqueConstraint("prescription_id", "test_name", name="uq_lab_order_test"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    test_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="ORDERED", index=True)   # ORDERED / SAMPLE_COLLECTED / IN_PROGRESS / COMPLETED / REJECTED / CANCELLED
    urgent: Mapped[bool | None] = mapped_column(Boolean, default=False)
    sample_type: Mapped[str | None] = mapped_column(String(40))
    sample_code: Mapped[str | None] = mapped_column(String(30), unique=True)          # the label put on the sample, e.g. LAB-20261023-0007
    collected_at: Mapped[datetime | None] = mapped_column(DateTime)
    collected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    report_id: Mapped[int | None] = mapped_column(ForeignKey("health_reports.id"))   # the result
    note: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    prescription: Mapped[Prescription] = relationship()
    patient: Mapped[Patient] = relationship()
    doctor: Mapped[Doctor] = relationship()


# ------------------------------------------------------------------ detailed past medical history
class ChronicCondition(Base):
    """A long-term illness (diabetes, hypertension or any other) with its own details. `source` says who the information came from
    and `verified_by` is set only when a doctor has checked it. Records are never hard-deleted (`is_deleted`), and every change is kept
    in HistoryRevision."""
    __tablename__ = "chronic_conditions"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    kind: Mapped[str] = mapped_column(String(15))                      # DIABETES / HYPERTENSION / OTHER
    name: Mapped[str] = mapped_column(String(150))
    diagnosis_type: Mapped[str | None] = mapped_column(String(60))     # e.g. Type 2, Gestational, Unknown
    duration_text: Mapped[str | None] = mapped_column(String(60))
    diagnosis_year: Mapped[int | None] = mapped_column(Integer)
    control_status: Mapped[str | None] = mapped_column(String(20))     # GOOD / FAIR / POOR / UNKNOWN
    details_json: Mapped[str | None] = mapped_column(Text)             # complications, control readings, hospitalisation
    notes: Mapped[str | None] = mapped_column(Text)
    on_treatment: Mapped[bool | None] = mapped_column(Boolean)
    source: Mapped[str] = mapped_column(String(20), default="PATIENT_REPORTED")   # PATIENT_REPORTED / DOCTOR_VERIFIED / HOSPITAL_RECORD / EARLIER_ENTRY
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_deleted: Mapped[bool | None] = mapped_column(Boolean, default=False)


class HospitalAdmission(Base):
    """One earlier stay in a hospital (acute illness, accident, injury, operation ...). Nested lists (vital signs, medicines given,
    discharge medicines) are kept as JSON; the operation itself is a SurgeryRecord linked to the admission."""
    __tablename__ = "hospital_admissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    hospital_name: Mapped[str | None] = mapped_column(String(200))
    admitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    admitted_date_text: Mapped[str | None] = mapped_column(String(40))     # when only a month or year is known
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime)
    admission_type: Mapped[str | None] = mapped_column(String(15))         # EMERGENCY / PLANNED / REFERRAL / OTHER
    main_complaint: Mapped[str | None] = mapped_column(Text)
    secondary_complaints: Mapped[str | None] = mapped_column(Text)
    provisional_diagnosis: Mapped[str | None] = mapped_column(Text)
    final_diagnosis: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)                       # reason for hospitalisation
    referred_by: Mapped[str | None] = mapped_column(String(200))
    symptoms: Mapped[str | None] = mapped_column(Text)
    history_of_present_illness: Mapped[str | None] = mapped_column(Text)
    preexisting_conditions: Mapped[str | None] = mapped_column(Text)
    vitals_json: Mapped[str | None] = mapped_column(Text)                  # measured AT ADMISSION, never copied from today
    exam_findings: Mapped[str | None] = mapped_column(Text)
    investigations: Mapped[str | None] = mapped_column(Text)               # laboratory and imaging results
    complications: Mapped[str | None] = mapped_column(Text)                # associated with the diagnosis
    treatment_given: Mapped[str | None] = mapped_column(Text)
    medications_json: Mapped[str | None] = mapped_column(Text)             # list: name, dose, frequency, route, duration, category
    iv_fluids_oxygen: Mapped[str | None] = mapped_column(Text)
    procedures_supportive: Mapped[str | None] = mapped_column(Text)
    medication_changes: Mapped[str | None] = mapped_column(Text)
    response_to_treatment: Mapped[str | None] = mapped_column(Text)
    stay_complications: Mapped[str | None] = mapped_column(Text)           # complications during the stay
    discharge_condition: Mapped[str | None] = mapped_column(Text)
    treatment_completed: Mapped[str | None] = mapped_column(Text)
    discharge_medications_json: Mapped[str | None] = mapped_column(Text)
    discharge_instructions: Mapped[str | None] = mapped_column(Text)
    wound_rehab_instructions: Mapped[str | None] = mapped_column(Text)
    followup_date: Mapped[date | None] = mapped_column(Date)
    specialist_review: Mapped[str | None] = mapped_column(String(200))
    recovery_status: Mapped[str | None] = mapped_column(Text)
    remaining_symptoms: Mapped[str | None] = mapped_column(Text)
    readmission_notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="PATIENT_REPORTED")
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_deleted: Mapped[bool | None] = mapped_column(Boolean, default=False)

    surgeries: Mapped[list["SurgeryRecord"]] = relationship(back_populates="admission", order_by="SurgeryRecord.id")


class SurgeryRecord(Base):
    """An operation or procedure. It may belong to an admission or stand alone (for example an older operation with only a year)."""
    __tablename__ = "surgery_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    admission_id: Mapped[int | None] = mapped_column(ForeignKey("hospital_admissions.id"), index=True)
    procedure_name: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str | None] = mapped_column(Text)
    body_site: Mapped[str | None] = mapped_column(String(150))             # e.g. right femur (fracture location)
    operation_date: Mapped[date | None] = mapped_column(Date)
    operation_year: Mapped[int | None] = mapped_column(Integer)
    surgeon: Mapped[str | None] = mapped_column(String(150))
    hospital: Mapped[str | None] = mapped_column(String(200))
    anesthesia: Mapped[str | None] = mapped_column(String(100))
    findings: Mapped[str | None] = mapped_column(Text)
    implant_used: Mapped[bool | None] = mapped_column(Boolean)              # None = not documented (never assumed)
    implant_type: Mapped[str | None] = mapped_column(String(100))           # plate, screws, rod/nail, prosthesis, other
    implant_material: Mapped[str | None] = mapped_column(String(150))
    implant_serial: Mapped[str | None] = mapped_column(String(100))
    postop_xray: Mapped[str | None] = mapped_column(Text)
    postop_treatment: Mapped[str | None] = mapped_column(Text)
    postop_complications: Mapped[str | None] = mapped_column(Text)
    recovery_progress: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="PATIENT_REPORTED")
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_deleted: Mapped[bool | None] = mapped_column(Boolean, default=False)

    admission: Mapped["HospitalAdmission | None"] = relationship(back_populates="surgeries")


class HistoryRevision(Base):
    """Append-only log of every change to the detailed history: who changed what and what it looked like before."""
    __tablename__ = "history_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(20), index=True)       # condition / admission / surgery / medication
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(12))                        # CREATE / UPDATE / DELETE / VERIFY / MIGRATE
    before_json: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ------------------------------------------------------------------ patient assistant (chat + voice)
class PatientAssistantConversation(Base):
    """One chat of a patient with the assistant. Only the signed-in patient can read or delete it."""
    __tablename__ = "patient_assistant_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    title: Mapped[str] = mapped_column(String(120), default="New chat")
    language: Mapped[str] = mapped_column(String(5), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    messages: Mapped[list["PatientAssistantMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="PatientAssistantMessage.id")


class PatientAssistantMessage(Base):
    """What the patient typed or said (as text, never audio) and the answer they saw. No hidden reasoning is stored."""
    __tablename__ = "patient_assistant_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("patient_assistant_conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(10))                      # PATIENT / ASSISTANT
    text: Mapped[str] = mapped_column(Text)
    meta_json: Mapped[str | None] = mapped_column(Text)                # intent, topic (for follow-up questions), safety kind, ai_used
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    conversation: Mapped[PatientAssistantConversation] = relationship(back_populates="messages")
    evidence: Mapped[list["PatientAssistantEvidence"]] = relationship(cascade="all, delete-orphan", order_by="PatientAssistantEvidence.id")


class PatientAssistantEvidence(Base):
    """The record an answer was based on (a pointer and the date, not a copy of the record)."""
    __tablename__ = "patient_assistant_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("patient_assistant_messages.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(20))               # report / prescription / appointment / note / recommendation / history
    source_id: Mapped[int | None] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(200))
    record_date: Mapped[str | None] = mapped_column(String(20))


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


# ------------------------------------------------------------------ trainees (interns and PG students) and referrals
class Trainee(Base):
    """An intern or PG student. Not a doctor: takes histories and refers the patient to a doctor, never prescribes or orders tests."""
    __tablename__ = "trainees"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    trainee_type: Mapped[str] = mapped_column(String(15), default="INTERN")          # INTERN / PG_STUDENT
    year_branch: Mapped[str | None] = mapped_column(String(120))                      # PG only, e.g. "MD Medicine, Year 2"
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    phone: Mapped[str | None] = mapped_column(String(30))

    user: Mapped[User] = relationship()
    department: Mapped[Department | None] = relationship()
    supervisor: Mapped["Doctor | None"] = relationship()


class TraineeHistory(Base):
    """A history taken by a trainee. It is NOT the patient's permanent record: a doctor reviews it first (DRAFT -> COMPLETE -> VERIFIED)."""
    __tablename__ = "trainee_histories"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    trainee_id: Mapped[int] = mapped_column(ForeignKey("trainees.id"), index=True)
    status: Mapped[str] = mapped_column(String(15), default="DRAFT", index=True)
    data_json: Mapped[str | None] = mapped_column(Text)
    doctor_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)

    patient: Mapped[Patient] = relationship()
    trainee: Mapped[Trainee] = relationship()
    verifier: Mapped["Doctor | None"] = relationship(foreign_keys=[verified_by])


class TraineeHistoryRevision(Base):
    """The earlier version of a trainee history, kept whenever it is changed after completion (by the trainee or by a doctor)."""
    __tablename__ = "trainee_history_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    history_id: Mapped[int] = mapped_column(ForeignKey("trainee_histories.id"), index=True)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    data_json: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Referral(Base):
    """A trainee sends a patient, with the completed history, to a doctor."""
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    trainee_id: Mapped[int] = mapped_column(ForeignKey("trainees.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    history_id: Mapped[int] = mapped_column(ForeignKey("trainee_histories.id"), index=True)
    reason: Mapped[str] = mapped_column(String(300))
    urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(15), default="SENT", index=True)     # SENT / SEEN / COMPLETED
    suggested_department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    overridden: Mapped[bool] = mapped_column(Boolean, default=False)                  # the trainee chose a different department than suggested
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    supervisor_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    supervisor_note: Mapped[str | None] = mapped_column(String(500))

    patient: Mapped[Patient] = relationship()
    trainee: Mapped[Trainee] = relationship()
    doctor: Mapped[Doctor] = relationship()
    history: Mapped[TraineeHistory] = relationship()
