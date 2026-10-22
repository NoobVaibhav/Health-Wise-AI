"""The patient's medication history, from the hospital's own prescriptions and pharmacy records.

A PRESCRIBED medicine, a DISPENSED medicine and a medicine the patient TAKES are three different facts:
- prescribed = a doctor wrote it (prescription date, doctor, indication);
- dispensed  = the pharmacy handed it over (date and quantity);
- taking     = only the patient can say so. Nothing here assumes it. "Adherence: not documented".
Items such as duplicates, dose changes and allergy matches are for a qualified clinician to review; they are not verdicts
(there is no maintained interaction database behind them)."""
import re
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import MedicineDispensing, Patient, PatientMedication, Prescription
from app.services.clinical_timeline import source
from app.services.health_history_service import load_history

OPEN = ("ACTIVE", "PARTIALLY_DISPENSED")
NEW_DAYS = 30


def base_name(name: str) -> str:
    """'Tab. Aspirin 75 mg' -> 'aspirin' (so the same medicine on two prescriptions is recognised)."""
    lowered = name.lower()
    lowered = re.sub(r"\b(tab|tablet|tablets|cap|capsule|capsules|inj|injection|syrup|drops|cream|ointment|gel|inhaler)\b\.?", " ", lowered)
    lowered = re.sub(r"[0-9]+(\.[0-9]+)?\s*(mg|mcg|g|ml|iu|%|units?)\b", " ", lowered)
    return re.sub(r"[^a-z+ ]", " ", lowered).strip().replace("  ", " ")


def build(db: Session, patient: Patient) -> dict:
    prescriptions = db.scalars(select(Prescription).where(Prescription.patient_id == patient.id).order_by(Prescription.prescription_date, Prescription.id)).all()
    history = load_history(db, patient)
    allergies = history.get("allergies", [])
    today = date.today()

    groups: dict[str, dict] = {}
    for rx in prescriptions:
        for item in rx.items:
            key = base_name(item.medicine_name) or item.medicine_name.lower()
            dispensings = db.scalars(select(MedicineDispensing).where(MedicineDispensing.prescription_item_id == item.id).order_by(MedicineDispensing.dispensed_at)).all()
            entry = {
                "prescription_id": rx.id, "prescription_code": f"RX-{rx.id:05d}", "prescribed_on": rx.prescription_date.isoformat(), "doctor": rx.doctor.user.full_name,
                "name": item.medicine_name, "dose": item.dosage or None, "frequency": item.frequency or None, "duration": item.duration or None,
                "indication": rx.clinical_indication, "instructions": item.instructions, "prescribed_quantity": item.quantity,
                "prescription_status": rx.status, "dispense_status": item.dispense_status,
                "dispensed": [{"date": d.dispensed_at.date().isoformat(), "quantity": d.quantity_dispensed, "status": d.status} for d in dispensings],
                "dispensed_quantity": sum(d.quantity_dispensed for d in dispensings),
                "source": source("prescription", rx.id, f"Prescription RX-{rx.id:05d}", rx.prescription_date.isoformat()),
            }
            groups.setdefault(key, {"key": key, "name": item.medicine_name, "entries": []})["entries"].append(entry)

    medicines, new, stopped, changes, duplicates, missing = [], [], [], [], [], []
    for g in groups.values():
        entries = g["entries"]
        first, last = entries[0], entries[-1]
        is_open = last["prescription_status"] in OPEN
        cancelled = last["prescription_status"] == "CANCELLED"
        open_entries = [e for e in entries if e["prescription_status"] in OPEN]
        item = {
            "name": g["name"], "entries": entries,
            "first_prescribed": first["prescribed_on"], "last_prescribed": last["prescribed_on"],
            "start_date": None, "start_note": f"Start date not recorded. First prescribed here on {first['prescribed_on']}.",
            "stop_date": None, "stop_note": "Prescription cancelled by the doctor; the stop date was not recorded." if cancelled else ("No stop date recorded." if not is_open else "Prescription still open."),
            "status": "STOPPED" if cancelled else ("OPEN" if is_open else last["prescription_status"]),
            "prescribed_count": len(entries), "dispensed_quantity": sum(e["dispensed_quantity"] for e in entries),
            "adherence": "Not documented. A prescription or a dispensing does not show that the medicine was taken.",
            "adverse_reactions": "None recorded in the medication records.", "allergy_match": None, "changes": [],
        }
        for prev, nxt in zip(entries, entries[1:]):
            diffs = [f"{label} {prev[k] or 'not recorded'} -> {nxt[k] or 'not recorded'}" for k, label in (("dose", "dose"), ("frequency", "frequency"), ("duration", "duration")) if (prev[k] or "") != (nxt[k] or "")]
            if diffs:
                item["changes"].append({"from": prev["prescribed_on"], "to": nxt["prescribed_on"], "text": "; ".join(diffs), "source": nxt["source"]})
                changes.append({"medicine": g["name"], "text": f"{g['name']}: " + "; ".join(diffs) + f" (prescriptions of {prev['prescribed_on']} and {nxt['prescribed_on']})", "source": nxt["source"]})
        if date.fromisoformat(first["prescribed_on"]) >= today - timedelta(days=NEW_DAYS) and len(entries) == 1:
            new.append({"medicine": g["name"], "text": f"{g['name']} was first prescribed here on {first['prescribed_on']}.", "source": first["source"]})
        if cancelled:
            stopped.append({"medicine": g["name"], "text": f"The prescription for {g['name']} ({last['prescription_code']}) was cancelled.", "source": last["source"]})
        if len({e["prescription_id"] for e in open_entries}) > 1:
            codes = ", ".join(sorted({e["prescription_code"] for e in open_entries}))
            duplicates.append({"medicine": g["name"], "text": f"{g['name']} is on more than one open prescription ({codes}). For clinical review: possible duplicate therapy.", "source": open_entries[-1]["source"]})
        for a in allergies:
            word = a["name"].strip().lower()
            if len(word) >= 4 and word in g["name"].lower():
                item["allergy_match"] = f"A recorded allergy to {a['name']}" + (f" ({a['reaction']})" if a.get("reaction") else "") + " matches this medicine name. For clinical review."
        for e in entries:
            absent = [label for label, k in (("strength", "dose"), ("frequency", "frequency"), ("duration", "duration"), ("indication", "indication")) if not e[k]]
            if absent:
                missing.append({"medicine": g["name"], "text": f"{g['name']} ({e['prescription_code']}): {', '.join(absent)} not recorded.", "source": e["source"]})
        medicines.append(item)

    reported = [{"name": m.name, "dose": m.dose, "frequency": m.frequency, "reason": m.reason, "since": m.since, "origin": "Entered by the doctor or patient in the permanent history"}
                for m in db.scalars(select(PatientMedication).where(PatientMedication.patient_id == patient.id, PatientMedication.is_current.is_(True)))]
    known = {base_name(m["name"]) for m in medicines}
    reported_only = [m for m in reported if base_name(m["name"]) not in known]
    allergy_flags = [{"medicine": m["name"], "text": m["allergy_match"]} for m in medicines if m["allergy_match"]]
    medicines.sort(key=lambda m: (m["status"] != "OPEN", m["name"].lower()))
    return {"medicines": medicines, "reported": reported, "reported_only": reported_only, "new": new, "stopped": stopped, "changes": changes,
            "duplicates": duplicates, "allergy_flags": allergy_flags, "missing_details": missing,
            "documented_allergies": [{"name": a["name"], "reaction": a.get("reaction")} for a in allergies],
            "note": "Prescribed, dispensed and taken are different facts. Only prescriptions and pharmacy records are shown here; adherence is not documented."}
