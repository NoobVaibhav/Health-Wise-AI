"""Medical-shop billing endpoints (pharmacy staff only): barcode lookup, stock delivery, sales and bills."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import PHARMACY, forbidden, require_roles
from app.database.connection import get_db
from app.database.models import PharmacyStaff, Sale, User
from app.schemas.billing import (
    BillPreview, PrescriptionBillRequest, ReceiveStock, SaleCreate, SaleListItem, SaleOut, SalesSummary, StockLookup,
)
from app.schemas.pharmacy import InventoryOut
from app.services import audit_service, billing_service, prescription_service
from app.utils.validators import PathId, SearchText

router = APIRouter(prefix="/api/pharmacy", tags=["billing"])
pharmacy_only = require_roles(PHARMACY)


def _staff(db: Session, user: User) -> PharmacyStaff:
    staff = db.scalar(select(PharmacyStaff).where(PharmacyStaff.user_id == user.id))
    if staff is None:
        raise forbidden()
    return staff


@router.get("/inventory/lookup", response_model=StockLookup)
def lookup_barcode(code: str, _: User = Depends(pharmacy_only), db: Session = Depends(get_db)):
    """A scan: returns the medicine, its price and its batches, or 404 when the barcode is unknown."""
    return billing_service.lookup(db, code)


@router.post("/inventory/receive", response_model=InventoryOut, status_code=status.HTTP_201_CREATED)
def receive_stock(data: ReceiveStock, user: User = Depends(pharmacy_only), db: Session = Depends(get_db)):
    return billing_service.receive_stock(db, data, user.id)


@router.post("/sales", response_model=SaleOut, status_code=status.HTTP_201_CREATED)
def create_sale(data: SaleCreate, request: Request, user: User = Depends(pharmacy_only), db: Session = Depends(get_db)):
    sale = billing_service.create_sale(db, _staff(db, user), data)
    audit_service.log_action(db, user, audit_service.SALE_CREATED, "sale", sale.id, request,
                             f"{sale.bill_number} total {sale.total:g}")
    return billing_service.sale_out(sale)


@router.get("/prescriptions/{prescription_id}/bill-preview", response_model=BillPreview)
def prescription_bill_preview(prescription_id: PathId, user: User = Depends(pharmacy_only), db: Session = Depends(get_db)):
    """The bill for medicine of this prescription that was given but not billed yet."""
    rx = prescription_service.get_prescription_for_user(db, user, prescription_id)
    return billing_service.prescription_bill_preview(db, rx)


@router.post("/prescriptions/{prescription_id}/bill", response_model=SaleOut, status_code=status.HTTP_201_CREATED)
def bill_prescription(prescription_id: PathId, data: PrescriptionBillRequest, request: Request,
                      user: User = Depends(pharmacy_only), db: Session = Depends(get_db)):
    """Make the bill for the medicine already given on a prescription. The stock is not touched again."""
    rx = prescription_service.get_prescription_for_user(db, user, prescription_id)
    sale = billing_service.bill_prescription(db, _staff(db, user), rx, data)
    audit_service.log_action(db, user, audit_service.SALE_CREATED, "sale", sale.id, request,
                             f"{sale.bill_number} total {sale.total:g}")
    return billing_service.sale_out(sale)


@router.get("/sales/summary", response_model=SalesSummary)
def sales_summary(_: User = Depends(pharmacy_only), db: Session = Depends(get_db)):
    return billing_service.summary_today(db)


@router.get("/sales", response_model=list[SaleListItem])
def list_sales(q: SearchText = None, day: date | None = None, _: User = Depends(pharmacy_only),
               db: Session = Depends(get_db)):
    return billing_service.list_sales(db, q, day)


@router.get("/sales/{sale_id}", response_model=SaleOut)
def get_sale(sale_id: PathId, _: User = Depends(pharmacy_only), db: Session = Depends(get_db)):
    sale = db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bill not found.")
    return billing_service.sale_out(sale)
