"""Finance: charges, invoices, payments and receipts, advances (deposits), refunds, discounts, packages, insurance claims, and the reports.

Rules that never depend on AI:
- a price comes from the price list at the moment a line is made and is copied onto the line; a FINAL invoice is never edited (cancel with a reason and issue again)
- a payment is never more than the balance; a refund is never more than what was paid; money is counted in rupees to two places
- a refund and a discount above the limit are approved by a different person than the one who asked
- when an insurer has approved an amount, the patient pays only the rest; the insurer's settlement is a payment on the same invoice
- if no price is set for something, no charge is invented: it is reported as "no price in the list"
"""
from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    Admission, BedAssignment, BillingPackage, ClaimDocument, ClaimEvent, Deposit, EncounterCharge, InsuranceClaim, Invoice, InvoiceLine, LabTestOrder, Patient, PatientInsurance, Payment,
    RadiologyOrder, Refund, Sale, ServiceCatalog, User, utcnow,
)
from app.services import hospital_service
from app.utils.locking import lock
from app.utils.clock import hospital_today

METHODS = ("CASH", "UPI", "CARD", "BANK", "ADVANCE")
NEEDS_REFERENCE = ("UPI", "CARD", "BANK")
BED_WORDS = {"GENERAL": "general", "PRIVATE": "private", "SEMI_PRIVATE": "semi", "ICU": "icu", "NICU": "nicu", "PICU": "picu", "EMERGENCY": "emergency", "ISOLATION": "isolation", "RECOVERY": "recovery"}


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def money(x: float | None) -> float:
    return round(float(x or 0) + 0.0, 2)


def next_number(db: Session, model, column, prefix: str) -> str:
    count = db.scalar(select(func.count(model.id)).where(column.is_not(None))) or 0         # only numbered rows count: a draft has no number, so the numbers have no gaps
    while True:
        count += 1
        number = f"{prefix}-{hospital_today().year}-{count:05d}"
        if not db.scalar(select(model.id).where(column == number)):
            return number


def discount_limit_percent(db: Session) -> float:
    return float(hospital_service.setting_value(db, "discount_approval_percent"))


# ------------------------------------------------------------------ charges
def _price(db: Session, category: str, name: str, extra_word: str | None = None) -> ServiceCatalog | None:
    rows = db.scalars(select(ServiceCatalog).where(ServiceCatalog.category == category, ServiceCatalog.is_active.is_(True)).order_by(ServiceCatalog.id)).all()
    needle = (extra_word or name).strip().lower()
    for r in rows:
        if r.name.strip().lower() == needle:
            return r
    for r in rows:
        if needle in r.name.lower() or r.name.lower() in needle:
            return r
    return None


def _charge_exists(db: Session, source_type: str, source_id: int) -> bool:
    return db.scalar(select(EncounterCharge.id).where(EncounterCharge.source_type == source_type, EncounterCharge.source_id == source_id, EncounterCharge.status != "CANCELLED").limit(1)) is not None


def collect_charges(db: Session, patient: Patient, user: User) -> dict:
    """Turn finished lab tests, approved scans and bed days into pending charges, once each, at the price in the price list. Returns what was added and what has no price."""
    created, unpriced = [], []
    for o in db.scalars(select(LabTestOrder).where(LabTestOrder.patient_id == patient.id, LabTestOrder.status == "COMPLETED", LabTestOrder.encounter_id.is_not(None))):
        if _charge_exists(db, "LAB", o.id):
            continue
        svc = _price(db, "LAB", o.test_name)
        (created if svc else unpriced).append(o.test_name)
        if svc:
            db.add(EncounterCharge(encounter_id=o.encounter_id, patient_id=patient.id, service_id=svc.id, description=f"Lab: {o.test_name}", amount=svc.price, gst_percent=svc.gst_percent,
                                   source_type="LAB", source_id=o.id, created_by=user.id))
    for o in db.scalars(select(RadiologyOrder).where(RadiologyOrder.patient_id == patient.id, RadiologyOrder.status == "APPROVED", RadiologyOrder.encounter_id.is_not(None))):
        if _charge_exists(db, "RADIOLOGY", o.id):
            continue
        svc = _price(db, "RADIOLOGY", o.study)
        (created if svc else unpriced).append(o.study)
        if svc:
            db.add(EncounterCharge(encounter_id=o.encounter_id, patient_id=patient.id, service_id=svc.id, description=f"Scan: {o.study}", amount=svc.price, gst_percent=svc.gst_percent,
                                   source_type="RADIOLOGY", source_id=o.id, created_by=user.id))
    now = utcnow()
    for adm in db.scalars(select(Admission).where(Admission.patient_id == patient.id)):
        for stay in db.scalars(select(BedAssignment).where(BedAssignment.admission_id == adm.id)):
            days = max(1, ((stay.released_at or now) - stay.assigned_at).days + (0 if (stay.released_at or now) - stay.assigned_at < timedelta(hours=1) else 1))
            ward = stay.bed.ward.ward_type
            svc = _price(db, "BED", "", BED_WORDS.get(ward, ward.lower()))
            for day in range(days):
                key = stay.id * 10000 + day
                if _charge_exists(db, "BED", key):
                    continue
                if svc is None:
                    if f"Bed ({ward.replace('_', ' ').lower()})" not in unpriced:
                        unpriced.append(f"Bed ({ward.replace('_', ' ').lower()})")
                    break
                created.append(f"Bed day {day + 1} ({svc.name})")
                db.add(EncounterCharge(encounter_id=adm.encounter_id, patient_id=patient.id, service_id=svc.id, description=f"{svc.name}: day {day + 1}", amount=svc.price,
                                       gst_percent=svc.gst_percent, source_type="BED", source_id=key, created_by=user.id))
    db.commit()
    return {"added": created, "no_price_in_list": unpriced}


def billed_charge_ids(db: Session) -> set[int]:
    """Charges that sit on an invoice that is not cancelled."""
    return set(db.scalars(select(InvoiceLine.charge_id).join(Invoice, Invoice.id == InvoiceLine.invoice_id).where(InvoiceLine.charge_id.is_not(None), Invoice.status != "CANCELLED")))


def pending_charges(db: Session, patient_id: int) -> list[dict]:
    billed = billed_charge_ids(db)
    rows = db.scalars(select(EncounterCharge).where(EncounterCharge.patient_id == patient_id, EncounterCharge.status == "PENDING").order_by(EncounterCharge.id))
    return [{"id": c.id, "description": c.description, "amount": money(c.amount), "gst_percent": c.gst_percent, "created_at": c.created_at.isoformat()} for c in rows if c.id not in billed]


# ------------------------------------------------------------------ invoices
def _line(description: str, unit_price: float, gst: float, quantity: int = 1, **ids) -> InvoiceLine:
    amount = money(unit_price * quantity)
    return InvoiceLine(description=description[:250], quantity=quantity, unit_price=money(unit_price), gst_percent=gst or 0, amount=amount, tax=money(amount * (gst or 0) / 100), **ids)


def recalc(inv: Invoice) -> None:
    inv.subtotal = money(sum(l.amount for l in inv.lines))
    inv.tax = money(sum(l.tax for l in inv.lines))
    gross = inv.subtotal + inv.tax
    inv.discount = money(min(inv.discount or 0, gross))
    inv.total = money(gross - inv.discount)


def _draft(inv: Invoice) -> None:
    if inv.status != "DRAFT":
        raise conflict(f"This invoice is {inv.status.lower()}: a final invoice is never edited. Cancel it with a reason and make a new one.")


def create_invoice(db: Session, user: User, patient: Patient, admission_id: int | None, charge_ids: list[int], services: list[dict], package_ids: list[int], note: str | None) -> Invoice:
    if not (charge_ids or services or package_ids):
        raise HTTPException(422, "Add at least one charge, service or package.")
    adm = None
    if admission_id is not None:
        adm = db.get(Admission, admission_id)
        if adm is None or adm.patient_id != patient.id:
            raise HTTPException(422, "That admission does not belong to this patient.")
    inv = Invoice(patient_id=patient.id, admission_id=adm.id if adm else None, encounter_id=adm.encounter_id if adm else None, created_by=user.id, note=note)
    db.add(inv)
    db.flush()
    add_lines(db, inv, charge_ids, services, package_ids)
    db.commit()
    return inv


def add_lines(db: Session, inv: Invoice, charge_ids: list[int], services: list[dict], package_ids: list[int]) -> None:
    _draft(inv)
    billed = billed_charge_ids(db)
    for cid in dict.fromkeys(charge_ids):
        c = db.get(EncounterCharge, cid)
        if c is None or c.patient_id != inv.patient_id or c.status != "PENDING":
            raise HTTPException(422, "A charge does not exist, belongs to another patient, or is not pending.")
        if cid in billed or any(l.charge_id == cid for l in inv.lines):
            raise conflict(f"'{c.description}' is already on an invoice.")
        inv.lines.append(_line(c.description, c.amount, c.gst_percent, charge_id=c.id, service_id=c.service_id))
    for s in services:
        svc = db.get(ServiceCatalog, s["service_id"])
        if svc is None or not svc.is_active:
            raise HTTPException(422, "That service is not in the price list.")
        inv.lines.append(_line(svc.name, svc.price, svc.gst_percent, s.get("quantity", 1), service_id=svc.id))
    for pid in package_ids:
        pkg = db.get(BillingPackage, pid)
        if pkg is None or not pkg.is_active:
            raise HTTPException(422, "That package does not exist.")
        inv.lines.append(_line(f"Package: {pkg.name}", pkg.price, pkg.gst_percent, 1, package_id=pkg.id))
    db.flush()
    recalc(inv)


def remove_line(db: Session, inv: Invoice, line_id: int) -> None:
    _draft(inv)
    line = next((l for l in inv.lines if l.id == line_id), None)
    if line is None:
        raise HTTPException(404, "Line not found.")
    inv.lines.remove(line)
    db.flush()
    if not inv.lines:
        raise HTTPException(422, "An invoice needs at least one line: cancel the draft instead.")
    recalc(inv)
    db.commit()


def set_discount(db: Session, inv: Invoice, user: User, amount: float, reason: str | None) -> Invoice:
    _draft(inv)
    gross = inv.subtotal + inv.tax
    if amount < 0 or amount > gross:
        raise HTTPException(422, "The discount cannot be more than the bill.")
    if amount > 0 and not (reason or "").strip():
        raise HTTPException(422, "A discount needs a reason.")
    inv.discount, inv.discount_reason, inv.discount_approved_by = money(amount), (reason or "").strip() or None, None
    recalc(inv)
    db.commit()
    return inv


def needs_discount_approval(db: Session, inv: Invoice) -> bool:
    gross = inv.subtotal + inv.tax
    return gross > 0 and inv.discount * 100 / gross > discount_limit_percent(db) + 1e-9


def approve_discount(db: Session, inv: Invoice, user: User) -> Invoice:
    _draft(inv)
    if inv.discount <= 0:
        raise conflict("There is no discount to approve.")
    if inv.created_by == user.id:
        raise conflict("A discount must be approved by a different person than the one who made the invoice.")
    inv.discount_approved_by = user.id
    db.commit()
    return inv


def finalise(db: Session, inv: Invoice, user: User) -> Invoice:
    lock(db, inv)
    _draft(inv)
    if not inv.lines:
        raise HTTPException(422, "An invoice needs at least one line.")
    if needs_discount_approval(db, inv) and inv.discount_approved_by is None:
        raise conflict(f"A discount above {discount_limit_percent(db):g}% must be approved by a second person first.")
    inv.number = next_number(db, Invoice, Invoice.number, hospital_service.setting_value(db, "invoice_prefix") or "INV")
    inv.status, inv.finalised_by, inv.finalised_at = "FINAL", user.id, utcnow()
    for l in inv.lines:
        if l.charge_id:
            db.get(EncounterCharge, l.charge_id).status = "INVOICED"
    db.commit()
    return inv


def paid(inv: Invoice) -> float:
    return money(sum(p.amount for p in inv.payments))


def refunded(inv: Invoice) -> float:
    return money(sum(r.amount for r in inv.refunds if r.status == "APPROVED"))


def balance(inv: Invoice) -> float:
    return money(inv.total - paid(inv) + refunded(inv)) if inv.status == "FINAL" else 0.0


def cancel(db: Session, inv: Invoice, user: User, reason: str) -> Invoice:
    lock(db, inv)
    if inv.status == "CANCELLED":
        raise conflict("This invoice is already cancelled.")
    if inv.status == "DRAFT":
        inv.status, inv.cancel_reason, inv.cancelled_by = "CANCELLED", reason, user.id
        db.commit()
        return inv
    if money(paid(inv) - refunded(inv)) > 0:
        raise conflict("Money has been received on this invoice: refund it first, then cancel.")
    if any(c for c in db.scalars(select(InsuranceClaim).where(InsuranceClaim.invoice_id == inv.id)) if c.status not in ("REJECTED", "DRAFT")):
        raise conflict("An insurance claim is in progress for this invoice.")
    inv.status, inv.cancel_reason, inv.cancelled_by = "CANCELLED", reason, user.id
    for l in inv.lines:
        if l.charge_id:
            charge = db.get(EncounterCharge, l.charge_id)
            if charge and charge.status == "INVOICED":
                charge.status = "PENDING"
    db.commit()
    return inv


def claim_of(db: Session, inv: Invoice) -> InsuranceClaim | None:
    return db.scalar(select(InsuranceClaim).where(InsuranceClaim.invoice_id == inv.id))


def insurer_approved(db: Session, inv: Invoice) -> float:
    c = claim_of(db, inv)
    return money(c.approved_amount) if c and c.status in ("APPROVED", "PARTIAL", "SETTLED") else 0.0


def patient_payable(db: Session, inv: Invoice) -> float:
    return money(inv.total - insurer_approved(db, inv))


# ------------------------------------------------------------------ payments, deposits, refunds
def deposit_balance(d: Deposit) -> float:
    return money(d.amount - d.used - d.refunded)


def pay(db: Session, inv: Invoice, user: User, amount: float, method: str, reference: str | None, deposit_id: int | None = None, claim_id: int | None = None) -> Payment:
    lock(db, inv, db.get(Deposit, deposit_id) if deposit_id else None)
    if inv.status != "FINAL":
        raise conflict("Payments are taken only on a final invoice.")
    amount = money(amount)
    if amount <= 0:
        raise HTTPException(422, "The amount must be more than zero.")
    if claim_id is None:
        if method not in METHODS:
            raise HTTPException(422, "Please choose the payment method from the list.")
        if method in NEEDS_REFERENCE and not (reference or "").strip():
            raise HTTPException(422, "Please enter the transaction reference.")
    if amount > balance(inv) + 1e-9:
        raise conflict(f"The balance is {balance(inv):.2f}: the payment cannot be more than that.")
    if claim_id is None:
        own = money(sum(p.amount for p in inv.payments if p.method != "INSURANCE") + amount)
        if own > patient_payable(db, inv) + 1e-9:
            raise conflict(f"The insurer has approved part of this bill: the patient pays {patient_payable(db, inv):.2f} at most.")
    deposit = None
    if method == "ADVANCE":
        deposit = db.get(Deposit, deposit_id) if deposit_id else None
        if deposit is None or deposit.patient_id != inv.patient_id:
            raise HTTPException(422, "Please choose this patient's advance.")
        if amount > deposit_balance(deposit) + 1e-9:
            raise conflict(f"The advance has only {deposit_balance(deposit):.2f} left.")
        deposit.used = money(deposit.used + amount)
    p = Payment(receipt_number=next_number(db, Payment, Payment.receipt_number, "REC"), invoice_id=inv.id, amount=amount, method="INSURANCE" if claim_id else method, reference=(reference or None),
                deposit_id=deposit.id if deposit else None, claim_id=claim_id, received_by=user.id)
    db.add(p)
    db.flush()
    db.expire(inv, ["payments"])
    db.commit()
    return p


def take_deposit(db: Session, user: User, patient: Patient, admission_id: int | None, amount: float, method: str, reference: str | None) -> Deposit:
    amount = money(amount)
    if amount <= 0:
        raise HTTPException(422, "The amount must be more than zero.")
    if method not in METHODS or method == "ADVANCE":
        raise HTTPException(422, "Please choose how the advance was paid (cash, UPI, card or bank).")
    if method in NEEDS_REFERENCE and not (reference or "").strip():
        raise HTTPException(422, "Please enter the transaction reference.")
    if admission_id is not None:
        adm = db.get(Admission, admission_id)
        if adm is None or adm.patient_id != patient.id:
            raise HTTPException(422, "That admission does not belong to this patient.")
    d = Deposit(receipt_number=next_number(db, Deposit, Deposit.receipt_number, "DEP"), patient_id=patient.id, admission_id=admission_id, amount=amount, method=method, reference=reference, received_by=user.id)
    db.add(d)
    db.commit()
    return d


def _refundable(db: Session, inv: Invoice) -> float:
    own_paid = sum(p.amount for p in inv.payments if p.method != "INSURANCE")
    pending = sum(r.amount for r in inv.refunds if r.status == "PENDING")
    return money(own_paid - refunded(inv) - pending)


def request_refund(db: Session, user: User, inv: Invoice | None, deposit: Deposit | None, amount: float, method: str, reason: str) -> Refund:
    lock(db, inv, deposit)
    amount = money(amount)
    if amount <= 0:
        raise HTTPException(422, "The amount must be more than zero.")
    if method not in METHODS or method == "ADVANCE":
        raise HTTPException(422, "Please choose how the money is given back (cash, UPI, card or bank).")
    if inv is not None:
        if inv.status != "FINAL":
            raise conflict("Only money received on a final invoice can be refunded.")
        if amount > _refundable(db, inv) + 1e-9:
            raise conflict(f"At most {_refundable(db, inv):.2f} can be refunded on this invoice.")
    else:
        pending = sum(r.amount for r in db.scalars(select(Refund).where(Refund.deposit_id == deposit.id, Refund.status == "PENDING")))
        if amount > deposit_balance(deposit) - pending + 1e-9:
            raise conflict(f"At most {deposit_balance(deposit) - pending:.2f} of this advance can be refunded.")
    r = Refund(number=next_number(db, Refund, Refund.number, "RFD"), invoice_id=inv.id if inv else None, deposit_id=deposit.id if deposit else None, amount=amount, method=method,
               reason=reason.strip(), requested_by=user.id)
    db.add(r)
    db.commit()
    return r


def decide_refund(db: Session, r: Refund, user: User, approve: bool, note: str | None) -> Refund:
    lock(db, r, db.get(Invoice, r.invoice_id) if r.invoice_id else None, db.get(Deposit, r.deposit_id) if r.deposit_id else None)
    if r.status != "PENDING":
        raise conflict(f"This refund is already {r.status.lower()}.")
    if r.requested_by == user.id:
        raise conflict("A refund must be approved by a different person than the one who asked for it.")
    if not approve and not (note or "").strip():
        raise HTTPException(422, "Please write why it is rejected.")
    if approve:
        if r.invoice_id:
            inv = db.get(Invoice, r.invoice_id)
            own_paid = sum(p.amount for p in inv.payments if p.method != "INSURANCE")
            if r.amount > money(own_paid - refunded(inv)) + 1e-9:
                raise conflict("The invoice no longer has that much to refund.")
        else:
            d = db.get(Deposit, r.deposit_id)
            if r.amount > deposit_balance(d) + 1e-9:
                raise conflict("The advance no longer has that much left.")
            d.refunded = money(d.refunded + r.amount)
    r.status, r.decided_by, r.decided_at, r.decision_note = "APPROVED" if approve else "REJECTED", user.id, utcnow(), note
    db.commit()
    return r


# ------------------------------------------------------------------ output
def invoice_out(db: Session, inv: Invoice, detail: bool = True) -> dict:
    claim = claim_of(db, inv)
    row = {"id": inv.id, "number": inv.number, "status": inv.status, "patient_id": inv.patient_id, "patient_name": inv.patient.user.full_name, "patient_code": inv.patient.patient_code,
           "subtotal": inv.subtotal, "tax": inv.tax, "discount": inv.discount, "total": inv.total, "paid": paid(inv), "refunded": refunded(inv), "balance": balance(inv),
           "insurer_approved": insurer_approved(db, inv), "patient_payable": patient_payable(db, inv), "claim_status": claim.status if claim else None,
           "created_at": inv.created_at.isoformat(), "finalised_at": inv.finalised_at.isoformat() if inv.finalised_at else None,
           "needs_discount_approval": needs_discount_approval(db, inv) and inv.discount_approved_by is None, "discount_reason": inv.discount_reason}
    if detail:
        row.update({"note": inv.note, "cancel_reason": inv.cancel_reason, "admission_id": inv.admission_id, "claim_id": claim.id if claim else None,
                    "lines": [{"id": l.id, "description": l.description, "quantity": l.quantity, "unit_price": l.unit_price, "gst_percent": l.gst_percent, "amount": l.amount, "tax": l.tax} for l in inv.lines],
                    "payments": [{"id": p.id, "receipt_number": p.receipt_number, "amount": p.amount, "method": p.method, "reference": p.reference, "received_at": p.received_at.isoformat()} for p in inv.payments],
                    "refunds": [{"id": r.id, "number": r.number, "amount": r.amount, "status": r.status, "reason": r.reason, "method": r.method} for r in inv.refunds]})
    return row


def receipt_out(db: Session, p: Payment) -> dict:
    inv = db.get(Invoice, p.invoice_id)
    profile = hospital_service.get_profile(db)
    return {"receipt_number": p.receipt_number, "received_at": p.received_at.isoformat(), "amount": p.amount, "method": p.method, "reference": p.reference,
            "invoice_number": inv.number, "invoice_total": inv.total, "balance_after": balance(inv), "patient_name": inv.patient.user.full_name, "patient_code": inv.patient.patient_code,
            "received_by": db.get(User, p.received_by).full_name,
            "hospital": {"name": getattr(profile, "name", None), "address": getattr(profile, "address", None), "phone": getattr(profile, "phone", None), "gst_number": getattr(profile, "gst_number", None)}}


# ------------------------------------------------------------------ reports
def _day_range(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min).astimezone(timezone.utc).replace(tzinfo=None)
    return start, start + timedelta(days=1)


def daily_cash(db: Session, day: date) -> dict:
    """What was received and paid back on one local day, by method and by person. The insurer's settlements are shown apart from the counter's cash."""
    start, end = _day_range(day)
    pays = db.scalars(select(Payment).where(Payment.received_at >= start, Payment.received_at < end)).all()
    deps = db.scalars(select(Deposit).where(Deposit.received_at >= start, Deposit.received_at < end)).all()
    refs = db.scalars(select(Refund).where(Refund.status == "APPROVED", Refund.decided_at >= start, Refund.decided_at < end)).all()
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({p.received_by for p in pays} | {d.received_by for d in deps} | {r.requested_by for r in refs} or {0})))}
    by_method: dict[str, float] = {}
    by_user: dict[str, float] = {}
    for p in pays:
        if p.method in ("ADVANCE", "INSURANCE"):
            continue
        by_method[p.method] = money(by_method.get(p.method, 0) + p.amount)
        by_user[names[p.received_by]] = money(by_user.get(names[p.received_by], 0) + p.amount)
    for d in deps:
        by_method[d.method] = money(by_method.get(d.method, 0) + d.amount)
        by_user[names[d.received_by]] = money(by_user.get(names[d.received_by], 0) + d.amount)
    collected = money(sum(by_method.values()))
    paid_back = money(sum(r.amount for r in refs))
    return {"day": day.isoformat(), "by_method": by_method, "by_user": by_user, "collected": collected, "refunds_paid": paid_back, "net": money(collected - paid_back),
            "insurer_settlements": money(sum(p.amount for p in pays if p.method == "INSURANCE")), "advance_used": money(sum(p.amount for p in pays if p.method == "ADVANCE")),
            "invoices_final": db.scalar(select(func.count(Invoice.id)).where(Invoice.status == "FINAL", Invoice.finalised_at >= start, Invoice.finalised_at < end)) or 0}


def outstanding(db: Session) -> dict:
    today = utcnow()
    rows, buckets = [], {"0-30": 0.0, "31-60": 0.0, "61+": 0.0}
    for inv in db.scalars(select(Invoice).where(Invoice.status == "FINAL").order_by(Invoice.finalised_at)):
        b = balance(inv)
        if b <= 0:
            continue
        age = (today - inv.finalised_at).days
        key = "0-30" if age <= 30 else "31-60" if age <= 60 else "61+"
        buckets[key] = money(buckets[key] + b)
        rows.append({"invoice_id": inv.id, "number": inv.number, "patient_name": inv.patient.user.full_name, "patient_code": inv.patient.patient_code, "total": inv.total, "balance": b,
                     "age_days": age, "insurer_approved": insurer_approved(db, inv), "claim_status": (claim_of(db, inv).status if claim_of(db, inv) else None)})
    return {"total_outstanding": money(sum(r["balance"] for r in rows)), "aging": buckets, "invoices": rows}


def revenue(db: Session, start_day: date, end_day: date) -> dict:
    start, _ = _day_range(start_day)
    _, end = _day_range(end_day)
    by_category: dict[str, dict] = {}
    for inv in db.scalars(select(Invoice).where(Invoice.status == "FINAL", Invoice.finalised_at >= start, Invoice.finalised_at < end)):
        for l in inv.lines:
            svc = db.get(ServiceCatalog, l.service_id) if l.service_id else None
            key = svc.category if svc else ("PACKAGE" if l.package_id else "OTHER")
            row = by_category.setdefault(key, {"category": key, "amount": 0.0, "tax": 0.0, "lines": 0})
            row["amount"], row["tax"], row["lines"] = money(row["amount"] + l.amount), money(row["tax"] + l.tax), row["lines"] + 1
    sales = db.execute(select(func.coalesce(func.sum(Sale.total), 0), func.count(Sale.id)).where(Sale.created_at >= start, Sale.created_at < end)).one()
    discounts = db.scalar(select(func.coalesce(func.sum(Invoice.discount), 0)).where(Invoice.status == "FINAL", Invoice.finalised_at >= start, Invoice.finalised_at < end))
    return {"from": start_day.isoformat(), "to": end_day.isoformat(), "by_category": sorted(by_category.values(), key=lambda r: -r["amount"]), "invoiced_total": money(sum(r["amount"] + r["tax"] for r in by_category.values()) - (discounts or 0)),
            "discounts_given": money(discounts), "pharmacy_sales": {"total": money(sales[0]), "bills": sales[1]}}


# ------------------------------------------------------------------ insurance claims
def default_documents(db: Session) -> list[str]:
    return [x.strip() for x in hospital_service.setting_value(db, "claim_documents").split(",") if x.strip()]


def _event(claim: InsuranceClaim, user: User, text: str) -> None:
    claim.events.append(ClaimEvent(text=text[:300], created_by=user.id))
    claim.updated_at = utcnow()


def create_claim(db: Session, user: User, inv: Invoice, policy_id: int) -> InsuranceClaim:
    if inv.status != "FINAL":
        raise conflict("A claim is made for a final invoice.")
    if claim_of(db, inv):
        raise conflict("This invoice already has a claim.")
    policy = db.get(PatientInsurance, policy_id)
    if policy is None or policy.patient_id != inv.patient_id:
        raise HTTPException(422, "That policy does not belong to this patient.")
    if not policy.is_active or (policy.valid_to and policy.valid_to < hospital_today()) or (policy.valid_from and policy.valid_from > hospital_today()):
        raise conflict("This policy is not active or not valid today.")
    claim = InsuranceClaim(claim_number=next_number(db, InsuranceClaim, InsuranceClaim.claim_number, "CLM"), invoice_id=inv.id, patient_insurance_id=policy.id, created_by=user.id,
                           documents=[ClaimDocument(name=n) for n in default_documents(db)])
    db.add(claim)
    _event(claim, user, f"Claim made with {policy.insurer_name}" + (f" (TPA {policy.tpa_name})" if policy.tpa_name else ""))
    db.commit()
    return claim


def _claim_state(claim: InsuranceClaim, *allowed: str) -> None:
    if claim.status not in allowed:
        raise conflict(f"This claim is '{claim.status.lower().replace('_', ' ')}': that step is not possible now.")


def preauth_request(db: Session, claim: InsuranceClaim, user: User, amount: float, reference: str | None) -> InsuranceClaim:
    _claim_state(claim, "DRAFT")
    if amount <= 0 or amount > claim.invoice.total + 1e-9:
        raise HTTPException(422, "The amount must be more than zero and not more than the invoice.")
    claim.status, claim.preauth_requested, claim.preauth_reference = "PREAUTH_SENT", money(amount), reference
    _event(claim, user, f"Pre-authorisation of {amount:.2f} requested" + (f" (ref {reference})" if reference else ""))
    db.commit()
    return claim


def preauth_decide(db: Session, claim: InsuranceClaim, user: User, approved_amount: float, reason: str | None) -> InsuranceClaim:
    _claim_state(claim, "PREAUTH_SENT")
    if approved_amount > (claim.preauth_requested or 0) + 1e-9 or approved_amount < 0:
        raise HTTPException(422, "The approved amount cannot be more than what was asked.")
    if approved_amount == 0:
        if not (reason or "").strip():
            raise HTTPException(422, "Please write why the pre-authorisation was refused.")
        claim.status, claim.rejection_reason, claim.preauth_approved = "REJECTED", reason, 0
        _event(claim, user, f"Pre-authorisation refused: {reason}")
    else:
        claim.status, claim.preauth_approved = "PREAUTH_APPROVED", money(approved_amount)
        _event(claim, user, f"Pre-authorisation approved for {approved_amount:.2f}")
    db.commit()
    return claim


def mark_document(db: Session, claim: InsuranceClaim, user: User, doc_id: int, received: bool) -> InsuranceClaim:
    doc = next((d for d in claim.documents if d.id == doc_id), None)
    if doc is None:
        raise HTTPException(404, "Document not found.")
    if claim.status in ("SETTLED", "REJECTED"):
        raise conflict("This claim is closed.")
    doc.received, doc.received_by, doc.received_at = received, user.id, utcnow() if received else None
    _event(claim, user, f"{doc.name}: {'received' if received else 'marked as not received'}")
    db.commit()
    return claim


def submit(db: Session, claim: InsuranceClaim, user: User, amount: float) -> InsuranceClaim:
    _claim_state(claim, "DRAFT", "PREAUTH_APPROVED")
    missing = [d.name for d in claim.documents if not d.received]
    if missing:
        raise conflict("These documents are still needed: " + ", ".join(missing) + ".")
    if amount <= 0 or amount > claim.invoice.total + 1e-9:
        raise HTTPException(422, "The claimed amount must be more than zero and not more than the invoice.")
    claim.status, claim.claimed_amount = "SUBMITTED", money(amount)
    _event(claim, user, f"Claim of {amount:.2f} submitted")
    db.commit()
    return claim


def decide(db: Session, claim: InsuranceClaim, user: User, approved_amount: float, reason: str | None) -> InsuranceClaim:
    _claim_state(claim, "SUBMITTED")
    approved = money(approved_amount)
    if approved < 0 or approved > claim.claimed_amount + 1e-9:
        raise HTTPException(422, "The approved amount cannot be more than the claimed amount.")
    claim.approved_amount, claim.rejected_amount = approved, money(claim.claimed_amount - approved)
    if approved == claim.claimed_amount:
        claim.status = "APPROVED"
    else:
        if not (reason or "").strip():
            raise HTTPException(422, "Please write why the claim was not approved in full.")
        claim.status, claim.rejection_reason = ("PARTIAL" if approved > 0 else "REJECTED"), reason
    _event(claim, user, f"Insurer decision: approved {approved:.2f}, rejected {claim.rejected_amount:.2f}" + (f" ({reason})" if reason else ""))
    db.commit()
    return claim


def settle(db: Session, claim: InsuranceClaim, user: User, amount: float, reference: str) -> InsuranceClaim:
    lock(db, claim, claim.invoice)
    _claim_state(claim, "APPROVED", "PARTIAL")
    amount = money(amount)
    if amount <= 0 or amount > money(claim.approved_amount - claim.settled_amount) + 1e-9:
        raise HTTPException(422, f"The settlement must be more than zero and at most {claim.approved_amount - claim.settled_amount:.2f}.")
    if not (reference or "").strip():
        raise HTTPException(422, "Please enter the settlement reference.")
    pay(db, claim.invoice, user, amount, "INSURANCE", reference, claim_id=claim.id)
    claim.settled_amount = money(claim.settled_amount + amount)
    claim.settlement_reference = reference
    if claim.settled_amount >= claim.approved_amount - 1e-9:
        claim.status = "SETTLED"
    _event(claim, user, f"Insurer paid {amount:.2f} (ref {reference})")
    db.commit()
    return claim


def claim_out(db: Session, c: InsuranceClaim) -> dict:
    inv = c.invoice
    return {"id": c.id, "claim_number": c.claim_number, "status": c.status, "invoice_id": inv.id, "invoice_number": inv.number, "invoice_total": inv.total, "patient_name": inv.patient.user.full_name,
            "patient_code": inv.patient.patient_code, "insurer": c.policy.insurer_name, "tpa": c.policy.tpa_name, "policy_number": c.policy.policy_number, "member_id": c.policy.member_id,
            "preauth_reference": c.preauth_reference, "preauth_requested": c.preauth_requested, "preauth_approved": c.preauth_approved, "claimed_amount": c.claimed_amount, "approved_amount": c.approved_amount,
            "rejected_amount": c.rejected_amount, "settled_amount": c.settled_amount, "settlement_reference": c.settlement_reference, "rejection_reason": c.rejection_reason,
            "patient_payable": patient_payable(db, inv), "created_at": c.created_at.isoformat(),
            "documents": [{"id": d.id, "name": d.name, "received": d.received} for d in c.documents],
            "events": [{"text": e.text, "at": e.created_at.isoformat()} for e in c.events]}
