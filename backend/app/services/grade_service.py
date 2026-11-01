"""Doctor grades: what an intern, a PG resident, a senior resident and a consultant may finish on their own, the move of the old trainee accounts into
doctor grades, and the countersign queue of a supervising consultant. See docs/DOCTOR_GRADES.md."""
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import Session

from app.core.permissions import CONSULTANT, GRADES, INTERN, JUNIOR_GRADES, PG_RESIDENT, SENIOR_RESIDENT, get_doctor_profile
from app.database.connection import engine
from app.database.models import CountersignRequest, Doctor, Patient, User


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ------------------------------------------------------------------ what each grade may finish
def can_sign_consultation(doctor: Doctor) -> bool:
    return doctor.current_grade != INTERN


def can_set_final_diagnosis(doctor: Doctor) -> bool:
    return doctor.current_grade == CONSULTANT


def diagnosis_kind(doctor: Doctor, asked: str) -> str:
    """An intern writes drafts, a resident provisional diagnoses, a consultant final ones. Asking for more than the grade allows is a clear 403."""
    grade = doctor.current_grade
    if grade == INTERN:
        return "DRAFT"
    if asked == "FINAL" and grade != CONSULTANT:
        raise HTTPException(403, "Only a consultant makes the final diagnosis. Please save it as provisional.")
    return asked if asked in ("PROVISIONAL", "FINAL") else "PROVISIONAL"


def prescription_status(doctor: Doctor) -> str:
    """ACTIVE when the doctor may prescribe alone, else PENDING_COUNTERSIGN. An intern cannot prescribe at all."""
    grade = doctor.current_grade
    if grade == INTERN:
        raise HTTPException(403, "An intern cannot prescribe. Please write a draft note for your consultant.")
    if grade == CONSULTANT or doctor.can_prescribe_independently:
        return "ACTIVE"
    return "PENDING_COUNTERSIGN"


def order_status(doctor: Doctor) -> str:
    """A consultant's or resident's order goes ahead; an intern's order is a draft until the supervisor approves it."""
    return "DRAFT" if doctor.current_grade == INTERN else "ORDERED"


# ------------------------------------------------------------------ supervisor
def consultants_of(db: Session, department_id: int | None) -> list[Doctor]:
    query = select(Doctor).join(User, Doctor.user_id == User.id).where(User.is_active.is_(True), or_(Doctor.grade == CONSULTANT, Doctor.grade.is_(None)))
    if department_id:
        query = query.where(Doctor.department_id == department_id)
    return list(db.scalars(query))


def check_supervisor(db: Session, supervisor_id: int | None, department_id: int | None) -> None:
    """422 with a clear sentence unless the supervisor is a consultant of the same department."""
    if supervisor_id is None:
        return
    sup = db.get(Doctor, supervisor_id)
    if sup is None or not sup.user.is_active:
        raise HTTPException(422, "The selected supervising consultant does not exist.")
    if sup.current_grade != CONSULTANT:
        raise HTTPException(422, "The supervisor must be a consultant.")
    if sup.department_id != department_id:
        raise HTTPException(422, "The supervising consultant must belong to the same department.")


def check_grade_fields(db: Session, grade: str | None, department_id: int | None, pg_year: int | None, pg_branch: str | None, supervisor_id: int | None) -> None:
    grade = grade or CONSULTANT
    if grade not in GRADES:
        raise HTTPException(422, "The grade must be Intern, PG Resident, Senior Resident or Consultant.")
    if grade == CONSULTANT:
        return
    if department_id is None:
        raise HTTPException(422, "Please choose a department for the junior doctor.")
    if grade == PG_RESIDENT:
        if pg_year is None or not 1 <= pg_year <= 3:
            raise HTTPException(422, "Please choose the PG year (1 to 3).")
        if not pg_branch:
            raise HTTPException(422, "Please enter the PG branch, for example MD Medicine.")
    check_supervisor(db, supervisor_id, department_id)
    if supervisor_id is None:
        raise HTTPException(422, "Please choose the supervising consultant.")


# ------------------------------------------------------------------ countersign queue
def request_countersign(db: Session, kind: str, item_id: int, patient_id: int, doctor: Doctor, summary: str, original: dict | None = None) -> CountersignRequest:
    existing = db.scalar(select(CountersignRequest).where(CountersignRequest.kind == kind, CountersignRequest.item_id == item_id, CountersignRequest.status == "PENDING"))
    if existing:
        existing.summary = summary[:300]
        return existing
    row = CountersignRequest(kind=kind, item_id=item_id, patient_id=patient_id, requested_by=doctor.id, supervisor_id=doctor.supervisor_id, status="PENDING",
                             summary=summary[:300], original_json=json.dumps(original) if original is not None else None)
    db.add(row)
    db.flush()
    return row


def may_decide(db: Session, doctor: Doctor, row: CountersignRequest) -> bool:
    """The named supervisor; when none was named, any consultant of the junior doctor's department. Never the junior doctor themselves."""
    if doctor.current_grade != CONSULTANT or doctor.id == row.requested_by:
        return False
    if row.supervisor_id is not None:
        return row.supervisor_id == doctor.id
    return doctor.department_id is not None and doctor.department_id == row.requester.department_id


def countersign_out(r: CountersignRequest) -> dict:
    return {"id": r.id, "kind": r.kind, "item_id": r.item_id, "patient_id": r.patient_id, "patient_name": r.patient.user.full_name, "uhid": r.patient.uhid,
            "requested_by": r.requester.user.full_name, "requester_grade": r.requester.current_grade, "summary": r.summary, "status": r.status, "comment": r.comment,
            "created_at": r.created_at.isoformat(), "decided_at": r.decided_at.isoformat() if r.decided_at else None, "edited": r.original_json is not None and r.status == "EDITED"}


# ------------------------------------------------------------------ migration (start-up, safe to repeat)
def migrate(db: Session) -> None:
    """1. Every doctor without a grade is a consultant (nobody loses anything). 2. The accounts of the old trainee role become doctors with a grade, and their
    histories and referrals follow them. The old `trainees` table is left in place, untouched."""
    db.execute(update(Doctor).where(Doctor.grade.is_(None)).values(grade=CONSULTANT))
    db.execute(update(Doctor).where(Doctor.can_prescribe_independently.is_(None)).values(can_prescribe_independently=False))
    db.commit()
    with engine.connect() as conn:
        has = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='trainees'")).first() if engine.dialect.name == "sqlite" else None
        rows = conn.execute(text("SELECT id, user_id, department_id, trainee_type, year_branch, supervisor_id, phone FROM trainees")).mappings().all() if has else []
    moved: dict[int, int] = {}                                # old trainee id -> new doctor id
    for t in rows:
        user = db.get(User, t["user_id"])
        if user is None:
            continue
        doctor = db.scalar(select(Doctor).where(Doctor.user_id == user.id))
        if doctor is None:
            branch = t["year_branch"] or ""
            year = None
            for token in branch.replace(",", " ").split():
                if token.isdigit() and 1 <= int(token) <= 3:
                    year = int(token)
            is_pg = t["trainee_type"] == "PG_STUDENT"
            doctor = Doctor(user_id=user.id, department_id=t["department_id"], phone=t["phone"], grade=PG_RESIDENT if is_pg else INTERN, pg_year=year if is_pg else None,
                            pg_branch=(branch.split(",")[0].strip() or None) if is_pg else None, supervisor_id=t["supervisor_id"], can_prescribe_independently=False)
            db.add(doctor)
            db.flush()
            moved[t["id"]] = doctor.id
        user.role = "DOCTOR"
    if moved:                                                 # one statement per table, so an id that is both an old and a new number is never moved twice
        case = " ".join(f"WHEN {old} THEN {new}" for old, new in moved.items())
        olds = ",".join(str(old) for old in moved)
        for table in ("trainee_histories", "referrals"):
            db.execute(text(f"UPDATE {table} SET trainee_id = CASE trainee_id {case} END WHERE trainee_id IN ({olds})"))
    db.commit()
