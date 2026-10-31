"""The patient registry: duplicate check, consents, insurance, ABHA number and the audited merge of two records.
Reception and the administrator work here; a patient can read their own registry details."""
import json
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import get_accessible_patient, get_current_user
from app.database.connection import get_db
from app.database.models import Patient, PatientConsent, PatientInsurance, PatientMerge, User
from app.schemas.patient import PatientBasic
from app.services import access_service, audit_service, registry_service
from app.services.access_service import require_permission
from app.services.serializers import patient_basic
from app.utils.validators import DateOfBirth, OptionalPhone, PathId, PersonName, PositiveId, opt_text, text

router = APIRouter(prefix="/api/patient-registry", tags=["patient registry"])
REGISTRY_PERMISSIONS = {"patient.search", "patient.register", "consent.manage", "insurance.manage", "abha.manage", "patient.merge"}
ABHA_RE = re.compile(r"^\d{14}$")


class ConsentIn(BaseModel):
    kind: text(20)
    given_by: opt_text(150) = None
    note: opt_text(300) = None


class InsuranceIn(BaseModel):
    insurer_name: text(150, min_length=2)
    tpa_name: opt_text(150) = None
    policy_number: text(60, min_length=2)
    member_id: opt_text(60) = None
    valid_from: date | None = None
    valid_to: date | None = None

    @model_validator(mode="after")
    def dates(self):
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("The policy end date cannot be before its start date.")
        return self


class AbhaIn(BaseModel):
    abha_id: opt_text(30) = None


class MergeIn(BaseModel):
    keep_id: PositiveId
    merge_id: PositiveId
    reason: text(500, min_length=10)


def _patient_for(db: Session, user: User, patient_id: int) -> Patient:
    """Staff with a registry permission see any patient's registry details; everybody else goes through the normal patient scope rules."""
    if access_service.permissions_of(db, user) & REGISTRY_PERMISSIONS:
        patient = db.get(Patient, patient_id)
        if patient is None:
            raise HTTPException(404, "Patient not found.")
        return patient
    return get_accessible_patient(db, user, patient_id, clinical=False)


def _insurance_out(i: PatientInsurance) -> dict:
    return {"id": i.id, "insurer_name": i.insurer_name, "tpa_name": i.tpa_name, "policy_number": i.policy_number, "member_id": i.member_id,
            "valid_from": i.valid_from.isoformat() if i.valid_from else None, "valid_to": i.valid_to.isoformat() if i.valid_to else None, "is_active": i.is_active,
            "expired": bool(i.valid_to and i.valid_to < date.today())}


def _registry_out(db: Session, p: Patient) -> dict:
    consents = db.scalars(select(PatientConsent).where(PatientConsent.patient_id == p.id).order_by(PatientConsent.id.desc())).all()
    insurance = db.scalars(select(PatientInsurance).where(PatientInsurance.patient_id == p.id).order_by(PatientInsurance.id.desc())).all()
    return {"id": p.id, "uhid": p.uhid, "patient_code": p.patient_code, "full_name": p.user.full_name, "branch_id": p.branch_id, "abha_id": p.abha_id,
            "merged_into_id": p.merged_into_id, "consents": [registry_service.consent_out(c) for c in consents], "insurance": [_insurance_out(i) for i in insurance]}


@router.get("/duplicates")
def duplicates(full_name: PersonName | None = None, date_of_birth: DateOfBirth | None = None, phone: OptionalPhone = None, exclude_id: int | None = None,
               _: User = Depends(require_permission("patient.search", "patient.register")), db: Session = Depends(get_db)):
    """Is this person probably already registered? Used by reception before a new registration is saved."""
    return [registry_service.duplicate_out(e) for e in registry_service.find_duplicates(db, full_name, date_of_birth, phone, exclude_id)]


@router.get("/merges")
def merges(_: User = Depends(require_permission("patient.merge")), db: Session = Depends(get_db)):
    rows = db.scalars(select(PatientMerge).order_by(PatientMerge.id.desc()).limit(200)).all()
    out = []
    for m in rows:
        keep, old = db.get(Patient, m.kept_patient_id), db.get(Patient, m.merged_patient_id)
        out.append({"id": m.id, "kept": {"id": keep.id, "uhid": keep.uhid, "full_name": keep.user.full_name}, "merged": {"id": old.id, "uhid": old.uhid, "full_name": old.user.full_name},
                    "reason": m.reason, "merged_at": m.merged_at.isoformat(), "details": json.loads(m.moved_json or "{}")})
    return out


@router.post("/merge", status_code=status.HTTP_201_CREATED)
def merge(data: MergeIn, request: Request, user: User = Depends(require_permission("patient.merge")), db: Session = Depends(get_db)):
    keep, old = db.get(Patient, data.keep_id), db.get(Patient, data.merge_id)
    if keep is None or old is None:
        raise HTTPException(404, "Patient not found.")
    record = registry_service.merge_patients(db, keep, old, user, data.reason)
    audit_service.log_action(db, user, audit_service.PATIENT_MERGED, "patient", keep.id, request, f"{old.uhid} into {keep.uhid}: {data.reason[:150]}")
    return {"id": record.id, "kept_patient_id": keep.id, "merged_patient_id": old.id, "details": json.loads(record.moved_json or "{}")}


@router.get("/{patient_id}")
def registry(patient_id: PathId, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _registry_out(db, _patient_for(db, user, patient_id))


@router.post("/{patient_id}/consents", status_code=status.HTTP_201_CREATED)
def add_consent(patient_id: PathId, data: ConsentIn, request: Request, user: User = Depends(require_permission("consent.manage")), db: Session = Depends(get_db)):
    patient = _patient_for(db, user, patient_id)
    kind = data.kind.upper()
    if kind not in registry_service.CONSENT_KINDS:
        raise HTTPException(422, "The consent must be one of: " + ", ".join(registry_service.CONSENT_KINDS) + ".")
    if registry_service.active_consent(db, patient.id, kind):
        raise HTTPException(409, "This consent has already been given.")
    row = PatientConsent(patient_id=patient.id, kind=kind, recorded_by=user.id, given_by=data.given_by or patient.user.full_name, note=data.note)
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, audit_service.CONSENT_RECORDED, "patient", patient.id, request, kind)
    return registry_service.consent_out(row)


@router.post("/{patient_id}/consents/{consent_id}/withdraw")
def withdraw_consent(patient_id: PathId, consent_id: PathId, request: Request, user: User = Depends(require_permission("consent.manage")), db: Session = Depends(get_db)):
    patient = _patient_for(db, user, patient_id)
    row = db.get(PatientConsent, consent_id)
    if row is None or row.patient_id != patient.id:
        raise HTTPException(404, "Consent not found.")
    if row.withdrawn_at is None:
        row.withdrawn_at, row.withdrawn_by = registry_service.now(), user.id
        if row.kind == "ABHA":
            patient.abha_id = None                                  # the number is removed with the consent
        db.commit()
        audit_service.log_action(db, user, audit_service.CONSENT_WITHDRAWN, "patient", patient.id, request, row.kind)
    return registry_service.consent_out(row)


@router.put("/{patient_id}/abha")
def set_abha(patient_id: PathId, data: AbhaIn, request: Request, user: User = Depends(require_permission("abha.manage")), db: Session = Depends(get_db)):
    """Saves (or clears) the patient's ABHA number. Saving needs an active ABHA consent. Nothing is sent to any ABDM service: this only stores the number."""
    patient = _patient_for(db, user, patient_id)
    if data.abha_id:
        digits = re.sub(r"[\s-]", "", data.abha_id)
        if not ABHA_RE.match(digits):
            raise HTTPException(422, "An ABHA number has 14 digits, for example 12-3456-7890-1234.")
        if not registry_service.active_consent(db, patient.id, "ABHA"):
            raise HTTPException(422, "Please record the patient's ABHA consent first.")
        patient.abha_id = f"{digits[:2]}-{digits[2:6]}-{digits[6:10]}-{digits[10:]}"
    else:
        patient.abha_id = None
    db.commit()
    audit_service.log_action(db, user, audit_service.ABHA_SET, "patient", patient.id, request, "set" if patient.abha_id else "cleared")
    return {"abha_id": patient.abha_id}


@router.post("/{patient_id}/insurance", status_code=status.HTTP_201_CREATED)
def add_insurance(patient_id: PathId, data: InsuranceIn, request: Request, user: User = Depends(require_permission("insurance.manage")), db: Session = Depends(get_db)):
    patient = _patient_for(db, user, patient_id)
    row = PatientInsurance(patient_id=patient.id, created_by=user.id, **data.model_dump())
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, audit_service.INSURANCE_ADDED, "patient", patient.id, request, data.insurer_name[:100])
    return _insurance_out(row)


@router.post("/{patient_id}/insurance/{insurance_id}/deactivate")
def deactivate_insurance(patient_id: PathId, insurance_id: PathId, request: Request, user: User = Depends(require_permission("insurance.manage")), db: Session = Depends(get_db)):
    patient = _patient_for(db, user, patient_id)
    row = db.get(PatientInsurance, insurance_id)
    if row is None or row.patient_id != patient.id:
        raise HTTPException(404, "Insurance not found.")
    row.is_active = False
    db.commit()
    audit_service.log_action(db, user, audit_service.INSURANCE_ADDED, "patient", patient.id, request, "deactivated")
    return _insurance_out(row)
