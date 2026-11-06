"""Follow-up tracking: what must still happen for this patient, and what has no documented completion.

Three kinds of item, each with its source:
- TASKS a doctor created (title, due date, status, outcome);
- RECOMMENDATIONS with a follow-up date that no task and no completed appointment covers: shown as "no documented completion"
  (that is not proof that it did not happen);
- INVESTIGATIONS advised in a doctor's assessment, with no report uploaded since: shown the same careful way."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Appointment, ClinicalAssessment, DoctorRecommendation, FollowUpTask, HealthReport, Patient
from app.services.clinical_timeline import source
from app.utils.clock import hospital_now, hospital_today


def _task(t: FollowUpTask, today: date) -> dict:
    overdue = t.status == "PENDING" and t.due_date is not None and t.due_date < today
    return {"id": t.id, "title": t.title, "details": t.details, "due_date": t.due_date.isoformat() if t.due_date else None, "status": t.status,
            "overdue": overdue, "completed_at": t.completed_at.isoformat() if t.completed_at else None, "outcome": t.outcome,
            "created_by": t.creator.user.full_name, "created_at": t.created_at.isoformat(),
            "origin": {"type": t.source_type, "id": t.source_id} if t.source_type else None, "source": source("follow_up", t.id, "Follow-up task", t.created_at.date().isoformat())}


def build(db: Session, patient: Patient) -> dict:
    today, now = hospital_today(), hospital_now()
    tasks = db.scalars(select(FollowUpTask).where(FollowUpTask.patient_id == patient.id).order_by(FollowUpTask.due_date.is_(None), FollowUpTask.due_date, FollowUpTask.id)).all()
    task_rows = [_task(t, today) for t in tasks]
    covered = {(t.source_type, t.source_id) for t in tasks if t.source_type}

    derived = []
    completed_visits = [a.scheduled_at for a in db.scalars(select(Appointment).where(Appointment.patient_id == patient.id, Appointment.status == "COMPLETED"))]
    for rec in db.scalars(select(DoctorRecommendation).where(DoctorRecommendation.patient_id == patient.id, DoctorRecommendation.follow_up_date.is_not(None))):
        if ("recommendation", rec.id) in covered:
            continue
        due = rec.follow_up_date
        done = any(v.date() >= rec.created_at.date() and v.date() >= due for v in completed_visits)
        if done:
            continue
        derived.append({"kind": "RECOMMENDATION", "title": rec.title, "due_date": due.isoformat(), "overdue": due < today,
                        "text": f"Follow-up was recommended for {due.isoformat()}" + ("; no completed visit on or after that date is documented." if due < today else "."),
                        "source": source("recommendation", rec.id, "Doctor's recommendation", rec.created_at.date().isoformat())})

    uploaded = [r.uploaded_at for r in db.scalars(select(HealthReport).where(HealthReport.patient_id == patient.id))]
    for a in db.scalars(select(ClinicalAssessment).where(ClinicalAssessment.patient_id == patient.id).order_by(ClinicalAssessment.created_at)):
        if a.investigations_advised and not any(u > a.created_at for u in uploaded) and ("assessment", a.id) not in covered:
            derived.append({"kind": "INVESTIGATION", "title": f"Investigations advised: {a.investigations_advised}", "due_date": None, "overdue": False,
                            "text": f"Advised on {a.created_at.date().isoformat()}; no report has been uploaded since then.",
                            "source": source("assessment", a.id, "Doctor's assessment", a.created_at.date().isoformat())})

    upcoming = [{"id": a.id, "scheduled_at": a.scheduled_at.isoformat(), "doctor": a.doctor.user.full_name, "reason": a.reason, "status": a.status,
                 "source": source("appointment", a.id, "Appointment", a.scheduled_at.date().isoformat())}
                for a in db.scalars(select(Appointment).where(Appointment.patient_id == patient.id, Appointment.status.in_(["SCHEDULED", "CONFIRMED"]), Appointment.scheduled_at >= now).order_by(Appointment.scheduled_at))]
    pending = [t for t in task_rows if t["status"] == "PENDING"]
    return {"tasks": task_rows, "derived": derived, "upcoming_appointments": upcoming,
            "pending_count": len(pending) + len(derived), "overdue_count": sum(1 for t in pending if t["overdue"]) + sum(1 for d in derived if d["overdue"])}
