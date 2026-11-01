"""Operation theatre: scheduling without clashes, the safety gates, and the record of an operation.

Gates (plain rules, no AI):
- no overlap in one theatre, for one surgeon, or for one anaesthetist
- to start: a pre-op assessment that says fit, consent for THIS surgery, and the sign-in checklist complete
- to move to recovery: the time-out checklist complete and an operation note saved
- to complete: sign-out complete, operation note final (by the surgeon), anaesthesia record made
- the operation note is written by the surgeon, the pre-op assessment and anaesthesia record by the anaesthetist; nobody edits another person's record
"""
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Doctor, EncounterCharge, Admission, InventoryItem, OperationTheatre, ServiceCatalog, Surgery, SurgeryChecklistItem, SurgeryConsumable, SurgeryEvent, User, utcnow,
)
from app.services import stock_service
from app.utils.locking import lock, lock_row

CHECKLIST = {
    "SIGN_IN": ["Patient identity and procedure confirmed", "Surgical site marked", "Consent checked", "Anaesthesia machine and medicines checked", "Allergies reviewed"],
    "TIME_OUT": ["Team members introduced", "Patient, site and procedure confirmed aloud", "Antibiotic prophylaxis given if needed", "Essential imaging displayed"],
    "SIGN_OUT": ["Procedure recorded", "Instrument, sponge and needle counts correct", "Specimen labelled", "Recovery concerns discussed"],
}
ACTIVE = ("SCHEDULED", "IN_PROGRESS", "RECOVERY", "COMPLETED")
ANAESTHESIA = ("GENERAL", "SPINAL", "EPIDURAL", "REGIONAL", "LOCAL", "SEDATION")


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def get(db: Session, surgery_id: int) -> Surgery:
    s = db.get(Surgery, surgery_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Surgery not found.")
    return s


def check_clash(db: Session, start: datetime, end: datetime, theatre_id: int, surgeon_id: int, anaesthetist_id: int | None, exclude: int | None = None) -> None:
    rows = db.scalars(select(Surgery).where(Surgery.status.in_(ACTIVE), Surgery.scheduled_start < end, Surgery.scheduled_end > start)).all()
    for s in rows:
        if s.id == exclude:
            continue
        if s.theatre_id == theatre_id:
            raise conflict(f"{s.theatre.name} is already booked from {s.scheduled_start:%H:%M} to {s.scheduled_end:%H:%M} on {s.scheduled_start:%d %b}.")
        if s.surgeon_id == surgeon_id or (anaesthetist_id and anaesthetist_id in (s.surgeon_id, s.anaesthetist_id)):
            name = s.surgeon.user.full_name if s.surgeon_id == surgeon_id else (s.anaesthetist.user.full_name if s.anaesthetist else "The anaesthetist")
            raise conflict(f"{name} already has a surgery from {s.scheduled_start:%H:%M} to {s.scheduled_end:%H:%M} on {s.scheduled_start:%d %b}.")
        if s.anaesthetist_id and s.anaesthetist_id == surgeon_id:
            raise conflict(f"{s.anaesthetist.user.full_name} is the anaesthetist of another surgery at that time.")


def validate_booking(db: Session, start: datetime, end: datetime, theatre_id: int, surgeon_id: int, anaesthetist_id: int | None, service_id: int | None) -> None:
    if end <= start:
        raise HTTPException(422, "The end must be after the start.")
    if end - start > timedelta(hours=24):
        raise HTTPException(422, "A surgery cannot be booked for more than 24 hours.")
    theatre = db.get(OperationTheatre, theatre_id)
    if theatre is None or not theatre.is_active:
        raise HTTPException(422, "Please choose an active operation theatre.")
    surgeon = db.get(Doctor, surgeon_id)
    if surgeon is None or surgeon.current_grade == "INTERN":
        raise HTTPException(422, "Please choose a surgeon (an intern cannot be the surgeon).")
    if anaesthetist_id is not None:
        if anaesthetist_id == surgeon_id:
            raise HTTPException(422, "The anaesthetist and the surgeon must be different doctors.")
        anaesthetist = db.get(Doctor, anaesthetist_id)
        if anaesthetist is None or anaesthetist.current_grade == "INTERN":
            raise HTTPException(422, "Please choose an anaesthetist (an intern cannot be the anaesthetist).")
    if service_id is not None and db.get(ServiceCatalog, service_id) is None:
        raise HTTPException(422, "That price-list service does not exist.")


def book(db: Session, user: User, patient_id: int, data: dict) -> Surgery:
    lock_row(db, OperationTheatre, data["theatre_id"])                 # two bookings for the same theatre are checked one after the other
    validate_booking(db, data["scheduled_start"], data["scheduled_end"], data["theatre_id"], data["surgeon_id"], data.get("anaesthetist_id"), data.get("service_id"))
    check_clash(db, data["scheduled_start"], data["scheduled_end"], data["theatre_id"], data["surgeon_id"], data.get("anaesthetist_id"))
    admission = None
    if data.get("admission_id"):
        admission = db.get(Admission, data["admission_id"])
        if admission is None or admission.patient_id != patient_id or admission.status != "ADMITTED":
            raise HTTPException(422, "That admission does not belong to this patient or is closed.")
    surgery = Surgery(patient_id=patient_id, admission_id=admission.id if admission else None, encounter_id=admission.encounter_id if admission else None, created_by=user.id,
                      **{k: data.get(k) for k in ("theatre_id", "service_id", "procedure", "priority", "surgeon_id", "anaesthetist_id", "scheduled_start", "scheduled_end")})
    db.add(surgery)
    db.commit()
    return surgery


def reschedule(db: Session, surgery: Surgery, data: dict) -> Surgery:
    lock_row(db, OperationTheatre, data.get("theatre_id", surgery.theatre_id))
    lock(db, surgery)
    if surgery.status != "SCHEDULED":
        raise conflict("Only a surgery that has not started can be rescheduled.")
    merged = {k: data.get(k, getattr(surgery, k)) for k in ("scheduled_start", "scheduled_end", "theatre_id", "surgeon_id", "anaesthetist_id", "service_id")}
    validate_booking(db, merged["scheduled_start"], merged["scheduled_end"], merged["theatre_id"], merged["surgeon_id"], merged["anaesthetist_id"], merged["service_id"])
    check_clash(db, merged["scheduled_start"], merged["scheduled_end"], merged["theatre_id"], merged["surgeon_id"], merged["anaesthetist_id"], exclude=surgery.id)
    for k, v in merged.items():
        setattr(surgery, k, v)
    if "anaesthetist_id" in data and data["anaesthetist_id"] != surgery.anaesthetist_id:
        surgery.preop_fit = surgery.preop_by = surgery.preop_at = None            # a new anaesthetist assesses again
    db.commit()
    return surgery


def cancel(db: Session, surgery: Surgery, reason: str) -> Surgery:
    if surgery.status not in ("SCHEDULED",):
        raise conflict("Only a surgery that has not started can be cancelled.")
    surgery.status, surgery.cancel_reason = "CANCELLED", reason.strip()
    db.commit()
    return surgery


# ------------------------------------------------------------------ records
def _doctor_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Doctor.id).where(Doctor.user_id == user.id))


def _open(surgery: Surgery) -> None:
    if surgery.status in ("COMPLETED", "CANCELLED"):
        raise conflict(f"This surgery is {surgery.status.lower()}: its record is closed.")


def record_preop(db: Session, surgery: Surgery, user: User, fit: bool, notes: str | None) -> Surgery:
    _open(surgery)
    if surgery.status != "SCHEDULED":
        raise conflict("The pre-operative assessment must be done before the surgery starts.")
    if surgery.anaesthetist_id is None:
        raise conflict("Assign an anaesthetist first: the pre-operative assessment is the anaesthetist's.")
    if _doctor_id(db, user) != surgery.anaesthetist_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the anaesthetist of this surgery makes the pre-operative assessment.")
    if not fit and not (notes or "").strip():
        raise HTTPException(422, "Please write why the patient is not fit.")
    surgery.preop_fit, surgery.preop_notes, surgery.preop_by, surgery.preop_at = fit, notes, user.id, utcnow()
    db.commit()
    return surgery


def record_consent(db: Session, surgery: Surgery, user: User, given: bool, by_name: str, note: str | None) -> Surgery:
    _open(surgery)
    if surgery.status != "SCHEDULED":
        raise conflict("Consent is recorded before the surgery starts.")
    surgery.consent_given, surgery.consent_by_name, surgery.consent_note, surgery.consent_recorded_by, surgery.consent_at = given, by_name.strip(), note, user.id, utcnow()
    db.commit()
    return surgery


def tick_checklist(db: Session, surgery: Surgery, user: User, phase: str, items: list[str]) -> Surgery:
    _open(surgery)
    if phase not in CHECKLIST:
        raise HTTPException(422, "Unknown checklist phase.")
    if phase == "SIGN_IN" and surgery.status != "SCHEDULED":
        raise conflict("The sign-in is done before the surgery starts.")
    if phase in ("TIME_OUT", "SIGN_OUT") and surgery.status == "SCHEDULED":
        raise conflict("Start the surgery before the time-out and sign-out.")
    done = {c.item for c in surgery.checklist if c.phase == phase}
    for item in items:
        if item not in CHECKLIST[phase]:
            raise HTTPException(422, f"'{item}' is not an item of the {phase.replace('_', '-').lower()} checklist.")
        if item not in done:
            surgery.checklist.append(SurgeryChecklistItem(phase=phase, item=item, ticked_by=user.id))
            done.add(item)
    db.commit()
    return surgery


def phase_done(surgery: Surgery, phase: str) -> bool:
    return {c.item for c in surgery.checklist if c.phase == phase} >= set(CHECKLIST[phase])


def start(db: Session, surgery: Surgery) -> Surgery:
    if surgery.status != "SCHEDULED":
        raise conflict(f"This surgery is {surgery.status.lower()}.")
    missing = []
    if surgery.preop_fit is not True:
        missing.append("a pre-operative assessment that says the patient is fit")
    if surgery.consent_given is not True:
        missing.append("the patient's consent for this surgery")
    if not phase_done(surgery, "SIGN_IN"):
        missing.append("the completed sign-in checklist")
    if missing:
        raise conflict("The surgery cannot start without " + ", ".join(missing) + ".")
    surgery.status, surgery.started_at = "IN_PROGRESS", utcnow()
    db.commit()
    return surgery


def record_anaesthesia(db: Session, surgery: Surgery, user: User, kind: str, notes: str | None) -> Surgery:
    _open(surgery)
    if surgery.status == "SCHEDULED":
        raise conflict("The anaesthesia record is written once the surgery has started.")
    if _doctor_id(db, user) != surgery.anaesthetist_id or surgery.anaesthetist_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the anaesthetist of this surgery writes the anaesthesia record.")
    if kind not in ANAESTHESIA:
        raise HTTPException(422, "Please choose the type of anaesthesia from the list.")
    surgery.anaesthesia_type, surgery.anaesthesia_notes, surgery.anaesthesia_by, surgery.anaesthesia_at = kind, notes, user.id, utcnow()
    db.commit()
    return surgery


def record_op_note(db: Session, surgery: Surgery, user: User, data: dict, final: bool) -> Surgery:
    _open(surgery)
    if surgery.status == "SCHEDULED":
        raise conflict("The operation note is written once the surgery has started.")
    if _doctor_id(db, user) != surgery.surgeon_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the surgeon of this surgery writes the operation note.")
    if surgery.op_note_final:
        raise conflict("The operation note is final and cannot be changed.")
    surgery.op_findings, surgery.op_procedure_done, surgery.op_complications, surgery.op_blood_loss_ml = data["findings"], data["procedure_done"], data.get("complications"), data.get("blood_loss_ml")
    surgery.op_note_by, surgery.op_note_at = user.id, utcnow()
    if final:
        if not (surgery.op_findings or "").strip() or not (surgery.op_procedure_done or "").strip():
            raise HTTPException(422, "A final operation note needs the findings and the procedure done.")
        surgery.op_note_final = True
    db.commit()
    return surgery


def add_event(db: Session, surgery: Surgery, user: User, text: str) -> Surgery:
    if surgery.status not in ("IN_PROGRESS", "RECOVERY"):
        raise conflict("Events are recorded while the surgery is in progress or in recovery.")
    surgery.events.append(SurgeryEvent(text=text.strip(), created_by=user.id))
    db.commit()
    return surgery


def use_consumable(db: Session, surgery: Surgery, user: User, item_id: int, quantity: int) -> Surgery:
    if surgery.status not in ("IN_PROGRESS", "RECOVERY"):
        raise conflict("Consumables are recorded while the surgery is in progress or in recovery.")
    item = db.get(InventoryItem, item_id)
    if item is None or not item.is_active:
        raise HTTPException(422, "That store item does not exist.")
    if item.quantity < quantity:
        raise conflict(f"Not enough {item.name} in the store: {item.quantity} available.")
    item.quantity -= quantity
    stock_service.record(db, item=item, kind="CONSUME", quantity=-quantity, reference_type="surgery", reference_id=surgery.id, user_id=user.id)
    surgery.consumables.append(SurgeryConsumable(inventory_item_id=item.id, quantity=quantity, created_by=user.id))
    db.commit()
    return surgery


def to_recovery(db: Session, surgery: Surgery, notes: str | None) -> Surgery:
    if surgery.status != "IN_PROGRESS":
        raise conflict("Only a surgery in progress can move to recovery.")
    missing = []
    if not phase_done(surgery, "TIME_OUT"):
        missing.append("the completed time-out checklist")
    if not surgery.op_note_by:
        missing.append("an operation note")
    if missing:
        raise conflict("The patient cannot move to recovery without " + " and ".join(missing) + ".")
    surgery.status, surgery.recovery_at, surgery.recovery_notes = "RECOVERY", utcnow(), notes
    db.commit()
    return surgery


def complete(db: Session, surgery: Surgery, user: User) -> Surgery:
    if surgery.status != "RECOVERY":
        raise conflict("Only a surgery in recovery can be completed.")
    missing = []
    if not phase_done(surgery, "SIGN_OUT"):
        missing.append("the completed sign-out checklist")
    if not surgery.op_note_final:
        missing.append("a final operation note from the surgeon")
    if not surgery.anaesthesia_by:
        missing.append("the anaesthesia record")
    if missing:
        raise conflict("The surgery cannot be completed without " + ", ".join(missing) + ".")
    surgery.status, surgery.completed_at = "COMPLETED", utcnow()
    if surgery.service_id and surgery.encounter_id:
        service = db.get(ServiceCatalog, surgery.service_id)
        db.add(EncounterCharge(encounter_id=surgery.encounter_id, patient_id=surgery.patient_id, service_id=service.id, description=f"{service.name}: {surgery.procedure}"[:200],
                               amount=service.price, gst_percent=service.gst_percent, status="PENDING", created_by=user.id))
    db.commit()
    return surgery


def out(db: Session, s: Surgery, detail: bool = False) -> dict:
    row = {"id": s.id, "patient_id": s.patient_id, "patient_name": s.patient.user.full_name, "patient_code": s.patient.patient_code, "theatre_id": s.theatre_id, "theatre": s.theatre.name,
           "procedure": s.procedure, "priority": s.priority, "status": s.status, "surgeon_id": s.surgeon_id, "surgeon": s.surgeon.user.full_name,
           "anaesthetist_id": s.anaesthetist_id, "anaesthetist": s.anaesthetist.user.full_name if s.anaesthetist else None, "admission_id": s.admission_id,
           "scheduled_start": s.scheduled_start.isoformat(), "scheduled_end": s.scheduled_end.isoformat(), "cancel_reason": s.cancel_reason,
           "preop_fit": s.preop_fit, "consent_given": s.consent_given,
           "sign_in_done": phase_done(s, "SIGN_IN"), "time_out_done": phase_done(s, "TIME_OUT"), "sign_out_done": phase_done(s, "SIGN_OUT"),
           "op_note_final": bool(s.op_note_final), "anaesthesia_recorded": bool(s.anaesthesia_by)}
    if detail:
        names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({c.ticked_by for c in s.checklist} | {e.created_by for e in s.events} | {c.created_by for c in s.consumables})))}
        items = {i.id: i.name for i in db.scalars(select(InventoryItem).where(InventoryItem.id.in_([c.inventory_item_id for c in s.consumables] or [0])))}
        row.update({
            "preop": {"fit": s.preop_fit, "notes": s.preop_notes, "at": s.preop_at.isoformat() if s.preop_at else None},
            "consent": {"given": s.consent_given, "by_name": s.consent_by_name, "note": s.consent_note, "at": s.consent_at.isoformat() if s.consent_at else None},
            "anaesthesia": {"type": s.anaesthesia_type, "notes": s.anaesthesia_notes, "at": s.anaesthesia_at.isoformat() if s.anaesthesia_at else None},
            "op_note": {"findings": s.op_findings, "procedure_done": s.op_procedure_done, "complications": s.op_complications, "blood_loss_ml": s.op_blood_loss_ml, "final": bool(s.op_note_final),
                        "at": s.op_note_at.isoformat() if s.op_note_at else None},
            "checklist": {phase: [{"item": i, "done": any(c.phase == phase and c.item == i for c in s.checklist),
                                   "by": names.get(next((c.ticked_by for c in s.checklist if c.phase == phase and c.item == i), 0))} for i in items_] for phase, items_ in CHECKLIST.items()},
            "events": [{"text": e.text, "at": e.created_at.isoformat(), "by": names.get(e.created_by)} for e in s.events],
            "consumables": [{"item": items.get(c.inventory_item_id), "quantity": c.quantity, "at": c.created_at.isoformat(), "by": names.get(c.created_by)} for c in s.consumables],
            "started_at": s.started_at.isoformat() if s.started_at else None, "recovery_at": s.recovery_at.isoformat() if s.recovery_at else None, "recovery_notes": s.recovery_notes,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None})
    return row
