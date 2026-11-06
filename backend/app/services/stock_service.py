"""Stock history, alerts, recalls, returns and medicines requested by the wards.

Rules that never depend on AI:
- every change of stock leaves one StockMovement (signed quantity, balance after, who, why); nothing is edited or deleted
- expired or recalled stock is never dispensed, sold or issued
- a returned medicine goes back on the shelf only when it is still in date and not recalled
- requested (ward), issued (pharmacy) and given (MAR, nursing) are three different records
"""
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.utils.locking import lock
from app.database.models import (
    Admission, InventoryItem, MedicineInventory, MedicineRequest, MedicineRequestItem, MedicineReturn, SaleItem, StockMovement, User, utcnow,
)
from app.utils.clock import hospital_today

DEFAULT_REORDER_LEVEL = 10
EXPIRY_WARNING_DAYS = 60


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def record(db: Session, *, medicine: MedicineInventory | None = None, item: InventoryItem | None = None, kind: str, quantity: int,
           reference_type: str | None = None, reference_id: int | None = None, note: str | None = None, user_id: int | None = None) -> StockMovement:
    """Call after the quantity of the batch or item was changed: the movement keeps the signed change and the balance that resulted."""
    target = medicine or item
    move = StockMovement(medicine_inventory_id=medicine.id if medicine else None, inventory_item_id=item.id if item else None, kind=kind, quantity=quantity,
                         balance_after=target.quantity, reference_type=reference_type, reference_id=reference_id, note=note, created_by=user_id)
    db.add(move)
    return move


def is_usable(row: MedicineInventory) -> bool:
    return row.quantity > 0 and not row.recalled and (row.expiry_date is None or row.expiry_date >= hospital_today())


def usable_batches(db: Session, medicine_name: str) -> list[MedicineInventory]:
    rows = db.scalars(select(MedicineInventory).where(func.lower(MedicineInventory.medicine_name) == medicine_name.lower()).with_for_update()).all()
    return sorted([r for r in rows if is_usable(r)], key=lambda r: (r.expiry_date is None, r.expiry_date or date.max, r.id))


# ------------------------------------------------------------------ alerts
def alerts(db: Session) -> dict:
    today = hospital_today()
    soon = today + timedelta(days=EXPIRY_WARNING_DAYS)
    rows = db.scalars(select(MedicineInventory)).all()
    by_name: dict[str, list[MedicineInventory]] = {}
    for r in rows:
        by_name.setdefault(r.medicine_name.lower(), []).append(r)
    low = []
    for batches in by_name.values():
        level = max((b.reorder_level for b in batches if b.reorder_level is not None), default=DEFAULT_REORDER_LEVEL)
        total = sum(b.quantity for b in batches if is_usable(b))
        if total <= level:
            low.append({"medicine_name": batches[0].medicine_name, "usable_quantity": total, "reorder_level": level})
    out = lambda r: {"id": r.id, "medicine_name": r.medicine_name, "batch_number": r.batch_number, "quantity": r.quantity, "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None,
                     "recall_reason": r.recall_reason}
    items = db.scalars(select(InventoryItem).where(InventoryItem.is_active.is_(True))).all()
    return {"low_stock": sorted(low, key=lambda x: x["usable_quantity"]),
            "expiring_soon": [out(r) for r in rows if r.quantity > 0 and r.expiry_date and today <= r.expiry_date <= soon and not r.recalled],
            "expired": [out(r) for r in rows if r.quantity > 0 and r.expiry_date and r.expiry_date < today],
            "recalled": [out(r) for r in rows if r.quantity > 0 and r.recalled],
            "items_to_reorder": [{"id": i.id, "code": i.code, "name": i.name, "quantity": i.quantity, "min_level": i.min_level, "reorder_quantity": i.reorder_quantity}
                                 for i in items if i.quantity <= i.min_level]}


# ------------------------------------------------------------------ recall and write-off
def recall_batch(db: Session, row: MedicineInventory, reason: str, user: User) -> MedicineInventory:
    if row.recalled:
        raise conflict("This batch is already recalled.")
    row.recalled, row.recall_reason = True, reason.strip()
    record(db, medicine=row, kind="RECALL", quantity=0, reference_type="batch", reference_id=row.id, note=reason.strip()[:300], user_id=user.id)
    db.commit()
    return row


def write_off(db: Session, row: MedicineInventory, reason: str, user: User) -> MedicineInventory:
    """Remove the stock of a batch that is expired or recalled (the quantity goes to zero, the history keeps what was removed)."""
    if not row.recalled and not (row.expiry_date and row.expiry_date < hospital_today()):
        raise conflict("Only an expired or recalled batch can be written off.")
    if row.quantity <= 0:
        raise conflict("There is nothing left in this batch.")
    removed = row.quantity
    row.quantity = 0
    record(db, medicine=row, kind="WRITE_OFF", quantity=-removed, reference_type="batch", reference_id=row.id, note=reason.strip()[:300], user_id=user.id)
    db.commit()
    return row


def movement_out(m: StockMovement) -> dict:
    return {"id": m.id, "kind": m.kind, "quantity": m.quantity, "balance_after": m.balance_after, "reference_type": m.reference_type, "reference_id": m.reference_id, "note": m.note,
            "created_at": m.created_at.isoformat(), "medicine_inventory_id": m.medicine_inventory_id, "inventory_item_id": m.inventory_item_id}


# ------------------------------------------------------------------ returns
def return_sold(db: Session, sale_item_id: int, quantity: int, reason: str, user: User) -> dict:
    sale_item = db.get(SaleItem, sale_item_id)
    if sale_item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sale line not found.")
    lock(db, sale_item)
    returned = db.scalar(select(func.coalesce(func.sum(MedicineReturn.quantity), 0)).where(MedicineReturn.sale_item_id == sale_item.id)) or 0
    if quantity > sale_item.quantity - returned:
        raise conflict(f"Only {sale_item.quantity - returned} of this line can still be returned.")
    row = db.get(MedicineInventory, sale_item.inventory_id) if sale_item.inventory_id else None
    restock = bool(row and not row.recalled and (row.expiry_date is None or row.expiry_date >= hospital_today()))
    db.add(MedicineReturn(sale_item_id=sale_item.id, quantity=quantity, reason=reason.strip(), restocked=restock, created_by=user.id))
    if restock:
        row.quantity += quantity
        record(db, medicine=row, kind="RETURN", quantity=quantity, reference_type="sale_item", reference_id=sale_item.id, note=reason.strip()[:300], user_id=user.id)
    db.commit()
    return {"sale_item_id": sale_item.id, "returned": quantity, "restocked": restock,
            "message": "Returned to stock." if restock else "Returned, but not put back on the shelf (expired or recalled stock is never reused)."}


# ------------------------------------------------------------------ medicines requested by a ward
def request_out(r: MedicineRequest) -> dict:
    return {"id": r.id, "admission_id": r.admission_id, "patient_id": r.patient_id, "patient_name": r.patient.user.full_name, "patient_code": r.patient.patient_code, "status": r.status,
            "note": r.note, "decision_note": r.decision_note, "created_at": r.created_at.isoformat(),
            "items": [{"id": i.id, "medicine_name": i.medicine_name, "quantity": i.quantity, "issued_quantity": i.issued_quantity} for i in r.items]}


def create_request(db: Session, admission: Admission, user: User, items: list[dict], note: str | None) -> MedicineRequest:
    if admission.status != "ADMITTED":
        raise conflict("Medicines can be requested only for a patient who is admitted.")
    names = [i["medicine_name"].strip().lower() for i in items]
    if len(set(names)) != len(names):
        raise HTTPException(422, "A medicine is listed twice.")
    req = MedicineRequest(admission_id=admission.id, patient_id=admission.patient_id, requested_by=user.id, note=note,
                          items=[MedicineRequestItem(medicine_name=i["medicine_name"].strip(), quantity=i["quantity"]) for i in items])
    db.add(req)
    db.commit()
    return req


def issue_request(db: Session, req: MedicineRequest, user: User, issues: dict[int, int], note: str | None) -> MedicineRequest:
    """The pharmacy issues what it can. An item the pharmacy does not issue stays open; the request is PARTIAL until every line is full, then ISSUED."""
    lock(db, req)
    if req.status not in ("PENDING", "PARTIAL"):
        raise conflict(f"This request is {req.status.lower()}.")
    lines = {i.id: i for i in req.items}
    for line_id, qty in issues.items():
        line = lines.get(line_id)
        if line is None:
            raise HTTPException(422, "That line does not belong to this request.")
        if qty < 0 or qty > line.quantity - line.issued_quantity:
            raise HTTPException(422, f"{line.medicine_name}: at most {line.quantity - line.issued_quantity} can still be issued.")
    if not any(q > 0 for q in issues.values()):
        raise HTTPException(422, "Issue at least one medicine, or reject the request.")
    for line_id, qty in issues.items():
        if qty == 0:
            continue
        line = lines[line_id]
        batches = usable_batches(db, line.medicine_name)
        available = sum(b.quantity for b in batches)
        if available < qty:
            raise conflict(f"Not enough usable stock for {line.medicine_name}: {available} available (expired and recalled stock is not counted).")
        remaining = qty
        for batch in batches:
            take = min(batch.quantity, remaining)
            batch.quantity -= take
            remaining -= take
            record(db, medicine=batch, kind="ISSUE", quantity=-take, reference_type="medicine_request", reference_id=req.id, user_id=user.id)
            if remaining == 0:
                break
        line.issued_quantity += qty
    req.status = "ISSUED" if all(i.issued_quantity >= i.quantity for i in req.items) else "PARTIAL"
    req.decided_by, req.decided_at, req.decision_note = user.id, utcnow(), note
    db.commit()
    return req


def reject_request(db: Session, req: MedicineRequest, user: User, reason: str) -> MedicineRequest:
    if req.status != "PENDING":
        raise conflict(f"This request is {req.status.lower()}.")
    req.status, req.decided_by, req.decided_at, req.decision_note = "REJECTED", user.id, utcnow(), reason.strip()
    db.commit()
    return req
