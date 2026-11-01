"""The hospital's list of tests and scans, with the unit, method, reference and critical limits of every measured value.
Everyone who works with orders can read it; only the administrator changes it. The limits are the hospital's own decision: nothing is filled in by AI."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ADMIN, DOCTOR, EMPLOYEE, LAB, RADIOLOGY, require_roles
from app.database.connection import get_db
from app.database.models import DiagnosticAnalyte, DiagnosticTest, User
from app.services import audit_service, diagnostic_service
from app.utils.validators import PathId

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


class TestIn(BaseModel):
    kind: str = Field(pattern="^(LAB|RADIOLOGY)$")
    name: str = Field(min_length=2, max_length=150)
    category: str = Field(min_length=2, max_length=30)
    sample_type: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def category_fits(self):
        allowed = diagnostic_service.LAB_CATEGORIES if self.kind == "LAB" else diagnostic_service.MODALITIES
        if self.category not in allowed:
            raise ValueError("The category must be one of: " + ", ".join(allowed) + ".")
        return self


class AnalyteIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    unit: str | None = Field(default=None, max_length=30)
    method: str | None = Field(default=None, max_length=100)
    ref_low: float | None = Field(default=None, ge=-1e9, le=1e9)
    ref_high: float | None = Field(default=None, ge=-1e9, le=1e9)
    critical_low: float | None = Field(default=None, ge=-1e9, le=1e9)
    critical_high: float | None = Field(default=None, ge=-1e9, le=1e9)

    @model_validator(mode="after")
    def limits_in_order(self):
        chain = [v for v in (self.critical_low, self.ref_low, self.ref_high, self.critical_high) if v is not None]
        if chain != sorted(chain):
            raise ValueError("The limits must go in order: critical low, normal low, normal high, critical high.")
        return self


@router.get("/tests")
def tests(kind: str | None = None, user: User = Depends(require_roles(ADMIN, DOCTOR, EMPLOYEE, LAB, RADIOLOGY)), db: Session = Depends(get_db)):
    if kind not in (None, "LAB", "RADIOLOGY"):
        raise HTTPException(422, "The kind must be LAB or RADIOLOGY.")
    return diagnostic_service.catalogue(db, kind)


@router.post("/tests", status_code=status.HTTP_201_CREATED)
def add_test(data: TestIn, request: Request, user: User = Depends(require_roles(ADMIN)), db: Session = Depends(get_db)):
    if db.scalar(select(DiagnosticTest.id).where(DiagnosticTest.kind == data.kind, DiagnosticTest.name == data.name.strip())):
        raise HTTPException(status.HTTP_409_CONFLICT, "This test is already in the list.")
    test = DiagnosticTest(kind=data.kind, name=data.name.strip(), category=data.category, sample_type=data.sample_type)
    db.add(test)
    db.commit()
    audit_service.log_action(db, user, "DIAGNOSTIC_TEST_ADDED", "diagnostic_test", test.id, request, test.name)
    return {"id": test.id, "name": test.name}


@router.post("/tests/{test_id}/analytes", status_code=status.HTTP_201_CREATED)
def add_analyte(test_id: PathId, data: AnalyteIn, request: Request, user: User = Depends(require_roles(ADMIN)), db: Session = Depends(get_db)):
    test = db.get(DiagnosticTest, test_id)
    if test is None or test.kind != "LAB":
        raise HTTPException(404, "Laboratory test not found.")
    if any(a.name.lower() == data.name.strip().lower() for a in test.analytes):
        raise HTTPException(status.HTTP_409_CONFLICT, "This value is already part of the test.")
    analyte = DiagnosticAnalyte(test_id=test.id, name=data.name.strip(), unit=data.unit, method=data.method, ref_low=data.ref_low, ref_high=data.ref_high,
                                critical_low=data.critical_low, critical_high=data.critical_high, sort_order=len(test.analytes))
    db.add(analyte)
    db.commit()
    audit_service.log_action(db, user, "DIAGNOSTIC_ANALYTE_ADDED", "diagnostic_test", test.id, request, analyte.name)
    return {"id": analyte.id, "name": analyte.name}
