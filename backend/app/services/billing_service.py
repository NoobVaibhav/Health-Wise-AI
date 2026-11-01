"""Medical-shop billing: scan a barcode, sell the medicine, take it out of stock and print a bill.

Rules (all decided by the server, never by the browser):
- the price and GST always come from the stock register, not from what the screen sends
- stock is taken from the batch that expires first; expired batches are never sold
- not enough stock -> the whole sale is refused and nothing changes
- a line that fills a doctor's prescription also records the dispensing (and does not take the stock twice)
- bill number: BILL-YYYYMMDD-0001, 0002 ... (restarts every day)
"""
from collections import defaultdict
from datetime import date, datetime, time, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import MedicineInventory, PharmacyStaff, Prescription, Sale, SaleItem
from app.schemas.billing import (
    BillPreview, PrescriptionBillRequest, ReceiveStock, SaleCreate, SaleItemOut, SaleListItem, SaleOut, SalesSummary, StockLookup, StockLookupBatch,
)
from app.schemas.pharmacy import DispenseRequest
from app.services import dispensing_service
from app.services.prescription_service import is_open
from app.services import stock_service
from app.services.serializers import dispensed_quantity

DEFAULT_SHOP = "HealthWise Pharmacy"


def _usable(row: MedicineInventory) -> bool:
    return row.quantity > 0 and not row.recalled and (row.expiry_date is None or row.expiry_date >= date.today())


def _order(rows: list[MedicineInventory]) -> list[MedicineInventory]:
    """Earliest expiry first (no expiry date last)."""
    return sorted(rows, key=lambda r: (r.expiry_date is None, r.expiry_date or date.max, r.id))


def find_batches(db: Session, barcode: str | None = None, inventory_id: int | None = None) -> list[MedicineInventory]:
    """All batches of one product: same barcode, or (no barcode) same medicine name. The rows are locked until the sale is committed
    (on PostgreSQL), so two cashiers cannot sell the same last units."""
    if inventory_id is not None:
        row = db.get(MedicineInventory, inventory_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Medicine not found in stock.")
        if row.barcode:
            rows = db.scalars(select(MedicineInventory).where(MedicineInventory.barcode == row.barcode).with_for_update()).all()
        else:
            rows = db.scalars(select(MedicineInventory).where(
                func.lower(MedicineInventory.medicine_name) == row.medicine_name.lower()).with_for_update()).all()
    else:
        code = (barcode or "").strip()
        rows = db.scalars(select(MedicineInventory).where(MedicineInventory.barcode == code).with_for_update()).all() if code else []
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No medicine with this barcode was found in stock.")
    return _order(list(rows))


def lookup(db: Session, code: str) -> StockLookup:
    rows = find_batches(db, barcode=code)
    first = next((r for r in rows if _usable(r)), rows[0])
    return StockLookup(
        barcode=first.barcode, medicine_name=first.medicine_name, unit_price=first.unit_price,
        gst_percent=first.gst_percent or 0, available=sum(r.quantity for r in rows if _usable(r)),
        batches=[StockLookupBatch(id=r.id, batch_number=r.batch_number, quantity=r.quantity, expiry_date=r.expiry_date,
                                  unit_price=r.unit_price,
                                  expired=r.expiry_date is not None and r.expiry_date < date.today()) for r in rows],
    )


# ------------------------------------------------------------------ adding stock
def receive_stock(db: Session, data: ReceiveStock, user_id: int | None = None, reference: tuple[str, int] | None = None) -> MedicineInventory:
    """New delivery. Same product + same batch already on the shelf -> add to it. Otherwise a new batch is created.
    A new batch of a known medicine reuses its barcode; a brand-new medicine without a barcode gets one automatically."""
    barcode = (data.barcode or "").strip() or None
    name = data.medicine_name.strip()
    batch = (data.batch_number or "").strip() or None

    same_product = (MedicineInventory.barcode == barcode) if barcode else (
        func.lower(MedicineInventory.medicine_name) == name.lower())
    batch_rows = db.scalars(select(MedicineInventory).where(same_product)).all()
    existing = next((r for r in batch_rows if (r.batch_number or None) == batch and r.expiry_date == data.expiry_date), None)
    if existing:
        existing.quantity += data.quantity
        stock_service.record(db, medicine=existing, kind="RECEIPT", quantity=data.quantity, reference_type=reference[0] if reference else "receipt", reference_id=reference[1] if reference else None, user_id=user_id)
        if data.unit_price is not None:
            existing.unit_price = data.unit_price
        if data.gst_percent is not None:
            existing.gst_percent = data.gst_percent
        db.commit()
        db.refresh(existing)
        return existing

    if barcode is None:   # reuse the barcode of the same medicine if it already has one
        barcode = next((r.barcode for r in batch_rows if r.barcode), None)
    sibling = batch_rows[0] if batch_rows else None
    item = MedicineInventory(
        medicine_name=name, barcode=barcode, batch_number=batch, quantity=data.quantity, expiry_date=data.expiry_date, manufacture_date=data.manufacture_date,
        manufacturer=data.manufacturer or (sibling.manufacturer if sibling else None),
        unit_price=data.unit_price if data.unit_price is not None else (sibling.unit_price if sibling else None),
        gst_percent=data.gst_percent if data.gst_percent is not None else (sibling.gst_percent if sibling else None),
    )
    db.add(item)
    db.flush()
    if not item.barcode:
        item.barcode = f"HW{item.id:08d}"
    stock_service.record(db, medicine=item, kind="RECEIPT", quantity=data.quantity, reference_type=reference[0] if reference else "receipt", reference_id=reference[1] if reference else None, user_id=user_id)
    db.commit()
    db.refresh(item)
    return item


def backfill_barcodes(db: Session) -> int:
    """Stock added before barcodes existed gets one: every batch of the same medicine shares a barcode."""
    rows = db.scalars(select(MedicineInventory).order_by(MedicineInventory.id)).all()
    known: dict[str, str] = {r.medicine_name.lower(): r.barcode for r in rows if r.barcode}
    changed = 0
    for row in rows:
        if row.barcode:
            continue
        key = row.medicine_name.lower()
        row.barcode = known.setdefault(key, f"HW{row.id:08d}")
        changed += 1
    if changed:
        db.commit()
    return changed


# ------------------------------------------------------------------ selling
def _next_bill_number(db: Session) -> str:
    stamp = date.today().strftime("%Y%m%d")
    count = db.scalar(select(func.count(Sale.id)).where(Sale.bill_number.like(f"BILL-{stamp}-%"))) or 0
    number = f"BILL-{stamp}-{count + 1:04d}"
    while db.scalar(select(Sale.id).where(Sale.bill_number == number)):
        count += 1
        number = f"BILL-{stamp}-{count + 1:04d}"
    return number


def create_sale(db: Session, staff: PharmacyStaff, data: SaleCreate) -> Sale:
    prescription = None
    if data.prescription_id is not None:
        prescription = db.get(Prescription, data.prescription_id)
        if prescription is None or not is_open(prescription):
            raise HTTPException(status.HTTP_409_CONFLICT, "This prescription is not open, so it cannot be billed.")
    rx_item_ids = {i.id for i in prescription.items} if prescription else set()

    sale = Sale(bill_number="", pharmacy_staff_id=staff.id, customer_name=data.customer_name,
                customer_phone=data.customer_phone, prescription_id=data.prescription_id,
                payment_method=data.payment_method, subtotal=0, discount=0, tax=0, total=0)
    given_for_rx: dict[int, int] = defaultdict(int)
    moves = []

    for line in data.items:
        if line.inventory_id is None and not (line.barcode or "").strip():
            raise HTTPException(422, "Each line needs a barcode or a medicine.")
        rows = find_batches(db, barcode=line.barcode, inventory_id=line.inventory_id)
        name = rows[0].medicine_name
        usable = [r for r in rows if _usable(r)]
        available = sum(r.quantity for r in usable)
        if available < line.quantity:
            if not usable and any(r.quantity > 0 for r in rows):
                raise HTTPException(status.HTTP_409_CONFLICT, f"{name} is expired or recalled and cannot be sold.")
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"Not enough stock for {name}: {available} available, {line.quantity} requested.")

        if line.prescription_item_id is not None:
            rx_item = next((i for i in (prescription.items if prescription else []) if i.id == line.prescription_item_id), None)
            if rx_item is None or line.prescription_item_id not in rx_item_ids:
                raise HTTPException(status.HTTP_409_CONFLICT, "That prescription line does not belong to this prescription.")
            if rx_item.medicine_name.strip().lower() != name.strip().lower():
                raise HTTPException(status.HTTP_409_CONFLICT,
                                    f"{name} is not the medicine the doctor prescribed ({rx_item.medicine_name}).")

        remaining = line.quantity
        for row in usable:
            if remaining == 0:
                break
            take = min(row.quantity, remaining)
            if row.unit_price is None:
                raise HTTPException(422, f"No price is set for {name}. Set the price in Medicine stock first.")
            gst = row.gst_percent or 0
            net = round(take * row.unit_price, 2)
            tax = round(net * gst / 100, 2)
            sale.items.append(SaleItem(
                inventory_id=row.id, prescription_item_id=line.prescription_item_id, medicine_name=row.medicine_name, batch_number=row.batch_number,
                expiry_date=row.expiry_date, quantity=take, unit_price=row.unit_price, gst_percent=gst,
                line_total=net, tax_amount=tax))
            row.quantity -= take
            moves.append(stock_service.record(db, medicine=row, kind="SALE", quantity=-take, reference_type="sale", user_id=staff.user_id))
            remaining -= take
        if line.prescription_item_id is not None:
            given_for_rx[line.prescription_item_id] += line.quantity

    sale.subtotal = round(sum(i.line_total for i in sale.items), 2)
    sale.tax = round(sum(i.tax_amount for i in sale.items), 2)
    if data.discount > sale.subtotal + sale.tax:
        raise HTTPException(422, "The discount cannot be more than the bill amount.")
    sale.discount = round(data.discount, 2)
    sale.total = round(sale.subtotal + sale.tax - sale.discount, 2)
    sale.bill_number = _next_bill_number(db)
    db.add(sale)
    db.flush()
    for move in moves:
        move.reference_id = sale.id

    # medicines that fill a prescription are also recorded as dispensed (stock was already taken above)
    for rx_item_id, quantity in given_for_rx.items():
        dispensing_service.dispense(db, staff, DispenseRequest(prescription_item_id=rx_item_id, quantity=quantity),
                                    deduct_stock=False, commit=False)
    db.commit()
    db.refresh(sale)
    return sale


# ------------------------------------------------------------------ bill for medicine already given on a prescription
def _price_row(db: Session, medicine_name: str) -> MedicineInventory | None:
    """The stock row whose price and GST are used: earliest-expiry batch that is not expired and has a price."""
    rows = _order(list(db.scalars(select(MedicineInventory).where(
        func.lower(MedicineInventory.medicine_name) == medicine_name.strip().lower())).all()))
    priced = [r for r in rows if r.unit_price is not None]
    fresh = [r for r in priced if r.expiry_date is None or r.expiry_date >= date.today()]
    return (fresh or priced or [None])[0]


def _billed_quantity(db: Session, prescription_item_id: int) -> int:
    return db.scalar(select(func.coalesce(func.sum(SaleItem.quantity), 0)).where(
        SaleItem.prescription_item_id == prescription_item_id)) or 0


def _unbilled_lines(db: Session, rx: Prescription) -> tuple[list[SaleItem], list[str]]:
    """One bill line per prescription medicine that was given but not billed yet. The stock was already taken when
    the medicine was given, so billing never touches the stock again."""
    lines: list[SaleItem] = []
    problems: list[str] = []
    for item in rx.items:
        quantity = dispensed_quantity(item) - _billed_quantity(db, item.id)
        if quantity <= 0:
            continue
        row = _price_row(db, item.medicine_name)
        if row is None:
            problems.append(f"No price is set for {item.medicine_name}. Set the price in Medicine stock first.")
            continue
        gst = row.gst_percent or 0
        net = round(quantity * row.unit_price, 2)
        lines.append(SaleItem(inventory_id=row.id, prescription_item_id=item.id, medicine_name=item.medicine_name,
                              batch_number=row.batch_number, expiry_date=row.expiry_date, quantity=quantity,
                              unit_price=row.unit_price, gst_percent=gst, line_total=net,
                              tax_amount=round(net * gst / 100, 2)))
    return lines, problems


def prescription_bill_preview(db: Session, rx: Prescription) -> BillPreview:
    lines, problems = _unbilled_lines(db, rx)
    made = db.execute(select(Sale.id, Sale.bill_number).where(Sale.prescription_id == rx.id).order_by(Sale.id)).all()
    subtotal = round(sum(l.line_total for l in lines), 2)
    tax = round(sum(l.tax_amount for l in lines), 2)
    return BillPreview(
        prescription_code=f"RX-{rx.id:05d}", patient_name=rx.patient.user.full_name,
        lines=[SaleItemOut(medicine_name=l.medicine_name, batch_number=l.batch_number, expiry_date=l.expiry_date,
                           quantity=l.quantity, unit_price=l.unit_price, gst_percent=l.gst_percent,
                           line_total=l.line_total, tax_amount=l.tax_amount, amount=round(l.line_total + l.tax_amount, 2))
               for l in lines],
        subtotal=subtotal, tax=tax, total=round(subtotal + tax, 2), problems=problems,
        bills=[{"id": i, "bill_number": n} for i, n in made])


def bill_prescription(db: Session, staff: PharmacyStaff, rx: Prescription, data: PrescriptionBillRequest) -> Sale:
    lines, problems = _unbilled_lines(db, rx)
    if problems:
        raise HTTPException(422, problems[0])
    if not lines:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "There is nothing to bill. Give the medicine first, or the bill was already made.")
    sale = Sale(bill_number="", pharmacy_staff_id=staff.id, prescription_id=rx.id,
                customer_name=data.customer_name or rx.patient.user.full_name, customer_phone=data.customer_phone,
                payment_method=data.payment_method)
    sale.items.extend(lines)
    sale.subtotal = round(sum(l.line_total for l in lines), 2)
    sale.tax = round(sum(l.tax_amount for l in lines), 2)
    if data.discount > sale.subtotal + sale.tax:
        raise HTTPException(422, "The discount cannot be more than the bill amount.")
    sale.discount = round(data.discount, 2)
    sale.total = round(sale.subtotal + sale.tax - sale.discount, 2)
    sale.bill_number = _next_bill_number(db)
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return sale


# ------------------------------------------------------------------ reading
def sale_out(sale: Sale) -> SaleOut:
    staff = sale.pharmacy_staff
    return SaleOut(
        id=sale.id, bill_number=sale.bill_number, created_at=sale.created_at,
        shop_name=staff.pharmacy_name or DEFAULT_SHOP, staff_name=staff.user.full_name,
        customer_name=sale.customer_name, customer_phone=sale.customer_phone,
        prescription_code=f"RX-{sale.prescription_id:05d}" if sale.prescription_id else None,
        payment_method=sale.payment_method,
        items=[SaleItemOut(id=i.id, medicine_name=i.medicine_name, batch_number=i.batch_number, expiry_date=i.expiry_date,
                           quantity=i.quantity, unit_price=i.unit_price, gst_percent=i.gst_percent,
                           line_total=i.line_total, tax_amount=i.tax_amount, amount=round(i.line_total + i.tax_amount, 2))
               for i in sale.items],
        subtotal=sale.subtotal, discount=sale.discount, tax=sale.tax, total=sale.total,
    )


def _local_day_start_utc(day: date) -> datetime:
    """Midnight of a local calendar day, as the UTC time the database stores."""
    return datetime.combine(day, time.min).astimezone(timezone.utc).replace(tzinfo=None)


def list_sales(db: Session, q: str | None, day: date | None) -> list[SaleListItem]:
    query = select(Sale).order_by(Sale.id.desc()).limit(300)
    if day:
        query = query.where(Sale.created_at >= _local_day_start_utc(day),
                            Sale.created_at < _local_day_start_utc(date.fromordinal(day.toordinal() + 1)))
    rows = db.scalars(query).all()
    needle = (q or "").strip().lower()
    result = []
    for s in rows:
        if needle and needle not in f"{s.bill_number} {s.customer_name or ''} {s.customer_phone or ''}".lower():
            continue
        result.append(SaleListItem(id=s.id, bill_number=s.bill_number, created_at=s.created_at,
                                   prescription_code=f"RX-{s.prescription_id:05d}" if s.prescription_id else None,
                                   customer_name=s.customer_name, payment_method=s.payment_method,
                                   item_count=sum(i.quantity for i in s.items), total=s.total))
    return result


def summary_today(db: Session) -> SalesSummary:
    start = _local_day_start_utc(date.today())
    sales = db.scalars(select(Sale).where(Sale.created_at >= start)).all()
    by_method: dict[str, float] = defaultdict(float)
    units: dict[str, int] = defaultdict(int)
    for s in sales:
        by_method[s.payment_method] += s.total
        for i in s.items:
            units[i.medicine_name] += i.quantity
    top = sorted(units.items(), key=lambda kv: -kv[1])[:5]
    return SalesSummary(bills_today=len(sales), sales_today=round(sum(s.total for s in sales), 2),
                        by_method={k: round(v, 2) for k, v in by_method.items()},
                        top_medicines=[{"medicine_name": n, "quantity": q} for n, q in top])
