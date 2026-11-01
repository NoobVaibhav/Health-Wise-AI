"""Inventory and procurement: items, requisitions, purchase orders, goods receipts (GRN), stock counts and reports.

Flow: someone asks (requisition) -> a manager approves -> a purchase order to a supplier is made and approved by a different person -> goods arrive (GRN) and stock goes up
once -> a physical count may find a difference, which changes the stock only after a second person approves it, with a reason.
Nothing here is edited after it is final and every stock change leaves a StockMovement.
"""
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    GoodsReceipt, GoodsReceiptItem, InventoryItem, MedicineInventory, PurchaseOrder, PurchaseOrderItem, Requisition, RequisitionItem, StockCount, StockMovement, Supplier, User, utcnow,
)
from app.services import stock_service
from app.utils.locking import lock


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def next_number(db: Session, model, prefix: str) -> str:
    count = db.scalar(select(func.count(model.id))) or 0
    while True:
        count += 1
        number = f"{prefix}-{date.today().year}-{count:05d}"
        if not db.scalar(select(model.id).where(model.number == number)):
            return number


# ------------------------------------------------------------------ requisitions
def create_requisition(db: Session, user: User, department_id: int | None, note: str | None, lines: list[dict]) -> Requisition:
    clean = []
    for line in lines:
        if bool(line.get("inventory_item_id")) == bool(line.get("medicine_name")):
            raise HTTPException(422, "Each line needs either a store item or a medicine name.")
        if line.get("inventory_item_id") and db.get(InventoryItem, line["inventory_item_id"]) is None:
            raise HTTPException(422, "That store item does not exist.")
        clean.append(RequisitionItem(inventory_item_id=line.get("inventory_item_id"), medicine_name=(line.get("medicine_name") or "").strip() or None, quantity=line["quantity"]))
    req = Requisition(number=next_number(db, Requisition, "REQ"), requested_by=user.id, department_id=department_id, note=note, items=clean)
    db.add(req)
    db.commit()
    return req


def decide_requisition(db: Session, req: Requisition, user: User, approve: bool, note: str | None) -> Requisition:
    lock(db, req)
    if req.status != "PENDING":
        raise conflict(f"This requisition is already {req.status.lower()}.")
    if req.requested_by == user.id:
        raise conflict("A requisition cannot be approved by the person who made it.")
    if not approve and not (note or "").strip():
        raise HTTPException(422, "Please write why it is rejected.")
    req.status, req.decided_by, req.decided_at, req.decision_note = "APPROVED" if approve else "REJECTED", user.id, utcnow(), note
    db.commit()
    return req


# ------------------------------------------------------------------ purchase orders
def create_order(db: Session, user: User, supplier_id: int, requisition_id: int | None, note: str | None, lines: list[dict]) -> PurchaseOrder:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None or not supplier.is_active:
        raise HTTPException(422, "Please choose an active supplier.")
    if requisition_id is not None:
        req = db.get(Requisition, requisition_id)
        if req is None or req.status != "APPROVED":
            raise conflict("A purchase order can follow only an approved requisition.")
    items = []
    for line in lines:
        if bool(line.get("inventory_item_id")) == bool(line.get("medicine_name")):
            raise HTTPException(422, "Each line needs either a store item or a medicine name.")
        if line.get("inventory_item_id") and db.get(InventoryItem, line["inventory_item_id"]) is None:
            raise HTTPException(422, "That store item does not exist.")
        items.append(PurchaseOrderItem(inventory_item_id=line.get("inventory_item_id"), medicine_name=(line.get("medicine_name") or "").strip() or None, ordered_quantity=line["quantity"], unit_cost=line.get("unit_cost")))
    order = PurchaseOrder(number=next_number(db, PurchaseOrder, "PO"), supplier_id=supplier_id, requisition_id=requisition_id, created_by=user.id, note=note, items=items)
    db.add(order)
    if requisition_id is not None:
        db.get(Requisition, requisition_id).status = "ORDERED"
    db.commit()
    return order


def approve_order(db: Session, order: PurchaseOrder, user: User) -> PurchaseOrder:
    lock(db, order)
    if order.status != "DRAFT":
        raise conflict(f"This order is already {order.status.lower()}.")
    if order.created_by == user.id:
        raise conflict("A purchase order cannot be approved by the person who made it.")
    order.status, order.approved_by, order.approved_at = "APPROVED", user.id, utcnow()
    db.commit()
    return order


def cancel_order(db: Session, order: PurchaseOrder) -> PurchaseOrder:
    if order.status not in ("DRAFT", "APPROVED") or any(i.received_quantity for i in order.items):
        raise conflict("An order that has received goods cannot be cancelled.")
    order.status = "CANCELLED"
    db.commit()
    return order


def receive_goods(db: Session, order: PurchaseOrder, user: User, lines: list[dict], note: str | None) -> GoodsReceipt:
    lock(db, order)
    if order.status not in ("APPROVED", "PARTIAL"):
        raise conflict("Goods can be received only against an approved order." if order.status == "DRAFT" else f"This order is {order.status.lower()}.")
    by_id = {i.id: i for i in order.items}
    receipt = GoodsReceipt(number=next_number(db, GoodsReceipt, "GRN"), order_id=order.id, received_by=user.id, note=note)
    db.add(receipt)
    db.flush()
    for line in lines:
        item = by_id.get(line["order_item_id"])
        if item is None:
            raise HTTPException(422, "That line does not belong to this order.")
        if line["quantity"] > item.ordered_quantity - item.received_quantity:
            raise conflict(f"Only {item.ordered_quantity - item.received_quantity} more can be received for this line.")
        if item.medicine_name:
            if line.get("expiry_date") is None:
                raise HTTPException(422, f"Please enter the expiry date of {item.medicine_name}.")
            if line["expiry_date"] <= date.today():
                raise HTTPException(422, f"{item.medicine_name} has expired: it cannot be received into stock.")
            if not (line.get("batch_number") or "").strip():
                raise HTTPException(422, f"Please enter the batch number of {item.medicine_name}.")
            from app.schemas.billing import ReceiveStock
            from app.services import billing_service
            billing_service.receive_stock(db, ReceiveStock(medicine_name=item.medicine_name, batch_number=line["batch_number"], quantity=line["quantity"], expiry_date=line["expiry_date"],
                                                           unit_price=line.get("selling_price"), gst_percent=line.get("gst_percent")), user.id, ("grn", receipt.id))
            db.flush()
        else:
            stock = db.get(InventoryItem, item.inventory_item_id)
            stock.quantity += line["quantity"]
            stock_service.record(db, item=stock, kind="RECEIPT", quantity=line["quantity"], reference_type="grn", reference_id=receipt.id, user_id=user.id)
        item.received_quantity += line["quantity"]
        receipt.items.append(GoodsReceiptItem(order_item_id=item.id, quantity=line["quantity"], batch_number=line.get("batch_number"), expiry_date=line.get("expiry_date"),
                                              selling_price=line.get("selling_price"), gst_percent=line.get("gst_percent")))
    order.status = "RECEIVED" if all(i.received_quantity >= i.ordered_quantity for i in order.items) else "PARTIAL"
    db.commit()
    return receipt


# ------------------------------------------------------------------ stock counts
def record_count(db: Session, user: User, medicine: MedicineInventory | None, item: InventoryItem | None, counted: int, reason: str | None) -> StockCount:
    system = (medicine or item).quantity
    if counted != system and not (reason or "").strip():
        raise HTTPException(422, "A difference needs a reason.")
    count = StockCount(medicine_inventory_id=medicine.id if medicine else None, inventory_item_id=item.id if item else None, system_quantity=system, counted_quantity=counted,
                       reason=reason, counted_by=user.id, status="PENDING" if counted != system else "APPLIED", decided_by=None if counted != system else user.id,
                       decided_at=None if counted != system else utcnow())
    db.add(count)
    db.commit()
    return count


def decide_count(db: Session, count: StockCount, user: User, approve: bool) -> StockCount:
    lock(db, count)
    if count.status != "PENDING":
        raise conflict(f"This count is already {count.status.lower()}.")
    if count.counted_by == user.id:
        raise conflict("A count must be approved by a second person.")
    if approve:
        target = db.get(MedicineInventory, count.medicine_inventory_id) if count.medicine_inventory_id else db.get(InventoryItem, count.inventory_item_id)
        delta = count.counted_quantity - target.quantity                       # against the stock now, not the stock at the time of the count
        target.quantity = count.counted_quantity
        stock_service.record(db, medicine=target if count.medicine_inventory_id else None, item=target if count.inventory_item_id else None, kind="ADJUST", quantity=delta,
                             reference_type="stock_count", reference_id=count.id, note=(count.reason or "")[:300], user_id=user.id)
    count.status, count.decided_by, count.decided_at = "APPLIED" if approve else "REJECTED", user.id, utcnow()
    db.commit()
    return count


# ------------------------------------------------------------------ reports
def consumption(db: Session, days: int = 30) -> list[dict]:
    since = utcnow() - timedelta(days=days)
    rows = db.execute(select(StockMovement.inventory_item_id, func.sum(-StockMovement.quantity)).where(
        StockMovement.inventory_item_id.is_not(None), StockMovement.kind.in_(("CONSUME", "ISSUE")), StockMovement.created_at >= since).group_by(StockMovement.inventory_item_id)).all()
    names = {i.id: i for i in db.scalars(select(InventoryItem))}
    return sorted([{"item_id": iid, "name": names[iid].name, "code": names[iid].code, "unit": names[iid].unit, "used": int(used or 0)} for iid, used in rows], key=lambda r: -r["used"])


def order_out(o: PurchaseOrder) -> dict:
    return {"id": o.id, "number": o.number, "supplier": o.supplier.name, "status": o.status, "note": o.note, "created_at": o.created_at.isoformat(), "requisition_id": o.requisition_id,
            "items": [{"id": i.id, "inventory_item_id": i.inventory_item_id, "medicine_name": i.medicine_name, "ordered_quantity": i.ordered_quantity, "received_quantity": i.received_quantity, "unit_cost": i.unit_cost} for i in o.items]}


def requisition_out(r: Requisition) -> dict:
    return {"id": r.id, "number": r.number, "status": r.status, "note": r.note, "decision_note": r.decision_note, "created_at": r.created_at.isoformat(), "requested_by": r.requested_by,
            "items": [{"id": i.id, "inventory_item_id": i.inventory_item_id, "medicine_name": i.medicine_name, "quantity": i.quantity} for i in r.items]}
