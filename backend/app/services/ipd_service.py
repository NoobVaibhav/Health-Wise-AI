"""Inpatient care: admission numbers, wards and beds (with the database rule of one patient per bed), staff assignment, discharge."""
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import (
    Admission, AdmissionStaff, Bed, BedAssignment, Branch, ClinicalOrder, Consultation, DischargeSummary, Doctor, EncounterCharge, NumberCounter, Patient, ProgressNote, User, Ward,
)
from app.services import encounter_service as enc
from app.services import hospital_service


def now() -> datetime:
    return enc.now()


# ------------------------------------------------------------------ numbers
def next_number(db: Session, kind: str, branch: Branch, year: int | None = None) -> int:
    year = year or now().year
    row = db.scalar(select(NumberCounter).where(NumberCounter.kind == kind, NumberCounter.branch_id == branch.id, NumberCounter.year == year))
    if row is None:
        row = NumberCounter(kind=kind, branch_id=branch.id, year=year, last_number=0)
        db.add(row)
        db.flush()
    db.execute(update(NumberCounter).where(NumberCounter.id == row.id).values(last_number=NumberCounter.last_number + 1))
    db.flush()
    db.refresh(row)
    return row.last_number


# ------------------------------------------------------------------ beds
def active_assignment(db: Session, admission_id: int) -> BedAssignment | None:
    return db.scalar(select(BedAssignment).where(BedAssignment.admission_id == admission_id, BedAssignment.released_at.is_(None)))


def bed_occupant(db: Session, bed_id: int) -> BedAssignment | None:
    return db.scalar(select(BedAssignment).where(BedAssignment.bed_id == bed_id, BedAssignment.released_at.is_(None)))


def assign_bed(db: Session, admission: Admission, bed: Bed, user: User, reason: str | None = None) -> BedAssignment:
    """Moves the patient to the bed: the old bed is released and goes to cleaning. The two partial unique indexes of the table are the real guard: if two people
    take the same bed at the same moment, the second one gets a clear 409 and nothing is changed."""
    if admission.status != "ADMITTED":
        raise HTTPException(409, "This patient has been discharged.")
    if not bed.is_active or not bed.ward.is_active:
        raise HTTPException(409, "This bed is not in use.")
    if bed.status == "RESERVED" and bed.reserved_for_patient_id not in (None, admission.patient_id):
        raise HTTPException(409, "This bed is reserved for another patient.")
    if bed.status in ("CLEANING", "MAINTENANCE"):
        raise HTTPException(409, f"This bed is not ready ({bed.status.lower()}).")
    if bed_occupant(db, bed.id):
        raise HTTPException(409, "This bed already has a patient.")
    current = active_assignment(db, admission.id)
    if current and current.bed_id == bed.id:
        raise HTTPException(409, "The patient is already in this bed.")
    try:
        with db.begin_nested():
            if current:
                current.released_at = now()
                current.bed.status = "CLEANING"
                db.flush()
            row = BedAssignment(admission_id=admission.id, bed_id=bed.id, assigned_by=user.id, reason=reason, assigned_at=now())
            db.add(row)
            bed.status, bed.reserved_for_patient_id = "AVAILABLE", None
            db.flush()
    except IntegrityError:
        raise HTTPException(409, "This bed was taken a moment ago. Please choose another bed.")
    return row


def ward_summary(db: Session, ward: Ward, with_patients: bool) -> dict:
    beds = db.scalars(select(Bed).where(Bed.ward_id == ward.id).order_by(Bed.code)).all()
    counts = {"AVAILABLE": 0, "OCCUPIED": 0, "RESERVED": 0, "CLEANING": 0, "MAINTENANCE": 0}
    out = []
    for bed in beds:
        occupant = bed_occupant(db, bed.id)
        state = "OCCUPIED" if occupant else bed.status
        if bed.is_active:
            counts[state] += 1
        item = {"id": bed.id, "code": bed.code, "status": state, "is_active": bed.is_active}
        if occupant and with_patients:
            a = occupant.admission
            item["patient"] = {"admission_id": a.id, "admission_no": a.admission_no, "patient_id": a.patient_id, "full_name": a.patient.user.full_name, "uhid": a.patient.uhid, "since": occupant.assigned_at.isoformat()}
        out.append(item)
    return {"id": ward.id, "name": ward.name, "ward_type": ward.ward_type, "branch_id": ward.branch_id, "is_active": ward.is_active, "counts": counts, "beds": out}


# ------------------------------------------------------------------ admission
def admit(db: Session, patient: Patient, doctor: Doctor, department_id: int | None, diagnosis: str | None, source_encounter_id: int | None, expected: date | None, user: User) -> Admission:
    if patient.merged_into_id:
        raise HTTPException(404, "Patient not found.")
    if db.scalar(select(Admission.id).where(Admission.patient_id == patient.id, Admission.status == "ADMITTED")):
        raise HTTPException(409, "This patient is already admitted.")
    branch = db.get(Branch, patient.branch_id) if patient.branch_id else hospital_service.default_branch(db)
    encounter = enc.open_encounter(db, patient, "IPD", doctor=doctor, department_id=department_id or doctor.department_id, source="ADMISSION", user=user)
    year = now().year
    number = f"ADM-{branch.code}-{year % 100:02d}-{next_number(db, 'ADM', branch, year):06d}"
    admission = Admission(admission_no=number, patient_id=patient.id, branch_id=branch.id, department_id=encounter.department_id, encounter_id=encounter.id, source_encounter_id=source_encounter_id,
                          attending_doctor_id=doctor.id, admitting_diagnosis=diagnosis, status="ADMITTED", admitted_at=now(), expected_discharge=expected, created_by=user.id)
    db.add(admission)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This patient is already admitted.")
    return admission


def admission_out(db: Session, a: Admission) -> dict:
    assignment = active_assignment(db, a.id)
    staff = db.scalars(select(AdmissionStaff).where(AdmissionStaff.admission_id == a.id, AdmissionStaff.to_at.is_(None))).all()
    return {"id": a.id, "admission_no": a.admission_no, "status": a.status, "patient": enc.patient_line(a.patient), "department_id": a.department_id, "department_name": a.department.name if a.department else None,
            "attending_doctor_id": a.attending_doctor_id, "attending_doctor": a.attending_doctor.user.full_name, "admitting_diagnosis": a.admitting_diagnosis, "admitted_at": a.admitted_at.isoformat(),
            "expected_discharge": a.expected_discharge.isoformat() if a.expected_discharge else None, "discharged_at": a.discharged_at.isoformat() if a.discharged_at else None, "discharge_type": a.discharge_type,
            "encounter_id": a.encounter_id, "bed": None if assignment is None else {"id": assignment.bed_id, "code": assignment.bed.code, "ward": assignment.bed.ward.name, "ward_type": assignment.bed.ward.ward_type, "since": assignment.assigned_at.isoformat()},
            "staff": [{"id": s.id, "user_id": s.user_id, "name": s.user.full_name, "kind": s.kind, "from_at": s.from_at.isoformat()} for s in staff]}


def summary_out(s: DischargeSummary | None) -> dict | None:
    if s is None:
        return None
    return {"id": s.id, "status": s.status, "final_diagnosis": s.final_diagnosis, "hospital_course": s.hospital_course, "procedures": s.procedures, "investigations_summary": s.investigations_summary,
            "discharge_medicines": s.discharge_medicines, "follow_up": s.follow_up, "diet_advice": s.diet_advice, "warning_signs": s.warning_signs, "approved_at": s.approved_at.isoformat() if s.approved_at else None,
            "approved_by": s.approved_by, "updated_at": s.updated_at.isoformat()}


def discharge(db: Session, admission: Admission, discharge_type: str, note: str | None, user: User) -> dict:
    """Needs the discharge summary approved by the treating doctor. Releases the bed (it goes to cleaning) and closes the stay."""
    if admission.status != "ADMITTED":
        raise HTTPException(409, "This patient has already been discharged.")
    summary = db.scalar(select(DischargeSummary).where(DischargeSummary.admission_id == admission.id))
    if summary is None or summary.status != "APPROVED":
        raise HTTPException(409, "The treating doctor must approve the discharge summary before the patient is discharged.")
    assignment = active_assignment(db, admission.id)
    if assignment:
        assignment.released_at = now()
        assignment.bed.status = "CLEANING"
    admission.status, admission.discharged_at, admission.discharge_type = "DISCHARGED", now(), discharge_type
    admission.encounter.status, admission.encounter.ended_at = "CLOSED", now()
    for s in db.scalars(select(AdmissionStaff).where(AdmissionStaff.admission_id == admission.id, AdmissionStaff.to_at.is_(None))):
        s.to_at = now()
    for order in db.scalars(select(ClinicalOrder).where(ClinicalOrder.admission_id == admission.id, ClinicalOrder.status.in_(("ORDERED", "IN_PROGRESS")))):
        order.status, order.note = "CANCELLED", "Cancelled at discharge"
    from app.database.models import MedicationOrder
    for m in db.scalars(select(MedicationOrder).where(MedicationOrder.admission_id == admission.id, MedicationOrder.status == "ACTIVE")):
        m.status, m.stopped_at = "STOPPED", now()
    db.commit()
    pending = db.scalar(select(func.count(EncounterCharge.id)).where(EncounterCharge.encounter_id == admission.encounter_id, EncounterCharge.status == "PENDING")) or 0
    return {"discharged_at": admission.discharged_at.isoformat(), "pending_charges": pending}
