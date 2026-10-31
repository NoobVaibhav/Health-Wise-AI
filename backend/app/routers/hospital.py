"""The hospital itself: profile, branches, settings and the price list. All changes are made by people with the right permission and are written to the audit log."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import Branch, Department, HospitalSetting, ServiceCatalog, User
from app.services import audit_service, hospital_service
from app.services.access_service import permissions_of, require_permission
from app.utils.validators import Money, OptionalPhone, Percent, PathId, PositiveId, opt_text, text

router = APIRouter(prefix="/api/hospital", tags=["hospital"])
view = require_permission("hospital.view")
manage = require_permission("hospital.manage")
branch_admin = require_permission("branch.manage")
CATEGORIES = ("CONSULTATION", "PROCEDURE", "LAB", "RADIOLOGY", "BED", "NURSING", "OT", "PHARMACY", "OTHER")


class ProfileIn(BaseModel):
    name: opt_text(200) = None
    address: opt_text(300) = None
    phone: opt_text(30) = None                  # a hospital often has a landline, so this is not the mobile-number rule
    email: opt_text(150) = None
    registration_number: opt_text(80) = None
    gst_number: opt_text(30) = None


class BranchIn(BaseModel):
    code: text(8, min_length=2)
    name: text(150, min_length=2)
    address: opt_text(300) = None
    phone: opt_text(30) = None                  # a hospital often has a landline, so this is not the mobile-number rule
    email: opt_text(150) = None


class BranchUpdate(BaseModel):
    name: text(150, min_length=2) | None = None
    address: opt_text(300) = None
    phone: opt_text(30) = None                  # a hospital often has a landline, so this is not the mobile-number rule
    email: opt_text(150) = None
    is_active: bool | None = None


class SettingIn(BaseModel):
    key: text(60, min_length=2)
    value: text(500, min_length=1)
    branch_id: PositiveId | None = None


class ServiceIn(BaseModel):
    code: text(30, min_length=2)
    name: text(200, min_length=2)
    category: text(20)
    department_id: PositiveId | None = None
    price: Money = 0
    gst_percent: Percent = 0
    is_active: bool = True


class ServiceUpdate(BaseModel):
    name: text(200, min_length=2) | None = None
    category: text(20) | None = None
    department_id: PositiveId | None = None
    price: Money | None = None
    gst_percent: Percent | None = None
    is_active: bool | None = None


def _profile_out(p) -> dict:
    return {"name": p.name, "address": p.address, "phone": p.phone, "email": p.email, "registration_number": p.registration_number, "gst_number": p.gst_number}


def _branch_out(b: Branch) -> dict:
    return {"id": b.id, "code": b.code, "name": b.name, "address": b.address, "phone": b.phone, "email": b.email, "is_active": b.is_active}


def _service_out(s: ServiceCatalog) -> dict:
    return {"id": s.id, "code": s.code, "name": s.name, "category": s.category, "department_id": s.department_id, "department_name": s.department.name if s.department else None,
            "price": s.price, "gst_percent": s.gst_percent, "is_active": s.is_active}


@router.get("/profile")
def get_profile(_: User = Depends(view), db: Session = Depends(get_db)):
    return _profile_out(hospital_service.get_profile(db))


@router.put("/profile")
def update_profile(data: ProfileIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    profile = hospital_service.get_profile(db)
    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    profile.updated_at, profile.updated_by = hospital_service.now(), user.id
    db.commit()
    hospital_service.invalidate()
    audit_service.log_action(db, user, audit_service.HOSPITAL_CHANGED, "hospital_profile", profile.id, request, "profile")
    return _profile_out(profile)


# ------------------------------------------------------------------ branches
@router.get("/branches")
def branches(_: User = Depends(view), db: Session = Depends(get_db)):
    hospital_service.default_branch(db)
    return [_branch_out(b) for b in db.scalars(select(Branch).order_by(Branch.id))]


@router.post("/branches", status_code=status.HTTP_201_CREATED)
def add_branch(data: BranchIn, request: Request, user: User = Depends(branch_admin), db: Session = Depends(get_db)):
    code = data.code.upper().replace(" ", "")
    if not code.isalnum() or not 2 <= len(code) <= 8:
        raise HTTPException(422, "The branch code must be 2 to 8 letters or digits, for example PUN.")
    if db.scalar(select(Branch.id).where(func.upper(Branch.code) == code)):
        raise HTTPException(409, "A branch with this code already exists.")
    branch = Branch(code=code, name=data.name, address=data.address, phone=data.phone, email=data.email, is_active=True)
    db.add(branch)
    db.commit()
    audit_service.log_action(db, user, audit_service.HOSPITAL_CHANGED, "branch", branch.id, request, f"branch added: {code}")
    return _branch_out(branch)


@router.put("/branches/{branch_id}")
def update_branch(branch_id: PathId, data: BranchUpdate, request: Request, user: User = Depends(branch_admin), db: Session = Depends(get_db)):
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(404, "Branch not found.")
    changes = data.model_dump(exclude_unset=True)
    if changes.get("is_active") is False and not db.scalar(select(Branch.id).where(Branch.is_active.is_(True), Branch.id != branch.id)):
        raise HTTPException(409, "At least one branch must stay active.")
    for key, value in changes.items():
        if key == "name" and value is None:
            continue
        setattr(branch, key, value)                      # the code never changes: it is part of every UHID already issued
    db.commit()
    audit_service.log_action(db, user, audit_service.HOSPITAL_CHANGED, "branch", branch.id, request, "branch changed")
    return _branch_out(branch)


# ------------------------------------------------------------------ settings
@router.get("/settings")
def settings_list(branch_id: int | None = None, _: User = Depends(view), db: Session = Depends(get_db)):
    return [{"key": key, "value": hospital_service.setting_value(db, key, branch_id), "default": default, "kind": kind}
            for key, (default, kind, _l, _h) in hospital_service.SETTINGS.items()]


@router.put("/settings")
def settings_set(data: SettingIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    try:
        value = hospital_service.check_setting(data.key, data.value)
    except ValueError as err:
        raise HTTPException(422, str(err))
    if data.branch_id and db.get(Branch, data.branch_id) is None:
        raise HTTPException(422, "The selected branch does not exist.")
    row = db.scalar(select(HospitalSetting).where(HospitalSetting.key == data.key, HospitalSetting.branch_id.is_(None) if not data.branch_id else HospitalSetting.branch_id == data.branch_id))
    if row is None:
        row = HospitalSetting(key=data.key, branch_id=data.branch_id, value=value)
        db.add(row)
    row.value, row.updated_at, row.updated_by = value, hospital_service.now(), user.id
    db.commit()
    audit_service.log_action(db, user, audit_service.HOSPITAL_CHANGED, "setting", row.id, request, f"{data.key}={value}")
    return {"key": data.key, "value": value, "branch_id": data.branch_id}


# ------------------------------------------------------------------ price list
@router.get("/services")
def services(category: str | None = None, include_inactive: bool = False, user: User = Depends(require_permission("service.view", "service.manage")), db: Session = Depends(get_db)):
    query = select(ServiceCatalog).order_by(ServiceCatalog.category, ServiceCatalog.name)
    if category:
        if category.upper() not in CATEGORIES:
            raise HTTPException(422, "Unknown service category.")
        query = query.where(ServiceCatalog.category == category.upper())
    if not (include_inactive and "service.manage" in permissions_of(db, user)):
        query = query.where(ServiceCatalog.is_active.is_(True))
    return [_service_out(s) for s in db.scalars(query)]


def _check_service(db: Session, category: str | None, department_id: int | None) -> None:
    if category is not None and category.upper() not in CATEGORIES:
        raise HTTPException(422, "The category must be one of: " + ", ".join(CATEGORIES) + ".")
    if department_id is not None and db.get(Department, department_id) is None:
        raise HTTPException(422, "The selected department does not exist.")


@router.post("/services", status_code=status.HTTP_201_CREATED)
def add_service(data: ServiceIn, request: Request, user: User = Depends(require_permission("service.manage")), db: Session = Depends(get_db)):
    _check_service(db, data.category, data.department_id)
    code = data.code.upper().replace(" ", "")
    if db.scalar(select(ServiceCatalog.id).where(ServiceCatalog.code == code)):
        raise HTTPException(409, "A service with this code already exists.")
    row = ServiceCatalog(code=code, name=data.name, category=data.category.upper(), department_id=data.department_id, price=float(data.price), gst_percent=float(data.gst_percent), is_active=data.is_active)
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, audit_service.HOSPITAL_CHANGED, "service", row.id, request, f"service added: {code}")
    return _service_out(row)


@router.put("/services/{service_id}")
def update_service(service_id: PathId, data: ServiceUpdate, request: Request, user: User = Depends(require_permission("service.manage")), db: Session = Depends(get_db)):
    row = db.get(ServiceCatalog, service_id)
    if row is None:
        raise HTTPException(404, "Service not found.")
    changes = data.model_dump(exclude_unset=True)
    _check_service(db, changes.get("category"), changes.get("department_id"))
    for key, value in changes.items():
        if value is None and key not in ("department_id",):
            continue
        setattr(row, key, value.upper() if key == "category" else (float(value) if key in ("price", "gst_percent") else value))
    row.updated_at = hospital_service.now()
    db.commit()
    audit_service.log_action(db, user, audit_service.HOSPITAL_CHANGED, "service", row.id, request, f"service changed: {row.code}")
    return _service_out(row)
