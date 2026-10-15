"""Convert database rows into the response schemas (adds names, labels and role-specific hiding)."""
import json
from datetime import timedelta

from app.core.permissions import ADMIN, DOCTOR, EMPLOYEE, PATIENT
from app.database.models import (
    Appointment, DoctorNote, DoctorRecommendation, HealthParameter, HealthReport, Patient, Prescription,
)
from app.schemas.appointment import AppointmentOut
from app.schemas.doctor import NoteOut, RecommendationOut
from app.schemas.patient import PatientBasic, PatientFull
from app.schemas.prescription import PrescriptionItemOut, PrescriptionOut
from app.schemas.report import ParameterOut, ReportDetail, ReportListItem
from app.services.analysis_engine import STATUS_LABELS
from app.services.insight_service import (REPORT_TYPE_LABELS, LabItem, build_lab_insights, build_narrative_insights,
                                          detect_report_type, extract_metrics)
from app.services.parameter_catalog import get_parameter_info
from app.services.safety_filter import DISCLAIMER
from app.services.user_service import age_from_dob

PRESCRIPTION_VALID_DAYS = 30


# ------------------------------------------------------------------ patients
def patient_basic(p: Patient) -> PatientBasic:
    return PatientBasic(
        id=p.id, patient_code=p.patient_code, full_name=p.user.full_name, email=p.user.email,
        date_of_birth=p.date_of_birth, age=age_from_dob(p.date_of_birth), gender=p.gender, phone=p.phone,
        address=p.address, emergency_contact=p.emergency_contact, assigned_doctor_id=p.assigned_doctor_id,
        assigned_doctor_name=p.assigned_doctor.user.full_name if p.assigned_doctor else None,
        is_active=p.user.is_active,
    )


def patient_for_role(p: Patient, role: str) -> PatientBasic | PatientFull:
    """Employees and admins get basic information only; patient and doctors get the clinical details too."""
    basic = patient_basic(p)
    if role in (ADMIN, EMPLOYEE):
        return basic
    return PatientFull(**basic.model_dump(), blood_group=p.blood_group, allergies=p.allergies,
                       medical_history_text=p.medical_history_text, current_medications=p.current_medications)


# ------------------------------------------------------------------ reports
def display_status(report: HealthReport) -> str:
    return "DOCTOR_REVIEWED" if report.doctor_review_status == "REVIEWED" else "WAITING_FOR_DOCTOR"


def effective_report_type(r: HealthReport) -> str:
    """Reports saved before the insights feature have no type: lab if they have lab values, otherwise 'other'."""
    return r.report_type or ("LAB" if r.parameters else "OTHER")


def report_list_item(r: HealthReport) -> ReportListItem:
    kind = effective_report_type(r)
    return ReportListItem(
        id=r.id, patient_id=r.patient_id, patient_name=r.patient.user.full_name, patient_code=r.patient.patient_code,
        filename=r.filename, report_date=r.report_date, uploaded_at=r.uploaded_at,
        uploaded_by_name=r.uploader.full_name, uploaded_by_id=r.uploaded_by, parameter_count=len(r.parameters),
        processing_status=r.processing_status, doctor_review_status=r.doctor_review_status,
        display_status=display_status(r), processing_method=r.processing_method,
        assigned_doctor_name=r.assigned_doctor.user.full_name if r.assigned_doctor else None,
        report_type=kind, report_type_label=REPORT_TYPE_LABELS.get(kind, "Medical report"),
    )


def stored_insights(r: HealthReport) -> dict | None:
    """The insights saved with the report. Older lab reports have none, so they are built now from the stored values."""
    if r.insights_json:
        data = json.loads(r.insights_json)
        if "metrics" not in data and not r.parameters and r.extracted_text:
            # saved before 'key numbers' existed: read the numbers now (and re-read the sentences unless an AI model wrote them)
            if data.get("source") == "llm":
                data["metrics"] = extract_metrics(r.extracted_text)
            else:
                data = build_narrative_insights(r.extracted_text, data.get("report_type") or detect_report_type(r.extracted_text))
        return data
    if r.parameters:
        items = []
        for p in r.parameters:
            info = get_parameter_info(p.normalized_name)
            items.append(LabItem(p.normalized_name, info.category if info else None, p.status, p.value, p.unit,
                                 p.reference_low, p.reference_high))
        return build_lab_insights(items)
    return None


PATIENT_INSIGHT_KEYS = ("report_type", "source", "summary", "key_findings", "metrics", "patient_recommendations")


def insights_for_role(r: HealthReport, role: str) -> dict | None:
    """Doctors get everything (including red flags and suggestions for the doctor). Patients get a safe subset and only
    after a doctor has reviewed the report. Employees and admins get none."""
    insights = stored_insights(r)
    if insights is None:
        return None
    if role == DOCTOR:
        return insights
    if role == PATIENT and r.doctor_review_status == "REVIEWED":
        return {key: insights[key] for key in PATIENT_INSIGHT_KEYS if key in insights}
    return None


def parameter_out(p: HealthParameter) -> ParameterOut:
    return ParameterOut(
        id=p.id, test_name=p.test_name, normalized_name=p.normalized_name, value=p.value, unit=p.unit,
        reference_text=p.reference_text, reference_low=p.reference_low, reference_high=p.reference_high,
        status=p.status, status_label=STATUS_LABELS.get(p.status, p.status),
        ai_explanation=json.loads(p.ai_explanation) if p.ai_explanation else {},
    )


def analysis_visible_to(role: str, report: HealthReport) -> bool:
    """Patients only see AI analysis once a doctor has reviewed it. Admin/employee never see clinical values."""
    if role == PATIENT:
        return report.doctor_review_status == "REVIEWED"
    return role not in (ADMIN, EMPLOYEE)


def report_detail(r: HealthReport, role: str, warnings: list[str] | None = None) -> ReportDetail:
    visible = analysis_visible_to(role, r)
    counts = {"WITHIN_RANGE": 0, "ABOVE_RANGE": 0, "BELOW_RANGE": 0, "UNKNOWN": 0}
    if visible:
        for p in r.parameters:
            counts[p.status] = counts.get(p.status, 0) + 1
    reviewer = r.reviewer
    return ReportDetail(
        **report_list_item(r).model_dump(),
        analysis_visible=visible,
        is_narrative=effective_report_type(r) != "LAB" and not r.parameters,
        insights=insights_for_role(r, role),
        ai_summary=r.ai_summary if visible else None,
        counts=counts,
        parameters=[parameter_out(p) for p in r.parameters] if visible else [],
        review_decision=r.review_decision, review_comment=r.review_comment,
        reviewed_by_name=reviewer.user.full_name if reviewer else None, reviewed_at=r.reviewed_at,
        disclaimer=DISCLAIMER, warnings=warnings or [],
    )


# ------------------------------------------------------------------ appointments
def appointment_out(a: Appointment) -> AppointmentOut:
    return AppointmentOut(
        id=a.id, patient_id=a.patient_id, patient_name=a.patient.user.full_name,
        patient_code=a.patient.patient_code, doctor_id=a.doctor_id, doctor_name=a.doctor.user.full_name,
        department_name=a.department.name if a.department else (
            a.doctor.department.name if a.doctor.department else None),
        scheduled_at=a.scheduled_at, reason=a.reason, status=a.status,
    )


# ------------------------------------------------------------------ doctor content
def note_out(n: DoctorNote) -> NoteOut:
    return NoteOut(id=n.id, patient_id=n.patient_id, patient_name=n.patient.user.full_name,
                   doctor_name=n.doctor.user.full_name, report_id=n.report_id, note=n.note,
                   priority=n.priority, created_at=n.created_at)


def recommendation_out(r: DoctorRecommendation) -> RecommendationOut:
    return RecommendationOut(
        id=r.id, patient_id=r.patient_id, patient_name=r.patient.user.full_name, doctor_name=r.doctor.user.full_name,
        report_id=r.report_id, title=r.title, recommendation=r.recommendation, follow_up_date=r.follow_up_date,
        priority=r.priority, created_at=r.created_at,
    )


# ------------------------------------------------------------------ prescriptions
def dispensed_quantity(item) -> int:
    return sum(d.quantity_dispensed for d in item.dispensings)


def effective_status(rx: Prescription) -> str:
    """Stored status, except that an old prescription with medicine still undispensed counts as EXPIRED."""
    from datetime import date
    if rx.status in ("ACTIVE", "PARTIALLY_DISPENSED") and date.today() > rx.prescription_date + timedelta(
            days=PRESCRIPTION_VALID_DAYS):
        return "EXPIRED"
    return rx.status


def tests_of(rx: Prescription) -> list[str]:
    return [line.strip() for line in (rx.tests_advised or "").splitlines() if line.strip()]


def prescription_out(rx: Prescription, include_tests: bool = True) -> PrescriptionOut:
    items = []
    for it in rx.items:
        done = dispensed_quantity(it)
        items.append(PrescriptionItemOut(
            id=it.id, medicine_name=it.medicine_name, dosage=it.dosage, frequency=it.frequency,
            duration=it.duration, quantity=it.quantity, instructions=it.instructions,
            dispense_status=it.dispense_status, dispensed_quantity=done,
            remaining_quantity=max(it.quantity - done, 0),
        ))
    return PrescriptionOut(
        id=rx.id, code=f"RX-{rx.id:05d}", patient_id=rx.patient_id, patient_name=rx.patient.user.full_name,
        patient_code=rx.patient.patient_code, doctor_id=rx.doctor_id, doctor_name=rx.doctor.user.full_name,
        report_id=rx.report_id, prescription_date=rx.prescription_date,
        valid_until=rx.prescription_date + timedelta(days=PRESCRIPTION_VALID_DAYS),
        clinical_indication=rx.clinical_indication, notes=rx.notes, status=effective_status(rx), items=items,
        tests=tests_of(rx) if include_tests else [],
    )
