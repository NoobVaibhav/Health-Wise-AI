"""Finance: charges, invoices, payments and receipts, advances, refunds, packages and the reports.
Billing staff see bills and money, never clinical notes. A patient sees only their own bills and receipts."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import PATIENT, forbidden, get_current_user, get_patient_profile, require_roles
from app.database.connection import get_db
from app.database.models import BillingPackage, Deposit, Invoice, Patient, Payment, Refund, User
from app.services import audit_service, finance_service as fin
from app.services.access_service import permissions_of, require_permission
from app.utils.validators import PathId, SearchText, opt_text, text

router = APIRouter(prefix="/api/finance", tags=["finance"])
view = require_permission("billing.view", "billing.create", "billing.collect", "billing.approve", "billing.report")
create = require_permission("billing.create")
collect = require_permission("billing.collect")
approve = require_permission("billing.approve")
report = require_permission("billing.report")


class ServiceLine(BaseModel):
    service_id: int = Field(ge=1)
    quantity: int = Field(default=1, ge=1, le=1000)


class InvoiceIn(BaseModel):
    patient_id: int = Field(ge=1)
    admission_id: int | None = Field(default=None, ge=1)
    charge_ids: list[int] = Field(default_factory=list, max_length=100)
    services: list[ServiceLine] = Field(default_factory=list, max_length=50)
    package_ids: list[int] = Field(default_factory=list, max_length=20)
    note: opt_text(300) = None


class LinesIn(BaseModel):
    charge_ids: list[int] = Field(default_factory=list, max_length=100)
    services: list[ServiceLine] = Field(default_factory=list, max_length=50)
    package_ids: list[int] = Field(default_factory=list, max_length=20)


class DiscountIn(BaseModel):
    amount: float = Field(ge=0, le=100000000)
    reason: opt_text(300) = None


class ReasonIn(BaseModel):
    reason: text(300, min_length=3)


class PayIn(BaseModel):
    amount: float = Field(gt=0, le=100000000)
    method: str = Field(max_length=12)
    reference: opt_text(60) = None
    deposit_id: int | None = Field(default=None, ge=1)


class DepositIn(BaseModel):
    patient_id: int = Field(ge=1)
    admission_id: int | None = Field(default=None, ge=1)
    amount: float = Field(gt=0, le=100000000)
    method: str = Field(max_length=12)
    reference: opt_text(60) = None


class RefundIn(BaseModel):
    invoice_id: int | None = Field(default=None, ge=1)
    deposit_id: int | None = Field(default=None, ge=1)
    amount: float = Field(gt=0, le=100000000)
    method: str = Field(max_length=12)
    reason: text(300, min_length=3)


class DecideIn(BaseModel):
    approve: bool
    note: opt_text(300) = None


class PackageIn(BaseModel):
    name: text(150, min_length=2)
    price: float = Field(ge=0, le=100000000)
    gst_percent: float = Field(default=0, ge=0, le=100)
    inclusions: opt_text(500) = None


def _invoice(db: Session, invoice_id: int) -> Invoice:
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(404, "Invoice not found.")
    return inv


def _patient(db: Session, patient_id: int) -> Patient:
    p = db.get(Patient, patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found.")
    return p


# ------------------------------------------------------------------ finding patients and charges
@router.get("/patients")
def find_patients(q: SearchText = None, user: User = Depends(view), db: Session = Depends(get_db)):
    """Name, patient ID and UHID only (billing never sees clinical details)."""
    if not (q or "").strip():
        return []
    like = f"%{q.strip()}%"
    rows = db.scalars(select(Patient).join(User, Patient.user_id == User.id).where(or_(User.full_name.ilike(like), Patient.patient_code.ilike(like), Patient.uhid.ilike(like))).limit(15))
    return [{"id": p.id, "full_name": p.user.full_name, "patient_code": p.patient_code, "uhid": p.uhid} for p in rows]


@router.get("/patients/{patient_id}/overview")
def overview(patient_id: PathId, user: User = Depends(view), db: Session = Depends(get_db)):
    from app.database.models import Admission, InsuranceClaim, PatientInsurance
    p = _patient(db, patient_id)
    deposits = db.scalars(select(Deposit).where(Deposit.patient_id == p.id).order_by(Deposit.id.desc())).all()
    return {"patient": {"id": p.id, "full_name": p.user.full_name, "patient_code": p.patient_code, "uhid": p.uhid},
            "pending_charges": fin.pending_charges(db, p.id),
            "invoices": [fin.invoice_out(db, i, detail=False) for i in db.scalars(select(Invoice).where(Invoice.patient_id == p.id).order_by(Invoice.id.desc()).limit(50))],
            "deposits": [{"id": d.id, "receipt_number": d.receipt_number, "amount": d.amount, "balance": fin.deposit_balance(d), "method": d.method, "received_at": d.received_at.isoformat()} for d in deposits],
            "admissions": [{"id": a.id, "admission_no": a.admission_no, "status": a.status} for a in db.scalars(select(Admission).where(Admission.patient_id == p.id).order_by(Admission.id.desc()))],
            "policies": [{"id": x.id, "insurer_name": x.insurer_name, "tpa_name": x.tpa_name, "policy_number": x.policy_number, "is_active": x.is_active} for x in db.scalars(select(PatientInsurance).where(PatientInsurance.patient_id == p.id))]}


@router.post("/patients/{patient_id}/collect-charges")
def collect_charges(patient_id: PathId, request: Request, user: User = Depends(create), db: Session = Depends(get_db)):
    p = _patient(db, patient_id)
    result = fin.collect_charges(db, p, user)
    audit_service.log_action(db, user, "CHARGES_COLLECTED", "patient", p.id, request, f"{len(result['added'])} added")
    return result


# ------------------------------------------------------------------ invoices
@router.get("/invoices")
def invoices(status_filter: str | None = None, patient_id: int | None = None, q: SearchText = None, user: User = Depends(view), db: Session = Depends(get_db)):
    query = select(Invoice).order_by(Invoice.id.desc()).limit(200)
    if status_filter:
        query = query.where(Invoice.status == status_filter)
    if patient_id:
        query = query.where(Invoice.patient_id == patient_id)
    if q:
        query = query.where(Invoice.number.ilike(f"%{q.strip()}%"))
    return [fin.invoice_out(db, i, detail=False) for i in db.scalars(query)]


@router.post("/invoices", status_code=status.HTTP_201_CREATED)
def make_invoice(data: InvoiceIn, request: Request, user: User = Depends(create), db: Session = Depends(get_db)):
    inv = fin.create_invoice(db, user, _patient(db, data.patient_id), data.admission_id, data.charge_ids, [s.model_dump() for s in data.services], data.package_ids, data.note)
    audit_service.log_action(db, user, "INVOICE_DRAFTED", "invoice", inv.id, request, f"{len(inv.lines)} lines")
    return fin.invoice_out(db, inv)


@router.get("/invoices/{invoice_id}")
def invoice(invoice_id: PathId, user: User = Depends(view), db: Session = Depends(get_db)):
    return fin.invoice_out(db, _invoice(db, invoice_id))


@router.post("/invoices/{invoice_id}/lines")
def add_lines(invoice_id: PathId, data: LinesIn, request: Request, user: User = Depends(create), db: Session = Depends(get_db)):
    inv = _invoice(db, invoice_id)
    fin.add_lines(db, inv, data.charge_ids, [s.model_dump() for s in data.services], data.package_ids)
    db.commit()
    audit_service.log_action(db, user, "INVOICE_LINES_ADDED", "invoice", inv.id, request, "")
    return fin.invoice_out(db, inv)


@router.delete("/invoices/{invoice_id}/lines/{line_id}")
def remove_line(invoice_id: PathId, line_id: PathId, request: Request, user: User = Depends(create), db: Session = Depends(get_db)):
    inv = _invoice(db, invoice_id)
    fin.remove_line(db, inv, line_id)
    audit_service.log_action(db, user, "INVOICE_LINE_REMOVED", "invoice", inv.id, request, "")
    return fin.invoice_out(db, inv)


@router.post("/invoices/{invoice_id}/discount")
def discount(invoice_id: PathId, data: DiscountIn, request: Request, user: User = Depends(create), db: Session = Depends(get_db)):
    inv = fin.set_discount(db, _invoice(db, invoice_id), user, data.amount, data.reason)
    audit_service.log_action(db, user, "INVOICE_DISCOUNT", "invoice", inv.id, request, f"{data.amount:.2f}")
    return fin.invoice_out(db, inv)


@router.post("/invoices/{invoice_id}/discount/approve")
def approve_discount(invoice_id: PathId, request: Request, user: User = Depends(approve), db: Session = Depends(get_db)):
    inv = fin.approve_discount(db, _invoice(db, invoice_id), user)
    audit_service.log_action(db, user, "DISCOUNT_APPROVED", "invoice", inv.id, request, f"{inv.discount:.2f}")
    return fin.invoice_out(db, inv)


@router.post("/invoices/{invoice_id}/finalise")
def finalise(invoice_id: PathId, request: Request, user: User = Depends(create), db: Session = Depends(get_db)):
    inv = fin.finalise(db, _invoice(db, invoice_id), user)
    audit_service.log_action(db, user, "INVOICE_FINALISED", "invoice", inv.id, request, inv.number)
    return fin.invoice_out(db, inv)


@router.post("/invoices/{invoice_id}/cancel")
def cancel(invoice_id: PathId, data: ReasonIn, request: Request, user: User = Depends(view), db: Session = Depends(get_db)):
    inv = _invoice(db, invoice_id)
    perms = permissions_of(db, user)
    if not perms & ({"billing.approve"} if inv.status == "FINAL" else {"billing.create", "billing.approve"}):
        raise forbidden()
    fin.cancel(db, inv, user, data.reason)
    audit_service.log_action(db, user, "INVOICE_CANCELLED", "invoice", inv.id, request, data.reason[:150])
    return fin.invoice_out(db, inv)


# ------------------------------------------------------------------ payments, advances, refunds
@router.post("/invoices/{invoice_id}/pay", status_code=status.HTTP_201_CREATED)
def pay(invoice_id: PathId, data: PayIn, request: Request, user: User = Depends(collect), db: Session = Depends(get_db)):
    inv = _invoice(db, invoice_id)
    p = fin.pay(db, inv, user, data.amount, data.method, data.reference, data.deposit_id)
    audit_service.log_action(db, user, "PAYMENT_RECEIVED", "invoice", inv.id, request, f"{p.receipt_number} {p.amount:.2f} {p.method}")
    return {"payment_id": p.id, "receipt_number": p.receipt_number, "invoice": fin.invoice_out(db, inv)}


@router.get("/payments/{payment_id}/receipt")
def receipt(payment_id: PathId, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Payment, payment_id)
    if p is None:
        raise HTTPException(404, "Receipt not found.")
    inv = db.get(Invoice, p.invoice_id)
    if user.role == PATIENT:
        if get_patient_profile(db, user).id != inv.patient_id:
            raise HTTPException(404, "Receipt not found.")
    elif not permissions_of(db, user) & {"billing.view", "billing.create", "billing.collect", "billing.approve", "billing.report"}:
        raise forbidden()
    return fin.receipt_out(db, p)


@router.post("/deposits", status_code=status.HTTP_201_CREATED)
def deposit(data: DepositIn, request: Request, user: User = Depends(collect), db: Session = Depends(get_db)):
    d = fin.take_deposit(db, user, _patient(db, data.patient_id), data.admission_id, data.amount, data.method, data.reference)
    audit_service.log_action(db, user, "DEPOSIT_RECEIVED", "deposit", d.id, request, f"{d.receipt_number} {d.amount:.2f}")
    return {"id": d.id, "receipt_number": d.receipt_number, "amount": d.amount, "balance": fin.deposit_balance(d)}


@router.post("/refunds", status_code=status.HTTP_201_CREATED)
def request_refund(data: RefundIn, request: Request, user: User = Depends(collect), db: Session = Depends(get_db)):
    if bool(data.invoice_id) == bool(data.deposit_id):
        raise HTTPException(422, "A refund is for an invoice or for an advance.")
    inv = _invoice(db, data.invoice_id) if data.invoice_id else None
    dep = db.get(Deposit, data.deposit_id) if data.deposit_id else None
    if data.deposit_id and dep is None:
        raise HTTPException(404, "Advance not found.")
    r = fin.request_refund(db, user, inv, dep, data.amount, data.method, data.reason)
    audit_service.log_action(db, user, "REFUND_REQUESTED", "refund", r.id, request, f"{r.number} {r.amount:.2f}")
    return {"id": r.id, "number": r.number, "status": r.status}


@router.get("/refunds")
def refunds(status_filter: str | None = None, user: User = Depends(view), db: Session = Depends(get_db)):
    query = select(Refund).order_by(Refund.id.desc()).limit(200)
    if status_filter:
        query = query.where(Refund.status == status_filter)
    return [{"id": r.id, "number": r.number, "invoice_id": r.invoice_id, "deposit_id": r.deposit_id, "amount": r.amount, "method": r.method, "reason": r.reason, "status": r.status,
             "requested_by": r.requested_by, "requested_at": r.requested_at.isoformat(), "decision_note": r.decision_note} for r in db.scalars(query)]


@router.post("/refunds/{refund_id}/decide")
def decide_refund(refund_id: PathId, data: DecideIn, request: Request, user: User = Depends(approve), db: Session = Depends(get_db)):
    r = db.get(Refund, refund_id)
    if r is None:
        raise HTTPException(404, "Refund not found.")
    fin.decide_refund(db, r, user, data.approve, data.note)
    audit_service.log_action(db, user, "REFUND_DECIDED", "refund", r.id, request, r.status)
    return {"id": r.id, "number": r.number, "status": r.status}


# ------------------------------------------------------------------ packages
@router.get("/packages")
def packages(user: User = Depends(view), db: Session = Depends(get_db)):
    return [{"id": p.id, "name": p.name, "price": p.price, "gst_percent": p.gst_percent, "inclusions": p.inclusions, "is_active": p.is_active} for p in db.scalars(select(BillingPackage).order_by(BillingPackage.name))]


@router.post("/packages", status_code=status.HTTP_201_CREATED)
def add_package(data: PackageIn, request: Request, user: User = Depends(require_permission("service.manage")), db: Session = Depends(get_db)):
    if db.scalar(select(BillingPackage.id).where(BillingPackage.name == data.name.strip())):
        raise HTTPException(status.HTTP_409_CONFLICT, "This package already exists.")
    row = BillingPackage(**{**data.model_dump(), "name": data.name.strip()})
    db.add(row)
    db.commit()
    audit_service.log_action(db, user, "PACKAGE_ADDED", "billing_package", row.id, request, row.name)
    return {"id": row.id, "name": row.name}


# ------------------------------------------------------------------ reports
@router.get("/reports/daily-cash")
def daily_cash(day: date | None = None, user: User = Depends(report), db: Session = Depends(get_db)):
    return fin.daily_cash(db, day or date.today())


@router.get("/reports/outstanding")
def outstanding(user: User = Depends(report), db: Session = Depends(get_db)):
    return fin.outstanding(db)


@router.get("/reports/revenue")
def revenue(from_day: date | None = None, to_day: date | None = None, user: User = Depends(report), db: Session = Depends(get_db)):
    end = to_day or date.today()
    start = from_day or (end - timedelta(days=30))
    if start > end or (end - start).days > 366:
        raise HTTPException(422, "Choose a period of at most a year, from earlier to later.")
    return fin.revenue(db, start, end)


# ------------------------------------------------------------------ the patient's own bills
@router.get("/my-invoices")
def my_invoices(user: User = Depends(require_roles(PATIENT)), db: Session = Depends(get_db)):
    p = get_patient_profile(db, user)
    return [fin.invoice_out(db, i) for i in db.scalars(select(Invoice).where(Invoice.patient_id == p.id, Invoice.status == "FINAL").order_by(Invoice.id.desc()))]
