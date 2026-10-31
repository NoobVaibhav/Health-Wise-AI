"""Patient records. Reception staff manage basic details; clinical views are limited to the patient and their doctors.
Also holds report comparison and trend charts for one patient."""
import json

import re
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import (
    ADMIN, DOCTOR, EMPLOYEE, PATIENT, doctor_patient_ids, get_accessible_patient, get_doctor_profile,
    get_current_user, require_roles,
)
from app.database.connection import get_db
from app.database.models import Doctor, HealthReport, Patient, ReportComparison, User
from app.schemas.patient import PatientBasic, PatientCreate, PatientCreated, PatientFull, PatientUpdate
from app.services import audit_service, report_service, user_service
from app.services.comparison_engine import compare_reports
from app.services.serializers import patient_basic, patient_for_role, report_list_item
from app.utils.validators import PathId, SearchText

router = APIRouter(prefix="/api/patients", tags=["patients"])
reception = require_roles(EMPLOYEE, ADMIN)


@router.post("", response_model=PatientCreated, status_code=status.HTTP_201_CREATED)
def register_patient(data: PatientCreate, request: Request, user: User = Depends(reception),
                     db: Session = Depends(get_db)):
    patient, temporary = user_service.create_patient(db, data)
    audit_service.log_action(db, user, audit_service.PATIENT_CREATED, "patient", patient.id, request)
    return PatientCreated(patient=patient_basic(patient), temporary_password=temporary)


@router.get("", response_model=list[PatientBasic])
def list_patients(q: SearchText = None, user: User = Depends(require_roles(ADMIN, EMPLOYEE, DOCTOR)),
                  db: Session = Depends(get_db)):
    """Search by name, patient id, phone or email. Doctors only get their own authorized patients."""
    query = select(Patient).join(User, Patient.user_id == User.id).order_by(User.full_name)
    if user.role == DOCTOR:
        ids = doctor_patient_ids(db, get_doctor_profile(db, user))
        query = query.where(Patient.id.in_(ids or {-1}))
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(User.full_name.ilike(like), Patient.patient_code.ilike(like),
                                Patient.phone.ilike(like), User.email.ilike(like)))
    return [patient_basic(p) for p in db.scalars(query)]


@router.get("/{patient_id}", response_model=PatientFull | PatientBasic)
def get_patient(patient_id: PathId, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient = get_accessible_patient(db, user, patient_id, clinical=False)
    return patient_for_role(patient, user.role)


@router.put("/{patient_id}", response_model=PatientBasic)
def update_patient(patient_id: PathId, data: PatientUpdate, request: Request, user: User = Depends(reception),
                   db: Session = Depends(get_db)):
    patient = get_accessible_patient(db, user, patient_id, clinical=False)
    changes = data.model_dump(exclude_unset=True)
    if "assigned_doctor_id" in changes and changes["assigned_doctor_id"] is not None \
            and not db.get(Doctor, changes["assigned_doctor_id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found.")
    if "full_name" in changes and changes["full_name"]:
        patient.user.full_name = changes.pop("full_name").strip()
    changes.pop("full_name", None)
    own = re.sub(r"\D", "", (changes.get("phone") if "phone" in changes else patient.phone) or "")[-10:]
    contact = re.sub(r"\D", "", (changes.get("emergency_contact") if "emergency_contact" in changes else patient.emergency_contact) or "")[-10:]
    if len(own) >= 10 and own == contact:        # the same rule as when a patient is created: the contact is somebody else
        raise HTTPException(422, "The emergency contact must be a different person: it has the patient's own phone number.")
    # Reception staff may update basic details only. Clinical fields are ignored here.
    for clinical_field in ("blood_group", "allergies", "medical_history_text", "current_medications"):
        changes.pop(clinical_field, None)
    for field, value in changes.items():
        setattr(patient, field, value)
    db.commit()
    audit_service.log_action(db, user, audit_service.PATIENT_UPDATED, "patient", patient.id, request)
    return patient_basic(patient)


# ------------------------------------------------------------------ comparison and trends
def _comparable_reports(db: Session, user: User, patient: Patient) -> list[HealthReport]:
    """Oldest first. Patients only get reports that a doctor has already reviewed."""
    reports = report_service.list_reports_for_user(db, user, patient_id=patient.id)
    if user.role == PATIENT:
        reports = [r for r in reports if r.doctor_review_status == "REVIEWED"]
    return list(reversed(reports))


@router.get("/{patient_id}/comparison")
def compare(patient_id: PathId, previous: int | None = None, latest: int | None = None,
            user: User = Depends(require_roles(DOCTOR, PATIENT)), db: Session = Depends(get_db)):
    """Compare two reports of one patient (default: the two newest)."""
    patient = get_accessible_patient(db, user, patient_id)
    reports = _comparable_reports(db, user, patient)
    by_id = {r.id: r for r in reports}
    if previous is None and latest is None:
        if len(reports) < 2:
            return {"available": False, "message": "At least two reports are needed to compare.", "rows": []}
        prev_report, latest_report = reports[-2], reports[-1]
    else:
        prev_report, latest_report = by_id.get(previous), by_id.get(latest)
        if prev_report is None or latest_report is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    rows = compare_reports(prev_report.parameters, latest_report.parameters)
    result = {
        "available": True,
        "previous": report_list_item(prev_report).model_dump(mode="json"),
        "latest": report_list_item(latest_report).model_dump(mode="json"),
        "rows": rows, "matched_count": len(rows),
        "message": None if rows else "These two reports have no parameters in common.",
        "reports": [report_list_item(r).model_dump(mode="json") for r in reports],
    }
    saved = db.scalar(select(ReportComparison).where(
        ReportComparison.patient_id == patient.id, ReportComparison.previous_report_id == prev_report.id,
        ReportComparison.latest_report_id == latest_report.id))
    if saved is None:
        saved = ReportComparison(patient_id=patient.id, previous_report_id=prev_report.id,
                                 latest_report_id=latest_report.id)
        db.add(saved)
    saved.result_json = json.dumps({k: v for k, v in result.items() if k != "reports"})
    db.commit()
    return result


@router.get("/{patient_id}/trends")
def trend_parameters(patient_id: PathId, user: User = Depends(require_roles(DOCTOR, PATIENT)),
                     db: Session = Depends(get_db)):
    patient = get_accessible_patient(db, user, patient_id)
    counts: dict[str, int] = {}
    for report in _comparable_reports(db, user, patient):
        for p in report.parameters:
            counts[p.normalized_name] = counts.get(p.normalized_name, 0) + 1
    return [{"name": name, "points": n} for name, n in sorted(counts.items())]


@router.get("/{patient_id}/trends/{parameter_name}")
def parameter_trend(patient_id: PathId, parameter_name: str, user: User = Depends(require_roles(DOCTOR, PATIENT)),
                    db: Session = Depends(get_db)):
    patient = get_accessible_patient(db, user, patient_id)
    points, unit = [], None
    for report in _comparable_reports(db, user, patient):
        for p in report.parameters:
            if p.normalized_name == parameter_name:
                unit = p.unit or unit
                points.append({"date": report_service.effective_date(report).isoformat(), "value": p.value,
                               "status": p.status, "reference_low": p.reference_low,
                               "reference_high": p.reference_high, "report_id": report.id})
    return {"parameter": parameter_name, "unit": unit, "points": points}
