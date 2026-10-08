from datetime import date, datetime

from pydantic import BaseModel, Field


class DispenseRequest(BaseModel):
    prescription_item_id: int
    quantity: int = Field(ge=0, le=10000)     # 0 is allowed only together with mark_unavailable
    notes: str | None = Field(default=None, max_length=500)
    mark_unavailable: bool = False


class InventoryCreate(BaseModel):
    medicine_name: str = Field(min_length=2, max_length=200)
    batch_number: str | None = Field(default=None, max_length=50)
    quantity: int = Field(ge=0, le=1000000)
    expiry_date: date | None = None
    manufacturer: str | None = Field(default=None, max_length=150)
    unit_price: float | None = Field(default=None, ge=0)


class InventoryUpdate(BaseModel):
    quantity: int | None = Field(default=None, ge=0, le=1000000)
    expiry_date: date | None = None
    unit_price: float | None = Field(default=None, ge=0)
    batch_number: str | None = Field(default=None, max_length=50)
    manufacturer: str | None = Field(default=None, max_length=150)


class InventoryOut(BaseModel):
    id: int
    medicine_name: str
    batch_number: str | None
    quantity: int
    expiry_date: date | None
    manufacturer: str | None
    unit_price: float | None


class DispensingOut(BaseModel):
    id: int
    prescription_id: int
    prescription_code: str
    patient_name: str
    medicine_name: str
    quantity_prescribed: int
    quantity_dispensed: int
    status: str
    dispensed_at: datetime
    pharmacy_staff_name: str
    notes: str | None
