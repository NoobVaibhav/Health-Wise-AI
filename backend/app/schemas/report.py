from datetime import date, datetime

from pydantic import BaseModel, field_validator
from app.utils.validators import PositiveId, opt_text


class ParameterOut(BaseModel):
    id: int
    test_name: str
    normalized_name: str
    value: float
    unit: str | None
    reference_text: str | None
    reference_low: float | None
    reference_high: float | None
    status: str
    status_label: str
    ai_explanation: dict


class ReportListItem(BaseModel):
    id: int
    patient_id: PositiveId
    patient_name: str
    patient_code: str
    filename: str
    report_date: date | None
    uploaded_at: datetime
    uploaded_by_name: str
    uploaded_by_id: PositiveId
    parameter_count: int
    processing_status: str
    doctor_review_status: str
    display_status: str          # WAITING_FOR_DOCTOR / DOCTOR_REVIEWED
    assigned_doctor_name: str | None
    processing_method: str | None
    report_type: str
    report_type_label: str


class ReportDetail(ReportListItem):
    """Full report. `parameters` / `ai_summary` are hidden from patients until a doctor has reviewed the report."""
    analysis_visible: bool
    is_narrative: bool                  # True for scans, ECGs, summaries ... (no lab table)
    insights: dict | None               # doctor: suggestions + red flags + tips; patient: tips only (after review)
    ai_summary: str | None
    counts: dict[str, int]
    parameters: list[ParameterOut]
    review_decision: str | None
    review_comment: str | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    disclaimer: str
    warnings: list[str] = []


class ReviewRequest(BaseModel):
    decision: str            # APPROVED / MODIFIED / CLARIFIED
    comment: opt_text(2000, multiline=True) = None

    @field_validator("decision")
    @classmethod
    def _decision(cls, value):
        v = (value or "").strip().upper()
        if v not in ("APPROVED", "MODIFIED", "CLARIFIED"):
            raise ValueError("The decision must be APPROVED, MODIFIED or CLARIFIED.")
        return v
