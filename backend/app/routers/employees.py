"""Employee (receptionist / lab assistant) module."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import EMPLOYEE, require_roles
from app.database.connection import get_db
from app.database.models import User
from app.services import dashboard_service

router = APIRouter(prefix="/api/employee", tags=["employee"])


@router.get("/dashboard")
def dashboard(user: User = Depends(require_roles(EMPLOYEE)), db: Session = Depends(get_db)):
    return dashboard_service.employee_dashboard(db, user)
