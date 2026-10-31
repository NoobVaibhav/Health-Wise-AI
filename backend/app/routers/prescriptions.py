"""Prescriptions: only doctors create them. Patients, doctors and the pharmacy can read (within their permissions)."""
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, PATIENT, PHARMACY, get_doctor_profile, require_roles
from app.database.connection import get_db
from app.database.models import User
from app.schemas.prescription import PrescriptionCreate, PrescriptionOut
from app.services import audit_service, prescription_service
from app.services.serializers import prescription_out
from app.utils.validators import PathId, QueryId, SearchText

router = APIRouter(prefix="/api/prescriptions", tags=["prescriptions"])


@router.post("", response_model=PrescriptionOut, status_code=status.HTTP_201_CREATED)
def create_prescription(data: PrescriptionCreate, request: Request, user: User = Depends(require_roles(DOCTOR)),
                        db: Session = Depends(get_db)):
    """Only an authorized doctor can prescribe. The system never chooses or suggests the medicine."""
    doctor = get_doctor_profile(db, user)
    rx = prescription_service.create_prescription(db, doctor, data)
    audit_service.log_action(db, user, audit_service.PRESCRIPTION_CREATED, "prescription", rx.id, request)
    out = prescription_out(rx)
    names = [" ".join(i.medicine_name.lower().split()) for i in data.items]
    twice = sorted({n for n in names if names.count(n) > 1})
    if twice:                                          # a warning, not an error: the doctor may mean it (two strengths, morning and night)
        out.warnings = [f"{n.title()} is on this prescription more than once. Please check that this is what you meant." for n in twice]
    return out


@router.get("", response_model=list[PrescriptionOut])
def list_prescriptions(q: SearchText = None, patient_id: QueryId = None,
                       user: User = Depends(require_roles(DOCTOR, PATIENT, PHARMACY)),
                       db: Session = Depends(get_db)):
    rows = prescription_service.list_prescriptions_for_user(db, user, q, patient_id)
    return [prescription_out(r, include_tests=user.role != PHARMACY) for r in rows]


@router.get("/{prescription_id}", response_model=PrescriptionOut)
def get_prescription(prescription_id: PathId, request: Request,
                     user: User = Depends(require_roles(DOCTOR, PATIENT, PHARMACY)),
                     db: Session = Depends(get_db)):
    rx = prescription_service.get_prescription_for_user(db, user, prescription_id)
    if user.role == PHARMACY:
        audit_service.log_action(db, user, audit_service.PRESCRIPTION_VIEWED, "prescription", rx.id, request)
    return prescription_out(rx, include_tests=user.role != PHARMACY)


@router.put("/{prescription_id}/cancel", response_model=PrescriptionOut)
def cancel_prescription(prescription_id: PathId, request: Request, user: User = Depends(require_roles(DOCTOR)),
                        db: Session = Depends(get_db)):
    rx = prescription_service.get_prescription_for_user(db, user, prescription_id)
    prescription_service.cancel_prescription(db, rx)
    audit_service.log_action(db, user, audit_service.PRESCRIPTION_CANCELLED, "prescription", rx.id, request)
    return prescription_out(rx)
