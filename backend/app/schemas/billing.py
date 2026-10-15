from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class StockLookupBatch(BaseModel):
    id: int
    batch_number: str | None
    quantity: int
    expiry_date: date | None
    unit_price: float | None
    expired: bool


class StockLookup(BaseModel):
    """What a scan of one barcode finds: the medicine, its price and every batch on the shelf."""
    barcode: str | None
    medicine_name: str
    unit_price: float | None
    gst_percent: float
    available: int                  # units that can be sold now (expired batches are not counted)
    batches: list[StockLookupBatch]


class ReceiveStock(BaseModel):
    """Add stock by scanning. If the same barcode + batch is already on the shelf, the quantity is added to it."""
    barcode: str | None = Field(default=None, max_length=64)
    medicine_name: str = Field(min_length=2, max_length=200)
    batch_number: str | None = Field(default=None, max_length=50)
    quantity: int = Field(ge=1, le=1000000)
    expiry_date: date | None = None
    manufacturer: str | None = Field(default=None, max_length=150)
    unit_price: float | None = Field(default=None, ge=0)
    gst_percent: float | None = Field(default=None, ge=0, le=100)


class SaleItemIn(BaseModel):
    barcode: str | None = Field(default=None, max_length=64)
    inventory_id: int | None = None
    quantity: int = Field(ge=1, le=10000)
    prescription_item_id: int | None = None   # set when the line fills a doctor's prescription


class SaleCreate(BaseModel):
    customer_name: str | None = Field(default=None, max_length=150)
    customer_phone: str | None = Field(default=None, max_length=30)
    payment_method: Literal["CASH", "UPI", "CARD"] = "CASH"
    discount: float = Field(default=0, ge=0, le=1000000)
    prescription_id: int | None = None
    items: list[SaleItemIn] = Field(min_length=1, max_length=60)

    @field_validator("customer_name", "customer_phone")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class SaleItemOut(BaseModel):
    medicine_name: str
    batch_number: str | None
    expiry_date: date | None
    quantity: int
    unit_price: float
    gst_percent: float
    line_total: float      # quantity x price, before GST
    tax_amount: float
    amount: float          # line_total + tax_amount


class SaleOut(BaseModel):
    id: int
    bill_number: str
    created_at: datetime
    shop_name: str
    staff_name: str
    customer_name: str | None
    customer_phone: str | None
    prescription_code: str | None
    payment_method: str
    items: list[SaleItemOut]
    subtotal: float
    discount: float
    tax: float
    total: float


class PrescriptionBillRequest(BaseModel):
    """Bill for the medicine of one prescription that has already been given."""
    customer_name: str | None = Field(default=None, max_length=150)
    customer_phone: str | None = Field(default=None, max_length=30)
    payment_method: Literal["CASH", "UPI", "CARD"] = "CASH"
    discount: float = Field(default=0, ge=0, le=1000000)

    @field_validator("customer_name", "customer_phone")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class BillPreview(BaseModel):
    """What the bill for a prescription would contain right now (medicine given but not yet billed)."""
    prescription_code: str
    patient_name: str
    lines: list[SaleItemOut]
    subtotal: float
    tax: float
    total: float
    problems: list[str]                      # e.g. a medicine that has no price in the stock register
    bills: list[dict]                        # bills already made for this prescription: {id, bill_number}


class SaleListItem(BaseModel):
    id: int
    bill_number: str
    created_at: datetime
    prescription_code: str | None = None
    customer_name: str | None
    payment_method: str
    item_count: int
    total: float


class SalesSummary(BaseModel):
    bills_today: int
    sales_today: float
    by_method: dict[str, float]
    top_medicines: list[dict]
