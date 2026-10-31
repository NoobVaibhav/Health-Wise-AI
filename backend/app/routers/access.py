"""Roles, permissions and emergency (break-glass) access."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, get_doctor_profile
from app.database.connection import get_db
from app.database.models import BreakGlassGrant, Patient, Role, User, UserRole
from app.services import access_service, audit_service, hospital_service
from app.services.access_service import require_permission
from app.utils.validators import PathId, PositiveId, opt_text, text

router = APIRouter(prefix="/api/access", tags=["access"])
role_admin = require_permission("role.manage")


class RolePermissionsIn(BaseModel):
    permissions: list[text(60)]


class UserRolesIn(BaseModel):
    roles: list[text(40)]


class BreakGlassIn(BaseModel):
    patient_id: PositiveId
    reason: text(500, min_length=10)


class ReviewIn(BaseModel):
    note: opt_text(500) = None


# ------------------------------------------------------------------ roles
@router.get("/permissions")
def permissions(_: User = Depends(role_admin)):
    return [{"code": code, "description": text_} for code, text_ in access_service.PERMISSIONS.items()]


@router.get("/roles")
def roles(_: User = Depends(role_admin), db: Session = Depends(get_db)):
    return [access_service.role_out(db, r) for r in db.scalars(select(Role).order_by(Role.id))]


@router.put("/roles/{role_id}/permissions")
def set_permissions(role_id: PathId, data: RolePermissionsIn, request: Request, user: User = Depends(role_admin), db: Session = Depends(get_db)):
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(404, "Role not found.")
    access_service.set_role_permissions(db, role, data.permissions)
    audit_service.log_action(db, user, audit_service.ROLE_CHANGED, "role", role.id, request, f"{role.code}: {len(data.permissions)} permissions")
    return access_service.role_out(db, role)


@router.get("/me")
def my_access(user: User = Depends(access_service.get_current_user), db: Session = Depends(get_db)):
    """The hospital roles and permissions of the signed-in person (the screens use it to show or hide menu items; the server checks again on every call)."""
    return {"roles": access_service.role_codes(db, user), "permissions": sorted(access_service.permissions_of(db, user))}


@router.get("/users/{user_id}/roles")
def user_roles(user_id: PathId, _: User = Depends(role_admin), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "User not found.")
    return {"user_id": target.id, "login_role": target.role, "roles": access_service.role_codes(db, target), "extra_roles": list(db.scalars(select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == target.id)))}


@router.put("/users/{user_id}/roles")
def set_user_roles(user_id: PathId, data: UserRolesIn, request: Request, user: User = Depends(role_admin), db: Session = Depends(get_db)):
    """The extra roles of a person (the role they log in with is not touched)."""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "User not found.")
    found = {r.code: r for r in db.scalars(select(Role).where(Role.code.in_(data.roles or ["-"])))}
    unknown = [c for c in data.roles if c not in found]
    if unknown:
        raise HTTPException(422, f"Unknown role: {unknown[0]}.")
    if target.role == "PATIENT" and data.roles:
        raise HTTPException(422, "A patient cannot be given a staff role.")
    if "SUPER_ADMIN" in data.roles:
        raise HTTPException(422, "Super Admin is the first administrator only.")
    for row in db.scalars(select(UserRole).where(UserRole.user_id == target.id)):
        db.delete(row)
    db.flush()
    for code in dict.fromkeys(data.roles):
        db.add(UserRole(user_id=target.id, role_id=found[code].id, granted_by=user.id))
    db.commit()
    audit_service.log_action(db, user, audit_service.ROLE_CHANGED, "user", target.id, request, "extra roles: " + ", ".join(data.roles))
    return {"user_id": target.id, "extra_roles": list(dict.fromkeys(data.roles))}


# ------------------------------------------------------------------ break-glass
use_glass = require_permission("breakglass.use")


def _grant_out(g: BreakGlassGrant) -> dict:
    return {"id": g.id, "user": g.user.full_name, "user_id": g.user_id, "patient_id": g.patient_id, "patient_name": g.patient.user.full_name, "uhid": g.patient.uhid,
            "reason": g.reason, "granted_at": g.granted_at.isoformat(), "expires_at": g.expires_at.isoformat(), "active": g.expires_at > hospital_service.now(),
            "reviewed_at": g.reviewed_at.isoformat() if g.reviewed_at else None, "review_note": g.review_note}


@router.get("/break-glass/lookup")
def lookup(uhid: text(30, min_length=4), user: User = Depends(use_glass), db: Session = Depends(get_db)):
    """Find a patient by the exact UHID or patient code. Only name, age and sex are shown, so the lookup cannot be used to browse patients."""
    patient = db.scalar(select(Patient).where(or_(Patient.uhid == uhid.upper(), Patient.patient_code == uhid.upper()), Patient.merged_into_id.is_(None)))
    if patient is None:
        raise HTTPException(404, "No patient with this UHID.")
    from app.services.health_history_service import age_of
    return {"id": patient.id, "uhid": patient.uhid, "full_name": patient.user.full_name, "age": age_of(patient), "gender": patient.gender}


@router.post("/break-glass", status_code=status.HTTP_201_CREATED)
def open_glass(data: BreakGlassIn, request: Request, user: User = Depends(use_glass), db: Session = Depends(get_db)):
    """A clinician who is not otherwise authorised opens one patient for a short time, with a written reason. Every use is recorded and reviewed afterwards."""
    patient = db.get(Patient, data.patient_id)
    if patient is None or patient.merged_into_id:
        raise HTTPException(404, "Patient not found.")
    if user.role == DOCTOR:
        get_doctor_profile(db, user)
    minutes = int(hospital_service.setting_value(db, "break_glass_minutes", patient.branch_id))
    now = hospital_service.now()
    grant = BreakGlassGrant(user_id=user.id, patient_id=patient.id, reason=data.reason, granted_at=now, expires_at=now + timedelta(minutes=minutes))
    db.add(grant)
    db.commit()
    db.refresh(grant)
    audit_service.log_action(db, user, audit_service.BREAK_GLASS, "patient", patient.id, request, data.reason[:200])
    return _grant_out(grant)


@router.get("/break-glass")
def list_glass(only_unreviewed: bool = False, _: User = Depends(require_permission("breakglass.review")), db: Session = Depends(get_db)):
    query = select(BreakGlassGrant).order_by(BreakGlassGrant.id.desc()).limit(200)
    if only_unreviewed:
        query = query.where(BreakGlassGrant.reviewed_at.is_(None))
    return [_grant_out(g) for g in db.scalars(query)]


@router.post("/break-glass/{grant_id}/review")
def review_glass(grant_id: PathId, data: ReviewIn, request: Request, user: User = Depends(require_permission("breakglass.review")), db: Session = Depends(get_db)):
    grant = db.get(BreakGlassGrant, grant_id)
    if grant is None:
        raise HTTPException(404, "Not found.")
    grant.reviewed_by, grant.reviewed_at, grant.review_note = user.id, hospital_service.now(), data.note
    db.commit()
    audit_service.log_action(db, user, audit_service.BREAK_GLASS_REVIEWED, "break_glass", grant.id, request)
    return _grant_out(grant)
