"""One chronological list of everything documented about a patient, for the doctor.

Every event keeps
- its SOURCE (what record it came from, so the doctor can open it), and
- the KIND of date it has: the date of the event itself, the date printed on a report, the date a file was uploaded, or the date a
  doctor reviewed it. These are different things. A report without a printed date is shown as "Date not recorded": the upload date
  is shown as its own event and is never used as if it were the date of the medical event.
Nothing here is written by an AI model: it is a sorted, linked copy of the hospital's own records."""
import json
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Appointment, ClinicalAssessment, DoctorNote, DoctorRecommendation, EmergencyEvent, FollowUpTask, HealthReport,
    MedicalHistoryEntry, MedicineDispensing, Patient, Prescription,
)

NOT_RECORDED = "Date not recorded"


def source(kind: str, ident: int, label: str, when: str | None = None) -> dict:
    """A pointer to the original record: the screen opens the record from `type` and `id`."""
    return {"type": kind, "id": ident, "label": label, "date": when}


def _event(key: str, kind: str, title: str, detail: str | None, when: datetime | date | None, date_label: str, src: dict) -> dict:
    iso = when.isoformat() if when else None
    day = (when.date() if isinstance(when, datetime) else when) if when else None
    return {"key": key, "kind": kind, "title": title, "detail": detail, "datetime": iso, "date": day.isoformat() if day else None,
            "date_label": date_label, "date_note": None if when else NOT_RECORDED, "source": src,
            "origin": "DOCUMENTED"}


def _sort_value(e: dict) -> str:
    return e["datetime"] or ""


def build(db: Session, patient: Patient, q: str | None = None) -> list[dict]:
    events: list[dict] = []

    for a in db.scalars(select(Appointment).where(Appointment.patient_id == patient.id)):
        told = []
        if a.reason:
            told.append(a.reason)
        if a.symptoms_json:
            told.append("symptoms told by the patient: " + ", ".join(json.loads(a.symptoms_json)))
        events.append(_event(f"appointment:{a.id}", "APPOINTMENT", f"Appointment with {a.doctor.user.full_name} ({a.status.title()})", "; ".join(told) or None,
                             a.scheduled_at, "Scheduled for", source("appointment", a.id, "Appointment", a.scheduled_at.date().isoformat())))

    for r in db.scalars(select(HealthReport).where(HealthReport.patient_id == patient.id)):
        printed = r.report_date
        label = f"Report: {r.filename}"
        src = source("report", r.id, label, printed.isoformat() if printed else None)
        outside = [p for p in r.parameters if p.status in ("ABOVE_RANGE", "BELOW_RANGE")]
        detail = (f"{len(r.parameters)} test results, {len(outside)} outside the printed range" if r.parameters else "A report without a laboratory results table (for example a scan, ECG or summary)")
        events.append(_event(f"report:{r.id}", "REPORT", label, detail, datetime.combine(printed, time(0, 0)) if printed else None, "Report date", src))
        events.append(_event(f"report-upload:{r.id}", "REPORT_UPLOADED", f"Report uploaded: {r.filename}", f"Uploaded by {r.uploader.full_name}", r.uploaded_at, "Uploaded", src))
        if r.doctor_review_status == "REVIEWED" and r.reviewed_at:
            how = {"APPROVED": "approved", "MODIFIED": "modified", "CLARIFIED": "added a clarification to"}.get(r.review_decision or "", "reviewed")
            events.append(_event(f"report-review:{r.id}", "REPORT_REVIEWED", f"Doctor {how} the analysis of {r.filename}", r.review_comment, r.reviewed_at, "Reviewed by the doctor", src))

    for n in db.scalars(select(DoctorNote).where(DoctorNote.patient_id == patient.id)):
        events.append(_event(f"note:{n.id}", "NOTE", f"Doctor's note ({n.priority.replace('_', ' ').lower()})", n.note, n.created_at, "Written",
                             source("note", n.id, "Doctor's note", n.created_at.date().isoformat())))

    for rec in db.scalars(select(DoctorRecommendation).where(DoctorRecommendation.patient_id == patient.id)):
        due = f" Follow-up date: {rec.follow_up_date.isoformat()}." if rec.follow_up_date else ""
        events.append(_event(f"recommendation:{rec.id}", "RECOMMENDATION", f"Recommendation: {rec.title}", rec.recommendation + due, rec.created_at, "Written",
                             source("recommendation", rec.id, "Doctor's recommendation", rec.created_at.date().isoformat())))

    for rx in db.scalars(select(Prescription).where(Prescription.patient_id == patient.id)):
        meds = ", ".join(i.medicine_name for i in rx.items)
        events.append(_event(f"prescription:{rx.id}", "PRESCRIPTION", f"Prescription RX-{rx.id:05d} issued by {rx.doctor.user.full_name}", meds, datetime.combine(rx.prescription_date, time(0, 0)),
                             "Prescription date", source("prescription", rx.id, f"Prescription RX-{rx.id:05d}", rx.prescription_date.isoformat())))
        for d in db.scalars(select(MedicineDispensing).where(MedicineDispensing.prescription_id == rx.id)):
            what = "marked unavailable" if d.quantity_dispensed == 0 else f"{d.quantity_dispensed} dispensed"
            events.append(_event(f"dispensing:{d.id}", "DISPENSING", f"Pharmacy: {d.item.medicine_name} {what}", "The pharmacy handed the medicine over. This does not show that the patient took it.", d.dispensed_at, "Dispensed",
                                 source("prescription", rx.id, f"Prescription RX-{rx.id:05d}", d.dispensed_at.date().isoformat())))

    for h in db.scalars(select(MedicalHistoryEntry).where(MedicalHistoryEntry.patient_id == patient.id)):
        events.append(_event(f"history:{h.id}", "HISTORY", f"History entry: {h.entry_type}", h.description, datetime.combine(h.entry_date, time(0, 0)), "Entry date",
                             source("history", h.id, h.entry_type, h.entry_date.isoformat())))

    for a in db.scalars(select(ClinicalAssessment).where(ClinicalAssessment.patient_id == patient.id)):
        bits = [a.chief_complaint]
        if a.provisional_diagnosis:
            bits.append(f"Doctor's provisional diagnosis: {a.provisional_diagnosis}")
        events.append(_event(f"assessment:{a.id}", "ASSESSMENT", f"Doctor's assessment by {a.doctor.user.full_name}", "; ".join(b for b in bits if b) or None, a.created_at, "Recorded",
                             source("assessment", a.id, "Doctor's assessment", a.created_at.date().isoformat())))

    for e in db.scalars(select(EmergencyEvent).where(EmergencyEvent.patient_id == patient.id)):
        events.append(_event(f"emergency:{e.id}", "EMERGENCY", "Emergency visit", e.chief_complaint, e.event_at, "Event date",
                             source("emergency", e.id, "Emergency visit", e.event_at.date().isoformat() if e.event_at else None)))

    for t in db.scalars(select(FollowUpTask).where(FollowUpTask.patient_id == patient.id)):
        state = {"PENDING": "pending", "DONE": "done", "CANCELLED": "cancelled"}[t.status]
        events.append(_event(f"followup:{t.id}", "FOLLOW_UP", f"Follow-up task ({state}): {t.title}", (f"Due {t.due_date.isoformat()}. " if t.due_date else "") + (t.outcome or ""), t.created_at, "Created",
                             source("follow_up", t.id, "Follow-up task", t.created_at.date().isoformat())))

    if q:
        needle = q.strip().lower()
        events = [e for e in events if needle in e["title"].lower() or needle in (e["detail"] or "").lower() or needle in e["kind"].lower().replace("_", " ")]
    events.sort(key=_sort_value, reverse=True)                      # newest first; events with no date go to the end
    return [e for e in events if e["datetime"]] + [e for e in events if not e["datetime"]]
