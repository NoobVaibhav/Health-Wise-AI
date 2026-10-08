"""Patient medical history timeline.

The timeline is BUILT FROM THE DATABASE every time (appointments, reports, reviews, notes, recommendations,
prescriptions, dispensing, doctor history entries). Nothing here is hard-coded.
"""
from datetime import datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import PATIENT
from app.database.models import (
    Appointment, DoctorNote, DoctorRecommendation, HealthReport, MedicalHistoryEntry, MedicineDispensing,
    Patient, Prescription,
)


def _event(when: datetime, kind: str, title: str, detail: str | None, entity_type: str, entity_id: int,
           source: str) -> dict:
    """source says WHO produced the item: AI / DOCTOR / SYSTEM / PHARMACY / HOSPITAL (kept visible in the UI)."""
    return {"timestamp": when.isoformat(), "date": when.date().isoformat(), "type": kind, "title": title,
            "detail": detail, "entity_type": entity_type, "entity_id": entity_id, "source": source}


def build_timeline(db: Session, patient: Patient, viewer_role: str, q: str | None = None) -> list[dict]:
    events: list[dict] = []
    for_patient = viewer_role == PATIENT

    for a in db.scalars(select(Appointment).where(Appointment.patient_id == patient.id)):
        events.append(_event(a.scheduled_at, "APPOINTMENT", f"Appointment ({a.status.title()})",
                             f"With {a.doctor.user.full_name}" + (f": {a.reason}" if a.reason else ""),
                             "appointment", a.id, "HOSPITAL"))

    for r in db.scalars(select(HealthReport).where(HealthReport.patient_id == patient.id)):
        events.append(_event(r.uploaded_at, "REPORT_UPLOADED", "Laboratory report uploaded", r.filename,
                             "report", r.id, "HOSPITAL"))
        reviewed = r.doctor_review_status == "REVIEWED"
        if not for_patient or reviewed:  # patients see the AI step only after the doctor reviewed the report
            events.append(_event(r.uploaded_at, "AI_ANALYSIS", "AI analysis completed",
                                 f"{len(r.parameters)} parameters analyzed ({r.filename})", "report", r.id, "AI"))
        if reviewed and r.reviewed_at:
            detail = {"APPROVED": "Doctor approved the AI analysis", "MODIFIED": "Doctor modified the AI analysis",
                      "CLARIFIED": "Doctor added a clarification"}.get(r.review_decision or "", "Reviewed")
            events.append(_event(r.reviewed_at, "DOCTOR_REVIEW", "Reviewed by Doctor",
                                 f"{detail} - {r.reviewer.user.full_name}" if r.reviewer else detail,
                                 "report", r.id, "DOCTOR"))

    for n in db.scalars(select(DoctorNote).where(DoctorNote.patient_id == patient.id)):
        events.append(_event(n.created_at, "DOCTOR_NOTE", f"Doctor's Note ({n.priority.replace('_', ' ').title()})",
                             n.note, "note", n.id, "DOCTOR"))

    for rec in db.scalars(select(DoctorRecommendation).where(DoctorRecommendation.patient_id == patient.id)):
        follow = f" (follow-up {rec.follow_up_date})" if rec.follow_up_date else ""
        events.append(_event(rec.created_at, "RECOMMENDATION", f"Doctor's Recommendation: {rec.title}",
                             rec.recommendation + follow, "recommendation", rec.id, "DOCTOR"))

    for rx in db.scalars(select(Prescription).where(Prescription.patient_id == patient.id)):
        medicines = ", ".join(i.medicine_name for i in rx.items)
        events.append(_event(datetime.combine(rx.prescription_date, time(12, 0)), "PRESCRIPTION",
                             f"Prescription RX-{rx.id:05d} created", f"{medicines} - {rx.doctor.user.full_name}",
                             "prescription", rx.id, "DOCTOR"))
        for d in db.scalars(select(MedicineDispensing).where(MedicineDispensing.prescription_id == rx.id)):
            label = "marked unavailable" if d.quantity_dispensed == 0 else f"dispensed ({d.quantity_dispensed})"
            events.append(_event(d.dispensed_at, "DISPENSING", f"Medicine {label}",
                                 f"{d.item.medicine_name} - {d.status.replace('_', ' ').title()}",
                                 "prescription", rx.id, "PHARMACY"))

    for h in db.scalars(select(MedicalHistoryEntry).where(MedicalHistoryEntry.patient_id == patient.id)):
        events.append(_event(datetime.combine(h.entry_date, time(0, 0)), "HISTORY_ENTRY", h.entry_type,
                             h.description, "history", h.id, "DOCTOR"))

    if q:
        needle = q.strip().lower()
        events = [e for e in events if needle in e["title"].lower() or needle in (e["detail"] or "").lower()
                  or needle in e["type"].lower()]
    events.sort(key=lambda e: e["timestamp"], reverse=True)  # newest first
    return events
