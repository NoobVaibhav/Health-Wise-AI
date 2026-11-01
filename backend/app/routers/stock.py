"""Pharmacy stock control: stock history, alerts, recall, write-off, returns, suppliers, and medicines requested by the wards.
Recalled and expired stock can never be dispensed, sold or issued. Every stock change leaves a movement that is never edited."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import DOCTOR, NURSE, forbidden, get_accessible_patient, get_current_user
from app.database.connection import get_db
from app.database.models import Admission, MedicineInventory, MedicineRequest, StockMovement, Supplier, User
from app.services import audit_service, stock_service
from app.services.access_service import permissions_of, require_permission
from app.utils.validators import PathId, SearchText, opt_text, text

router = APIRouter(prefix="/api/stock", tags=["stock"])
view = require_permission("stock.view", "stock.manage")
manage = require_permission("stock.manage")


class SupplierIn(BaseModel):
    name: text(150, min_length=2)
    contact_person: opt_text(100) = None
    phone: opt_text(30) = None
    email: opt_text(254) = None
    gstin: opt_text(20) = None
    address: opt_text(300) = None


class ReasonIn(BaseModel):
    reason: text(300, min_length=3)


class ReturnIn(BaseModel):
    sale_item_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=100000)
    reason: text(300, min_length=3)


class RequestLine(BaseModel):
    medicine_name: text(200, min_length=2)
    quantity: int = Field(ge=1, le=10000)


class RequestIn(BaseModel):
    admission_id: int = Field(ge=1)
    note: opt_text(300) = None
    items: list[RequestLine] = Field(min_length=1, max_length=30)


class IssueIn(BaseModel):
    issues: dict[int, int] = Field(min_length=1)
    note: opt_text(300) = None


@router.get("/alerts")
def alerts(user: User = Depends(view), db: Session = Depends(get_db)):
    return stock_service.alerts(db)


@router.get("/movements")
def movements(medicine_id: int | None = None, item_id: int | None = None, limit: int = 100, user: User = Depends(view), db: Session = Depends(get_db)):
    query = select(StockMovement).order_by(StockMovement.id.desc()).limit(max(1, min(limit, 300)))
    if medicine_id:
        query = query.where(StockMovement.medicine_inventory_id == medicine_id)
    if item_id:
        query = query.where(StockMovement.inventory_item_id == item_id)
    return [stock_service.movement_out(m) for m in db.scalars(query)]


@router.post("/batches/{batch_id}/recall")
def recall(batch_id: PathId, data: ReasonIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    row = db.get(MedicineInventory, batch_id)
    if row is None:
        raise HTTPException(404, "Batch not found.")
    stock_service.recall_batch(db, row, data.reason, user)
    audit_service.log_action(db, user, "STOCK_RECALLED", "medicine_batch", row.id, request, data.reason[:200])
    return {"id": row.id, "recalled": True, "recall_reason": row.recall_reason}


@router.post("/batches/{batch_id}/write-off")
def write_off(batch_id: PathId, data: ReasonIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    row = db.get(MedicineInventory, batch_id)
    if row is None:
        raise HTTPException(404, "Batch not found.")
    stock_service.write_off(db, row, data.reason, user)
    audit_service.log_action(db, user, "STOCK_WRITTEN_OFF", "medicine_batch", row.id, request, data.reason[:200])
    return {"id": row.id, "quantity": row.quantity}


@router.post("/returns", status_code=status.HTTP_201_CREATED)
def returns(data: ReturnIn, request: Request, user: User = Depends(require_permission("stock.manage", "stock.view")), db: Session = Depends(get_db)):
    result = stock_service.return_sold(db, data.sale_item_id, data.quantity, data.reason, user)
    audit_service.log_action(db, user, "MEDICINE_RETURNED", "sale_item", data.sale_item_id, request, f"qty {data.quantity}")
    return result


@router.get("/suppliers")
def suppliers(user: User = Depends(require_permission("stock.view", "stock.manage", "procure.order", "procure.approve")), db: Session = Depends(get_db)):
    return [{"id": s.id, "name": s.name, "contact_person": s.contact_person, "phone": s.phone, "email": s.email, "gstin": s.gstin, "is_active": s.is_active} for s in db.scalars(select(Supplier).order_by(Supplier.name))]


@router.post("/suppliers", status_code=status.HTTP_201_CREATED)
def add_supplier(data: SupplierIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    if db.scalar(select(Supplier.id).where(Supplier.name == data.name.strip())):
        raise HTTPException(status.HTTP_409_CONFLICT, "This supplier is already in the list.")
    row = Supplier(**{**data.model_dump(), "name": data.name.strip()})
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, "SUPPLIER_ADDED", "supplier", row.id, request, row.name)
    return {"id": row.id, "name": row.name}


# ------------------------------------------------------------------ medicines requested by a ward for an admitted patient
def _may_request(db: Session, user: User, admission: Admission) -> None:
    if user.role == DOCTOR:
        get_accessible_patient(db, user, admission.patient_id, clinical=True)
    elif user.role == NURSE or "nursing.chart" in permissions_of(db, user):
        return
    else:
        raise forbidden()


@router.post("/requests", status_code=status.HTTP_201_CREATED)
def create_request(data: RequestIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    admission = db.get(Admission, data.admission_id)
    if admission is None:
        raise HTTPException(404, "Admission not found.")
    _may_request(db, user, admission)
    req = stock_service.create_request(db, admission, user, [i.model_dump() for i in data.items], data.note)
    audit_service.log_action(db, user, "MEDICINE_REQUESTED", "medicine_request", req.id, request, f"{len(data.items)} medicines")
    return stock_service.request_out(req)


@router.get("/requests")
def list_requests(status_filter: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The pharmacy sees every request; a nurse or doctor sees the requests they made."""
    query = select(MedicineRequest).order_by(MedicineRequest.id.desc()).limit(200)
    if status_filter:
        query = query.where(MedicineRequest.status == status_filter)
    if not permissions_of(db, user) & {"stock.view", "stock.manage"}:
        if user.role not in (DOCTOR, NURSE):
            raise forbidden()
        query = query.where(MedicineRequest.requested_by == user.id)
    return [stock_service.request_out(r) for r in db.scalars(query)]


def _get_request(db: Session, request_id: int) -> MedicineRequest:
    req = db.get(MedicineRequest, request_id)
    if req is None:
        raise HTTPException(404, "Request not found.")
    return req


@router.post("/requests/{request_id}/issue")
def issue(request_id: PathId, data: IssueIn, request: Request, user: User = Depends(view), db: Session = Depends(get_db)):
    req = stock_service.issue_request(db, _get_request(db, request_id), user, data.issues, data.note)
    audit_service.log_action(db, user, "MEDICINE_ISSUED", "medicine_request", req.id, request, req.status)
    return stock_service.request_out(req)


@router.post("/requests/{request_id}/reject")
def reject(request_id: PathId, data: ReasonIn, request: Request, user: User = Depends(view), db: Session = Depends(get_db)):
    req = stock_service.reject_request(db, _get_request(db, request_id), user, data.reason)
    audit_service.log_action(db, user, "MEDICINE_REQUEST_REJECTED", "medicine_request", req.id, request, data.reason[:200])
    return stock_service.request_out(req)


@router.post("/requests/{request_id}/cancel")
def cancel(request_id: PathId, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = _get_request(db, request_id)
    if req.requested_by != user.id:
        raise HTTPException(404, "Request not found.")
    if req.status != "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT, f"This request is {req.status.lower()}.")
    req.status = "CANCELLED"
    db.commit()
    audit_service.log_action(db, user, "MEDICINE_REQUEST_CANCELLED", "medicine_request", req.id, request, "")
    return stock_service.request_out(req)
