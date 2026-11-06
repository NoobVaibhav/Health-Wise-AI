"""The detailed past medical history: long-term illnesses, regular medicines, hospital admissions and operations.

Rules this module keeps:
- nothing is invented: unknown stays empty and is shown as "Not recorded";
- nothing is destroyed: "delete" hides a record (is_deleted) and every change stores the earlier version in HistoryRevision;
- every record says where it came from (told by the patient / checked by a doctor / hospital record / entered earlier) and who verified it;
- the length of a hospital stay is calculated only from a real admission AND discharge time."""
import json
import re
from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    ChronicCondition, Doctor, HistoryRevision, HospitalAdmission, Patient, PatientHistory, PatientMedication, SurgeryRecord, User, utcnow,
)
from app.schemas.past_history import (
    COMPLICATION_LABELS, DIABETES_COMPLICATIONS, HYPERTENSION_COMPLICATIONS, AdmissionIn, ConditionIn, PastMedicationIn, SurgeryIn,
)
from app.utils.clock import hospital_today

SOURCE_LABELS = {"PATIENT_REPORTED": "Told by the patient", "DOCTOR_VERIFIED": "Checked by a doctor", "HOSPITAL_RECORD": "From a hospital record",
                 "EARLIER_ENTRY": "Entered earlier (source not recorded)"}
STANDARD_NAMES = {"DIABETES": "Diabetes mellitus", "HYPERTENSION": "Hypertension"}
NOT_DELETED = lambda col: col.is_not(True)           # NULL (old rows) counts as "not deleted"


def not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found.")


# ------------------------------------------------------------------ change log
def _log(db: Session, patient_id: int, entity: str, entity_id: int, action: str, before: dict | None, user: User | None) -> None:
    db.add(HistoryRevision(patient_id=patient_id, entity_type=entity, entity_id=entity_id, action=action,
                           before_json=json.dumps(before, default=str) if before is not None else None, changed_by=user.id if user else None))


def _doctor_name(db: Session, doctor_id: int | None) -> str | None:
    doctor = db.get(Doctor, doctor_id) if doctor_id else None
    return doctor.user.full_name if doctor else None


def _verification(db: Session, row) -> dict:
    return {"source": row.source, "source_label": SOURCE_LABELS.get(row.source, row.source), "verified": row.verified_at is not None,
            "verified_by_name": _doctor_name(db, row.verified_by), "verified_at": row.verified_at.isoformat() if row.verified_at else None}


def _stamp(row, user: User, doctor: Doctor | None, source: str) -> None:
    """Set the source of a record. 'Checked by a doctor' also records which doctor and when."""
    row.source = source
    row.updated_by, row.updated_at = user.id, utcnow()
    if source == "DOCTOR_VERIFIED" and doctor is not None:
        row.verified_by, row.verified_at = doctor.id, utcnow()
    elif source != "DOCTOR_VERIFIED":
        row.verified_by, row.verified_at = None, None


# ------------------------------------------------------------------ length of stay
def length_of_stay(admitted: datetime | None, discharged: datetime | None) -> dict | None:
    """Worked out only when both times exist. Returns days/hours/minutes and a sentence; None when it cannot be known."""
    if not admitted or not discharged or discharged < admitted:
        return None
    minutes = int((discharged - admitted).total_seconds() // 60)
    days, rest = divmod(minutes, 1440)
    hours, mins = divmod(rest, 60)
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if not days and mins:
        parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
    return {"days": days, "hours": hours, "minutes": mins, "text": " ".join(parts) or "less than a minute"}


# ------------------------------------------------------------------ conditions
def classify(name: str) -> str:
    n = name.lower().strip()
    if "diabet" in n:
        return "DIABETES"
    if "hypertens" in n or "high blood pressure" in n or n in ("bp", "htn", "high bp"):
        return "HYPERTENSION"
    return "OTHER"


def _condition_dict(db: Session, c: ChronicCondition, meds: list[dict] | None = None) -> dict:
    details = json.loads(c.details_json) if c.details_json else {}
    allowed = {"DIABETES": DIABETES_COMPLICATIONS, "HYPERTENSION": HYPERTENSION_COMPLICATIONS}.get(c.kind, ())
    answers = details.get("complications", {})
    years = hospital_today().year - c.diagnosis_year if c.diagnosis_year else None
    return {
        "id": c.id, "kind": c.kind, "name": c.name, "diagnosis_type": c.diagnosis_type, "duration_text": c.duration_text, "diagnosis_year": c.diagnosis_year,
        "years_since_diagnosis": years if years is not None and years >= 0 else None,       # calculated from the year, labelled as such on screen
        "control_status": c.control_status, "on_treatment": c.on_treatment, "control": details.get("control", {}),
        "complications": {k: answers.get(k, "UNKNOWN") for k in allowed} if allowed else answers,
        "complications_present": [COMPLICATION_LABELS.get(k, k) for k, v in answers.items() if v == "YES"],
        "complications_other": details.get("complications_other"), "hospitalisation": details.get("hospitalisation", {"happened": "UNKNOWN"}),
        "other_details": details.get("other_details"), "notes": c.notes, "medications": meds or [],
        "created_at": c.created_at.isoformat() if c.created_at else None, "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        **_verification(db, c),
    }


def _condition_snapshot(c: ChronicCondition) -> dict:
    return {k: getattr(c, k) for k in ("kind", "name", "diagnosis_type", "duration_text", "diagnosis_year", "control_status", "on_treatment", "details_json", "notes", "source", "verified_by", "verified_at", "is_deleted")}


def _apply_condition(c: ChronicCondition, data: ConditionIn) -> None:
    c.kind = data.kind
    c.name = (data.name or "").strip() or STANDARD_NAMES.get(data.kind, "")
    c.diagnosis_type, c.duration_text, c.diagnosis_year = data.diagnosis_type, data.duration_text, data.diagnosis_year
    c.control_status, c.on_treatment, c.notes = data.control_status, data.on_treatment, data.notes
    c.details_json = json.dumps({"control": data.control.model_dump(exclude_none=True), "complications": data.complications,
                                 "complications_other": data.complications_other, "hospitalisation": data.hospitalisation.model_dump(),
                                 "other_details": data.other_details})


def create_condition(db: Session, patient: Patient, data: ConditionIn, user: User, doctor: Doctor | None) -> ChronicCondition:
    ensure_migrated(db, patient)                                       # earlier entries become records first, so nothing is entered twice
    if data.kind in STANDARD_NAMES:                                    # one diabetes and one hypertension record per patient
        exists = db.scalar(select(ChronicCondition.id).where(ChronicCondition.patient_id == patient.id, ChronicCondition.kind == data.kind, NOT_DELETED(ChronicCondition.is_deleted)))
        if exists:
            raise HTTPException(status.HTTP_409_CONFLICT, f"{STANDARD_NAMES[data.kind]} is already recorded. Please edit that record.")
    row = ChronicCondition(patient_id=patient.id, created_by=user.id)
    _apply_condition(row, data)
    _stamp(row, user, doctor, data.source)
    db.add(row)
    db.flush()
    _log(db, patient.id, "condition", row.id, "CREATE", None, user)
    db.commit()
    return row


def get_condition(db: Session, patient: Patient, condition_id: int) -> ChronicCondition:
    row = db.get(ChronicCondition, condition_id)
    if row is None or row.patient_id != patient.id or row.is_deleted:
        raise not_found("Illness record")
    return row


def update_condition(db: Session, patient: Patient, condition_id: int, data: ConditionIn, user: User, doctor: Doctor | None) -> ChronicCondition:
    row = get_condition(db, patient, condition_id)
    if row.kind in STANDARD_NAMES and data.kind != row.kind:
        raise HTTPException(422, "The type of an illness record cannot be changed.")
    _log(db, patient.id, "condition", row.id, "UPDATE", _condition_snapshot(row), user)
    _apply_condition(row, data)
    _stamp(row, user, doctor, data.source)
    db.commit()
    return row


def delete_condition(db: Session, patient: Patient, condition_id: int, user: User) -> None:
    row = get_condition(db, patient, condition_id)
    _log(db, patient.id, "condition", row.id, "DELETE", _condition_snapshot(row), user)
    row.is_deleted, row.updated_by, row.updated_at = True, user.id, utcnow()
    for med in db.scalars(select(PatientMedication).where(PatientMedication.condition_id == row.id)):
        med.condition_id = None                                        # the medicine stays in the list, just no longer linked
    db.commit()


# ------------------------------------------------------------------ medicines
def medication_dict(db: Session, m: PatientMedication) -> dict:
    return {"id": m.id, "name": m.name, "dose": m.dose, "frequency": m.frequency, "route": m.route, "reason": m.reason, "since": m.since, "notes": m.notes,
            "prescriber": m.prescriber, "adherence": m.adherence, "condition_id": m.condition_id, "is_current": bool(m.is_current),
            **({"source": m.source, "source_label": SOURCE_LABELS.get(m.source, m.source), "verified": m.verified_at is not None,
                "verified_by_name": _doctor_name(db, m.verified_by)} if m.source else
               {"source": "EARLIER_ENTRY", "source_label": SOURCE_LABELS["EARLIER_ENTRY"], "verified": False, "verified_by_name": None})}


def _med_snapshot(m: PatientMedication) -> dict:
    return {k: getattr(m, k) for k in ("name", "dose", "frequency", "route", "reason", "since", "notes", "prescriber", "adherence", "condition_id", "is_current", "source", "is_deleted")}


def active_medications(db: Session, patient: Patient) -> list[PatientMedication]:
    return list(db.scalars(select(PatientMedication).where(PatientMedication.patient_id == patient.id, NOT_DELETED(PatientMedication.is_deleted)).order_by(PatientMedication.id)))


def _check_condition_link(db: Session, patient: Patient, condition_id: int | None) -> None:
    if condition_id is not None:
        c = db.get(ChronicCondition, condition_id)
        if c is None or c.patient_id != patient.id or c.is_deleted:
            raise HTTPException(422, "The illness this medicine is linked to was not found for this patient.")


def create_medication(db: Session, patient: Patient, data: PastMedicationIn, user: User, doctor: Doctor | None) -> PatientMedication:
    _check_condition_link(db, patient, data.condition_id)
    row = PatientMedication(patient_id=patient.id, updated_at=utcnow())
    _apply_med(row, data)
    _stamp(row, user, doctor, data.source)
    db.add(row)
    db.flush()
    _log(db, patient.id, "medication", row.id, "CREATE", None, user)
    db.commit()
    return row


def _apply_med(row: PatientMedication, data: PastMedicationIn) -> None:
    for key in ("name", "dose", "frequency", "route", "since", "prescriber", "adherence", "reason", "notes", "condition_id", "is_current"):
        setattr(row, key, getattr(data, key))


def get_medication(db: Session, patient: Patient, medication_id: int) -> PatientMedication:
    row = db.get(PatientMedication, medication_id)
    if row is None or row.patient_id != patient.id or row.is_deleted:
        raise not_found("Medicine record")
    return row


def update_medication(db: Session, patient: Patient, medication_id: int, data: PastMedicationIn, user: User, doctor: Doctor | None) -> PatientMedication:
    row = get_medication(db, patient, medication_id)
    _check_condition_link(db, patient, data.condition_id)
    _log(db, patient.id, "medication", row.id, "UPDATE", _med_snapshot(row), user)
    _apply_med(row, data)
    row.updated_at = utcnow()
    _stamp(row, user, doctor, data.source)
    db.commit()
    return row


def delete_medication(db: Session, patient: Patient, medication_id: int, user: User) -> None:
    row = get_medication(db, patient, medication_id)
    _log(db, patient.id, "medication", row.id, "DELETE", _med_snapshot(row), user)
    row.is_deleted, row.updated_at = True, utcnow()
    db.commit()


# ------------------------------------------------------------------ admissions
LIST_FIELDS = ("medications", "discharge_medications")
ADMISSION_TEXT = ("hospital_name", "admitted_at", "admitted_date_text", "discharged_at", "admission_type", "main_complaint", "secondary_complaints", "provisional_diagnosis",
                  "final_diagnosis", "reason", "referred_by", "symptoms", "history_of_present_illness", "preexisting_conditions", "exam_findings", "investigations", "complications",
                  "treatment_given", "iv_fluids_oxygen", "procedures_supportive", "medication_changes", "response_to_treatment", "stay_complications", "discharge_condition",
                  "treatment_completed", "discharge_instructions", "wound_rehab_instructions", "followup_date", "specialist_review", "recovery_status", "remaining_symptoms", "readmission_notes")


def _surgery_dict(db: Session, s: SurgeryRecord) -> dict:
    return {"id": s.id, "admission_id": s.admission_id, "procedure_name": s.procedure_name, "reason": s.reason, "body_site": s.body_site,
            "operation_date": s.operation_date.isoformat() if s.operation_date else None, "operation_year": s.operation_year, "surgeon": s.surgeon, "hospital": s.hospital,
            "anesthesia": s.anesthesia, "findings": s.findings, "implant_used": s.implant_used, "implant_type": s.implant_type, "implant_material": s.implant_material,
            "implant_serial": s.implant_serial, "postop_xray": s.postop_xray, "postop_treatment": s.postop_treatment, "postop_complications": s.postop_complications,
            "recovery_progress": s.recovery_progress, **_verification(db, s)}


def _admission_dict(db: Session, a: HospitalAdmission) -> dict:
    out = {k: (getattr(a, k).isoformat() if isinstance(getattr(a, k), (date, datetime)) else getattr(a, k)) for k in ADMISSION_TEXT}
    out.update({"id": a.id, "vitals": json.loads(a.vitals_json) if a.vitals_json else {}, "medications": json.loads(a.medications_json) if a.medications_json else [],
                "discharge_medications": json.loads(a.discharge_medications_json) if a.discharge_medications_json else [],
                "length_of_stay": length_of_stay(a.admitted_at, a.discharged_at),
                "surgeries": [_surgery_dict(db, s) for s in a.surgeries if not s.is_deleted], "updated_at": a.updated_at.isoformat() if a.updated_at else None, **_verification(db, a)})
    return out


def _admission_snapshot(a: HospitalAdmission) -> dict:
    snap = {k: getattr(a, k) for k in (*ADMISSION_TEXT, "vitals_json", "medications_json", "discharge_medications_json", "source", "verified_by", "verified_at", "is_deleted")}
    return snap


def _apply_admission(a: HospitalAdmission, data: AdmissionIn) -> None:
    for key in ADMISSION_TEXT:
        setattr(a, key, getattr(data, key))
    a.vitals_json = json.dumps(data.vitals.model_dump(exclude_none=True)) if data.vitals.model_dump(exclude_none=True) else None
    a.medications_json = json.dumps([m.model_dump(exclude_none=True) for m in data.medications]) if data.medications else None
    a.discharge_medications_json = json.dumps([m.model_dump(exclude_none=True) for m in data.discharge_medications]) if data.discharge_medications else None


def create_admission(db: Session, patient: Patient, data: AdmissionIn, user: User, doctor: Doctor | None) -> HospitalAdmission:
    if not any([data.main_complaint, data.reason, data.final_diagnosis, data.provisional_diagnosis, data.hospital_name, data.admitted_at, data.admitted_date_text]):
        raise HTTPException(422, "Please record at least the reason, the diagnosis, the hospital or the date of the admission.")
    row = HospitalAdmission(patient_id=patient.id, created_by=user.id)
    _apply_admission(row, data)
    _stamp(row, user, doctor, data.source)
    db.add(row)
    db.flush()
    _log(db, patient.id, "admission", row.id, "CREATE", None, user)
    db.commit()
    return row


def get_admission(db: Session, patient: Patient, admission_id: int) -> HospitalAdmission:
    row = db.get(HospitalAdmission, admission_id)
    if row is None or row.patient_id != patient.id or row.is_deleted:
        raise not_found("Admission record")
    return row


def update_admission(db: Session, patient: Patient, admission_id: int, data: AdmissionIn, user: User, doctor: Doctor | None) -> HospitalAdmission:
    row = get_admission(db, patient, admission_id)
    _log(db, patient.id, "admission", row.id, "UPDATE", _admission_snapshot(row), user)
    _apply_admission(row, data)
    _stamp(row, user, doctor, data.source)
    db.commit()
    return row


def delete_admission(db: Session, patient: Patient, admission_id: int, user: User) -> None:
    row = get_admission(db, patient, admission_id)
    _log(db, patient.id, "admission", row.id, "DELETE", _admission_snapshot(row), user)
    row.is_deleted, row.updated_by, row.updated_at = True, user.id, utcnow()
    for s in row.surgeries:                                           # an operation belonging to the hidden admission is hidden with it
        if not s.is_deleted:
            _log(db, patient.id, "surgery", s.id, "DELETE", _surgery_snapshot(s), user)
            s.is_deleted, s.updated_at = True, utcnow()
    db.commit()


# ------------------------------------------------------------------ surgeries
SURGERY_FIELDS = ("procedure_name", "reason", "body_site", "operation_date", "operation_year", "surgeon", "hospital", "anesthesia", "findings", "implant_used", "implant_type",
                  "implant_material", "implant_serial", "postop_xray", "postop_treatment", "postop_complications", "recovery_progress")


def _surgery_snapshot(s: SurgeryRecord) -> dict:
    return {k: getattr(s, k) for k in (*SURGERY_FIELDS, "admission_id", "source", "verified_by", "verified_at", "is_deleted")}


def _check_admission_link(db: Session, patient: Patient, admission_id: int | None) -> None:
    if admission_id is not None:
        a = db.get(HospitalAdmission, admission_id)
        if a is None or a.patient_id != patient.id or a.is_deleted:
            raise HTTPException(422, "The admission this operation is linked to was not found for this patient.")


def create_surgery(db: Session, patient: Patient, data: SurgeryIn, user: User, doctor: Doctor | None) -> SurgeryRecord:
    _check_admission_link(db, patient, data.admission_id)
    row = SurgeryRecord(patient_id=patient.id, created_by=user.id, admission_id=data.admission_id)
    for key in SURGERY_FIELDS:
        setattr(row, key, getattr(data, key))
    _stamp(row, user, doctor, data.source)
    db.add(row)
    db.flush()
    _log(db, patient.id, "surgery", row.id, "CREATE", None, user)
    db.commit()
    return row


def get_surgery(db: Session, patient: Patient, surgery_id: int) -> SurgeryRecord:
    row = db.get(SurgeryRecord, surgery_id)
    if row is None or row.patient_id != patient.id or row.is_deleted:
        raise not_found("Operation record")
    return row


def update_surgery(db: Session, patient: Patient, surgery_id: int, data: SurgeryIn, user: User, doctor: Doctor | None) -> SurgeryRecord:
    row = get_surgery(db, patient, surgery_id)
    _check_admission_link(db, patient, data.admission_id)
    _log(db, patient.id, "surgery", row.id, "UPDATE", _surgery_snapshot(row), user)
    row.admission_id = data.admission_id
    for key in SURGERY_FIELDS:
        setattr(row, key, getattr(data, key))
    _stamp(row, user, doctor, data.source)
    db.commit()
    return row


def delete_surgery(db: Session, patient: Patient, surgery_id: int, user: User) -> None:
    row = get_surgery(db, patient, surgery_id)
    _log(db, patient.id, "surgery", row.id, "DELETE", _surgery_snapshot(row), user)
    row.is_deleted, row.updated_at = True, utcnow()
    db.commit()


# ------------------------------------------------------------------ verification (a doctor confirms what the patient said)
def verify(db: Session, patient: Patient, entity: str, entity_id: int, user: User, doctor: Doctor) -> None:
    getter = {"condition": get_condition, "admission": get_admission, "surgery": get_surgery, "medication": get_medication}.get(entity)
    if getter is None:
        raise not_found("Record")
    row = getter(db, patient, entity_id)
    before = {"source": row.source, "verified_by": row.verified_by, "verified_at": row.verified_at}
    _log(db, patient.id, entity, row.id, "VERIFY", before, user)
    row.source, row.verified_by, row.verified_at = "DOCTOR_VERIFIED", doctor.id, utcnow()
    db.commit()


# ------------------------------------------------------------------ the whole picture
def detailed(db: Session, patient: Patient) -> dict:
    """Everything of the detailed history, ready for the screens and the printed sheet."""
    ensure_migrated(db, patient)
    meds = active_medications(db, patient)
    med_out = [medication_dict(db, m) for m in meds]
    by_condition: dict[int, list[dict]] = {}
    for m in med_out:
        if m["condition_id"]:
            by_condition.setdefault(m["condition_id"], []).append(m)
    conditions = [_condition_dict(db, c, by_condition.get(c.id)) for c in db.scalars(
        select(ChronicCondition).where(ChronicCondition.patient_id == patient.id, NOT_DELETED(ChronicCondition.is_deleted)).order_by(ChronicCondition.id))]
    admissions = [_admission_dict(db, a) for a in db.scalars(
        select(HospitalAdmission).where(HospitalAdmission.patient_id == patient.id, NOT_DELETED(HospitalAdmission.is_deleted))
        .order_by(HospitalAdmission.admitted_at.desc(), HospitalAdmission.id.desc()))]
    standalone = [_surgery_dict(db, s) for s in db.scalars(
        select(SurgeryRecord).where(SurgeryRecord.patient_id == patient.id, SurgeryRecord.admission_id.is_(None), NOT_DELETED(SurgeryRecord.is_deleted))
        .order_by(SurgeryRecord.operation_date.desc(), SurgeryRecord.operation_year.desc(), SurgeryRecord.id.desc()))]
    # undated admissions go last; the rest newest first
    dated = sorted([a for a in admissions if a["admitted_at"]], key=lambda a: a["admitted_at"], reverse=True)
    admissions = dated + [a for a in admissions if not a["admitted_at"]]
    return {
        "diabetes": next((c for c in conditions if c["kind"] == "DIABETES"), None),
        "hypertension": next((c for c in conditions if c["kind"] == "HYPERTENSION"), None),
        "other_conditions": [c for c in conditions if c["kind"] == "OTHER"],
        "medications": med_out, "unlinked_medications": [m for m in med_out if not m["condition_id"]],
        "admissions": admissions, "standalone_surgeries": standalone,
        "counts": {"conditions": len(conditions), "medications": len(med_out), "admissions": len(admissions),
                   "surgeries": len(standalone) + sum(len(a["surgeries"]) for a in admissions)},
        "unverified": sum(1 for x in [*conditions, *med_out, *admissions, *standalone, *[s for a in admissions for s in a["surgeries"]]] if not x["verified"]),
    }


def revisions(db: Session, patient: Patient, limit: int = 100) -> list[dict]:
    rows = db.scalars(select(HistoryRevision).where(HistoryRevision.patient_id == patient.id).order_by(HistoryRevision.id.desc()).limit(limit)).all()
    out = []
    for r in rows:
        who = db.get(User, r.changed_by) if r.changed_by else None
        out.append({"id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id, "action": r.action, "changed_at": r.changed_at.isoformat(),
                    "changed_by": who.full_name if who else None, "before": json.loads(r.before_json) if r.before_json else None})
    return out


# ------------------------------------------------------------------ records written before these screens existed
def ensure_migrated(db: Session, patient: Patient) -> None:
    """The earlier history kept illnesses and operations as short lists. They are copied (once) into the new records, labelled
    'entered earlier', and the earlier lists are left untouched."""
    done = db.scalar(select(HistoryRevision.id).where(HistoryRevision.patient_id == patient.id, HistoryRevision.entity_type == "patient", HistoryRevision.action == "MIGRATE"))
    if done:
        return
    row = db.scalar(select(PatientHistory).where(PatientHistory.patient_id == patient.id))
    stored = json.loads(row.data_json) if row and row.data_json else {}
    for item in stored.get("conditions", []):
        name = (item.get("name") or "").strip()
        if not name:
            continue
        since = (item.get("since") or "").strip()
        year = int(since) if re.fullmatch(r"(19|20)\d\d", since) and int(since) <= hospital_today().year else None
        kind = classify(name)
        c = ChronicCondition(patient_id=patient.id, kind=kind, name=STANDARD_NAMES.get(kind, name) if kind != "OTHER" else name,
                             diagnosis_year=year, duration_text=None if year else (since or None), on_treatment=item.get("on_treatment"), notes=item.get("notes"),
                             source="EARLIER_ENTRY", is_deleted=False)
        if kind != "OTHER" and db.scalar(select(ChronicCondition.id).where(ChronicCondition.patient_id == patient.id, ChronicCondition.kind == kind, NOT_DELETED(ChronicCondition.is_deleted))):
            c.kind, c.name = "OTHER", name                              # a second diabetes/hypertension entry stays visible as an ordinary illness
        db.add(c)
        db.flush()
        _log(db, patient.id, "condition", c.id, "MIGRATE", None, None)
    for item in stored.get("surgeries", []):
        what = (item.get("what") or "").strip()
        if not what:
            continue
        year = (item.get("year") or "").strip()
        s = SurgeryRecord(patient_id=patient.id, procedure_name=what, operation_year=int(year) if re.fullmatch(r"(19|20)\d\d", year) and int(year) <= hospital_today().year else None,
                          hospital=item.get("hospital"), source="EARLIER_ENTRY", is_deleted=False)
        db.add(s)
        db.flush()
        _log(db, patient.id, "surgery", s.id, "MIGRATE", None, None)
    db.add(HistoryRevision(patient_id=patient.id, entity_type="patient", entity_id=patient.id, action="MIGRATE", before_json=None, changed_by=None))
    db.commit()


# ------------------------------------------------------------------ the earlier one-form screens still work: they read and write through the new records
def legacy_conditions(db: Session, patient: Patient) -> list[dict]:
    ensure_migrated(db, patient)
    rows = db.scalars(select(ChronicCondition).where(ChronicCondition.patient_id == patient.id, NOT_DELETED(ChronicCondition.is_deleted)).order_by(ChronicCondition.id))
    return [{"name": c.name, "since": str(c.diagnosis_year) if c.diagnosis_year else c.duration_text, "on_treatment": bool(c.on_treatment), "notes": c.notes} for c in rows]


def legacy_surgeries(db: Session, patient: Patient) -> list[dict]:
    ensure_migrated(db, patient)
    rows = db.scalars(select(SurgeryRecord).where(SurgeryRecord.patient_id == patient.id, NOT_DELETED(SurgeryRecord.is_deleted)).order_by(SurgeryRecord.id))
    return [{"what": s.procedure_name, "year": str(s.operation_date.year if s.operation_date else s.operation_year) if (s.operation_date or s.operation_year) else None, "hospital": s.hospital} for s in rows]


def sync_conditions(db: Session, patient: Patient, items: list[dict], none_known: bool, user: User) -> None:
    """Make the records match the list sent by the one-form screen. An empty list that is not marked 'none known' means 'not touched'."""
    ensure_migrated(db, patient)
    if not items and not none_known:
        return
    wanted = {i["name"].strip().lower(): i for i in items}
    for c in db.scalars(select(ChronicCondition).where(ChronicCondition.patient_id == patient.id, NOT_DELETED(ChronicCondition.is_deleted))):
        item = wanted.pop(c.name.strip().lower(), None)
        if item is None:
            _log(db, patient.id, "condition", c.id, "DELETE", _condition_snapshot(c), user)
            c.is_deleted, c.updated_by, c.updated_at = True, user.id, utcnow()
            continue
        since = (item.get("since") or "").strip()
        new = {"on_treatment": bool(item.get("on_treatment")), "notes": item.get("notes")}
        if new["on_treatment"] != bool(c.on_treatment) or new["notes"] != c.notes or (since and since != (str(c.diagnosis_year) if c.diagnosis_year else c.duration_text)):
            _log(db, patient.id, "condition", c.id, "UPDATE", _condition_snapshot(c), user)
            c.on_treatment, c.notes = new["on_treatment"], new["notes"]
            if since:
                c.diagnosis_year, c.duration_text = (int(since), None) if re.fullmatch(r"(19|20)\d\d", since) else (None, since)
            c.updated_by, c.updated_at = user.id, utcnow()
    for item in wanted.values():
        since = (item.get("since") or "").strip()
        kind = classify(item["name"])
        if kind != "OTHER" and db.scalar(select(ChronicCondition.id).where(ChronicCondition.patient_id == patient.id, ChronicCondition.kind == kind, NOT_DELETED(ChronicCondition.is_deleted))):
            kind = "OTHER"
        c = ChronicCondition(patient_id=patient.id, kind=kind, name=STANDARD_NAMES.get(kind, item["name"].strip()) if kind != "OTHER" else item["name"].strip(), on_treatment=bool(item.get("on_treatment")),
                             notes=item.get("notes"), source="PATIENT_REPORTED", created_by=user.id, updated_by=user.id, is_deleted=False,
                             diagnosis_year=int(since) if re.fullmatch(r"(19|20)\d\d", since) else None, duration_text=None if re.fullmatch(r"(19|20)\d\d", since) else (since or None))
        db.add(c)
        db.flush()
        _log(db, patient.id, "condition", c.id, "CREATE", None, user)


def sync_surgeries(db: Session, patient: Patient, items: list[dict], none_known: bool, user: User) -> None:
    ensure_migrated(db, patient)
    if not items and not none_known:
        return
    wanted = {i["what"].strip().lower(): i for i in items}
    for s in db.scalars(select(SurgeryRecord).where(SurgeryRecord.patient_id == patient.id, NOT_DELETED(SurgeryRecord.is_deleted))):
        item = wanted.pop(s.procedure_name.strip().lower(), None)
        if item is None and s.admission_id is None:
            _log(db, patient.id, "surgery", s.id, "DELETE", _surgery_snapshot(s), user)
            s.is_deleted, s.updated_at = True, utcnow()
    for item in wanted.values():
        year = (item.get("year") or "").strip()
        s = SurgeryRecord(patient_id=patient.id, procedure_name=item["what"].strip(), hospital=item.get("hospital"), source="PATIENT_REPORTED", created_by=user.id, updated_by=user.id, is_deleted=False,
                          operation_year=int(year) if re.fullmatch(r"(19|20)\d\d", year) and int(year) <= hospital_today().year else None)
        db.add(s)
        db.flush()
        _log(db, patient.id, "surgery", s.id, "CREATE", None, user)


def sync_medications(db: Session, patient: Patient, items: list[dict], none_known: bool, user: User) -> None:
    """Match by medicine name: update, add, and hide (never delete) the ones that are no longer listed."""
    if not items and not none_known:
        return
    wanted = {i["name"].strip().lower(): i for i in items}
    for m in active_medications(db, patient):
        item = wanted.pop(m.name.strip().lower(), None)
        if item is None:
            _log(db, patient.id, "medication", m.id, "DELETE", _med_snapshot(m), user)
            m.is_deleted, m.updated_at = True, utcnow()
            continue
        changed = any((item.get(k) or None) != getattr(m, k) for k in ("dose", "frequency", "reason", "since", "notes")) or bool(item.get("is_current", True)) != bool(m.is_current)
        if changed:
            _log(db, patient.id, "medication", m.id, "UPDATE", _med_snapshot(m), user)
            for k in ("dose", "frequency", "reason", "since", "notes"):
                setattr(m, k, item.get(k) or None)
            m.is_current, m.updated_at = bool(item.get("is_current", True)), utcnow()
    for item in wanted.values():
        m = PatientMedication(patient_id=patient.id, updated_at=utcnow(), source="PATIENT_REPORTED", is_deleted=False, **{k: item.get(k) for k in ("name", "dose", "frequency", "reason", "since", "notes")},
                              is_current=bool(item.get("is_current", True)))
        db.add(m)
        db.flush()
        _log(db, patient.id, "medication", m.id, "CREATE", None, user)
