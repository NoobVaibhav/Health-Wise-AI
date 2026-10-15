"""Pick-lists for the doctor: medicines and tests used in the hospital (a typing shortcut, not a restriction)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, PHARMACY, require_roles
from app.database.connection import get_db
from app.database.models import User
from app.services import hospital_catalog

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/medicines")
def medicines(user: User = Depends(require_roles(DOCTOR, PHARMACY)), db: Session = Depends(get_db)):
    """Medicine names only (no patient data), so the pharmacy can pick them when adding stock."""
    return hospital_catalog.medicine_options(db)


@router.get("/tests")
def tests(user: User = Depends(require_roles(DOCTOR))):
    return hospital_catalog.test_options()
