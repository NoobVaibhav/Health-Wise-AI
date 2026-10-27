"""Audit trail: records who did what, to which record and when (useful for hospital accountability)."""
from fastapi import Request
from sqlalchemy.orm import Session

from app.database.models import AuditLog, User

# Action names used across the application
LOGIN = "LOGIN"
LOGIN_FAILED = "LOGIN_FAILED"
USER_CREATED = "USER_CREATED"
USER_CHANGED = "USER_CHANGED"
USER_DELETED = "USER_DELETED"
PATIENT_CREATED = "PATIENT_CREATED"
PATIENT_UPDATED = "PATIENT_UPDATED"
REPORT_UPLOADED = "REPORT_UPLOADED"
REPORT_ANALYZED = "REPORT_ANALYZED"
REPORT_FILE_VIEWED = "REPORT_FILE_VIEWED"
REPORT_REVIEWED = "REPORT_REVIEWED"
REPORT_DELETED = "REPORT_DELETED"
INSIGHTS_REFRESHED = "INSIGHTS_REFRESHED"
NOTE_ADDED = "NOTE_ADDED"
RECOMMENDATION_ADDED = "RECOMMENDATION_ADDED"
PRESCRIPTION_CREATED = "PRESCRIPTION_CREATED"
PRESCRIPTION_CANCELLED = "PRESCRIPTION_CANCELLED"
PRESCRIPTION_VIEWED = "PRESCRIPTION_VIEWED"
MEDICINE_DISPENSED = "MEDICINE_DISPENSED"
SALE_CREATED = "SALE_CREATED"
PROFILE_UPDATED = "PROFILE_UPDATED"
AVATAR_CHANGED = "AVATAR_CHANGED"
HISTORY_UPDATED = "HISTORY_UPDATED"
HISTORY_VIEWED = "HISTORY_VIEWED"
ASSESSMENT_ADDED = "ASSESSMENT_ADDED"
CLINICAL_SUMMARY_VIEWED = "CLINICAL_SUMMARY_VIEWED"
CLINICAL_SUMMARY_AI = "CLINICAL_SUMMARY_AI"
SUMMARY_REVIEWED = "SUMMARY_REVIEWED"
EMERGENCY_RECORDED = "EMERGENCY_RECORDED"
EMERGENCY_VIEWED = "EMERGENCY_VIEWED"
FOLLOW_UP_CREATED = "FOLLOW_UP_CREATED"
FOLLOW_UP_UPDATED = "FOLLOW_UP_UPDATED"
APPOINTMENT_CREATED = "APPOINTMENT_CREATED"
APPOINTMENT_UPDATED = "APPOINTMENT_UPDATED"


def log_action(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    request: Request | None = None,
    details: str | None = None,
) -> None:
    """Add one audit row and commit it. Never raises: logging must not break the real action."""
    try:
        ip = request.client.host if request and request.client else None
        db.add(AuditLog(user_id=user.id if user else None, action=action, entity_type=entity_type,
                        entity_id=entity_id, details=(details or "")[:300] or None, ip_address=ip))
        db.commit()
    except Exception:
        db.rollback()
