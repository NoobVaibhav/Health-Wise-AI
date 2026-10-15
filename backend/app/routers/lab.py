"""Tests the doctors have advised. Seen by laboratory staff and hospital employees only.
The pharmacy never receives this information (see prescription_out(include_tests=False))."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import EMPLOYEE, LAB, require_roles
from app.database.connection import get_db
from app.database.models import Prescription, User
from app.services.serializers import tests_of

router = APIRouter(prefix="/api/lab", tags=["lab"])


@router.get("/test-orders")
def test_orders(q: str | None = None, user: User = Depends(require_roles(LAB, EMPLOYEE)),
                db: Session = Depends(get_db)):
    """Newest first. Search by patient name, patient ID, prescription code (RX-00001) or test name."""
    rows = db.scalars(
        select(Prescription).where(Prescription.tests_advised.is_not(None), Prescription.status != "CANCELLED")
        .order_by(Prescription.id.desc()).limit(300)
    ).all()
    result = []
    needle = (q or "").strip().lower()
    for rx in rows:
        tests = tests_of(rx)
        if not tests:
            continue
        code = f"RX-{rx.id:05d}"
        haystack = " ".join([rx.patient.user.full_name, rx.patient.patient_code, code, *tests]).lower()
        if needle and needle not in haystack:
            continue
        result.append({
            "id": rx.id, "code": code, "patient_name": rx.patient.user.full_name,
            "patient_code": rx.patient.patient_code, "doctor_name": rx.doctor.user.full_name,
            "date": rx.prescription_date.isoformat(), "reason": rx.clinical_indication, "tests": tests,
        })
    return result
