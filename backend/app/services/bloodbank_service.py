"""Blood bank: donors, donations, units, requests, cross-match, issue and transfusion.

Plain rules, no AI. The limits below are common practice defaults and are NOT clinical advice: the blood bank medical officer must review and set them for the hospital.
- a donor must be 18-65, at least 45 kg, haemoglobin at least 12.5 g/dL, not deferred, and past the interval since the last donation (men 90 days, women 120 days)
- units from a donation stay in QUARANTINE until a second person records a CLEARED infection screening; a REACTIVE screening discards them and defers the donor
- a unit is matched only to a request of the same component and only if the ABO and Rh rule allows it; the technician's cross-match is then recorded
- a unit is issued by one person and verified by another; a transfusion is started by a nurse and checked at the bedside by a second person
- an expired unit is never matched, issued or transfused
"""
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.utils.locking import lock
from app.database.models import (
    BloodCrossmatch, BloodDonation, BloodDonor, BloodIssue, BloodRequest, BloodUnit, Doctor, Patient, Transfusion, User, utcnow,
)
from app.utils.clock import hospital_today

GROUPS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")
COMPONENTS = ("WHOLE_BLOOD", "PRBC", "FFP", "PLATELETS")
SHELF_LIFE_DAYS = {"WHOLE_BLOOD": 35, "PRBC": 42, "FFP": 365, "PLATELETS": 5}
RULES = {"min_age": 18, "max_age": 65, "min_weight_kg": 45.0, "min_haemoglobin": 12.5, "interval_days_male": 90, "interval_days_female": 120, "return_window_minutes": 30, "min_volume_ml": 250, "max_volume_ml": 550}


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def age_on(dob: date, day: date | None = None) -> int:
    day = day or hospital_today()
    return day.year - dob.year - ((day.month, day.day) < (dob.month, dob.day))


# ------------------------------------------------------------------ compatibility
def compatible(unit_group: str, component: str, patient_group: str | None) -> bool:
    """ABO and Rh. Red cells and whole blood: the donor's red cells must suit the patient. Plasma: the donor's plasma antibodies must suit the patient. Platelets: Rh rule only (ABO-identical is preferred).
    Group unknown (an emergency): only O negative red cells, AB plasma, or Rh negative platelets."""
    ug_abo, ug_rh = unit_group[:-1], unit_group[-1]
    if patient_group is None:
        return (unit_group == "O-") if component in ("WHOLE_BLOOD", "PRBC") else (ug_abo == "AB") if component == "FFP" else (ug_rh == "-")
    pg_abo, pg_rh = patient_group[:-1], patient_group[-1]
    if component in ("WHOLE_BLOOD", "PRBC"):
        abo_ok = ug_abo == "O" or pg_abo == "AB" or ug_abo == pg_abo
        rh_ok = ug_rh == "-" or pg_rh == "+"
        return abo_ok and rh_ok
    if component == "FFP":
        return ug_abo == "AB" or pg_abo == "O" or ug_abo == pg_abo
    return ug_rh == "-" or pg_rh == "+"


# ------------------------------------------------------------------ donors
def eligibility(donor: BloodDonor, haemoglobin: float | None = None, weight_kg: float | None = None, today: date | None = None) -> list[str]:
    """The reasons why this person cannot donate today (empty = eligible)."""
    today = today or hospital_today()
    reasons = []
    age = age_on(donor.date_of_birth, today)
    if age < RULES["min_age"] or age > RULES["max_age"]:
        reasons.append(f"Age must be {RULES['min_age']} to {RULES['max_age']} years.")
    if donor.deferred_until and donor.deferred_until >= today:
        reasons.append(f"Deferred until {donor.deferred_until:%d %b %Y}" + (f": {donor.deferral_reason}." if donor.deferral_reason else "."))
    interval = RULES["interval_days_male" if donor.gender.lower() == "male" else "interval_days_female"]
    if donor.last_donation_date and (today - donor.last_donation_date).days < interval:
        reasons.append(f"The last donation was {(today - donor.last_donation_date).days} days ago: wait at least {interval} days.")
    if weight_kg is not None and weight_kg < RULES["min_weight_kg"]:
        reasons.append(f"Weight must be at least {RULES['min_weight_kg']:g} kg.")
    if haemoglobin is not None and haemoglobin < RULES["min_haemoglobin"]:
        reasons.append(f"Haemoglobin must be at least {RULES['min_haemoglobin']:g} g/dL.")
    return reasons


def next_number(db: Session, model, column, prefix: str) -> str:
    count = db.scalar(select(func.count(model.id))) or 0
    while True:
        count += 1
        number = f"{prefix}{hospital_today():%y}{count:06d}"
        if not db.scalar(select(model.id).where(column == number)):
            return number


def register_donor(db: Session, user: User, data: dict) -> BloodDonor:
    if data["blood_group"] not in GROUPS:
        raise HTTPException(422, "Please choose the blood group from the list.")
    donor = BloodDonor(donor_no=next_number(db, BloodDonor, BloodDonor.donor_no, "D"), created_by=user.id, **data)
    db.add(donor)
    db.commit()
    return donor


def donor_out(d: BloodDonor) -> dict:
    return {"id": d.id, "donor_no": d.donor_no, "full_name": d.full_name, "gender": d.gender, "age": age_on(d.date_of_birth), "blood_group": d.blood_group, "phone": d.phone,
            "last_donation_date": d.last_donation_date.isoformat() if d.last_donation_date else None, "deferred_until": d.deferred_until.isoformat() if d.deferred_until else None,
            "deferral_reason": d.deferral_reason, "ineligible_reasons": eligibility(d)}


def collect(db: Session, user: User, donor: BloodDonor, volume_ml: int, haemoglobin: float, weight_kg: float, components: list[str]) -> BloodDonation:
    reasons = eligibility(donor, haemoglobin, weight_kg)
    if reasons:
        raise conflict("This donor cannot donate today: " + " ".join(reasons))
    if not RULES["min_volume_ml"] <= volume_ml <= RULES["max_volume_ml"]:
        raise HTTPException(422, f"The volume must be {RULES['min_volume_ml']} to {RULES['max_volume_ml']} ml.")
    if not components or any(c not in COMPONENTS for c in components) or len(set(components)) != len(components):
        raise HTTPException(422, "Choose the components to make from this donation (each once).")
    if "WHOLE_BLOOD" in components and len(components) > 1:
        raise HTTPException(422, "Whole blood is kept as it is; it cannot also be separated into components.")
    now = utcnow()
    donation = BloodDonation(donor_id=donor.id, donated_at=now, volume_ml=volume_ml, haemoglobin=haemoglobin, weight_kg=weight_kg, collected_by=user.id)
    db.add(donation)
    db.flush()
    for component in components:
        donation.units.append(BloodUnit(unit_number=next_number(db, BloodUnit, BloodUnit.unit_number, "U"), donation_id=donation.id, blood_group=donor.blood_group, component=component,
                                        volume_ml=volume_ml if len(components) == 1 else volume_ml // len(components), collected_at=now, expires_at=now + timedelta(days=SHELF_LIFE_DAYS[component])))
        db.flush()
    donor.last_donation_date = hospital_today()
    db.commit()
    return donation


def screen(db: Session, user: User, donation: BloodDonation, result: str, note: str | None) -> BloodDonation:
    if donation.screening != "PENDING":
        raise conflict(f"This donation is already screened ({donation.screening.lower()}).")
    if donation.collected_by == user.id:
        raise conflict("The screening must be recorded by a different person than the one who collected the blood.")
    if result == "REACTIVE" and not (note or "").strip():
        raise HTTPException(422, "Please write what was found.")
    donation.screening, donation.screening_note, donation.screened_by, donation.screened_at = result, note, user.id, utcnow()
    for unit in donation.units:
        if result == "CLEARED":
            unit.status = "AVAILABLE"
        else:
            unit.status, unit.discard_reason = "DISCARDED", "Infection screening reactive"
    if result == "REACTIVE":
        donation.donor.deferred_until, donation.donor.deferral_reason = hospital_today() + timedelta(days=3650), "Reactive screening: refer to the medical officer"
    db.commit()
    return donation


# ------------------------------------------------------------------ units
def refresh_expiry(db: Session) -> None:
    """Units past their expiry are marked EXPIRED (a unit in the fridge never changes by itself, so this runs whenever stock is looked at or matched)."""
    now = utcnow()
    changed = False
    for unit in db.scalars(select(BloodUnit).where(BloodUnit.expires_at < now, BloodUnit.status.in_(("AVAILABLE", "RESERVED", "QUARANTINE")))):
        unit.status = "EXPIRED"
        changed = True
    if changed:
        db.commit()


def unit_out(u: BloodUnit) -> dict:
    return {"id": u.id, "unit_number": u.unit_number, "blood_group": u.blood_group, "component": u.component, "volume_ml": u.volume_ml, "status": u.status, "reserved_for": u.reserved_for,
            "collected_at": u.collected_at.isoformat(), "expires_at": u.expires_at.isoformat(), "discard_reason": u.discard_reason}


def discard(db: Session, unit: BloodUnit, reason: str) -> BloodUnit:
    if unit.status in ("ISSUED", "TRANSFUSED", "DISCARDED"):
        raise conflict(f"A unit that is {unit.status.lower()} cannot be discarded here.")
    unit.status, unit.discard_reason = "DISCARDED", reason.strip()
    db.commit()
    return unit


def stock_summary(db: Session) -> list[dict]:
    refresh_expiry(db)
    rows = db.execute(select(BloodUnit.blood_group, BloodUnit.component, BloodUnit.status, func.count(BloodUnit.id)).group_by(BloodUnit.blood_group, BloodUnit.component, BloodUnit.status)).all()
    table: dict[tuple, dict] = {}
    for group, component, state, n in rows:
        row = table.setdefault((group, component), {"blood_group": group, "component": component, "available": 0, "reserved": 0, "quarantine": 0})
        if state in ("AVAILABLE", "RESERVED", "QUARANTINE"):
            row[state.lower()] += n
    return sorted(table.values(), key=lambda r: (r["component"], r["blood_group"]))


# ------------------------------------------------------------------ requests
def create_request(db: Session, doctor: Doctor, patient: Patient, data: dict) -> BloodRequest:
    if doctor.current_grade == "INTERN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "An intern cannot request blood: ask the supervising doctor.")
    record_group = (getattr(patient, "blood_group", None) or "").strip().upper() or None
    group = (data.get("blood_group") or "").strip().upper() or None
    if group and group not in GROUPS:
        raise HTTPException(422, "Please choose the blood group from the list.")
    if record_group and record_group in GROUPS and group and group != record_group:
        raise HTTPException(422, f"The blood group ({group}) does not match the patient's record ({record_group}). Check the patient and the sample.")
    group = group or (record_group if record_group in GROUPS else None)
    if group is None and data["urgency"] != "EMERGENCY":
        raise HTTPException(422, "The patient's blood group is needed. Only an emergency request can go without it.")
    if data["component"] not in COMPONENTS:
        raise HTTPException(422, "Please choose the component from the list.")
    req = BloodRequest(patient_id=patient.id, requested_by=doctor.id, component=data["component"], blood_group=group, units_requested=data["units_requested"],
                       urgency=data["urgency"], indication=data["indication"].strip())
    db.add(req)
    db.commit()
    return req


def request_out(db: Session, r: BloodRequest) -> dict:
    matched = db.scalars(select(BloodCrossmatch).where(BloodCrossmatch.request_id == r.id, BloodCrossmatch.result == "COMPATIBLE")).all()
    issues = db.scalars(select(BloodIssue).where(BloodIssue.request_id == r.id)).all()
    return {"id": r.id, "patient_id": r.patient_id, "patient_name": r.patient.user.full_name, "patient_code": r.patient.patient_code, "doctor": r.doctor.user.full_name, "component": r.component,
            "blood_group": r.blood_group, "units_requested": r.units_requested, "urgency": r.urgency, "indication": r.indication, "status": r.status, "decision_note": r.decision_note,
            "created_at": r.created_at.isoformat(), "units_matched": len({m.unit_id for m in matched}), "units_issued": len(issues),
            "issues": [{"id": i.id, "unit_number": i.unit.unit_number, "verified": i.verified_by is not None, "returned": i.returned_at is not None} for i in issues]}


def reject_request(db: Session, req: BloodRequest, reason: str) -> BloodRequest:
    if req.status not in ("PENDING", "CROSSMATCHED"):
        raise conflict(f"This request is {req.status.lower()}.")
    _release_reserved(db, req)
    req.status, req.decision_note = "REJECTED", reason.strip()
    db.commit()
    return req


def cancel_request(db: Session, req: BloodRequest) -> BloodRequest:
    if req.status not in ("PENDING", "CROSSMATCHED"):
        raise conflict(f"This request is {req.status.lower()}.")
    _release_reserved(db, req)
    req.status = "CANCELLED"
    db.commit()
    return req


def _release_reserved(db: Session, req: BloodRequest) -> None:
    for unit in db.scalars(select(BloodUnit).where(BloodUnit.reserved_for == req.id, BloodUnit.status == "RESERVED")):
        unit.status, unit.reserved_for = "AVAILABLE", None


# ------------------------------------------------------------------ cross-match, issue, return
def crossmatch(db: Session, user: User, req: BloodRequest, unit: BloodUnit, result: str) -> BloodCrossmatch:
    lock(db, unit, req)
    refresh_expiry(db)
    if req.status not in ("PENDING", "CROSSMATCHED"):
        raise conflict(f"This request is {req.status.lower()}.")
    if unit.status != "AVAILABLE":
        raise conflict(f"This unit is {unit.status.lower()}, so it cannot be matched.")
    if unit.component != req.component:
        raise conflict(f"The request is for {req.component.replace('_', ' ').lower()}, this unit is {unit.component.replace('_', ' ').lower()}.")
    if not compatible(unit.blood_group, unit.component, req.blood_group):
        raise conflict(f"Unit {unit.unit_number} ({unit.blood_group}) is not ABO/Rh compatible with the patient ({req.blood_group or 'group not known'}).")
    done = db.scalars(select(BloodCrossmatch).where(BloodCrossmatch.request_id == req.id, BloodCrossmatch.result == "COMPATIBLE")).all()
    if result == "COMPATIBLE" and len({m.unit_id for m in done}) >= req.units_requested:
        raise conflict("Enough units are already matched for this request.")
    row = BloodCrossmatch(request_id=req.id, unit_id=unit.id, result=result, done_by=user.id)
    db.add(row)
    if result == "COMPATIBLE":
        unit.status, unit.reserved_for = "RESERVED", req.id
        req.status = "CROSSMATCHED"
    db.commit()
    return row


def issue(db: Session, user: User, req: BloodRequest, unit: BloodUnit) -> BloodIssue:
    lock(db, unit, req)
    refresh_expiry(db)
    if unit.status != "RESERVED" or unit.reserved_for != req.id:
        raise conflict("Only a unit that was matched (cross-matched compatible) for this request can be issued.")
    if unit.expires_at < utcnow():
        raise conflict("This unit has expired.")
    row = BloodIssue(request_id=req.id, unit_id=unit.id, issued_by=user.id)
    unit.status = "ISSUED"
    db.add(row)
    req.status = "ISSUED"
    db.commit()
    return row


def verify_issue(db: Session, user: User, row: BloodIssue) -> BloodIssue:
    if row.verified_by is not None:
        raise conflict("This issue is already verified.")
    if row.returned_at is not None:
        raise conflict("This unit was returned.")
    if row.issued_by == user.id:
        raise conflict("The issue must be verified by a different person than the one who issued the unit.")
    row.verified_by, row.verified_at = user.id, utcnow()
    db.commit()
    return row


def return_unit(db: Session, row: BloodIssue, reason: str, cold_chain_ok: bool) -> BloodIssue:
    lock(db, row, row.unit)
    if row.returned_at is not None:
        raise conflict("This unit was already returned.")
    if db.scalar(select(Transfusion.id).where(Transfusion.issue_id == row.id)):
        raise conflict("A unit that has been started on a patient cannot be returned.")
    now = utcnow()
    row.returned_at, row.return_reason = now, reason.strip()
    within = (now - (row.verified_at or row.issued_at)) <= timedelta(minutes=RULES["return_window_minutes"])
    if cold_chain_ok and within and row.unit.expires_at > now:
        row.unit.status, row.unit.reserved_for = "AVAILABLE", None
    else:
        row.unit.status, row.unit.discard_reason = "DISCARDED", "Returned outside the cold-chain window or without a cold-chain check"
    row.request.status = "CROSSMATCHED" if row.unit.status == "AVAILABLE" else "PENDING"
    db.commit()
    return row


# ------------------------------------------------------------------ transfusion
def start_transfusion(db: Session, user: User, row: BloodIssue, patient_checked: bool, unit_checked: bool) -> Transfusion:
    lock(db, row)
    if row.verified_by is None:
        raise conflict("The blood bank has not verified this issue yet.")
    if row.returned_at is not None:
        raise conflict("This unit was returned.")
    if row.unit.expires_at < utcnow():
        raise conflict("This unit has expired and must not be transfused.")
    if db.scalar(select(Transfusion.id).where(Transfusion.issue_id == row.id)):
        raise conflict("A transfusion was already started with this unit.")
    if not (patient_checked and unit_checked):
        raise HTTPException(422, "Check the patient's identity and the unit label against the request before starting.")
    t = Transfusion(issue_id=row.id, patient_id=row.request.patient_id, started_by=user.id)
    db.add(t)
    db.commit()
    return t


def verify_transfusion(db: Session, user: User, t: Transfusion) -> Transfusion:
    if t.status != "AWAITING_CHECK":
        raise conflict(f"This transfusion is {t.status.lower().replace('_', ' ')}.")
    if t.started_by == user.id:
        raise conflict("The bedside check must be done by a second person.")
    t.status, t.verified_by, t.verified_at = "IN_PROGRESS", user.id, utcnow()
    db.commit()
    return t


def end_transfusion(db: Session, user: User, t: Transfusion, volume_ml: int, reaction: bool, note: str | None, stopped: bool) -> Transfusion:
    if t.status != "IN_PROGRESS":
        raise conflict("Only a transfusion that is running can be ended." if t.status != "AWAITING_CHECK" else "The bedside check is not done yet.")
    if reaction and not (note or "").strip():
        raise HTTPException(422, "Please describe the reaction.")
    t.status = "STOPPED" if (stopped or reaction) else "COMPLETED"
    t.ended_at, t.ended_by, t.volume_given_ml, t.reaction, t.reaction_note = utcnow(), user.id, volume_ml, reaction, note
    t.issue.unit.status = "TRANSFUSED"
    request = t.issue.request
    issues = db.scalars(select(BloodIssue).where(BloodIssue.request_id == request.id)).all()
    ended = {x for x in db.scalars(select(Transfusion.issue_id).where(Transfusion.ended_at.is_not(None)))} | {t.issue_id}
    if request.status == "ISSUED" and len(issues) >= request.units_requested and all(i.returned_at or i.id in ended for i in issues):
        request.status = "COMPLETED"
    db.commit()
    return t


def transfusion_out(t: Transfusion) -> dict:
    return {"id": t.id, "issue_id": t.issue_id, "patient_id": t.patient_id, "patient_name": t.patient.user.full_name, "unit_number": t.issue.unit.unit_number, "blood_group": t.issue.unit.blood_group,
            "component": t.issue.unit.component, "status": t.status, "started_at": t.started_at.isoformat(), "verified": t.verified_by is not None, "ended_at": t.ended_at.isoformat() if t.ended_at else None,
            "volume_given_ml": t.volume_given_ml, "reaction": t.reaction, "reaction_note": t.reaction_note}
