from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from app.utils.validators import Barcode, Money, OptionalMoney, OptionalPercent, OptionalPersonName, OptionalPhone, Quantity, opt_text, text, PositiveId


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
    barcode: Barcode = None
    medicine_name: text(200, min_length=2)
    batch_number: opt_text(50) = None
    quantity: Quantity
    expiry_date: date | None = None
    manufacture_date: date | None = None
    manufacturer: opt_text(150) = None
    unit_price: OptionalMoney = None
    gst_percent: OptionalPercent = None

    @model_validator(mode="after")
    def _dates(self):
        from app.schemas.pharmacy import check_stock_dates
        check_stock_dates(self.manufacture_date, self.expiry_date)
        return self


class SaleItemIn(BaseModel):
    barcode: Barcode = None
    inventory_id: PositiveId | None = None
    quantity: Quantity
    prescription_item_id: PositiveId | None = None   # set when the line fills a doctor's prescription


class SaleCreate(BaseModel):
    customer_name: OptionalPersonName = None
    customer_phone: OptionalPhone = None
    payment_method: Literal["CASH", "UPI", "CARD"] = "CASH"
    discount: Money = 0       # an amount in rupees (not a percentage); the bill service refuses a discount bigger than the bill
    prescription_id: PositiveId | None = None
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
    customer_name: OptionalPersonName = None
    customer_phone: OptionalPhone = None
    payment_method: Literal["CASH", "UPI", "CARD"] = "CASH"
    discount: Money = 0

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
