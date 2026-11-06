"""Inpatient care: wards and beds, admission, staff, progress notes, medication orders and discharge."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, NURSE, forbidden, get_accessible_patient, get_doctor_profile
from app.database.connection import get_db
from app.database.models import (
    Admission, AdmissionStaff, Bed, BedAssignment, Branch, ClinicalAlert, ClinicalOrder, DischargeSummary, Doctor, MedicationOrder, Patient, ProgressNote, User, Ward,
)
from app.schemas.clinical import (
    AdmitIn, BedAssignIn, BedIn, BedStatusIn, DischargeIn, DischargeSummaryIn, MedicationOrderIn, OrderIn, ProgressNoteIn, StaffAssignIn, WardIn, WardUpdate,
)
from app.services import audit_service, encounter_service as enc, grade_service, hospital_service, ipd_service as ipd, nursing_service
from app.services.access_service import require_permission
from app.utils.validators import PathId, QueryId
from app.utils.clock import hospital_today

router = APIRouter(prefix="/api/ipd", tags=["ipd"])
bed_perm = require_permission("ipd.bed", "ward.manage")
ward_admin = require_permission("ward.manage")
admit_perm = require_permission("ipd.admit")
notes_perm = require_permission("ipd.notes")


# ------------------------------------------------------------------ wards and beds
@router.get("/wards")
def wards(branch_id: QueryId = None, include_inactive: bool = False, user: User = Depends(bed_perm), db: Session = Depends(get_db)):
    """The live bed board: every ward with its beds, their state and the counts (available, occupied, reserved, cleaning, maintenance)."""
    query = select(Ward).order_by(Ward.ward_type, Ward.name)
    if branch_id:
        query = query.where(Ward.branch_id == branch_id)
    if not include_inactive:
        query = query.where(Ward.is_active.is_(True))
    return [ipd.ward_summary(db, w, with_patients=True) for w in db.scalars(query)]


@router.get("/bed-counts")
def bed_counts(branch_id: QueryId = None, user: User = Depends(bed_perm), db: Session = Depends(get_db)):
    total = {"AVAILABLE": 0, "OCCUPIED": 0, "RESERVED": 0, "CLEANING": 0, "MAINTENANCE": 0}
    for w in db.scalars(select(Ward).where(Ward.is_active.is_(True), *( [Ward.branch_id == branch_id] if branch_id else []))):
        for k, v in ipd.ward_summary(db, w, with_patients=False)["counts"].items():
            total[k] += v
    return {"counts": total, "beds": sum(total.values())}


@router.post("/wards", status_code=status.HTTP_201_CREATED)
def add_ward(data: WardIn, request: Request, user: User = Depends(ward_admin), db: Session = Depends(get_db)):
    branch_id = data.branch_id or hospital_service.default_branch(db).id
    if db.get(Branch, branch_id) is None:
        raise HTTPException(422, "The selected branch does not exist.")
    if db.scalar(select(Ward.id).where(Ward.branch_id == branch_id, func.lower(Ward.name) == data.name.lower())):
        raise HTTPException(409, "A ward with this name already exists in the branch.")
    ward = Ward(branch_id=branch_id, name=data.name, ward_type=data.ward_type, is_active=True)
    db.add(ward)
    db.commit()
    audit_service.log_action(db, user, audit_service.HOSPITAL_CHANGED, "ward", ward.id, request, f"ward added: {ward.name}")
    return ipd.ward_summary(db, ward, with_patients=False)


@router.put("/wards/{ward_id}")
def update_ward(ward_id: PathId, data: WardUpdate, request: Request, user: User = Depends(ward_admin), db: Session = Depends(get_db)):
    ward = db.get(Ward, ward_id)
    if ward is None:
        raise HTTPException(404, "Ward not found.")
    if data.is_active is False and db.scalar(select(BedAssignment.id).join(Bed, Bed.id == BedAssignment.bed_id).where(Bed.ward_id == ward.id, BedAssignment.released_at.is_(None))):
        raise HTTPException(409, "This ward still has patients. Move them first.")
    if data.name:
        ward.name = data.name
    if data.is_active is not None:
        ward.is_active = data.is_active
    db.commit()
    audit_service.log_action(db, user, audit_service.HOSPITAL_CHANGED, "ward", ward.id, request, "ward changed")
    return ipd.ward_summary(db, ward, with_patients=False)


@router.post("/wards/{ward_id}/beds", status_code=status.HTTP_201_CREATED)
def add_bed(ward_id: PathId, data: BedIn, request: Request, user: User = Depends(ward_admin), db: Session = Depends(get_db)):
    ward = db.get(Ward, ward_id)
    if ward is None:
        raise HTTPException(404, "Ward not found.")
    code = data.code.upper().replace(" ", "")
    if db.scalar(select(Bed.id).where(Bed.ward_id == ward.id, func.upper(Bed.code) == code)):
        raise HTTPException(409, "This ward already has a bed with this code.")
    bed = Bed(ward_id=ward.id, code=code, status="AVAILABLE", is_active=True)
    db.add(bed)
    db.commit()
    audit_service.log_action(db, user, audit_service.HOSPITAL_CHANGED, "bed", bed.id, request, f"bed added: {ward.name} {code}")
    return {"id": bed.id, "code": bed.code, "status": bed.status}


@router.post("/beds/{bed_id}/status")
def set_bed_status(bed_id: PathId, data: BedStatusIn, request: Request, user: User = Depends(bed_perm), db: Session = Depends(get_db)):
    """Cleaning is finished (AVAILABLE), a bed goes to maintenance, or is reserved for a patient. A bed with a patient in it cannot be changed."""
    bed = db.get(Bed, bed_id)
    if bed is None:
        raise HTTPException(404, "Bed not found.")
    if ipd.bed_occupant(db, bed.id):
        raise HTTPException(409, "This bed has a patient in it.")
    if data.status == "RESERVED":
        if data.reserved_for_patient_id is None or db.get(Patient, data.reserved_for_patient_id) is None:
            raise HTTPException(422, "Please choose the patient the bed is reserved for.")
    bed.status = data.status
    bed.reserved_for_patient_id = data.reserved_for_patient_id if data.status == "RESERVED" else None
    db.commit()
    audit_service.log_action(db, user, audit_service.BED_ASSIGNED, "bed", bed.id, request, data.status)
    return {"id": bed.id, "status": bed.status}


# ------------------------------------------------------------------ admission
def _clinical_patient(db: Session, user: User, patient_id: int) -> Patient:
    return get_accessible_patient(db, user, patient_id, clinical=True)


def _admission(db: Session, admission_id: int) -> Admission:
    a = db.get(Admission, admission_id)
    if a is None:
        raise HTTPException(404, "Admission not found.")
    return a


def _doctor_of_admission(db: Session, user: User, admission: Admission) -> Doctor:
    """The doctor must be the attending or a consulting doctor of this stay."""
    doctor = get_doctor_profile(db, user)
    _clinical_patient(db, user, admission.patient_id)
    if admission.attending_doctor_id == doctor.id or admission.attending_doctor.supervisor_id == doctor.id:       # the attending doctor, or the consultant who supervises them
        return doctor
    if db.scalar(select(AdmissionStaff.id).where(AdmissionStaff.admission_id == admission.id, AdmissionStaff.user_id == user.id, AdmissionStaff.kind == "CONSULTING_DOCTOR", AdmissionStaff.to_at.is_(None))):
        return doctor
    raise forbidden()


def _treating_consultant(doctor: Doctor, admission: Admission) -> bool:
    """The attending doctor when they are a consultant, or the consultant who supervises a junior attending doctor."""
    if doctor.current_grade != "CONSULTANT":
        return False
    return admission.attending_doctor_id == doctor.id or admission.attending_doctor.supervisor_id == doctor.id


@router.post("/admissions", status_code=status.HTTP_201_CREATED)
def admit(data: AdmitIn, request: Request, user: User = Depends(admit_perm), db: Session = Depends(get_db)):
    """The admission decision of a doctor: an admission number, an inpatient visit, and (if a bed is given) the bed, all in one transaction."""
    patient = db.get(Patient, data.patient_id)
    if patient is None:
        raise HTTPException(404, "Patient not found.")
    if user.role == DOCTOR:
        me = get_doctor_profile(db, user)
        _clinical_patient(db, user, patient.id)
        doctor = db.get(Doctor, data.attending_doctor_id) if data.attending_doctor_id else (me.supervisor if me.current_grade == "INTERN" else me)
        if me.current_grade == "INTERN" and (doctor is None or doctor.is_junior):
            raise HTTPException(422, "An intern admits under a consultant. Please choose the attending consultant.")
    else:
        doctor = db.get(Doctor, data.attending_doctor_id) if data.attending_doctor_id else None
    if doctor is None or not doctor.user.is_active:
        raise HTTPException(422, "Please choose the attending doctor.")
    bed = None
    if data.bed_id:
        bed = db.get(Bed, data.bed_id)
        if bed is None:
            raise HTTPException(422, "The selected bed does not exist.")
    admission = ipd.admit(db, patient, doctor, data.department_id, data.diagnosis, data.source_encounter_id, data.expected_discharge, user)
    if bed is not None:
        ipd.assign_bed(db, admission, bed, user, "Admission")
    db.commit()
    audit_service.log_action(db, user, audit_service.ADMISSION_CREATED, "admission", admission.id, request, admission.admission_no)
    return ipd.admission_out(db, admission)


@router.get("/admissions")
def admissions(state: str = "ADMITTED", user: User = Depends(require_permission("ipd.bed", "ipd.admit", "ipd.notes", "nursing.chart")), db: Session = Depends(get_db)):
    """Inpatients. A doctor sees the stays they look after; a nurse sees all current inpatients; reception and ward staff see the list for the beds."""
    if state not in ("ADMITTED", "DISCHARGED"):
        raise HTTPException(422, "The state must be ADMITTED or DISCHARGED.")
    rows = list(db.scalars(select(Admission).where(Admission.status == state).order_by(Admission.admitted_at.desc()).limit(300)))
    if user.role == DOCTOR:
        from app.core.permissions import doctor_patient_ids
        ids = doctor_patient_ids(db, get_doctor_profile(db, user))
        rows = [a for a in rows if a.patient_id in ids]
    return [ipd.admission_out(db, a) for a in rows]


@router.get("/admissions/{admission_id}")
def admission_detail(admission_id: PathId, user: User = Depends(require_permission("ipd.bed", "ipd.admit", "ipd.notes", "nursing.chart")), db: Session = Depends(get_db)):
    a = _admission(db, admission_id)
    out = ipd.admission_out(db, a)
    try:
        _clinical_patient(db, user, a.patient_id)
    except HTTPException:
        if user.role in (DOCTOR, NURSE):
            raise                                                    # a clinician who is not on this case gets 403; reception and ward staff see the summary only
        return {"admission": out, "clinical": False}
    notes = db.scalars(select(ProgressNote).where(ProgressNote.admission_id == a.id).order_by(ProgressNote.id.desc())).all()
    meds = db.scalars(select(MedicationOrder).where(MedicationOrder.admission_id == a.id).order_by(MedicationOrder.id.desc())).all()
    orders = db.scalars(select(ClinicalOrder).where(ClinicalOrder.admission_id == a.id).order_by(ClinicalOrder.id.desc())).all()
    alerts = db.scalars(select(ClinicalAlert).where(ClinicalAlert.admission_id == a.id, ClinicalAlert.status == "OPEN")).all()
    summary = db.scalar(select(DischargeSummary).where(DischargeSummary.admission_id == a.id))
    return {"admission": out, "clinical": True,
            "progress_notes": [{"id": n.id, "note": n.note, "doctor": n.doctor.user.full_name, "created_at": n.created_at.isoformat(), "corrects_id": n.corrects_id} for n in notes],
            "medication_orders": [nursing_service.med_order_out(m) for m in meds],
            "orders": [{"id": o.id, "kind": o.kind, "text": o.text, "priority": o.priority, "status": o.status, "ordered_at": o.ordered_at.isoformat()} for o in orders],
            "alerts": [enc.alert_out(x) for x in alerts], "discharge_summary": ipd.summary_out(summary)}


@router.post("/admissions/{admission_id}/bed")
def assign_or_transfer(admission_id: PathId, data: BedAssignIn, request: Request, user: User = Depends(bed_perm), db: Session = Depends(get_db)):
    a = _admission(db, admission_id)
    bed = db.get(Bed, data.bed_id)
    if bed is None:
        raise HTTPException(404, "Bed not found.")
    ipd.assign_bed(db, a, bed, user, data.reason)
    db.commit()
    audit_service.log_action(db, user, audit_service.BED_ASSIGNED, "admission", a.id, request, f"{bed.ward.name} {bed.code}")
    return ipd.admission_out(db, a)


@router.get("/staff-options")
def staff_options(kind: str, user: User = Depends(admit_perm), db: Session = Depends(get_db)):
    """The people a doctor can add to a stay: consulting doctors or nurses (name and user id only)."""
    if kind not in ("CONSULTING_DOCTOR", "NURSE"):
        raise HTTPException(422, "The kind must be CONSULTING_DOCTOR or NURSE.")
    role = DOCTOR if kind == "CONSULTING_DOCTOR" else NURSE
    rows = db.scalars(select(User).where(User.role == role, User.is_active.is_(True)).order_by(User.full_name))
    return [{"user_id": u.id, "name": u.full_name} for u in rows if u.id != user.id]


@router.post("/admissions/{admission_id}/staff", status_code=status.HTTP_201_CREATED)
def assign_staff(admission_id: PathId, data: StaffAssignIn, request: Request, user: User = Depends(admit_perm), db: Session = Depends(get_db)):
    a = _admission(db, admission_id)
    if a.status != "ADMITTED":
        raise HTTPException(409, "This patient has been discharged.")
    target = db.get(User, data.user_id)
    if target is None or not target.is_active:
        raise HTTPException(404, "User not found.")
    if data.kind == "CONSULTING_DOCTOR" and target.role != DOCTOR:
        raise HTTPException(422, "A consulting doctor must be a doctor.")
    if data.kind == "NURSE" and target.role != NURSE:
        raise HTTPException(422, "Please choose a nurse.")
    if user.role == DOCTOR:
        _doctor_of_admission(db, user, a)
    if db.scalar(select(AdmissionStaff.id).where(AdmissionStaff.admission_id == a.id, AdmissionStaff.user_id == target.id, AdmissionStaff.kind == data.kind, AdmissionStaff.to_at.is_(None))):
        raise HTTPException(409, "This person is already assigned.")
    row = AdmissionStaff(admission_id=a.id, user_id=target.id, kind=data.kind, assigned_by=user.id)
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, audit_service.ADMISSION_CREATED, "admission", a.id, request, f"{data.kind}: {target.full_name}")
    return ipd.admission_out(db, a)


@router.post("/admissions/{admission_id}/staff/{staff_id}/end")
def end_staff(admission_id: PathId, staff_id: PathId, request: Request, user: User = Depends(admit_perm), db: Session = Depends(get_db)):
    row = db.get(AdmissionStaff, staff_id)
    if row is None or row.admission_id != admission_id:
        raise HTTPException(404, "Assignment not found.")
    row.to_at = row.to_at or ipd.now()
    db.commit()
    audit_service.log_action(db, user, "STAFF_ASSIGNMENT_ENDED", "admission", admission_id, request, f"assignment {staff_id}")
    return ipd.admission_out(db, _admission(db, admission_id))


# ------------------------------------------------------------------ notes, medicines, orders
@router.post("/admissions/{admission_id}/notes", status_code=status.HTTP_201_CREATED)
def progress_note(admission_id: PathId, data: ProgressNoteIn, request: Request, user: User = Depends(notes_perm), db: Session = Depends(get_db)):
    """A daily progress note. It is never edited: a correction is a new note that points to the old one."""
    a = _admission(db, admission_id)
    doctor = _doctor_of_admission(db, user, a)
    if a.status != "ADMITTED":
        raise HTTPException(409, "This patient has been discharged. Please add the correction to the discharge summary.")
    if data.corrects_id:
        old = db.get(ProgressNote, data.corrects_id)
        if old is None or old.admission_id != a.id:
            raise HTTPException(422, "The note to correct does not exist.")
    row = ProgressNote(admission_id=a.id, patient_id=a.patient_id, doctor_id=doctor.id, note=data.note, corrects_id=data.corrects_id)
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, audit_service.PROGRESS_NOTE_ADDED, "admission", a.id, request)
    return {"id": row.id, "note": row.note, "created_at": row.created_at.isoformat(), "corrects_id": row.corrects_id}


@router.post("/admissions/{admission_id}/medication-orders", status_code=status.HTTP_201_CREATED)
def medication_order(admission_id: PathId, data: MedicationOrderIn, request: Request, user: User = Depends(notes_perm), db: Session = Depends(get_db)):
    a = _admission(db, admission_id)
    doctor = _doctor_of_admission(db, user, a)
    if doctor.current_grade == "INTERN":
        raise HTTPException(403, "An intern cannot order medicines. Please ask your consultant.")
    if a.status != "ADMITTED":
        raise HTTPException(409, "This patient has been discharged.")
    start = data.start_date or hospital_today()
    if start < hospital_today():
        raise HTTPException(422, "The start date cannot be in the past.")
    if data.end_date and data.end_date < start:
        raise HTTPException(422, "The end date cannot be before the start date.")
    row = MedicationOrder(admission_id=a.id, patient_id=a.patient_id, medicine_name=data.medicine_name, dose=data.dose, route=data.route, times=",".join(sorted(data.times)),
                          instructions=data.instructions, start_date=start, end_date=data.end_date, status="ACTIVE", ordered_by=doctor.id)
    db.add(row)
    db.flush()
    nursing_service.generate_mar(db, a, hospital_today())
    db.commit()
    audit_service.log_action(db, user, audit_service.MEDICATION_ORDERED, "admission", a.id, request, data.medicine_name[:100])
    return nursing_service.med_order_out(row)


@router.post("/medication-orders/{order_id}/stop")
def stop_medication(order_id: PathId, request: Request, user: User = Depends(notes_perm), db: Session = Depends(get_db)):
    row = db.get(MedicationOrder, order_id)
    if row is None:
        raise HTTPException(404, "Medication order not found.")
    doctor = _doctor_of_admission(db, user, _admission(db, row.admission_id))
    if row.status == "ACTIVE":
        row.status, row.stopped_by, row.stopped_at = "STOPPED", doctor.id, ipd.now()
        db.commit()
        audit_service.log_action(db, user, audit_service.MEDICATION_ORDERED, "admission", row.admission_id, request, f"stopped {row.medicine_name[:80]}")
    return nursing_service.med_order_out(row)


@router.post("/admissions/{admission_id}/orders", status_code=status.HTTP_201_CREATED)
def admission_order(admission_id: PathId, data: OrderIn, request: Request, user: User = Depends(require_permission("orders.write")), db: Session = Depends(get_db)):
    a = _admission(db, admission_id)
    _doctor_of_admission(db, user, a)
    if a.status != "ADMITTED":
        raise HTTPException(409, "This patient has been discharged.")
    doctor = get_doctor_profile(db, user)
    row = ClinicalOrder(encounter_id=a.encounter_id, patient_id=a.patient_id, admission_id=a.id, kind=data.kind, text=data.text, priority=data.priority, ordered_by=user.id,
                        status=grade_service.order_status(doctor))
    db.add(row)
    db.flush()
    if row.status == "DRAFT":
        grade_service.request_countersign(db, "ORDER", row.id, a.patient_id, doctor, f"{data.kind.title()} order: {data.text}")
    db.commit()
    audit_service.log_action(db, user, audit_service.ORDER_PLACED, "clinical_order", row.id, request, f"{data.kind} {data.priority}")
    return {"id": row.id, "kind": row.kind, "text": row.text, "priority": row.priority, "status": row.status}


# ------------------------------------------------------------------ discharge
@router.put("/admissions/{admission_id}/discharge-summary")
def save_summary(admission_id: PathId, data: DischargeSummaryIn, request: Request, user: User = Depends(require_permission("discharge.write")), db: Session = Depends(get_db)):
    a = _admission(db, admission_id)
    doctor = _doctor_of_admission(db, user, a)
    if doctor.current_grade == "INTERN":
        raise HTTPException(403, "An intern does not prepare the discharge summary.")
    summary = db.scalar(select(DischargeSummary).where(DischargeSummary.admission_id == a.id))
    if summary is None:
        summary = DischargeSummary(admission_id=a.id, status="DRAFT", prepared_by=doctor.id)
        db.add(summary)
    if summary.status == "APPROVED":
        raise HTTPException(409, "This discharge summary has been approved and cannot be changed.")
    for key, value in data.model_dump().items():
        setattr(summary, key, value)
    summary.updated_at = ipd.now()
    db.flush()
    if doctor.is_junior:                                        # a resident prepares it; the consultant approves it
        grade_service.request_countersign(db, "DISCHARGE_SUMMARY", summary.id, a.patient_id, doctor, f"Discharge summary of {a.admission_no}")
    db.commit()
    audit_service.log_action(db, user, "DISCHARGE_SUMMARY_SAVED", "admission", a.id, request, summary.status)
    return ipd.summary_out(summary)


@router.post("/admissions/{admission_id}/discharge-summary/approve")
def approve_summary(admission_id: PathId, request: Request, user: User = Depends(require_permission("discharge.approve")), db: Session = Depends(get_db)):
    """Only the treating (attending) doctor approves the summary."""
    a = _admission(db, admission_id)
    doctor = get_doctor_profile(db, user)
    if not _treating_consultant(doctor, a):
        raise HTTPException(403, "Only the treating consultant of this patient can approve the discharge summary.")
    summary = db.scalar(select(DischargeSummary).where(DischargeSummary.admission_id == a.id))
    if summary is None:
        raise HTTPException(409, "There is no discharge summary yet.")
    missing = [label for label, value in (("the final diagnosis", summary.final_diagnosis), ("the hospital course", summary.hospital_course), ("the follow-up", summary.follow_up)) if not (value or "").strip()]
    if missing:
        raise HTTPException(422, "Before approving, please write " + ", ".join(missing) + ".")
    if summary.status != "APPROVED":
        summary.status, summary.approved_by, summary.approved_at = "APPROVED", doctor.id, ipd.now()
        db.commit()
        audit_service.log_action(db, user, audit_service.DISCHARGE_APPROVED, "admission", a.id, request)
    return ipd.summary_out(summary)


@router.post("/admissions/{admission_id}/discharge")
def discharge(admission_id: PathId, data: DischargeIn, request: Request, user: User = Depends(require_permission("discharge.approve")), db: Session = Depends(get_db)):
    a = _admission(db, admission_id)
    doctor = _doctor_of_admission(db, user, a)
    if not _treating_consultant(doctor, a):
        raise HTTPException(403, "Only the treating consultant of this patient can discharge the patient.")
    result = ipd.discharge(db, a, data.discharge_type, data.note, user)
    audit_service.log_action(db, user, audit_service.PATIENT_DISCHARGED, "admission", a.id, request, data.discharge_type)
    return {**result, "admission": ipd.admission_out(db, a)}
