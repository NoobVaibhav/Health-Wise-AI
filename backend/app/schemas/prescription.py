from datetime import date

from pydantic import BaseModel, Field


class PrescriptionItemCreate(BaseModel):
    medicine_name: str = Field(min_length=2, max_length=200)
    dosage: str = Field(min_length=1, max_length=100)
    frequency: str = Field(min_length=1, max_length=100)
    duration: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0, le=10000)
    instructions: str | None = Field(default=None, max_length=1000)


class PrescriptionCreate(BaseModel):
    patient_id: int
    report_id: int | None = None
    clinical_indication: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)
    items: list[PrescriptionItemCreate] = Field(min_length=1, max_length=30)


class PrescriptionItemOut(BaseModel):
    id: int
    medicine_name: str
    dosage: str
    frequency: str
    duration: str
    quantity: int
    instructions: str | None
    dispense_status: str
    dispensed_quantity: int
    remaining_quantity: int


class PrescriptionOut(BaseModel):
    id: int
    code: str
    patient_id: int
    patient_name: str
    patient_code: str
    doctor_id: int
    doctor_name: str
    report_id: int | None
    prescription_date: date
    valid_until: date
    clinical_indication: str | None
    notes: str | None
    status: str
    items: list[PrescriptionItemOut]
    label: str = "Prescribed by a doctor"
