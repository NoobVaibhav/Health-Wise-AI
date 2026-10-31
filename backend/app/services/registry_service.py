"""The patient registry: UHID, duplicate detection, consents, insurance, ABHA and the audited merge of two records of the same person."""
import json
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database.connection import Base
from app.database.models import Branch, Patient, PatientConsent, PatientMerge, UhidCounter, User
from app.services import hospital_service
from app.utils.validators import normalise_phone

CONSENT_KINDS = ("TREATMENT", "DATA_SHARING", "ABHA", "PHOTO", "RESEARCH")


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ------------------------------------------------------------------ UHID
def format_uhid(branch_code: str, year: int, number: int) -> str:
    return f"{branch_code}-{year % 100:02d}-{number:06d}"


def next_uhid(db: Session, branch: Branch, year: int | None = None) -> str:
    """The next number of this branch and year. The counter is changed in the same transaction as the patient, so a failed registration gives no number away."""
    year = year or now().year
    counter = db.scalar(select(UhidCounter).where(UhidCounter.branch_id == branch.id, UhidCounter.year == year))
    if counter is None:
        counter = UhidCounter(branch_id=branch.id, year=year, last_number=0)
        db.add(counter)
        db.flush()
    db.execute(update(UhidCounter).where(UhidCounter.id == counter.id).values(last_number=UhidCounter.last_number + 1))
    db.flush()
    db.refresh(counter)
    return format_uhid(branch.code, year, counter.last_number)


def backfill_uhids(db: Session) -> None:
    """Start-up: every patient without a UHID gets one (in the order of registration), and the default branch. Safe to repeat."""
    branch = hospital_service.default_branch(db)
    for patient in db.scalars(select(Patient).where(Patient.uhid.is_(None)).order_by(Patient.id)):
        patient.branch_id = patient.branch_id or branch.id
        patient.uhid = next_uhid(db, branch if patient.branch_id == branch.id else db.get(Branch, patient.branch_id), (patient.created_at or now()).year)
    db.commit()


# ------------------------------------------------------------------ duplicates
def _name_key(name: str) -> str:
    return " ".join((name or "").lower().split())


def find_duplicates(db: Session, full_name: str | None, dob, phone: str | None, exclude_id: int | None = None) -> list[dict]:
    """Probable second records of the same person. Same name and date of birth is a strong match; the same phone number alone is a weak one
    (families share a phone). Archived (merged) records are not shown."""
    found: dict[int, dict] = {}
    base = select(Patient).join(User, Patient.user_id == User.id).where(Patient.merged_into_id.is_(None))
    if exclude_id:
        base = base.where(Patient.id != exclude_id)
    if full_name and dob:
        for p in db.scalars(base.where(Patient.date_of_birth == dob, func.lower(User.full_name) == _name_key(full_name))):
            found[p.id] = {"patient": p, "reasons": ["same name and date of birth"], "strong": True}
    cleaned = normalise_phone(phone) if phone else None
    if cleaned:
        for p in db.scalars(base.where(Patient.phone == cleaned)):
            entry = found.setdefault(p.id, {"patient": p, "reasons": [], "strong": False})
            entry["reasons"].append("same phone number")
    return list(found.values())


def duplicate_out(entry: dict) -> dict:
    p = entry["patient"]
    return {"id": p.id, "uhid": p.uhid, "patient_code": p.patient_code, "full_name": p.user.full_name, "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
            "phone": p.phone, "reasons": entry["reasons"], "strong": entry["strong"]}


# ------------------------------------------------------------------ consent and ABHA
def active_consent(db: Session, patient_id: int, kind: str) -> PatientConsent | None:
    return db.scalar(select(PatientConsent).where(PatientConsent.patient_id == patient_id, PatientConsent.kind == kind, PatientConsent.withdrawn_at.is_(None)).order_by(PatientConsent.id.desc()))


def consent_out(c: PatientConsent) -> dict:
    return {"id": c.id, "kind": c.kind, "granted_at": c.granted_at.isoformat(), "given_by": c.given_by, "note": c.note,
            "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None, "active": c.withdrawn_at is None}


# ------------------------------------------------------------------ merge
def merge_patients(db: Session, keep: Patient, old: Patient, user: User, reason: str) -> PatientMerge:
    """Repoint every record of the old patient to the kept one. The old record stays, archived (so nothing is lost and the merge can be understood later);
    its login is switched off. A table that may hold only one row per patient (the standing history) keeps the kept patient's row; the old row stays
    with the archived record."""
    if keep.id == old.id:
        raise HTTPException(422, "Choose two different patient records.")
    if keep.merged_into_id or old.merged_into_id:
        raise HTTPException(409, "One of these records was already merged.")
    moved: dict[str, int] = {}
    skipped: list[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name in ("patients", "patient_merges"):
            continue
        for fk in table.foreign_keys:
            if fk.column.table.name != "patients" or fk.column.name != "id":
                continue
            column = fk.parent
            if column.unique or any(set(c.columns) == {column} for c in table.constraints if c.__class__.__name__ == "UniqueConstraint"):
                if db.scalar(select(func.count()).select_from(table).where(column == keep.id)):
                    skipped.append(table.name)
                    continue
            count = db.execute(update(table).where(column == old.id).values({column.name: keep.id})).rowcount or 0
            if count:
                moved[table.name] = moved.get(table.name, 0) + count
    old.merged_into_id = keep.id
    old.user.is_active = False
    record = PatientMerge(kept_patient_id=keep.id, merged_patient_id=old.id, merged_by=user.id, reason=reason, moved_json=json.dumps({"moved": moved, "left_with_archived": skipped}))
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
