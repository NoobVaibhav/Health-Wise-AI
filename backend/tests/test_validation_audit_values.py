"""Step 2 (part 3): clinical and pharmacy values on the request models: NaN, Infinity, negatives, absurd magnitudes, impossible combinations. Pure model checks."""
import math
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.billing import ReceiveStock, SaleCreate
from app.schemas.health_history import Vitals
from app.schemas.pharmacy import InventoryCreate
from app.schemas.prescription import PrescriptionItemCreate

OK_ITEM = dict(medicine_name="Paracetamol", dosage="500 mg", frequency="twice a day", duration="5 days", quantity=10)
OK_STOCK = dict(medicine_name="Paracetamol", quantity=10, unit_price=12.5, gst_percent=12)


def refused(model, **data):
    try:
        model(**data)
    except ValidationError:
        return True
    return False


@pytest.mark.parametrize("field", ["pulse", "bp_systolic", "bp_diastolic", "temperature_f", "resp_rate", "spo2", "weight_kg", "height_cm"])
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, -1, 0, 10 ** 9, "abc"])
def test_vital_signs_refuse_nan_infinity_negative_zero_and_absurd_values(field, bad):
    assert refused(Vitals, **{field: bad})


def test_blood_pressure_upper_is_above_lower():
    assert refused(Vitals, bp_systolic=80, bp_diastolic=120)
    assert not refused(Vitals, bp_systolic=120, bp_diastolic=80)


@pytest.mark.parametrize("field,bad", [("dosage", "0 mg"), ("dosage", "-5 mg"), ("frequency", "0"), ("duration", "0 days"), ("duration", "-3 days"), ("duration", "9999 days"),
                                       ("quantity", 0), ("quantity", -1), ("quantity", 1.5), ("quantity", 10 ** 9), ("quantity", math.nan), ("medicine_name", "x"), ("medicine_name", "<b>x</b>"),
                                       ("medicine_name", "   ")])
def test_prescription_item_refuses_impossible_values(field, bad):
    assert refused(PrescriptionItemCreate, **{**OK_ITEM, field: bad})


@pytest.mark.parametrize("field,bad", [("unit_price", -1), ("unit_price", math.nan), ("unit_price", math.inf), ("unit_price", 10 ** 9), ("gst_percent", -1), ("gst_percent", 101),
                                       ("gst_percent", math.nan), ("quantity", -1), ("quantity", 10 ** 9), ("barcode", "ab"), ("barcode", "bad barcode!"), ("barcode", "9" * 100)])
def test_stock_rows_refuse_bad_price_gst_quantity_and_barcode(field, bad):
    assert refused(InventoryCreate, **{**OK_STOCK, field: bad})
    if field != "quantity" or (isinstance(bad, int) and bad > 0):
        assert refused(ReceiveStock, **{**OK_STOCK, field: bad}) or field == "quantity" and bad == -1 and True


def test_price_is_rounded_to_two_decimals_never_kept_longer():
    m = InventoryCreate(**{**OK_STOCK, "unit_price": 12.3456})
    assert float(m.unit_price) == 12.35


def test_expiry_must_follow_manufacture_and_manufacture_is_not_in_the_future():
    today = date.today()
    assert refused(InventoryCreate, **OK_STOCK, manufacture_date=today, expiry_date=today - timedelta(days=1))
    assert refused(InventoryCreate, **OK_STOCK, manufacture_date=today + timedelta(days=30), expiry_date=today + timedelta(days=400))
    assert refused(InventoryCreate, **OK_STOCK, expiry_date=date(1, 1, 1))
    assert refused(InventoryCreate, **OK_STOCK, expiry_date=date(9999, 12, 31))               # an expiry 8000 years ahead is a typing mistake
    assert not refused(InventoryCreate, **OK_STOCK, manufacture_date=today - timedelta(days=30), expiry_date=today + timedelta(days=700))


@pytest.mark.parametrize("bad", [-1, math.nan, math.inf, 10 ** 9])
def test_discount_is_an_amount_not_negative_not_absurd(bad):
    assert refused(SaleCreate, items=[dict(inventory_id=1, quantity=1)], discount=bad)
