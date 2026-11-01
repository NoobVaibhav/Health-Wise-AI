"""Pick-lists for the doctor: medicines and tests used in the hospital (a typing shortcut, not a restriction)."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import ADMIN, DOCTOR, EMPLOYEE, LAB, NURSE, PATIENT, PHARMACY, require_roles
from app.database.connection import get_db
from app.database.models import Department, Specialization, User
from app.services import audit_service, catalog_service, hospital_catalog
from app.utils.validators import PathId, PositiveId, QueryId, text

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/medicines")
def medicines(user: User = Depends(require_roles(DOCTOR, PHARMACY)), db: Session = Depends(get_db)):
    """Medicine names only (no patient data), so the pharmacy can pick them when adding stock."""
    return hospital_catalog.medicine_options(db)


@router.get("/tests")
def tests(user: User = Depends(require_roles(DOCTOR))):
    return hospital_catalog.test_options()


# ------------------------------------------------------------------ departments and specializations
ANY_SIGNED_IN = (ADMIN, DOCTOR, EMPLOYEE, PATIENT, PHARMACY, LAB, NURSE)
admin_only = require_roles(ADMIN)


class NameBody(BaseModel):
    name: text(100, min_length=2)


class SpecializationCreate(NameBody):
    department_id: PositiveId


class ActiveBody(BaseModel):
    is_active: bool


def _department_out(d: Department, doctors: int | None = None) -> dict:
    out = {"id": d.id, "name": d.name, "is_active": d.is_active is not False}
    if doctors is not None:
        out["doctor_count"] = doctors
    return out


def _specialization_out(s: Specialization, doctors: int | None = None) -> dict:
    out = {"id": s.id, "name": s.name, "department_id": s.department_id, "is_active": s.is_active is not False}
    if doctors is not None:
        out["doctor_count"] = doctors
    return out


@router.get("/departments")
def departments(include_inactive: bool = False, user: User = Depends(require_roles(*ANY_SIGNED_IN)), db: Session = Depends(get_db)):
    """Active departments (id, name) for the dropdowns. The admin can also ask for the inactive ones."""
    show_all = include_inactive and user.role == ADMIN
    query = select(Department).order_by(Department.name)
    if not show_all:
        query = query.where(Department.is_active.is_not(False))
    return [_department_out(d, catalog_service.doctors_using_department(db, d.id)) if show_all else {"id": d.id, "name": d.name}
            for d in db.scalars(query)]


@router.get("/specializations")
def specializations(department_id: QueryId = None, include_inactive: bool = False, user: User = Depends(require_roles(*ANY_SIGNED_IN)),
                    db: Session = Depends(get_db)):
    """Active specializations, optionally only those of one department."""
    show_all = include_inactive and user.role == ADMIN
    query = select(Specialization).order_by(Specialization.name)
    if not show_all:
        query = query.where(Specialization.is_active.is_not(False))
    if department_id is not None:
        query = query.where(Specialization.department_id == department_id)
    return [_specialization_out(s, catalog_service.doctors_using_specialization(db, s.id)) if show_all
            else {"id": s.id, "name": s.name, "department_id": s.department_id} for s in db.scalars(query)]


def _department_or_404(db: Session, department_id: int) -> Department:
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found.")
    return department


def _specialization_or_404(db: Session, specialization_id: int) -> Specialization:
    specialization = db.get(Specialization, specialization_id)
    if specialization is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Specialization not found.")
    return specialization


def _department_name_free(db: Session, name: str, except_id: int | None = None) -> None:
    other = db.scalar(select(Department).where(func.lower(Department.name) == name.lower()))
    if other is not None and other.id != except_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "A department with this name already exists.")


def _specialization_name_free(db: Session, department_id: int, name: str, except_id: int | None = None) -> None:
    other = db.scalar(select(Specialization).where(Specialization.department_id == department_id,
                                                   Specialization.name_key == catalog_service.name_key(name)))
    if other is not None and other.id != except_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "This department already has a specialization with this name.")


@router.post("/departments", status_code=status.HTTP_201_CREATED)
def create_department(data: NameBody, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    _department_name_free(db, data.name)
    department = Department(name=data.name, is_active=True)
    db.add(department)
    db.commit()
    audit_service.log_action(db, admin, audit_service.USER_CHANGED, "department", department.id, request, f"department added: {department.name}")
    return _department_out(department, 0)


@router.put("/departments/{department_id}")
def rename_department(department_id: PathId, data: NameBody, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    department = _department_or_404(db, department_id)
    _department_name_free(db, data.name, department.id)
    department.name = data.name
    db.commit()
    audit_service.log_action(db, admin, audit_service.USER_CHANGED, "department", department.id, request, f"department renamed: {department.name}")
    return _department_out(department, catalog_service.doctors_using_department(db, department.id))


@router.patch("/departments/{department_id}")
def set_department_active(department_id: PathId, data: ActiveBody, request: Request, admin: User = Depends(admin_only),
                          db: Session = Depends(get_db)):
    """Hide from the dropdowns, or bring back. Nothing is deleted, so doctors that use it keep it."""
    department = _department_or_404(db, department_id)
    department.is_active = data.is_active
    db.commit()
    audit_service.log_action(db, admin, audit_service.USER_CHANGED, "department", department.id, request,
                             f"department {'activated' if data.is_active else 'deactivated'}: {department.name}")
    return _department_out(department, catalog_service.doctors_using_department(db, department.id))


@router.post("/specializations", status_code=status.HTTP_201_CREATED)
def create_specialization(data: SpecializationCreate, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    _department_or_404(db, data.department_id)
    _specialization_name_free(db, data.department_id, data.name)
    specialization = Specialization(name=data.name, name_key=catalog_service.name_key(data.name), department_id=data.department_id, is_active=True)
    db.add(specialization)
    db.commit()
    audit_service.log_action(db, admin, audit_service.USER_CHANGED, "specialization", specialization.id, request,
                             f"specialization added: {specialization.name}")
    return _specialization_out(specialization, 0)


@router.put("/specializations/{specialization_id}")
def rename_specialization(specialization_id: PathId, data: NameBody, request: Request, admin: User = Depends(admin_only),
                          db: Session = Depends(get_db)):
    specialization = _specialization_or_404(db, specialization_id)
    _specialization_name_free(db, specialization.department_id, data.name, specialization.id)
    specialization.name = data.name
    specialization.name_key = catalog_service.name_key(data.name)
    db.commit()
    audit_service.log_action(db, admin, audit_service.USER_CHANGED, "specialization", specialization.id, request,
                             f"specialization renamed: {specialization.name}")
    return _specialization_out(specialization, catalog_service.doctors_using_specialization(db, specialization.id))


@router.patch("/specializations/{specialization_id}")
def set_specialization_active(specialization_id: PathId, data: ActiveBody, request: Request, admin: User = Depends(admin_only),
                              db: Session = Depends(get_db)):
    specialization = _specialization_or_404(db, specialization_id)
    specialization.is_active = data.is_active
    db.commit()
    audit_service.log_action(db, admin, audit_service.USER_CHANGED, "specialization", specialization.id, request,
                             f"specialization {'activated' if data.is_active else 'deactivated'}: {specialization.name}")
    return _specialization_out(specialization, catalog_service.doctors_using_specialization(db, specialization.id))
