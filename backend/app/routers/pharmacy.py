"""Pharmacy module: view authorized prescriptions, dispense medicines, manage stock.
The pharmacy has NO endpoint that creates or edits a prescription."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import PHARMACY, forbidden, require_roles
from app.database.connection import get_db
from app.database.models import MedicineDispensing, MedicineInventory, PharmacyStaff, User
from app.schemas.pharmacy import (
    DispenseRequest, DispensingOut, InventoryCreate, InventoryOut, InventoryUpdate,
)
from app.schemas.prescription import PrescriptionOut
from app.services import audit_service, dashboard_service, dispensing_service, prescription_service
from app.services.serializers import prescription_out

router = APIRouter(prefix="/api/pharmacy", tags=["pharmacy"])
pharmacy_only = require_roles(PHARMACY)


def _staff(db: Session, user: User) -> PharmacyStaff:
    staff = db.scalar(select(PharmacyStaff).where(PharmacyStaff.user_id == user.id))
    if staff is None:
        raise forbidden()
    return staff


def _dispensing_out(d: MedicineDispensing) -> DispensingOut:
    return DispensingOut(
        id=d.id, prescription_id=d.prescription_id, prescription_code=f"RX-{d.prescription_id:05d}",
        patient_name=d.item.prescription.patient.user.full_name, medicine_name=d.item.medicine_name,
        quantity_prescribed=d.quantity_prescribed, quantity_dispensed=d.quantity_dispensed, status=d.status,
        dispensed_at=d.dispensed_at, pharmacy_staff_name=d.pharmacy_staff.user.full_name, notes=d.notes)


@router.get("/dashboard")
def dashboard(_: User = Depends(pharmacy_only), db: Session = Depends(get_db)):
    return dashboard_service.pharmacy_dashboard(db)


@router.get("/prescriptions", response_model=list[PrescriptionOut])
def search_prescriptions(q: str | None = None, status_filter: str | None = None,
                         user: User = Depends(pharmacy_only), db: Session = Depends(get_db)):
    """Search by prescription code (RX-00001), patient name or patient id."""
    rows = prescription_service.list_prescriptions_for_user(db, user, q)
    result = [prescription_out(r, include_tests=False) for r in rows]
    if status_filter:
        result = [r for r in result if r.status == status_filter.upper()]
    return result


@router.post("/dispense", response_model=PrescriptionOut)
def dispense(data: DispenseRequest, request: Request, user: User = Depends(pharmacy_only),
             db: Session = Depends(get_db)):
    record = dispensing_service.dispense(db, _staff(db, user), data)
    audit_service.log_action(db, user, audit_service.MEDICINE_DISPENSED, "prescription", record.prescription_id,
                             request, f"item {record.prescription_item_id} qty {record.quantity_dispensed}")
    return prescription_out(record.item.prescription, include_tests=False)


@router.get("/history", response_model=list[DispensingOut])
def dispensing_history(_: User = Depends(pharmacy_only), db: Session = Depends(get_db)):
    rows = db.scalars(select(MedicineDispensing).order_by(MedicineDispensing.id.desc()).limit(300)).all()
    return [_dispensing_out(d) for d in rows]


# ------------------------------------------------------------------ inventory
@router.get("/inventory", response_model=list[InventoryOut])
def list_inventory(q: str | None = None, _: User = Depends(pharmacy_only), db: Session = Depends(get_db)):
    query = select(MedicineInventory).order_by(MedicineInventory.medicine_name, MedicineInventory.expiry_date)
    if q:
        query = query.where(MedicineInventory.medicine_name.ilike(f"%{q.strip()}%"))
    return list(db.scalars(query))


@router.post("/inventory", response_model=InventoryOut, status_code=status.HTTP_201_CREATED)
def add_inventory(data: InventoryCreate, _: User = Depends(pharmacy_only), db: Session = Depends(get_db)):
    item = MedicineInventory(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/inventory/{item_id}", response_model=InventoryOut)
def update_inventory(item_id: int, data: InventoryUpdate, _: User = Depends(pharmacy_only),
                     db: Session = Depends(get_db)):
    item = db.get(MedicineInventory, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Medicine not found in stock.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item
