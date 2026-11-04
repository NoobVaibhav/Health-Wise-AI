from datetime import date, datetime, timedelta

from pydantic import BaseModel, Field, model_validator
from app.utils.validators import Barcode, OptionalMoney, OptionalPercent, opt_text, text, PositiveId


def check_stock_dates(manufactured, expiry):
    """The manufacturing date is not in the future, and the expiry is after it."""
    if manufactured and manufactured > date.today():
        raise ValueError("The manufacturing date cannot be in the future.")
    if expiry and not date(2000, 1, 1) <= expiry <= date.today() + timedelta(days=366 * 20):
        raise ValueError("Please check the expiry date: it must be between the year 2000 and 20 years ahead.")
    if manufactured and expiry and expiry <= manufactured:
        raise ValueError("The expiry date must be after the manufacturing date.")


class DispenseRequest(BaseModel):
    prescription_item_id: PositiveId
    quantity: int = Field(ge=0, le=10000)     # 0 is allowed only together with mark_unavailable
    notes: opt_text(500, multiline=True) = None
    mark_unavailable: bool = False


class InventoryCreate(BaseModel):
    medicine_name: text(200, min_length=2)
    batch_number: opt_text(50) = None
    quantity: int = Field(ge=0, le=1000000)
    expiry_date: date | None = None
    manufacture_date: date | None = None
    manufacturer: opt_text(150) = None
    unit_price: OptionalMoney = None
    barcode: Barcode = None
    gst_percent: OptionalPercent = None

    @model_validator(mode="after")
    def _dates(self):
        check_stock_dates(self.manufacture_date, self.expiry_date)
        return self


class InventoryUpdate(BaseModel):
    quantity: int | None = Field(default=None, ge=0, le=1000000)
    expiry_date: date | None = None
    manufacture_date: date | None = None
    unit_price: OptionalMoney = None
    batch_number: opt_text(50) = None
    manufacturer: opt_text(150) = None
    barcode: Barcode = None
    gst_percent: OptionalPercent = None

    @model_validator(mode="after")
    def _dates(self):
        check_stock_dates(self.manufacture_date, self.expiry_date)
        return self


class InventoryOut(BaseModel):
    id: int
    medicine_name: str
    batch_number: str | None
    quantity: int
    expiry_date: date | None
    manufacture_date: date | None = None
    manufacturer: str | None
    unit_price: float | None
    barcode: str | None = None
    gst_percent: float | None = None


class DispensingOut(BaseModel):
    id: int
    prescription_id: PositiveId
    prescription_code: str
    patient_name: str
    medicine_name: str
    quantity_prescribed: int
    quantity_dispensed: int
    status: str
    dispensed_at: datetime
    pharmacy_staff_name: str
    notes: str | None
