"""Pharmacy dispensing. The pharmacy can only dispense what a doctor prescribed; it can never edit a prescription.

Rules:
- an expired / cancelled / fully dispensed prescription cannot be dispensed
- you cannot dispense more than the remaining quantity
- if the pharmacy keeps stock for that medicine, stock is deducted (earliest expiry first); not enough stock -> error
"""
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import MedicineDispensing, MedicineInventory, PharmacyStaff, Prescription, PrescriptionItem
from app.schemas.pharmacy import DispenseRequest
from app.services.prescription_service import is_open
from app.services.serializers import dispensed_quantity, effective_status


def _deduct_stock(db: Session, medicine_name: str, quantity: int) -> None:
    """Take `quantity` from inventory batches (earliest expiry first). Does nothing if no stock is tracked."""
    batches = db.scalars(
        select(MedicineInventory).where(func.lower(MedicineInventory.medicine_name) == medicine_name.lower(),
                                        MedicineInventory.quantity > 0)
        .order_by(MedicineInventory.expiry_date.is_(None), MedicineInventory.expiry_date)
    ).all()
    tracked = db.scalar(select(func.count(MedicineInventory.id)).where(
        func.lower(MedicineInventory.medicine_name) == medicine_name.lower()))
    if not tracked:
        return  # this medicine is not in the stock table: nothing to deduct
    available = sum(b.quantity for b in batches if b.expiry_date is None or b.expiry_date >= date.today())
    if available < quantity:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Not enough stock for {medicine_name}: {available} available, {quantity} requested.")
    remaining = quantity
    for batch in batches:
        if batch.expiry_date is not None and batch.expiry_date < date.today():
            continue  # never dispense expired stock
        take = min(batch.quantity, remaining)
        batch.quantity -= take
        remaining -= take
        if remaining == 0:
            break


def _refresh_prescription_status(rx: Prescription) -> None:
    states = [it.dispense_status for it in rx.items]
    if all(s == "DISPENSED" for s in states):
        rx.status = "DISPENSED"
    elif any(s in ("DISPENSED", "PARTIALLY_DISPENSED") for s in states):
        rx.status = "PARTIALLY_DISPENSED"
    else:
        rx.status = "ACTIVE"


def dispense(db: Session, staff: PharmacyStaff, data: DispenseRequest, *, deduct_stock: bool = True,
             commit: bool = True) -> MedicineDispensing:
    """deduct_stock=False and commit=False are used by billing, which has already taken the stock and commits the
    whole sale in one go."""
    item = db.get(PrescriptionItem, data.prescription_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active prescription found.")
    rx = item.prescription
    if not is_open(rx):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"This prescription is {effective_status(rx).lower().replace('_', ' ')} and cannot be dispensed.")

    already = dispensed_quantity(item)
    remaining = item.quantity - already
    if data.mark_unavailable:
        item.dispense_status = "UNAVAILABLE"
        quantity = 0
    else:
        quantity = data.quantity
        if quantity <= 0:
            raise HTTPException(422, "Quantity must be greater than zero.")
        if remaining <= 0:
            raise HTTPException(status.HTTP_409_CONFLICT, "This medicine has already been fully dispensed.")
        if quantity > remaining:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"Only {remaining} remaining to dispense for {item.medicine_name}.")
        if deduct_stock:
            _deduct_stock(db, item.medicine_name, quantity)
        item.dispense_status = "DISPENSED" if already + quantity >= item.quantity else "PARTIALLY_DISPENSED"

    record = MedicineDispensing(
        prescription_id=rx.id, prescription_item_id=item.id, pharmacy_staff_id=staff.id,
        quantity_prescribed=item.quantity, quantity_dispensed=quantity, status=item.dispense_status,
        notes=data.notes,
    )
    db.add(record)
    db.flush()
    db.refresh(rx)
    _refresh_prescription_status(rx)
    if commit:
        db.commit()
        db.refresh(record)
    return record
