"""Admin: staff accounts, departments, statistics and audit logs."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.services.profile_service import avatar_version
from app.core.permissions import ADMIN, DOCTOR, EMPLOYEE, LAB, PHARMACY, require_roles
from app.database.connection import get_db
from app.database.models import (
    Appointment, AuditLog, Department, Doctor, DoctorNote, DoctorRecommendation, Employee, HealthReport, Patient,
    LabStaff, PharmacyStaff, Prescription, User,
)
from app.services.user_service import age_from_dob
from app.routers.auth import user_out
from app.schemas.auth import CreatedUserResponse, DepartmentCreate, StaffCreate, UserOut, UserUpdate
from app.services import audit_service, dashboard_service, user_service
from app.utils.validators import Limit, PathId, SearchText, one_of
ROLE_FILTER = one_of("ADMIN", "DOCTOR", "EMPLOYEE", "PATIENT", "PHARMACY", "LAB", name="role")

router = APIRouter(prefix="/api/admin", tags=["admin"])
admin_only = require_roles(ADMIN)


@router.get("/dashboard")
def dashboard(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    return dashboard_service.admin_dashboard(db)


@router.get("/users", response_model=list[UserOut])
def list_users(role: ROLE_FILTER = None, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    query = select(User).order_by(User.id)
    if role:
        query = query.where(User.role == role.upper())
    return [user_out(u) for u in db.scalars(query)]


@router.get("/people")
def people(role: ROLE_FILTER = None, q: SearchText = None, _: User = Depends(admin_only),
           db: Session = Depends(get_db)):
    """Everybody with the details that matter for their role, in a form that is easy to show as cards."""
    query = select(User).order_by(User.full_name)
    if role:
        query = query.where(User.role == role.upper())
    users = db.scalars(query).all()
    if q:
        needle = q.strip().lower()
        users = [u for u in users if needle in u.full_name.lower() or needle in u.email.lower()]

    last_login = dict(db.execute(select(AuditLog.user_id, func.max(AuditLog.timestamp))
                                 .where(AuditLog.action == "LOGIN").group_by(AuditLog.user_id)).all())
    doctors = {d.user_id: d for d in db.scalars(select(Doctor))}
    employees = {e.user_id: e for e in db.scalars(select(Employee))}
    pharmacy = {p.user_id: p for p in db.scalars(select(PharmacyStaff))}
    lab = {l.user_id: l for l in db.scalars(select(LabStaff))}
    patients = {p.user_id: p for p in db.scalars(select(Patient))}

    result = []
    for u in users:
        details: list[list[str]] = []
        phone = None
        if u.id in doctors:
            d = doctors[u.id]
            phone = d.phone
            details = [["Specialization", d.specialization], ["Department", d.department.name if d.department else None]]
        elif u.id in employees:
            e = employees[u.id]
            phone = e.phone
            details = [["Job", e.designation]]
        elif u.id in pharmacy:
            ph = pharmacy[u.id]
            phone = ph.phone
            details = [["Pharmacy", ph.pharmacy_name]]
        elif u.id in lab:
            lb = lab[u.id]
            phone = lb.phone
            details = [["Laboratory", lb.lab_name]]
        elif u.id in patients:
            pt = patients[u.id]
            phone = pt.phone
            age = age_from_dob(pt.date_of_birth)
            details = [["Patient ID", pt.patient_code], ["Age", f"{age} years" if age is not None else None],
                       ["Doctor", pt.assigned_doctor.user.full_name if pt.assigned_doctor else None]]
        result.append({
            "id": u.id, "full_name": u.full_name, "email": u.email, "role": u.role, "is_active": u.is_active,
            "created_at": u.created_at.isoformat(), "last_login": last_login[u.id].isoformat() if u.id in last_login else None,
            "phone": phone, "details": [[label, value] for label, value in details if value],
            "has_avatar": bool(u.avatar_path), "avatar_version": avatar_version(u),
        })
    return result


def _create(role: str, data: StaffCreate, admin: User, request: Request, db: Session) -> CreatedUserResponse:
    user, temporary = user_service.create_staff(db, role, data)
    audit_service.log_action(db, admin, audit_service.USER_CREATED, "user", user.id, request, role)
    return CreatedUserResponse(user=user_out(user), temporary_password=temporary)


@router.post("/doctors", response_model=CreatedUserResponse, status_code=status.HTTP_201_CREATED)
def create_doctor(data: StaffCreate, request: Request, admin: User = Depends(admin_only),
                  db: Session = Depends(get_db)):
    return _create(DOCTOR, data, admin, request, db)


@router.post("/employees", response_model=CreatedUserResponse, status_code=status.HTTP_201_CREATED)
def create_employee(data: StaffCreate, request: Request, admin: User = Depends(admin_only),
                    db: Session = Depends(get_db)):
    return _create(EMPLOYEE, data, admin, request, db)


@router.post("/pharmacy-staff", response_model=CreatedUserResponse, status_code=status.HTTP_201_CREATED)
def create_pharmacy_staff(data: StaffCreate, request: Request, admin: User = Depends(admin_only),
                          db: Session = Depends(get_db)):
    return _create(PHARMACY, data, admin, request, db)


@router.post("/lab-staff", response_model=CreatedUserResponse, status_code=status.HTTP_201_CREATED)
def create_lab_staff(data: StaffCreate, request: Request, admin: User = Depends(admin_only),
                     db: Session = Depends(get_db)):
    return _create(LAB, data, admin, request, db)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: PathId, data: UserUpdate, request: Request, admin: User = Depends(admin_only),
                db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    if data.is_active is False and user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account.")
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.full_name:
        user.full_name = data.full_name.strip()
    db.commit()
    audit_service.log_action(db, admin, audit_service.USER_CHANGED, "user", user.id, request,
                             f"active={user.is_active}")
    return user_out(user)


@router.get("/users/{user_id}/delete-check")
def delete_check(user_id: PathId, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Can this account be deleted, and if not, why. Used by the confirmation window."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return user_service.delete_check(db, user, admin)


@router.delete("/users/{user_id}")
def delete_user(user_id: PathId, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Permanently deletes an account that has nothing linked to it (for example one made by mistake). An account with any
    medical, billing or other records cannot be deleted: deactivate it instead."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    summary = user_service.delete_user(db, user, admin)
    audit_service.log_action(db, admin, audit_service.USER_DELETED, "user", summary["id"], request, f"{summary['role']} {summary['email']} ({summary['full_name']})")
    return {"deleted": True, **summary}


@router.get("/departments")
def list_departments(_: User = Depends(require_roles(ADMIN, EMPLOYEE, DOCTOR)), db: Session = Depends(get_db)):
    return [{"id": d.id, "name": d.name} for d in db.scalars(select(Department).order_by(Department.name))]


@router.post("/departments", status_code=status.HTTP_201_CREATED)
def create_department(data: DepartmentCreate, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    if db.scalar(select(Department).where(Department.name == data.name.strip())):
        raise HTTPException(status.HTTP_409_CONFLICT, "This department already exists.")
    department = Department(name=data.name.strip())
    db.add(department)
    db.commit()
    return {"id": department.id, "name": department.name}


def _entity_label(db: Session, entity_type: str | None, entity_id: int | None) -> str | None:
    """A human name for the record an audit entry is about (never clinical values, only names)."""
    if not entity_type or entity_id is None:
        return None
    if entity_type == "user":
        row = db.get(User, entity_id)
        return row.full_name if row else None
    if entity_type == "patient":
        row = db.get(Patient, entity_id)
        return row.user.full_name if row else None
    if entity_type == "report":
        row = db.get(HealthReport, entity_id)
        return f"{row.filename} (patient {row.patient.user.full_name})" if row else None
    if entity_type == "prescription":
        row = db.get(Prescription, entity_id)
        return f"prescription RX-{entity_id:05d} (patient {row.patient.user.full_name})" if row else None
    if entity_type == "note":
        row = db.get(DoctorNote, entity_id)
        return f"a note for {row.patient.user.full_name}" if row else None
    if entity_type == "recommendation":
        row = db.get(DoctorRecommendation, entity_id)
        return f"advice for {row.patient.user.full_name}" if row else None
    if entity_type == "appointment":
        row = db.get(Appointment, entity_id)
        return f"{row.patient.user.full_name} with {row.doctor.user.full_name}" if row else None
    return None


@router.get("/audit-logs")
def audit_logs(action: SearchText = None, limit: Limit = 200, _: User = Depends(admin_only),
               db: Session = Depends(get_db)):
    query = select(AuditLog).order_by(AuditLog.id.desc()).limit(min(max(limit, 1), 1000))
    if action:
        query = query.where(AuditLog.action == action.upper())
    return [{"id": a.id, "user_id": a.user_id, "user_name": a.user.full_name if a.user else None,
             "user_role": a.user.role if a.user else None, "action": a.action, "entity_type": a.entity_type,
             "entity_id": a.entity_id, "entity_label": _entity_label(db, a.entity_type, a.entity_id),
             "details": a.details, "ip_address": a.ip_address, "timestamp": a.timestamp.isoformat()}
            for a in db.scalars(query)]
