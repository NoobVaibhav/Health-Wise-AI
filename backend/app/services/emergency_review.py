"""Emergency visits: record them, and review them without inventing anything.

What the review shows is only what a doctor recorded. Every statement carries its source. The review keeps four things apart:
- a DOCUMENTED CAUSE (the treating clinician wrote it),
- DOCUMENTED CONTRIBUTING FACTORS (the clinician recorded them as relevant),
- POSSIBLE ASSOCIATIONS (items from the patient's records that a doctor may want to review; NOT established as a cause), and
- UNKNOWN CAUSE (the records do not establish a reason).
Missing information is stated as missing. It is never read as proof that something did not happen."""
import json

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import EmergencyEvent, EmergencyTimelineEntry, HealthReport, Patient
from app.schemas.clinical_intel import EmergencyIn
from app.services import health_history_service
from app.services.clinical_timeline import source
from app.services.history_insights import points_to_check

NO_EMERGENCY = "No emergency encounter was found in the records currently available to this system."
NO_RESPONSE = "No documented treatment response was found in the available records."
NO_ASSESSMENT = "The final clinical assessment was not available in the reviewed records."
NO_CAUSE = "Cause: not established in the available records."
NO_DATE = "Date not recorded"


def _json(value) -> str | None:
    return json.dumps(value) if value else None


def create(db: Session, patient: Patient, doctor, data: EmergencyIn) -> EmergencyEvent:
    if data.source_report_ids:
        owned = set(db.scalars(select(HealthReport.id).where(HealthReport.patient_id == patient.id, HealthReport.id.in_(data.source_report_ids))))
        if owned != set(data.source_report_ids):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "A report you linked was not found for this patient.")
    vitals = {k: v for k, v in data.vitals.model_dump().items() if v is not None}
    event = EmergencyEvent(
        patient_id=patient.id, recorded_by=doctor.id, event_at=data.event_at, arrival_method=data.arrival_method, chief_complaint=data.chief_complaint,
        symptoms_json=_json(data.symptoms), onset_text=data.onset_text, duration_text=data.duration_text, vitals_json=_json(vitals),
        recent_medication_changes=data.recent_medication_changes, exam_findings=data.exam_findings, investigations_ordered=data.investigations_ordered,
        investigation_results=data.investigation_results, clinician_assessment=data.clinician_assessment, documented_cause=data.documented_cause,
        contributing_json=_json(data.contributing_factors), treatment_given=data.treatment_given, response_to_treatment=data.response_to_treatment,
        disposition=data.disposition, discharge_instructions=data.discharge_instructions, follow_up_recommendations=data.follow_up_recommendations,
        treating_clinician=data.treating_clinician, source_report_ids_json=_json(data.source_report_ids))
    for entry in data.timeline:
        event.timeline.append(EmergencyTimelineEntry(occurred_at=entry.occurred_at, kind=entry.kind, text=entry.text, recorded_by=doctor.id))
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_for_patient(db: Session, patient: Patient, event_id: int) -> EmergencyEvent:
    event = db.get(EmergencyEvent, event_id)
    if event is None or event.patient_id != patient.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency record not found.")
    return event


def _stmt(key: str, label: str, text: str, src: dict) -> dict:
    return {"key": key, "label": label, "text": text, "source": src}


def review(db: Session, patient: Patient, event: EmergencyEvent) -> dict:
    day = event.event_at.date().isoformat() if event.event_at else None
    src = source("emergency", event.id, "Emergency visit", day)
    D, M = "DIRECTLY_DOCUMENTED", "INSUFFICIENT_INFORMATION"
    k = lambda name: f"emergency:{event.id}:{name}"
    history = health_history_service.load_history(db, patient)
    vitals = json.loads(event.vitals_json) if event.vitals_json else {}
    symptoms = json.loads(event.symptoms_json) if event.symptoms_json else []
    contributing = json.loads(event.contributing_json) if event.contributing_json else []
    entries = [{"id": t.id, "time": t.occurred_at.isoformat(), "kind": t.kind, "text": t.text} for t in event.timeline]

    s = []
    s.append(_stmt(k("reason"), D, f"Reason for presentation: {event.chief_complaint}.", src) if event.chief_complaint else _stmt(k("reason"), M, "The reason for presentation was not recorded.", src))
    if symptoms:
        s.append(_stmt(k("symptoms"), D, "Symptoms recorded: " + ", ".join(symptoms) + (f" (onset: {event.onset_text})" if event.onset_text else "") + (f" (duration: {event.duration_text})" if event.duration_text else "") + ".", src))
    elif event.onset_text or event.duration_text:
        s.append(_stmt(k("symptoms"), D, f"Symptom onset: {event.onset_text or 'not recorded'}; duration: {event.duration_text or 'not recorded'}.", src))
    if vitals:
        names = {"pulse": "pulse {} per min", "bp_systolic": "BP top {} mmHg", "bp_diastolic": "BP bottom {} mmHg", "spo2": "SpO2 {}%", "temperature_f": "temperature {} F", "resp_rate": "breathing rate {} per min"}
        s.append(_stmt(k("vitals"), D, "Vital signs recorded: " + ", ".join(names[x].format(v) for x, v in vitals.items() if x in names) + ".", src))
    else:
        s.append(_stmt(k("vitals"), M, "No vital signs were recorded for this visit.", src))
    if history.get("conditions"):
        s.append(_stmt(k("history"), D, "Documented medical history: " + ", ".join(c["name"] + (f" (since {c['since']})" if c.get("since") else "") for c in history["conditions"]) + ".", source("history", patient.id, "Medical history")))
    if history.get("allergies"):
        s.append(_stmt(k("allergies"), D, "Documented allergies: " + ", ".join(a["name"] for a in history["allergies"]) + ".", source("history", patient.id, "Medical history")))
    current = [m["name"] for m in history.get("medications", []) if m.get("is_current", True)]
    if current:
        s.append(_stmt(k("medicines"), D, "Medicines documented in the patient's history: " + ", ".join(current) + ".", source("history", patient.id, "Medical history")))
    if event.recent_medication_changes:
        s.append(_stmt(k("medchanges"), D, f"Recent medication changes recorded: {event.recent_medication_changes}", src))
    if event.exam_findings:
        s.append(_stmt(k("exam"), D, f"Examination findings recorded: {event.exam_findings}", src))
    if event.investigations_ordered:
        s.append(_stmt(k("ordered"), D, f"Investigations ordered: {event.investigations_ordered}", src))
    if event.investigation_results:
        s.append(_stmt(k("results"), D, f"Investigation results recorded: {event.investigation_results}", src))
    s.append(_stmt(k("assessment"), D, f"Clinician-documented assessment: {event.clinician_assessment}", src) if event.clinician_assessment else _stmt(k("assessment"), M, NO_ASSESSMENT, src))
    s.append(_stmt(k("treatment"), D, f"Treatment recorded: {event.treatment_given}", src) if event.treatment_given else _stmt(k("treatment"), M, "No treatment was recorded for this visit.", src))
    s.append(_stmt(k("response"), D, f"Documented response to treatment: {event.response_to_treatment}", src) if event.response_to_treatment else _stmt(k("response"), M, NO_RESPONSE, src))
    if event.disposition:
        s.append(_stmt(k("disposition"), D, f"Outcome of the visit: {event.disposition.title()}.", src))
    else:
        s.append(_stmt(k("disposition"), M, "No admission, transfer or discharge decision was recorded.", src))
    if event.discharge_instructions:
        s.append(_stmt(k("discharge"), D, f"Discharge instructions: {event.discharge_instructions}", src))
    if event.follow_up_recommendations:
        s.append(_stmt(k("followup"), D, f"Follow-up recommended: {event.follow_up_recommendations}", src))
    if event.treating_clinician:
        s.append(_stmt(k("clinician"), D, f"Treating clinician: {event.treating_clinician}.", src))

    # --- cause: documented, contributing, possible, unknown. Nothing here is a conclusion by the computer.
    possible = []
    points = points_to_check({**history, "current_problem": {"complaint": event.chief_complaint, "symptoms": symptoms, "details": None}}, health_history_service.age_of(patient), vitals)
    for p in points:
        if p["category"] in ("medicine", "condition", "vitals", "safety", "habit"):
            possible.append({"title": p["title"], "text": p["detail"], "label": "REQUIRES_CLINICIAN_VERIFICATION"})
    cause = {
        "documented_cause": event.documented_cause, "documented_contributing": contributing, "possible_associations": possible,
        "unknown": not event.documented_cause,
        "text": f"Documented cause: {event.documented_cause}" if event.documented_cause else NO_CAUSE,
        "note": "Possible associations are items from the patient's records that a doctor may want to review. They are not established as the cause of this event, and a temporal or statistical link alone does not prove causation.",
        "source": src,
    }

    gaps = []
    if not event.event_at:
        gaps.append("The date and time of the visit were not recorded.")
    if not entries:
        gaps.append("No timestamped timeline entries were recorded, so the sequence of events cannot be reconstructed.")
    else:
        kinds = {e["kind"] for e in entries}
        for need, text in (("ARRIVAL", "No arrival entry was recorded."), ("ASSESSMENT", "No assessment entry was recorded on the timeline."), ("DISPOSITION", "No disposition entry was recorded on the timeline.")):
            if need not in kinds:
                gaps.append(text)
    if not event.clinician_assessment:
        gaps.append(NO_ASSESSMENT)
    if not event.response_to_treatment:
        gaps.append(NO_RESPONSE)
    if not event.treatment_given:
        gaps.append("No treatment was recorded for this visit.")
    if not vitals:
        gaps.append("No vital signs were recorded.")
    if not event.disposition:
        gaps.append("No admission, transfer or discharge decision was recorded.")
    reports = []
    if event.source_report_ids_json:
        for r in db.scalars(select(HealthReport).where(HealthReport.id.in_(json.loads(event.source_report_ids_json)))):
            reports.append(source("report", r.id, f"Report: {r.filename}", r.report_date.isoformat() if r.report_date else None))
    return {"id": event.id, "event_at": event.event_at.isoformat() if event.event_at else None, "date_note": None if event.event_at else NO_DATE,
            "arrival_method": event.arrival_method, "recorded_by": event.recorder.user.full_name, "recorded_at": event.created_at.isoformat(),
            "timeline": entries, "timeline_complete": not any("timeline" in g or "entry" in g for g in gaps),
            "timeline_note": None if entries else "The timeline is incomplete: no timestamped entries were recorded.",
            "what_happened": s, "cause": cause, "missing": gaps, "source_reports": reports, "source": src,
            "labels": {"DIRECTLY_DOCUMENTED": "Directly documented", "INSUFFICIENT_INFORMATION": "Insufficient information", "REQUIRES_CLINICIAN_VERIFICATION": "Requires clinician verification"}}


def list_events(db: Session, patient: Patient) -> dict:
    events = db.scalars(select(EmergencyEvent).where(EmergencyEvent.patient_id == patient.id)).all()
    events.sort(key=lambda e: (e.event_at is None, -(e.event_at.timestamp() if e.event_at else 0)))
    if not events:
        return {"events": [], "message": NO_EMERGENCY}
    return {"events": [{"id": e.id, "event_at": e.event_at.isoformat() if e.event_at else None, "date_note": None if e.event_at else NO_DATE, "chief_complaint": e.chief_complaint,
                        "disposition": e.disposition, "has_assessment": bool(e.clinician_assessment), "has_response": bool(e.response_to_treatment),
                        "treating_clinician": e.treating_clinician, "source": source("emergency", e.id, "Emergency visit", e.event_at.date().isoformat() if e.event_at else None)} for e in events],
            "message": None}
