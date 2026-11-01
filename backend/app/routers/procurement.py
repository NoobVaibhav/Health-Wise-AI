"""Inventory and procurement: store items, requisitions, purchase orders, goods receipts, stock counts, reorder alerts and consumption."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user
from app.database.connection import get_db
from app.database.models import InventoryItem, MedicineInventory, PurchaseOrder, Requisition, StockCount, User
from app.services import audit_service, procurement_service, stock_service
from app.services.access_service import require_permission
from app.utils.validators import PathId, SearchText, opt_text, text

router = APIRouter(prefix="/api/procurement", tags=["procurement"])
request_perm = require_permission("procure.request", "procure.order", "procure.approve")
approve_perm = require_permission("procure.approve")
order_perm = require_permission("procure.order", "procure.approve")
stock_perm = require_permission("stock.manage", "inventory.manage")
read_perm = require_permission("stock.view", "stock.manage", "procure.order", "procure.approve", "inventory.manage")


class ItemIn(BaseModel):
    code: text(30, min_length=2)
    name: text(200, min_length=2)
    category: str = Field(pattern="^(CONSUMABLE|EQUIPMENT|SUPPLY)$")
    unit: text(20, min_length=1) = "piece"
    min_level: int = Field(default=0, ge=0, le=1000000)
    reorder_quantity: int = Field(default=0, ge=0, le=1000000)
    supplier_id: int | None = Field(default=None, ge=1)


class Line(BaseModel):
    inventory_item_id: int | None = Field(default=None, ge=1)
    medicine_name: opt_text(200) = None
    quantity: int = Field(ge=1, le=1000000)
    unit_cost: float | None = Field(default=None, ge=0, le=10000000)


class RequisitionIn(BaseModel):
    department_id: int | None = Field(default=None, ge=1)
    note: opt_text(300) = None
    items: list[Line] = Field(min_length=1, max_length=50)


class DecisionIn(BaseModel):
    approve: bool
    note: opt_text(300) = None


class OrderIn(BaseModel):
    supplier_id: int = Field(ge=1)
    requisition_id: int | None = Field(default=None, ge=1)
    note: opt_text(300) = None
    items: list[Line] = Field(min_length=1, max_length=50)


class ReceiveLine(BaseModel):
    order_item_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=1000000)
    batch_number: opt_text(50) = None
    expiry_date: date | None = None
    selling_price: float | None = Field(default=None, ge=0, le=10000000)
    gst_percent: float | None = Field(default=None, ge=0, le=100)


class ReceiveIn(BaseModel):
    note: opt_text(300) = None
    items: list[ReceiveLine] = Field(min_length=1, max_length=50)


class CountIn(BaseModel):
    medicine_inventory_id: int | None = Field(default=None, ge=1)
    inventory_item_id: int | None = Field(default=None, ge=1)
    counted_quantity: int = Field(ge=0, le=10000000)
    reason: opt_text(300) = None

    @model_validator(mode="after")
    def one_target(self):
        if bool(self.medicine_inventory_id) == bool(self.inventory_item_id):
            raise ValueError("Count either a medicine batch or a store item.")
        return self


# ------------------------------------------------------------------ store items
@router.get("/items")
def items(q: SearchText = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.access_service import permissions_of
    if not permissions_of(db, user) & {"stock.view", "stock.manage", "procure.request", "procure.order", "procure.approve", "inventory.manage", "ot.record"}:
        from app.core.permissions import forbidden
        raise forbidden()
    query = select(InventoryItem).where(InventoryItem.is_active.is_(True)).order_by(InventoryItem.name)
    if q:
        query = query.where(InventoryItem.name.ilike(f"%{q.strip()}%") | InventoryItem.code.ilike(f"%{q.strip()}%"))
    return [{"id": i.id, "code": i.code, "name": i.name, "category": i.category, "unit": i.unit, "quantity": i.quantity, "min_level": i.min_level, "reorder_quantity": i.reorder_quantity,
             "needs_reorder": i.quantity <= i.min_level} for i in db.scalars(query)]


@router.post("/items", status_code=status.HTTP_201_CREATED)
def add_item(data: ItemIn, request: Request, user: User = Depends(stock_perm), db: Session = Depends(get_db)):
    if db.scalar(select(InventoryItem.id).where(InventoryItem.code == data.code.strip())):
        raise HTTPException(status.HTTP_409_CONFLICT, "This item code is already used.")
    row = InventoryItem(**{**data.model_dump(), "code": data.code.strip(), "name": data.name.strip()})
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, "INVENTORY_ITEM_ADDED", "inventory_item", row.id, request, row.name)
    return {"id": row.id, "code": row.code}


# ------------------------------------------------------------------ requisitions
@router.post("/requisitions", status_code=status.HTTP_201_CREATED)
def add_requisition(data: RequisitionIn, request: Request, user: User = Depends(request_perm), db: Session = Depends(get_db)):
    req = procurement_service.create_requisition(db, user, data.department_id, data.note, [i.model_dump() for i in data.items])
    audit_service.log_action(db, user, "REQUISITION_CREATED", "requisition", req.id, request, req.number)
    return procurement_service.requisition_out(req)


@router.get("/requisitions")
def requisitions(status_filter: str | None = None, user: User = Depends(request_perm), db: Session = Depends(get_db)):
    from app.services.access_service import permissions_of
    query = select(Requisition).order_by(Requisition.id.desc()).limit(200)
    if status_filter:
        query = query.where(Requisition.status == status_filter)
    if not permissions_of(db, user) & {"procure.approve", "procure.order"}:
        query = query.where(Requisition.requested_by == user.id)
    return [procurement_service.requisition_out(r) for r in db.scalars(query)]


@router.post("/requisitions/{req_id}/decide")
def decide_requisition(req_id: PathId, data: DecisionIn, request: Request, user: User = Depends(approve_perm), db: Session = Depends(get_db)):
    req = db.get(Requisition, req_id)
    if req is None:
        raise HTTPException(404, "Requisition not found.")
    procurement_service.decide_requisition(db, req, user, data.approve, data.note)
    audit_service.log_action(db, user, "REQUISITION_DECIDED", "requisition", req.id, request, req.status)
    return procurement_service.requisition_out(req)


# ------------------------------------------------------------------ purchase orders and goods receipts
@router.get("/orders")
def orders(status_filter: str | None = None, user: User = Depends(order_perm), db: Session = Depends(get_db)):
    query = select(PurchaseOrder).order_by(PurchaseOrder.id.desc()).limit(200)
    if status_filter:
        query = query.where(PurchaseOrder.status == status_filter)
    return [procurement_service.order_out(o) for o in db.scalars(query)]


@router.post("/orders", status_code=status.HTTP_201_CREATED)
def add_order(data: OrderIn, request: Request, user: User = Depends(order_perm), db: Session = Depends(get_db)):
    order = procurement_service.create_order(db, user, data.supplier_id, data.requisition_id, data.note, [i.model_dump() for i in data.items])
    audit_service.log_action(db, user, "PURCHASE_ORDER_CREATED", "purchase_order", order.id, request, order.number)
    return procurement_service.order_out(order)


def _order(db: Session, order_id: int) -> PurchaseOrder:
    order = db.get(PurchaseOrder, order_id)
    if order is None:
        raise HTTPException(404, "Order not found.")
    return order


@router.post("/orders/{order_id}/approve")
def approve_order(order_id: PathId, request: Request, user: User = Depends(approve_perm), db: Session = Depends(get_db)):
    order = procurement_service.approve_order(db, _order(db, order_id), user)
    audit_service.log_action(db, user, "PURCHASE_ORDER_APPROVED", "purchase_order", order.id, request, order.number)
    return procurement_service.order_out(order)


@router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: PathId, request: Request, user: User = Depends(approve_perm), db: Session = Depends(get_db)):
    order = procurement_service.cancel_order(db, _order(db, order_id))
    audit_service.log_action(db, user, "PURCHASE_ORDER_CANCELLED", "purchase_order", order.id, request, order.number)
    return procurement_service.order_out(order)


@router.post("/orders/{order_id}/receive", status_code=status.HTTP_201_CREATED)
def receive(order_id: PathId, data: ReceiveIn, request: Request, user: User = Depends(order_perm), db: Session = Depends(get_db)):
    order = _order(db, order_id)
    receipt = procurement_service.receive_goods(db, order, user, [i.model_dump() for i in data.items], data.note)
    audit_service.log_action(db, user, "GOODS_RECEIVED", "goods_receipt", receipt.id, request, receipt.number)
    return {"receipt": receipt.number, "order": procurement_service.order_out(order)}


# ------------------------------------------------------------------ stock counts and reports
@router.post("/counts", status_code=status.HTTP_201_CREATED)
def add_count(data: CountIn, request: Request, user: User = Depends(stock_perm), db: Session = Depends(get_db)):
    medicine = db.get(MedicineInventory, data.medicine_inventory_id) if data.medicine_inventory_id else None
    item = db.get(InventoryItem, data.inventory_item_id) if data.inventory_item_id else None
    if medicine is None and item is None:
        raise HTTPException(404, "Nothing to count.")
    count = procurement_service.record_count(db, user, medicine, item, data.counted_quantity, data.reason)
    audit_service.log_action(db, user, "STOCK_COUNTED", "stock_count", count.id, request, f"{count.system_quantity} -> {count.counted_quantity}")
    return {"id": count.id, "status": count.status, "system_quantity": count.system_quantity, "counted_quantity": count.counted_quantity}


@router.get("/counts")
def counts(user: User = Depends(stock_perm), db: Session = Depends(get_db)):
    return [{"id": c.id, "status": c.status, "system_quantity": c.system_quantity, "counted_quantity": c.counted_quantity, "reason": c.reason, "counted_by": c.counted_by,
             "medicine_inventory_id": c.medicine_inventory_id, "inventory_item_id": c.inventory_item_id} for c in db.scalars(select(StockCount).order_by(StockCount.id.desc()).limit(200))]


@router.post("/counts/{count_id}/decide")
def decide_count(count_id: PathId, data: DecisionIn, request: Request, user: User = Depends(stock_perm), db: Session = Depends(get_db)):
    count = db.get(StockCount, count_id)
    if count is None:
        raise HTTPException(404, "Count not found.")
    procurement_service.decide_count(db, count, user, data.approve)
    audit_service.log_action(db, user, "STOCK_COUNT_DECIDED", "stock_count", count.id, request, count.status)
    return {"id": count.id, "status": count.status}


@router.get("/reorder")
def reorder(user: User = Depends(read_perm), db: Session = Depends(get_db)):
    return stock_service.alerts(db)["items_to_reorder"]


@router.get("/consumption")
def consumption(days: int = 30, user: User = Depends(read_perm), db: Session = Depends(get_db)):
    return procurement_service.consumption(db, max(1, min(days, 365)))
