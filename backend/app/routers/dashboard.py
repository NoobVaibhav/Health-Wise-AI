"""One endpoint, GET /api/dashboard, that returns the dashboard for whichever role is logged in.
(The role-specific endpoints such as /api/doctor/dashboard return the same data.)"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import ADMIN, DOCTOR, EMPLOYEE, PATIENT, get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.services import dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == ADMIN:
        data = dashboard_service.admin_dashboard(db)
    elif user.role == DOCTOR:
        data = dashboard_service.doctor_dashboard(db, user)
    elif user.role == EMPLOYEE:
        data = dashboard_service.employee_dashboard(db, user)
    elif user.role == PATIENT:
        data = dashboard_service.patient_dashboard(db, user)
    else:
        data = dashboard_service.pharmacy_dashboard(db)
    return {"role": user.role, **data}
